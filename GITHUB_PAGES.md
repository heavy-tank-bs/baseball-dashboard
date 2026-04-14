# GitHub Pages Setup

This repository is prepared to publish the site with GitHub Pages through GitHub Actions.

## Files added for Pages

- `.github/workflows/deploy-pages.yml`
- `scripts/build_github_pages.py`
- `.gitignore`

## What the build does

- Copies the public site files from `summary/` into `site/summary/`
- Copies deployable assets from `generated/` into `site/generated/`
- Writes `site/index.html` that redirects to `site/summary/index.html`
- Writes `site/.nojekyll`

## Remaining steps on GitHub

1. Install Git on this PC if it is not already installed.
2. Initialize this folder as a Git repository.
3. Create a GitHub repository and add it as `origin`.
4. Push the default branch as `main`.
5. In GitHub: `Settings` -> `Pages` -> `Source` -> select `GitHub Actions`.
6. Push updates to `main`. The workflow will rebuild and redeploy the site.

## Local build check

Run:

```powershell
python scripts/build_github_pages.py
```

The publishable artifact will be created in `site/`.
