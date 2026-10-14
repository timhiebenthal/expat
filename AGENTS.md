# AGENTS.md

Pointers for agents in this repo. Keep this file to pointers; the substance belongs in the
documents it names.

## Commands

- `make test` runs `uv run pytest tests`. It is also wired as a pre-commit hook
  (`.pre-commit-config.yaml`), so commits run it for you. A fresh clone needs
  `uv tool install pre-commit` and then `pre-commit install`, once.
- `make fmt` runs the declared SQL formatter (`shandy-sqlfmt`) over `pipeline/`. The pre-commit
  hook runs the same command, so the SQL stays formatted without anyone remembering.
- `uv`, `bruin` and `pre-commit` live in `~/.local/bin`, which is **not** on the shell's PATH
  (non-interactive bash reads neither `~/.bashrc` nor `~/.profile`). Prefix
  `export PATH="$HOME/.local/bin:$PATH"` or use the full path.

## The pipeline

- `pipeline/assets/{ingest,clean,prep,core,seed}/` - one asset per file. `pipeline/lib/` holds the
  shared, network-free helpers and is deliberately not under `assets/`, which Bruin walks for assets.
- `.bruin.yml` must stay at the repo root; its connection reads `path: ${DUCKDB_LOCATION}`, so export
  that before any Bruin command.
- `bruin run` needs `--workers 1`. DuckDB allows a single writer, and Bruin's default of 16 workers
  collides on the file lock.
- Parity runs against the gitignored `baseline/` copy, never `database/dwh.duckdb` while the app holds
  it. Gate parity on the entity tables (`analytics.core__*`) with `scripts/parity.sql`.

## History

- The migration contract, its amendments and the Bruin v0.11.778 gotchas:
  `docs/specs/2026-10-14-bruin-migration/`.
- Cutover is deferred to its own branch: removing `dlt` / `dbt` and `loading/` / `dbt/`, and dropping
  the dlt-era `raw_*` tables, since `create+replace` never drops a pre-existing table.
