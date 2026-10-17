"""Reconcile context IBB events with the audited full-season NPB event ledger.

Existing source metadata and event details are preserved. Unexpected removals
or ambiguous innings stop the update; additions carry official provenance.
Run without --apply to inspect the exact proposed changes.
"""
import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from npb_boxscore_stats import TEAMS, normalize_name

ROOT = Path(__file__).resolve().parent.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def normalized(name):
    return TEAMS.get(name, {'楽天': '東北楽天'}.get(name, name))


def synchronize(season, apply=False):
    context_path = ROOT / f'summary/sportsnavi_game_context_{season}.json'
    report_path = ROOT / f'docs/intentional-walk-sync-{season}.json'
    old = read(context_path)
    context = copy.deepcopy(old)
    payload = read(ROOT / f'summary/sportsnavi_woba_events_{season}.json')
    constants = read(ROOT / 'summary/woba_constants.json')['byYear'][season]
    assert payload['source'] == 'NPB official play-by-play', 'Require official event source'
    assert constants['coverageComplete'], 'Require audited complete coverage'
    by_game = defaultdict(list)
    for event in payload['events']:
        by_game[event['gameId']].append(event)
    assert len(by_game) == constants['expectedGames'] == constants['games']
    games = {game['gameId']: game for game in context['games']}
    assert by_game.keys() <= games.keys()
    batting = read(ROOT / 'summary/game_batting_cache.json')['games']
    changes, identity_corrections = [], []
    for game_id, events in by_game.items():
        game = games[game_id]
        intentional = game['intentionalWalks']
        existing = Counter()
        teams = {}
        for team_name, team in intentional['teams'].items():
            normalized_team = normalized(team.get('team') or team_name)
            assert normalized_team not in teams
            teams[normalized_team] = team
            for player in team['players']:
                if not player.get('playerId'):
                    candidates = {event['batterId'] for event in events
                                  if event['battingTeam'] == normalized_team
                                  and normalize_name(event['batter']) == normalize_name(player['player'])}
                    assert len(candidates) == 1, f'Ambiguous missing player ID: {game_id} {player}'
                    player['playerId'] = next(iter(candidates))
                    identity_corrections.append({'gameId': game_id, 'date': game['date'],
                                                 'team': normalized_team, 'player': player['player'],
                                                 'beforePlayerId': '', 'afterPlayerId': player['playerId']})
                player_events = player.get('events', [])
                assert len(player_events) == player['intentionalWalks'], f'Incomplete IBB inning data: {game_id}'
                for event in player_events:
                    existing[(normalized_team, str(player['playerId']), int(event['inning']))] += 1
        expected = Counter((event['battingTeam'], event['batterId'], event['inning'])
                           for event in events if event['eventType'] == 'IBB')
        assert not (existing - expected), f'Existing IBB not supported by official events: {game_id} {existing - expected}'
        missing = expected - existing
        for event in events:
            key = (event['battingTeam'], event['batterId'], event['inning'])
            if event['eventType'] != 'IBB' or missing[key] <= 0:
                continue
            missing[key] -= 1
            if event['battingTeam'] not in teams:
                full_teams = [game['awayTeam'], game['homeTeam']]
                names = [name for name in full_teams if normalized(name) == event['battingTeam']]
                assert len(names) == 1
                team = {'team': names[0], 'intentionalWalks': 0, 'players': []}
                intentional['teams'][names[0]] = team
                teams[event['battingTeam']] = team
            team = teams[event['battingTeam']]
            matching = [row for row in team['players'] if str(row['playerId']) == event['batterId']]
            assert len(matching) <= 1
            if matching:
                player = matching[0]
            else:
                stats = batting[game_id][event['battingTeam']][event['batterId']]
                player = {'order': stats['order'], 'player': event['batter'], 'playerId': event['batterId'],
                          'intentionalWalks': 0, 'details': [], 'events': []}
                team['players'].append(player)
            player['intentionalWalks'] += 1
            player['details'].append(event['result'])
            player['events'].append({'inning': event['inning'], 'detail': event['result'],
                                     'source': 'NPB official play-by-play'})
            team['intentionalWalks'] += 1
            intentional['total'] += 1
            changes.append({key: event[key] for key in
                            ('gameId', 'date', 'inning', 'half', 'battingTeam', 'batterId', 'batter', 'result')})
        assert not +missing
    summary = context['summary']
    summary['gamesWithIntentionalWalks'] = sum(game['intentionalWalks']['total'] > 0 for game in context['games'])
    summary['intentionalWalkPlateAppearances'] = sum(game['intentionalWalks']['total'] for game in context['games'])
    metadata_corrections = []
    for key, summary_key in [('gamesWithIntentionalWalks', 'gamesWithIntentionalWalks'),
                             ('intentionalWalkGames', 'gamesWithIntentionalWalks'),
                             ('intentionalWalkPlateAppearances', 'intentionalWalkPlateAppearances')]:
        if key in context and context[key] != summary[summary_key]:
            metadata_corrections.append({'field': key, 'before': context[key], 'after': summary[summary_key]})
            context[key] = summary[summary_key]
    if changes or identity_corrections or metadata_corrections:
        context['updatedAt'] = datetime.now().astimezone().isoformat(timespec='seconds')
        context['intentionalWalkSync'] = {'source': 'NPB official play-by-play', 'gamesVerified': len(by_game),
                                          'report': str(report_path.relative_to(ROOT)).replace('\\', '/')}
    # Guard all unrelated data, including source fields, score/context rows,
    # all-star games and pitcher/batter source records.
    for before, after in zip(old['games'], context['games']):
        assert {k: v for k, v in before.items() if k != 'intentionalWalks'} == {
            k: v for k, v in after.items() if k != 'intentionalWalks'}
        if before['gameId'] not in by_game:
            assert before == after
    assert old['source'] == context['source']
    report = {'season': season, 'officialGamesVerified': len(by_game),
              'officialIntentionalWalks': sum(e['eventType'] == 'IBB' for e in payload['events']),
              'addedEvents': len(changes), 'affectedGames': len({e['gameId'] for e in changes}),
              'identityCorrections': identity_corrections,
              'metadataCorrections': metadata_corrections,
              'sourceAndUnrelatedContextUnchanged': True, 'changes': changes,
              'summaryBefore': old['summary'], 'summaryAfter': context['summary']}
    if apply and (changes or identity_corrections or metadata_corrections):
        context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if report_path.exists() and not changes and not identity_corrections:
            previous = read(report_path)
            previous.setdefault('metadataCorrections', []).extend(metadata_corrections)
            previous['summaryAfter'] = report['summaryAfter']
            report = previous
        report['affectedGames'] = len({row['gameId'] for row in report['changes'] + report['identityCorrections']})
        report.setdefault('baselineCommit', subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip())
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', default='2026')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    synchronize(args.season, args.apply)
