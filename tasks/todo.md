# Task List: Households - comparing a move for one person or a couple

Plan: `tasks/plan.md` | Contract: `SPEC.md` | Modules: `transform` `app` `quality` `docs`

## Worktree prerequisites

`baseline/` and `database/dwh.duckdb` are both gitignored, so a fresh worktree has neither and everything that needs a warehouse will skip or fail. Before Task 1:

```bash
export PATH="$HOME/.local/bin:$PATH"
# Pipeline work reads frozen inputs from the main checkout's baseline copy. The
# transforms replace its analytics.* tables; its raw_* stay frozen, which is the
# point of it.
export DUCKDB_LOCATION=/home/tim_ubuntu/git_repos/expat/baseline/dwh.duckdb
# Page tests copy a warehouse. A symlink is test-only: the app itself runs from
# the main checkout, and DuckDB allows a single writer.
ln -s /home/tim_ubuntu/git_repos/expat/database/dwh.duckdb database/dwh.duckdb
```

---

## Phase 1: The Cost item basis

## Task 1: Seed, prep and core carry `counted_for` `[transform]`

**Description:** Add one data column that says whether a Cost item's count is stated per Member or for the Household, default it from the Cost group in prep, and carry it through to `core__activity`. No value changes for a one-Member household: `activity_monthly_default_count` is untouched and this task changes no arithmetic anywhere.

**Acceptance criteria:**
- [ ] `seed_activity_mapping.csv` gains a fully quoted `counted_for` column: empty on every row except `Restaurant - Mid-range Meal for 2` (`household`) and `Utilities - Mobile Phone Plan` (`person`)
- [ ] `seed_activity_mapping.asset.yml` declares `counted_for` as `varchar`, next to the existing column declarations
- [ ] `prep__numbeo_cost_of_living` resolves an empty value with `coalesce(nullif(mapping.counted_for, ''), case when mapping.activity_type in ('Groceries', 'Restaurant', 'Mobility', 'Leisure', 'Clothing') then 'person' else 'household' end)` and names the result `counted_for`
- [ ] `core__activity`'s `distinct` select includes `counted_for`, so dashboard rows carry it
- [ ] No other column and no value in `prep__numbeo_cost_of_living` changes

**Verification:**
- [ ] `bruin run pipeline --selector "tag:layer:transform" --workers 1` succeeds against `baseline/dwh.duckdb` (the seed is tagged `layer:transform` on purpose, so the selector picks up the new column)
- [ ] `duckdb "$DUCKDB_LOCATION" -c "select counted_for, count(*) from analytics.core__activity group by 1 order by 1"` shows both values, and the two exception items resolve to their stated basis
- [ ] `duckdb "$DUCKDB_LOCATION" -c "select count(*) from analytics.prep__numbeo_cost_of_living where counted_for is null or counted_for = ''"` returns 0
- [ ] `make test` passes, including `tests/test_numbeo_activity_mapping.py`, which reads the seed by column name

**Dependencies:** None

**Files likely touched:**
- `pipeline/assets/seed/seed_activity_mapping.csv`
- `pipeline/assets/seed/seed_activity_mapping.asset.yml`
- `pipeline/assets/prep/numbeo_cost_of_living.sql`
- `pipeline/assets/core/activity.sql`

**Estimated scope:** Medium

---

## Checkpoint A: Basis

- [ ] The transform layer runs against the baseline copy and every row of `core__activity` resolves a basis
- [ ] The two exceptions resolve as specified; every other row follows its Cost group
- [ ] `make test` passes

---

## Phase 2: The counting model

## Task 2: `streamlit/household.py`, tests first `[app]`

**Description:** Write the failing tests first, then the module. Three pure functions, ported from the prototype's module, with no Streamlit import: the opening count for a Cost item, the per-Member figure for its label, and the Member count read from a settings mapping. One Member must reproduce today's numbers exactly, which is what makes the module's tests the regression test for the whole feature.

**Acceptance criteria:**
- [ ] `tests/test_household.py` exists and fails before the module does
- [ ] `default_count(seed_count, counted_for, members)`: couple - cappuccino 8, water 60, mobile phone 2, broadband 1, utilities 1, meal for two 4; single - 4, 30, 1, 1, 1, 4
- [ ] `per_member_figure(count, counted_for, members)`: `"20 per Member"` for 40 with two Members and for 40 with one, `"shared - paid once for the household"` for a shared Cost item
- [ ] `members_from_settings(settings)`: `"2"` -> 2, missing key -> 1, `None` -> 1, `"3"` -> 2, `"0"` -> 1, `"two"` -> 1
- [ ] The module imports nothing from Streamlit or DuckDB

