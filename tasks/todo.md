# Tasks: HITL city resolution for Numbeo

Plan: `tasks/plan.md`. Spec: `SPEC.md`.

Commands: `make test` (uv run pytest tests), `make fmt`, `bruin validate pipeline`.
Export `PATH="$HOME/.local/bin:$PATH"` and `DUCKDB_LOCATION=database/dwh.duckdb` first.

---

## Task 1: Numbeo search and canonical slug

**Description:** Add `search_cities(term, fetch=None)` and `canonical_slug(city_id, fetch=None)` to `pipeline/lib/numbeo.py`. `search_cities` GETs `https://www.numbeo.com/common/CitySearchJson?term=<term>` and returns the parsed `[{"label", "value"}]` list, `[]` on no match. `canonical_slug` GETs `.../common/dispatcher.jsp?city_id=<id>` with redirects NOT followed, and parses the malformed `Location` (`https://www.numbeo.com<slug>`, no slash) defensively: strip the prefix, strip leading slashes, take the last path segment.

**Acceptance criteria:**
- [x] `search_cities` returns `[{"label": ..., "value": ...}]`, and `[]` for an empty result.
- [x] `canonical_slug` returns the slug from `Location` for the malformed form, and `None` (not a crash) on an unparseable one.
- [x] Both take an injectable `fetch`; no test touches the network.

**Verification:**
- [x] `make test` passes.
- [x] `tests/test_costofliving.py::test_search_cities_returns_the_matches` and `::test_canonical_slug_parses_the_malformed_location` pass.

**Dependencies:** None.
**Files:** `pipeline/lib/numbeo.py`, `tests/test_costofliving.py`.
**Scope:** Small.

---

## Task 2: `resolve_city`

