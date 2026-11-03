# Spec: Persist scraped numbeo records

## Objective

Stop the numbeo ingest re-scraping every configured city on every run.

numbeo enforces a monthly page-view quota and, once it is gone, blocks the IP for the rest of the month (`Retry-After` on the 429). The pipeline is full-replace, so every run re-fetches every city, and a handful of runs exhausts the quota. Cost-of-living prices do not move fast enough to justify that.

Success: a re-run with the same cities costs **zero** numbeo requests. Only a city with no stored data, or data older than 180 days, is fetched.

## Assumptions

Correct any of these before planning.

1. **A stored city is reused while its data is under 180 days old.** Older than that, it is re-scraped. 180 days is a constant (`SCRAPE_TTL_DAYS`), not config.
2. **The timestamp lives on `raw_numbeo.cost_of_living`** as `scraped_at`, written by the ingest.
3. **Bruin's `create+replace` still writes the whole table.** The asset returns stored rows plus freshly scraped ones, so the full-replace contract holds - it is just that "the whole table" now includes rows it did not re-fetch.
4. **A refresh that numbeo throttles fails loudly** (`NumbeoThrottled`), exactly as it does today. The run stops rather than serving month-old prices as if fresh.
5. **`clean__numbeo_cost_of_living` is unaffected**: it selects `city`, `category`, `cost` explicitly, so the new column does not reach the dashboard.
6. **The app is unchanged.** It still runs the whole pipeline on Submit; the saving is inside the ingest.

## Baseline

`pipeline/assets/ingest/numbeo.py` today:

- `configured_cities()` returns `(name, numbeo_slug)` pairs from `raw_config.cities` (added by the HITL resolution work).
- `materialize()` scrapes every configured city with `get_city_data(name, slug=slug)` and returns one flat row per city and category.
- Bruin writes that as `raw_numbeo.cost_of_living` with `create+replace`.

So every run costs one cost-of-living request per city, and cities dropped from the config disappear (they are simply not in the list).

## Tech Stack

Unchanged: Bruin, DuckDB at `$DUCKDB_LOCATION`, pytest. No new dependency.

## Commands

```bash
export PATH="$HOME/.local/bin:$PATH"
export DUCKDB_LOCATION=database/dwh.duckdb

make test                       # uv run pytest tests
bruin run pipeline/assets/ingest/numbeo.py --workers 1
bruin run pipeline --workers 1
```

## Project Structure

```
pipeline/lib/numbeo.py            + SCRAPE_TTL_DAYS, plan_scrapes(...)  (pure, no network)
pipeline/assets/ingest/numbeo.py  read stored rows, scrape only the planned set, stamp scraped_at
tests/test_costofliving.py        the TTL and reuse cases
raw_numbeo.cost_of_living         + scraped_at
```

## Code Style

The decision - which cities to fetch - is a pure function in `pipeline/lib/`, with `now` injected, so it is tested without a database or a clock.

```python
SCRAPE_TTL_DAYS = 180


def plan_scrapes(configured, stored, now, ttl_days=SCRAPE_TTL_DAYS):
    """The ``(name, slug)`` pairs that need a fetch, oldest data first.

    ``stored`` is the existing ``raw_numbeo.cost_of_living`` rows. A city is
    reused while its most recent ``scraped_at`` is within the TTL; one with no
    rows at all, or rows older than that, is fetched.
    """
```

The ingest stays thin: read the table, call `plan_scrapes`, fetch those, return stored plus fresh.

## Testing Strategy

pytest, `make test`, no network. Extend `tests/test_costofliving.py`:

- a city whose stored rows are fresh is **not** fetched (the injected fetch must not be called);
- a city whose rows are older than 180 days **is** fetched;
- a city with no stored rows is fetched;
- a table with no `scraped_at` column (the old shape) fetches everything;
- a throttled refresh still raises `NumbeoThrottled`;
- a stale city whose refresh returns no table keeps its stored rows.

## Boundaries

**Always**
- Keep the decision logic pure and network-free in `pipeline/lib/`.
- Stamp every returned row with `scraped_at`, so the destination schema is uniform.
- Keep the full-replace contract: the asset returns the whole table it wants written.
- Run `make test` before committing.

**Ask first**
- Changing `SCRAPE_TTL_DAYS` away from 180, or making it configurable.
- Adding a refresh control (a flag, or a button in the app).
- Changing the `raw_numbeo` contract beyond adding `scraped_at`.

**Never**
- Write a partial table when a refresh is throttled - fail instead.
- Serve a stale city as if it were fresh, silently.
- Commit `.env`, secrets, or the `baseline/` warehouse.

## Success Criteria

- A second run with unchanged cities makes **zero** numbeo requests.
- A city with no stored rows, or data older than 180 days, is fetched and its `scraped_at` updated.
- A table without `scraped_at` still runs, fetching everything once.
- A throttled refresh stops the run with `NumbeoThrottled`; no partial table is written.
- `make test` passes, with the reuse and TTL cases covered.

## Out of Scope

- A refresh control (a `--force` flag or an app button). Deferred; deleting a city's rows re-fetches it.
- Caching the search/dispatcher resolution. Those endpoints are not what the quota blocks.
- Not re-running the pipeline on Submit, or any change to how the app triggers it.
- Backfilling `scraped_at` for rows written before the column existed.

## Open Questions

1. A stale city whose refresh returns no table keeps its stored rows and stays stale, so it is retried on every run - one wasted request per run while numbeo cannot serve it. Acceptable, or should a failed refresh back off for the TTL too?
