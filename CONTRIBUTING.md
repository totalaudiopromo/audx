# Contributing to audx

audx is a local-first terminal and browser music tool. The current goal is a
usable alpha: load stems, write patterns, play locally, render WAVs, and keep
the project file readable.

## Local Setup

```bash
uv sync
uv run audx doctor
```

## Checks

Run these before opening a pull request:

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src/audx
uv build
```

## Development Principles

- Keep the `.audx` file as the source of truth.
- Prefer local/offline behaviour. Network features must be explicit and opt-in.
- Add tests for new behaviour before implementation.
- Keep CLI output scriptable and calm.
- Be honest in docs about alpha features and scaffolds.

## Useful Commands

```bash
uv run audx init demo --parent /tmp --no-git
uv run audx load /path/to/kick.wav --ch 0 --project /tmp/demo/project.audx
uv run audx render-project /tmp/demo/project.audx --output /tmp/demo/renders/demo.wav
uv run audx serve --port 8080
```