**Description:** Add `resolve_city(name, country=None, fetch=None)` returning a result with `state` in `{"resolved", "ambiguous", "unresolved"}` plus the matches. Search `"<name>, <country>"` when a country is present, else the bare name; on zero results retry with the bare name (LLM countries may not match Numbeo's naming). On N matches with a country, filter labels by that country; if exactly one survives it is resolved, else ambiguous.

**Acceptance criteria:**
- [x] 0 matches -> `unresolved`; 1 -> `resolved`; N -> `ambiguous`.
- [x] The country filter narrows N -> 1.
- [x] A country-qualified miss falls back to the bare-name search.

**Verification:**
- [x] `make test` passes.
- [x] One test per outcome plus the country filter and the fallback.

**Dependencies:** Task 1.
**Files:** `pipeline/lib/numbeo.py`, `tests/test_costofliving.py`.
**Scope:** Small.

---

## Task 3: `get_city_data` prefers a stored slug

**Description:** Extend `get_city_data(city, slug=None, fetch=None)`. When `slug` is given, build the URL from it directly; otherwise keep the existing `build_city_url` naive slug. Keep the no-table warning, and add a distinct line when the title contains "Access Restricted".

**Acceptance criteria:**
- [x] With a slug, the request URL is `/cost-of-living/in/<slug>` and the display name is irrelevant.
- [x] Without a slug, the naive slug path is used unchanged.
- [x] The error-page warning still fires, and "Access Restricted" is logged distinctly.

**Verification:**
- [x] `make test` passes.
- [x] `tests/test_costofliving.py`: stored-slug URL, fallback URL, throttle log.

**Dependencies:** None (uses the existing `build_city_url`).
**Files:** `pipeline/lib/numbeo.py`, `tests/test_costofliving.py`.
**Scope:** Small.

---

## Checkpoint: Library
- [ ] `make test` passes.
- [ ] 0 / 1 / N, country filter, malformed `Location`, stored-slug preference, and the throttle log are all covered.

---

## Task 4: Ingest reads the slug

**Description:** `pipeline/assets/ingest/numbeo.py` reads `name` plus `numbeo_slug` from `raw_config.cities`, tolerating a table without the column (check `information_schema.columns`), and passes the slug to `get_city_data`.

**Acceptance criteria:**
- [x] With the column present, each city's stored slug is used.
- [x] With the column absent, it falls back to the naive path and does not error.
- [x] The zero-rows `RuntimeError` guard is unchanged.

**Verification:**
- [x] `make test` passes; a fixture-warehouse unit test covers both shapes.
- Deferred: a live `bruin run pipeline/assets/ingest/numbeo.py` - numbeo is rate-limiting this IP, so a live run would only exercise the throttle path (already unit-tested).

**Dependencies:** Task 3.
**Files:** `pipeline/assets/ingest/numbeo.py`, `tests/test_costofliving.py`.
**Scope:** Small.

---

## Checkpoint: Ingest
- [ ] Stored slug preferred; naive fallback intact; zero-rows guard intact.

---

## Task 5: App resolution helpers

**Description:** In `streamlit/utils.py` add `load_city_slugs()` (name -> `{slug, city_id}` from `raw_config.cities`, tolerant of the old shape), `resolve_city_rows(cities)` (calls `resolve_city` per row and returns rows annotated with `state` + matches), and `apply_resolution(cities, picks)` (merges the HITL picks into final rows carrying `numbeo_slug` / `numbeo_city_id`, dropping removed rows). No Streamlit widgets in any of them.

**Acceptance criteria:**
- [x] All three are pure functions, unit-testable without Streamlit.
- [x] `load_city_slugs` returns `{}` for an old-shape table.
- [x] `apply_resolution` attaches slug + id and drops removed rows.

**Verification:**
- [x] `make test` passes.
- [x] `tests/test_city_resolution.py` covers the three.

**Dependencies:** Task 2.
**Files:** `streamlit/utils.py`, `tests/test_city_resolution.py`.
**Scope:** Medium.

---

## Task 6: Submit gate and resolution panel

**Description:** In `streamlit/Home.py`, the Submit handler resolves first. If everything resolves, the existing save + `run_pipeline` path is unchanged. Otherwise it renders the panel below the editor: a lead-in caption, the resolved list one pair per line, a radio per ambiguous city, rename / paste-slug / remove per unresolved city, and a "Confirm and run pipeline" button disabled while anything is unresolved. Confirm merges the picks, saves with the slug columns, and runs the pipeline.

**Acceptance criteria:**
- [x] An all-resolved submit behaves exactly as today.
- [x] Ambiguous and unresolved rows render their widgets; Confirm is disabled while blocked.
- [x] Confirm writes `numbeo_slug` and `numbeo_city_id` into `raw_config.cities`.

**Verification:**
- [x] `make test` passes (`AppTest` in `tests/test_app_smoke.py` asserts the happy path and the blocked render).
- Deferred: a live click-through - it needs the LLM for the city list. The `AppTest` covers both branches with `utils` stubbed.

**Dependencies:** Task 5.
**Files:** `streamlit/Home.py`, `tests/test_app_smoke.py`.
**Scope:** Medium.

---

## Task 7: Throttle feedback and diagnostics

**Description:** At Submit, a Numbeo throttle aborts, keeps the previous `raw_config`, shows a distinct message, and offers the manual-slug path. The ingest logs "Access Restricted" distinctly from "no data".

**Acceptance criteria:**
- [x] A throttled submit writes nothing and says so.
- [x] The ingest logs a distinct line for "Access Restricted".
- [x] The normal no-table log is unchanged.

**Verification:**
- [x] `make test` passes; tests assert the distinct log line and the app's throttle message.

**Dependencies:** Task 6.
**Files:** `streamlit/Home.py`, `pipeline/lib/numbeo.py`, `pipeline/assets/ingest/numbeo.py`, `tests/`.
**Scope:** Small.

---

## Checkpoint: App
- [ ] `AppTest`: happy path unchanged; ambiguous and unresolved render; Confirm disabled while blocked.

---

## Task 8: End to end on a scratch warehouse

**Description:** One test drives resolution -> `apply_resolution` -> write to a scratch DuckDB `raw_config.cities` -> the ingest read, asserting the slug the app wrote is the slug the scrape URL uses.

**Acceptance criteria:**
- [ ] A single test proves the written slug reaches `/cost-of-living/in/<slug>`.

**Verification:**
- [ ] `make test` passes.

**Dependencies:** Tasks 4, 5.
**Files:** `tests/test_city_resolution.py`.
**Scope:** Small.

---

## Checkpoint: Complete
- [ ] Every acceptance criterion met.
- [ ] `make test` green; `bruin validate pipeline` clean.
