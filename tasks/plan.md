# Implementation Plan: Persist scraped numbeo records

Spec: `SPEC.md` (approved). Detailed tasks: `tasks/todo.md`.

## Overview

Make `raw_numbeo.cost_of_living` remember what it already scraped, so a run only fetches cities with no data or data older than 180 days. A re-run with unchanged cities costs zero numbeo requests.

## Architecture Decisions

- **The decision is a pure function in `pipeline/lib/`.** `plan_scrapes(configured, stored, now, ttl_days)` takes `now` as an argument, so it is tested without a clock or a database - the same pattern as the rest of the lib.
- **`scraped_at` lives on the raw table**, written by the ingest. No separate cache table; the raw table *is* the cache.
- **Full-replace is preserved.** The asset returns stored rows plus fresh ones, so Bruin's `create+replace` still writes the whole table - it just no longer re-fetches all of it.
- **A refresh that returns no table keeps the stored rows and stays stale**, logging a warning. It is retried next run rather than silently frozen for 180 days. This is the spec's open question, decided here: surfacing a broken city is worth one request per run. (Resolves SPEC Open Question 1.)
- **A throttled refresh still raises `NumbeoThrottled`.** No partial table is written.
- **The TTL is a constant** (`SCRAPE_TTL_DAYS = 180`), not config.

## Task List

### Phase 1: The decision
- [x] Task 1: `SCRAPE_TTL_DAYS` + `plan_scrapes` (pure)

### Checkpoint: Decision
- [x] `make test` passes; fresh / stale / missing / old-shape cases covered

### Phase 2: The ingest
- [x] Task 2: read stored rows, fetch only the planned set, stamp `scraped_at`

### Checkpoint: Ingest
- [x] A fresh city is not fetched; a stale or new one is, and is stamped

### Phase 3: Proof
- [ ] Task 3: two runs, the second makes zero requests

### Checkpoint: Complete
- [ ] Every acceptance criterion met; `make test` green; `bruin validate pipeline` clean

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Schema drift: stored rows lack `scraped_at` | Med | Detect the column; without it, fetch everything once and write the new shape |
| The destination infers schema from the first row | Med | Every returned row carries `scraped_at`, stored and fresh alike |
| A stale city that cannot be refreshed retries every run | Low | Accepted and documented; it is one request per run for a city that should not be broken |
| The cached rows silently go stale | Low | The TTL bounds it at 180 days; the timestamp is visible on the raw table |

## Open Questions

None. The spec's open question is decided above; it can be revisited at plan review.
