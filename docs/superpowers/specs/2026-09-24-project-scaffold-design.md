# 2pz-ai-case-study — project scaffold design

Date: 2026-09-24

## Purpose

Stand up a clean, working Python skeleton for a case study project. The
actual domain logic is not yet known — this spec covers only the scaffold:
project tooling, service structure, and the pattern for "background work"
that needs to run outside a request/response cycle. No case-study-specific
features are included.

## Architecture

- **API**: FastAPI, served via `uvicorn`.
- **"Workers"**: a Click CLI (`app/cli.py`), a `click.Group` with
  subcommands. Each subcommand is a script that reads/writes the same
  shared state as the API. These run on demand (manually, via cron, or a
  systemd timer) rather than as a long-running daemon.
- **Shared state**: SQLite via SQLAlchemy. A single engine/session setup in
  `app/db.py` is imported by both the API routes and the CLI commands, so
  connection/session logic is not duplicated.
- **Async / queueing**: explicitly out of scope for now. There is no
  evented or job-queue infrastructure (no Redis, no Celery/arq). If a real
  async background-processing need shows up later, the core logic should
  already live in plain functions called from CLI commands, so it can be
  lifted into a worker without a rewrite — but nothing is being built
  speculatively for that today.

## Project layout

```
2pz-ai-case-study/
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app + routes
│   ├── config.py        # pydantic-settings (env vars, e.g. DB path)
│   ├── db.py             # SQLAlchemy engine/session, shared by API + CLI
│   ├── models.py         # SQLAlchemy models
│   └── cli.py             # click group; subcommands = "worker" scripts
└── tests/
    ├── conftest.py        # test DB fixture (in-memory SQLite)
    ├── test_api.py
    └── test_cli.py
```

## Tooling

- **uv** manages dependencies, the virtualenv, and the lockfile.
  `[project.scripts]` exposes two entry points:
  - `api` → runs `uvicorn app.main:app`
  - `cli` → runs the Click group in `app.cli:cli`
- **ruff** for lint + format (single tool, no separate black/isort/flake8).
- **pytest** for tests.

## Data flow / error handling

- API and CLI both go through `app/db.py` for sessions, and `app/models.py`
  for schema — no separate data-access paths to keep in sync.
- Standard FastAPI exception handling (pydantic validation errors → 422,
  explicit `HTTPException` for domain errors).
- CLI commands use Click's standard error/exit-code conventions; unhandled
  exceptions surface as non-zero exit with a traceback, which is sufficient
  until specific CLI error-handling needs are known.

## Testing

- **API**: `httpx.AsyncClient` against the FastAPI app in-process (no real
  server needed).
- **CLI**: `click.testing.CliRunner` to invoke subcommands and assert on
  resulting DB state / stdout.
- Both point at an in-memory SQLite database via a shared pytest fixture in
  `tests/conftest.py`, so tests never touch a real file on disk.

## Explicitly out of scope

- No queue/broker (Redis, Celery, arq) — reconsider only if a genuine
  evented background-processing requirement appears.
- No case-study-specific domain models or endpoints — this scaffold is
  deliberately empty of business logic.
- No CI/CD, no Docker, no deployment config — can be added once the
  scaffold is validated.
