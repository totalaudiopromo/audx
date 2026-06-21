# Publishing audx

## Overview
audx uses a dual distribution model:
- **Python package** (via pip/uv) — primary distribution for the CLI
- **npm package** — namespace reservation + potential JS wrapper

Both versions must keep version numbers in sync.

---

## Automated PyPI release (recommended)

Releases are published to PyPI by `.github/workflows/release.yml` using
**PyPI Trusted Publishing (OIDC)** — no API token is stored in the repo.

**One-time setup** (on PyPI, by the project owner):
1. Create the `audx` project on PyPI (or run the first release to TestPyPI).
2. Add a *trusted publisher*: PyPI → project → Settings → Publishing →
   add GitHub, owner `totalaudiopromo`, repo `audx`, workflow `release.yml`,
   environment `pypi`. See https://docs.pypi.org/trusted-publishers/.
3. In GitHub repo settings, create an environment named `pypi`.

**Each release:**
```bash
# 1. bump version in pyproject.toml AND package.json (keep them in sync)
# 2. update CHANGELOG.md [Unreleased] -> the new version
git commit -am "release: audx v0.3.0"
git tag v0.3.0
git push origin main --tags        # the tag triggers the Release workflow
```
The workflow builds the sdist + wheel with `uv build`, runs `twine check`, and
publishes to PyPI. Verify a clean install afterwards: `pip install audx`.

To build/inspect locally without publishing:
```bash
uv build            # -> dist/audx-<version>.tar.gz + .whl
uvx twine check dist/*
```

---

## Prerequisites

### npm
```bash
# Create npm account (one-time)
npm adduser

# Verify login
npm whoami
```

### Python build tools
```bash
# Using uv (recommended)
uv pip install build twine

# Or standard pip
python -m pip install build twine --upgrade
```

---

## Release Workflow

### Option A: One-step full release (recommended)
```bash
cd ~/workspace/active/audx
bash scripts/release.sh
```
This script will:
1. Verify Python + npm version match
2. Build Python wheel + sdist
3. Commit with git tag
4. Publish to npm
5. Push to GitHub (you'll need to manually upload to PyPI unless you modify script)

### Option B: Step-by-step

**1. Bump version** (edit both files to same version):
- `pyproject.toml`: `version = "0.1.1"`
- `package.json`: `"version": "0.1.1"`

**2. Build Python distributions:**
```bash
bash scripts/build.sh
# Artifacts appear in dist/
```

**3. Publish to npm:**
```bash
bash scripts/publish-npm.sh
# Confirms version, requires manual 'yes' input
```

**4. Upload to PyPI (optional):**
```bash
# TestPyPI first
twine upload --repository testpypi dist/*

# Then production
twine upload dist/*
```

**5. Git tag & push:**
```bash
git add -A
git commit -m "release: audx v0.1.1"
git tag "v0.1.1"
git push origin main --tags
```

---

## Post-Publish Checklist

- [ ] npm page shows correct version: https://www.npmjs.com/package/audx
- [ ] PyPI page (if published): https://pypi.org/project/audx/
- [ ] GitHub release draft created with changelog
- [ ] Homebrew formula updated (if distributing via brew)
- [ ] Installation instructions tested:
  ```bash
  npm install -g audx   # if JS wrapper exists
  uv pip install audx  # Python
  ```

---

## Version Strategy

- **Major (X.0.0):** Breaking changes to CLI API
- **Minor (0.X.0):** New features, backwards-compatible
- **Patch (0.0.X):** Bug fixes, documentation updates

Current: `0.1.0` — initial functional release

---

## Troubleshooting

### npm E404: package name taken
If `audx` gets taken before you publish:
- Use scoped name: `@totalaudiopromo/audx`
- Update `package.json`: `"name": "@totalaudiopromo/audx"`

### Python build fails
```bash
# Clean and retry
rm -rf dist/ build/ audx.egg-info/
uv run python -m build --clean
```

### Permission errors on scripts
```bash
chmod +x scripts/*.sh
```
