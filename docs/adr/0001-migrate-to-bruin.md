# Migrate ingestion and transformation from dlt + dbt to Bruin

**Status:** accepted

The pipeline was three tools for one job: dlt ingested, dbt transformed, and `streamlit/utils.py` hand-rolled the orchestration between them. We are replacing all three with Bruin and abandoning `loading/` and `dbt/` rather than keeping them in service. The motivation is fewer moving parts on a solo hobby project, not engine portability - the project stays on DuckDB, where Bruin is supported but is its less-validated path.

## Considered options

- **Keep dlt + dbt.** There is no orchestration pain at 13 models, and dbt's `ref()` gives compile-time checking that Bruin does not. Rejected because consolidation is the actual goal, and the pain being solved is surface area rather than capability.
- **Bruin for transformation only, leaving dlt to ingest.** Rejected: it leaves two tools, which defeats the point.
- **Headless evaluation first, decide later.** Rejected in favour of committing, so the work is not gated on an artificial timebox.
- **ingestr's Yahoo Finance source instead of the existing FX loader.** Rejected for three reasons: it is `FSL-1.1-ALv2` rather than Apache-2.0, three uniform Python assets beat two mechanisms, and it reads the same undocumented Yahoo endpoints, so it inherits the fragility that already broke our loader once.

## Consequences

- **Correctness can no longer be diffed against dbt after the switch.** dlt stops writing `raw_*`, so a working `dbt build` cannot be reconstructed later. A frozen copy of `dwh.duckdb` plus one final dbt build must be captured *before* anything changes, and Bruin's output is diffed against that. This ordering constraint is the one irreversible step in the migration.
- **Table references stop being checked at author time.** Bruin has no `ref()`, and its dry-run validation is not wired for DuckDB (`QueryValidatorRule` requires `IsValid`, which the DuckDB client does not implement), so a mistyped table name fails at runtime instead. Bruin's `used-tables` lint only warns, and only about sibling assets missing from `depends`.
- **`depends` is declared by hand.** The dependency graph is explicit, not inferred from SQL.
- **Dead trees until parity, then deletion.** `loading/` and `dbt/` stay in the repo as reference, with `dlt`, `dbt-core` and `dbt-duckdb` still in `pyproject.toml`, and all of it is removed in one commit once parity is proven. A future reader finding a dead `dbt/` directory is the confusion this ADR exists to prevent.
- **Layer names change** to `clean` / `prep` / `core` / `mart`, and "activity" becomes "cost item" with frequency modelled separately. Deliberately done during the rewrite, because every model is being rewritten anyway and this is the cheapest it will ever be.
- **Mart is retained but currently empty.** `dataset__cost_earnings_comparison` had no consumer - the app derives its view from Core at query time - so the model is dropped while the layer stays reserved.
- **One schema, not one schema per layer.** Layers stay as name prefixes (`clean__`, `prep__`, `core__`) in a single schema, against Bruin's grain of naming assets `schema.table`. Chosen so a table name states its own layer without the reader having to know the convention, and to avoid multiplying schemas in a hobby project.