**Verification:**
- [ ] `uv run pytest tests/test_household.py -v` fails first for the right reason, then passes
- [ ] `make test` passes

**Dependencies:** None (Task 1 is not needed to write or test pure functions)

**Files likely touched:**
- `streamlit/household.py` (new)
- `tests/test_household.py` (new)

**Estimated scope:** Small

---

## Checkpoint B: Counting

- [ ] The couple and single-person numbers match the prototype's verified values
- [ ] `make test` passes

---

## Phase 3: The analysis surface

## Task 3: Counts open at the household's size, labelled per Member `[app]`

**Description:** Read the Member count from the app-owned settings and derive each count input's opening value from it. With no settings row the page must be indistinguishable from today, which is what makes this task safe to land before the mask can write a count.

**Acceptance criteria:**
- [ ] `utils.load_config()` returns `members` alongside `cities` and `jobs`, read from `raw_config.settings` where `key = 'members'`, through a typed accessor that falls back to 1 when the table, the row or the value is missing or nonsense, clamped to 1 or 2
- [ ] Each sidebar input's value is `household.default_count(...)` for the Member count, and `max_value` is raised so the largest default (water, 60) fits - today's ceiling of 50 would block it
- [ ] Every count shows its per-Member figure from `household.per_member_figure(...)`, and for a single Member it reads the same as the count
- [ ] Widgets are keyed (`count__<activity name>`), and a session-state record holds the counts the user has changed
- [ ] On render, a count the user has not changed is re-derived; a count they have changed keeps its value and is never silently rewritten
- [ ] With `raw_config.settings(members = 2)`, the page opens at doubled per-person defaults and unchanged shared ones; with no such table, at today's numbers

**Verification:**
- [ ] `make test` passes, including `tests/test_comparison_page.py` extended with a settings row written into the warehouse copy and an assertion on the rendered input values
- [ ] An `AppTest` rerun that changes one count and re-renders shows the changed value kept and the untouched ones still derived
- [ ] `uv run streamlit run streamlit/Home.py` by hand against a two-Member settings row: cappuccino reads 8 and its label reads "4 per Member" for a couple

**Dependencies:** Task 1 (the column has to exist in the warehouse), Task 2

**Files likely touched:**
- `streamlit/utils.py`
- `streamlit/pages/Comparison.py`
- `tests/test_comparison_page.py`

**Estimated scope:** Medium

---

## Task 4: Honest totals and the configured pair `[app]`

**Description:** Make the totals say what they are, and open the job picker on the household that was configured rather than on whichever title sorts first.

**Acceptance criteria:**
- [ ] The page's local column `variable_living_cost_eur` becomes `other_monthly_cost_eur`, displayed as "Other monthly cost" instead of "Additional Cost of Living"
- [ ] Rent, other and total appear as three separate lines with the sums they name, and the rent line names the selected location
- [ ] The sidebar's job multiselect opens on the pair configured in `raw_config.jobs`, matched against the warehouse's `job_title_experience_short` values, falling back to the first available title when a configured one is absent
- [ ] Changing the job selection moves income, total, the ratios and savings only: the rent and other cost columns are identical for the same cities
- [ ] No column is renamed in the pipeline; this is a page-local rename

**Verification:**
- [ ] `make test` passes, including a `tests/test_comparison_page.py` assertion that the picker's default is the configured pair and that the cost columns do not move when the selection changes
- [ ] `uv run streamlit run streamlit/Home.py` by hand: the three lines appear and add up

**Dependencies:** Task 3

**Files likely touched:**
- `streamlit/pages/Comparison.py`
- `tests/test_comparison_page.py`

**Estimated scope:** Small

---

## Checkpoint C: Analysis

- [ ] A two-Member settings row doubles the per-person counts and leaves the shared ones alone
- [ ] No settings row renders exactly today's numbers
- [ ] An edited count survives a rerun and a household change
- [ ] `make test` passes

---

## Phase 4: The entry mask

## Task 5: Single / Couple in the entry mask `[app]`

**Description:** Let the household be chosen where the rest of the config is chosen, persist it, and stop empty job rows from reaching the table the earnings retrieval loops over.

