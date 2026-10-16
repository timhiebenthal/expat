# Implementation Plan: HITL city resolution for Numbeo

Spec: `SPEC.md` (approved). Detailed tasks: `tasks/todo.md`.

## Overview

Resolve each submitted city to the slug Numbeo keys it under, in the Streamlit app at Submit, so the cost-of-living ingest stops failing on names Numbeo spells differently. The display name stays the identity; `numbeo_slug` and `numbeo_city_id` are added as attributes on `raw_config.cities`. The pipeline keeps its hard-fail check as the run-time backstop.

## Architecture Decisions

- **Resolution lives in `pipeline/lib/numbeo.py`, not the asset.** Same reason the rest of the lib exists: network-free at import, injectable fetcher, directly testable. Both the app and the ingest import it.
- **`resolve_city` returns a three-way outcome**, not a slug-or-None, because the app must tell "pick one of these" apart from "we found nothing".
- **The slug is fetched lazily**, only for the chosen id, so an ambiguous city does not cost one dispatcher call per candidate.
- **The app gate is thin; the decision logic sits in `streamlit/utils.py`.** `Home.py` renders widgets, `utils` resolves and merges, so the logic is unit-testable without Streamlit - which matters because `AppTest` cannot drive `data_editor`.
- **Tolerate the old `raw_config.cities` shape** (no slug columns) rather than migrate. The table is replaced wholesale on every Submit, so the old shape exists only until the first submit after deploy; a tolerant read is cheaper than a migration step. (Resolves spec Open Question 1.)
- **No "force re-resolve" in v1.** Renaming a city re-resolves it. (Resolves spec Open Question 2.)
- **The naive slug is the fallback**, not a hardcoded override map. `SLUG_OVERRIDES` never landed on `main`, and an alias map would contradict the point of the feature; a row without a stored slug uses `build_city_url` and fails loudly if numbeo does not serve it.

## Task List

### Phase 1: Resolution library
- [x] Task 1: `search_cities` + `canonical_slug`
- [x] Task 2: `resolve_city` (three-way outcome + country filter)
- [x] Task 3: `get_city_data(city, slug=None)`

### Checkpoint: Library
- [ ] `make test` passes; 0 / 1 / N matches, the country filter, and the malformed `Location` are covered

### Phase 2: Ingest
- [x] Task 4: ingest reads `numbeo_slug`, tolerates the old shape

### Checkpoint: Ingest
- [x] Stored slug preferred; naive fallback intact; zero-rows guard intact

### Phase 3: App helpers
- [x] Task 5: `load_city_slugs` / `resolve_city_rows` / `apply_resolution`

### Phase 4: App gate
- [x] Task 6: `Home.py` Submit gate + resolution panel
- [ ] Task 7: throttle feedback + distinct "Access Restricted" logging

### Checkpoint: App
- [ ] `AppTest`: happy path unchanged; ambiguous and unresolved render; Confirm disabled while blocked

### Phase 5: End to end
- [ ] Task 8: resolution -> write -> ingest read, on a scratch warehouse

### Checkpoint: Complete
- [ ] Every acceptance criterion met; `make test` green; `bruin validate pipeline` clean

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Numbeo's undocumented endpoints change, or the malformed `Location` shifts | High | Parse in one function, tests pin the exact shape; a change fails loudly at Submit, not silently downstream |
| Numbeo throttles ("Access Restricted") | Med | Abort at Submit, keep the previous config; distinct log line in the ingest; manual slug as the escape hatch |
| `AppTest` cannot drive `data_editor` | Med | Keep decision logic in `utils` (pure) and unit-test it; `AppTest` only asserts the render |
| Ambiguous city picked wrongly | Med | HITL confirm, country filter first, Numbeo order as the default only |
| Old `raw_config.cities` shape | Low | Tolerant read via `information_schema` |
| Extra `raw_config` columns break `capture_baseline`'s manifest | Low | It reads `name` only; verify in Task 5 |

## Open Questions

None. Both spec questions are decided above; either can be revisited at plan review.
