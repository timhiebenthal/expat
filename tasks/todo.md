# Tasks: Persist scraped numbeo records

Plan: `tasks/plan.md`. Spec: `SPEC.md`.

Commands: `make test` (uv run pytest tests), `bruin validate pipeline`.
Export `PATH="$HOME/.local/bin:$PATH"` and `DUCKDB_LOCATION=database/dwh.duckdb` first.

---

## Task 1: `SCRAPE_TTL_DAYS` and `plan_scrapes`

**Description:** Add `SCRAPE_TTL_DAYS = 180` and `plan_scrapes(configured, stored, now, ttl_days=SCRAPE_TTL_DAYS)` to `pipeline/lib/numbeo.py`. `configured` is a list of `(name, slug)` pairs; `stored` is the existing `raw_numbeo.cost_of_living` rows (dicts with `city` and `scraped_at`). Return the `(name, slug)` pairs that need a fetch: a city with no stored rows, or whose newest `scraped_at` is older than `now - ttl_days`.

**Acceptance criteria:**
- [x] A city with a `scraped_at` inside the TTL is excluded.
- [x] A city with a `scraped_at` older than the TTL is included.
- [x] A city with no stored rows is included.
- [x] A stored set with no `scraped_at` (the old shape) includes everything.
- [x] Returns `(name, slug)` pairs, in `configured` order.

**Verification:**
- [x] `make test` passes.
- [x] `tests/test_costofliving.py` covers fresh, stale, missing, and old-shape.

**Dependencies:** None.
**Files:** `pipeline/lib/numbeo.py`, `tests/test_costofliving.py`.
**Scope:** Small.

---

## Checkpoint: Decision
- [ ] `make test` passes; fresh / stale / missing / old-shape cases covered.

---

## Task 2: The ingest uses `plan_scrapes` and stamps `scraped_at`

**Description:** Rework `materialize()` in `pipeline/assets/ingest/numbeo.py`. Read the existing `raw_numbeo.cost_of_living` (tolerating the table being absent, or having no `scraped_at` column), call `plan_scrapes`, fetch only the planned cities with `get_city_data`, stamp `scraped_at` on the fresh rows, and return stored plus fresh rows. A refresh that returns no table keeps that city's stored rows and logs a warning. The zero-rows `RuntimeError` guard stays.

**Acceptance criteria:**
- [ ] A run whose cities are all fresh makes no fetch at all.
- [ ] A city with no rows, or stale rows, is fetched and stamped with the current time.
- [ ] Stored rows are returned unchanged, so the written table is the union.
- [ ] A table with no `scraped_at` column still runs (fetch everything once).
- [ ] A throttled refresh raises `NumbeoThrottled`; nothing is written.
- [ ] Every returned row carries `scraped_at`.

**Verification:**
- [ ] `make test` passes; fixture-warehouse tests cover each case.
- [ ] Manual: `bruin run pipeline/assets/ingest/numbeo.py --workers 1` against a scratch copy (deferred while numbeo throttles this IP).

**Dependencies:** Task 1.
**Files:** `pipeline/assets/ingest/numbeo.py`, `tests/test_costofliving.py`.
**Scope:** Medium.

---

## Checkpoint: Ingest
- [ ] A fresh city is not fetched; a stale or new one is, and is stamped.

---

## Task 3: Two runs, the second makes zero requests

**Description:** A test that calls `materialize()` twice against one scratch warehouse: the first fetch returns data for every city, the second fetch must not be called at all.

**Acceptance criteria:**
- [ ] The second run makes zero fetches.
- [ ] The table written by the second run is identical to the first (same rows, same `scraped_at`).

**Verification:**
- [ ] `make test` passes.

**Dependencies:** Task 2.
**Files:** `tests/test_costofliving.py`.
**Scope:** Small.

---

## Checkpoint: Complete
- [ ] Every acceptance criterion met.
- [ ] `make test` green; `bruin validate pipeline` clean.