**Acceptance criteria:**
- [ ] `Home.py` offers Single / Couple above the job editor, defaulting to whatever `raw_config.settings` holds, so a returning user sees their household
- [ ] Choosing Couple appends a second empty job row to the editor as an affordance; the Member count itself comes from the selector and is never inferred from the row count
- [ ] Job rows with an empty or missing title are dropped before `raw_config.jobs` is written
- [ ] Submitting with no job rows at all is refused with an error, since the comparison needs at least one income
- [ ] `utils.save_config_to_duckdb(city_df, jobs_df, members)` writes `raw_config.settings` as `CREATE OR REPLACE TABLE raw_config.settings AS SELECT * FROM settings_df` with one row, `key = 'members'`
- [ ] The pipeline trigger and the page switch are unchanged

**Verification:**
- [ ] `make test` passes, including `tests/test_app_smoke.py` with the selector rendered, and a settings round trip: write with two Members against a temporary warehouse, read back 2; read against a warehouse with no settings table, get 1
- [ ] By hand: choose Couple, submit, land on the Comparison page, and see the couple's counts and totals
- [ ] `duckdb "$DUCKDB_LOCATION" -c "select * from raw_config.settings"` shows `members | 2`, and `raw_config.jobs` holds no empty title

**Dependencies:** Task 3 (the reader and the page), Task 4

**Files likely touched:**
- `streamlit/Home.py`
- `streamlit/utils.py`
- `tests/test_app_smoke.py`
- `tests/test_config_settings.py` (new)

**Estimated scope:** Medium

---

## Checkpoint D: End to end

- [ ] Mask to pipeline to page: a couple reaches the comparison at two Members
- [ ] An empty job row reaches neither `raw_config.jobs` nor the earnings retrieval
- [ ] `make test` passes

---

## Phase 5: Guards and capture

## Task 6: The unknown Cost group check, seen failing `[quality]`

**Description:** Guard the one silent failure this design allows: a Numbeo Cost group arriving with no decision made about whether it is per-person, which the prep default would quietly treat as Shared. The check asserts every `activity_type` in the seed is one the Cost group rule knows.

**Acceptance criteria:**
- [ ] `core__activity` carries a `custom_check` in the port's shape whose query counts seed rows whose `activity_type` is outside the known groups (Groceries, Restaurant, Mobility, Leisure, Clothing, Utilities, Housing, Buy Housing, Childcare, Education) and whose `value` is 0
- [ ] The check has been observed failing on a deliberately unknown group, with the failure recorded in the commit message, then restored to passing
- [ ] The check attaches to `core__activity`, the asset that would be wrong, not to a central place

**Verification:**
- [ ] Break it: add a seed row with an unknown group, `bruin run pipeline --selector "tag:layer:transform" --workers 1`, observe the check fail and the count exceed 0
- [ ] Restore it: the same command passes with a count of 0
- [ ] `uv run pytest tests/test_pipeline_validates.py -v` and `make test` pass

**Dependencies:** Task 1

**Files likely touched:**
- `pipeline/assets/core/activity.sql`
- `pipeline/assets/seed/seed_activity_mapping.csv` (temporarily, for the failing run)

**Estimated scope:** Small

---

## Task 7: Capture the prototype, retire the README line `[docs]`

**Description:** The prototype answered its question, so it leaves the feature tree and becomes a primary source on a throwaway branch, with `SPEC.md` pointing at that branch instead of at the path. The README's couple item is done.

**Acceptance criteria:**
- [ ] The prototype commit is reachable from a `prototype/household-counts` branch
- [ ] `streamlit/prototypes/` no longer exists on the feature branch, and `SPEC.md` names the branch where the prototype lives
- [ ] The README's "allow for multi-select in jobs to simulate couple / group" line is gone, and nothing else in the README changes
- [ ] The counting functions it proved live in `streamlit/household.py`, not only in the prototype

**Verification:**
- [ ] `git log --oneline prototype/household-counts` shows the prototype
- [ ] `git ls-tree -r --name-only feature/couples | grep prototypes` returns nothing
- [ ] `make test` passes

**Dependencies:** Task 3 (the functions have to be in the real module first), Task 4, Task 5

**Files likely touched:**
- `streamlit/prototypes/household-member-counts.prototype.html` (removed from this branch)
- `SPEC.md`
- `README.md`

**Estimated scope:** Small

---

## Checkpoint E: Complete

- [ ] Every Success Criterion in `SPEC.md` holds
- [ ] The check has been observed failing on a deliberately unknown Cost group
- [ ] `make test` passes and `make fmt` leaves the SQL unchanged
