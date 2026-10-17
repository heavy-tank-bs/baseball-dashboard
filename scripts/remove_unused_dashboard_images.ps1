$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskGeneratedRoot = (Resolve-Path (Join-Path $taskRoot 'generated')).Path
$taskReportPath = Join-Path $taskRoot 'docs/dashboard-image-refresh.json'
$taskReport = Get-Content -LiteralPath $taskReportPath -Raw -Encoding utf8 | ConvertFrom-Json
$taskSummaryTexts = @(Get-ChildItem -LiteralPath (Join-Path $taskRoot 'summary') -File |
    Where-Object { $_.Extension -in '.js', '.json', '.html' } |
    ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw -Encoding utf8 })
$taskRemoved = @()
foreach ($taskSkipped in $taskReport.skipped) {
    $taskPrefix = $taskSkipped.firstPage -replace '-dashboard-1\.png$', ''
    if (Test-Path -LiteralPath (Join-Path $taskRoot ($taskPrefix + '-dashboard.json'))) {
        throw "Source JSON exists; refuse cleanup: $taskPrefix"
    }
    foreach ($taskPage in 1..4) {
        $taskRelative = "$taskPrefix-dashboard-$taskPage.png"
        $taskAbsolute = [IO.Path]::GetFullPath((Join-Path $taskRoot $taskRelative))
        if (-not $taskAbsolute.StartsWith($taskGeneratedRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Outside generated directory: $taskAbsolute"
        }
        $taskBasename = [IO.Path]::GetFileName($taskAbsolute)
        if ($taskSummaryTexts | Where-Object { $_.Contains($taskBasename) }) {
            throw "Referenced by summary; refuse cleanup: $taskRelative"
        }
        if (Test-Path -LiteralPath $taskAbsolute) {
            Remove-Item -LiteralPath $taskAbsolute
            $taskRemoved += $taskRelative
        }
    }
}
$taskReport | Add-Member -NotePropertyName removedUnreferencedImages -NotePropertyValue $taskRemoved -Force
$taskReport | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $taskReportPath -Encoding utf8
Write-Output "Removed unreferenced images without source JSON: $($taskRemoved.Count)"
