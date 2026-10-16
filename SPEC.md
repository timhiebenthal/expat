# Spec: Households - comparing a move for one person or a couple

## Objective

Let the comparison be run for a **Household** of one or two **Members**, instead of assuming one person per job.

The income half already half-exists: the sidebar sums up to two job titles into a column labelled "Household Net Salary (EUR)". The cost half does not. Every Cost item is treated as if one person consumed it, so a couple sees two incomes against one person's costs and every city looks affordable. The fix is deliberately asymmetric - income sums over the jobs, costs become Household totals whose *defaults* scale for Per-person cost items.

Success is a couple who can enter their household, get counts that open at the right size, and see a comparison whose totals they can trace back to the household they entered. A single person's numbers must not move at all.

One capability, not several: a capability map would split a vertical slice whose parts are useless apart. The entry mask, the Cost item attribute and the page all have to land together, so this is a single spec.

## What the app does today

- The pipeline is Bruin: `pipeline/assets/{ingest,clean,prep,core,seed}/`, one schema (`analytics`), layer prefixes. The app reads `analytics.core__job_earnings`, `core__activity` (filtered to `is_dynamic_in_dashboard`) and `core__cost_of_living`.
- App-owned config is `raw_config.{cities,jobs}`, written by `streamlit/utils.save_config_to_duckdb`, read by `utils.load_config` and by `clean__config_cities` / `clean__config_jobs`.
- `analytics.seed_activity_mapping` (CSV plus an `.asset.yml` declaring column types) maps a Numbeo category to an activity, an `activity_type` (the Cost group) and `activity_count`. `prep__numbeo_cost_of_living` joins it and produces `monthly_activity_count`; `core__activity` renames that to `activity_monthly_default_count`.
- The dashboard shows six Cost groups: Clothing, Groceries, Leisure, Mobility, Restaurant, Utilities. Anything matching `Housing|Education|Child` is filtered out by `is_dynamic_in_dashboard`.
- `streamlit/pages/Comparison.py` computes costs at query time: `cost_eur x selected_count` per Cost item, summed per city, with rent picked separately from a location selectbox and the income summed over the selected job titles. Every count input is an unkeyed `st.number_input` with `value=activity_monthly_default_count` and `max_value=50`.
- `streamlit/Home.py`'s job editor already accepts any number of rows (`num_rows="dynamic"`), and the sidebar multiselect already allows `max_selections=2`.

## Design decisions

Settled in the grilling session, with a prototype for the counting model. The prototype lives on the `prototype/household-counts` branch rather than in this tree; its pure counting functions are the source of the verified numbers below (couple, untouched: EUR 1,488 other monthly cost, EUR 2,688 with rent; single: EUR 984 / EUR 2,184).

1. **A couple is a Household of two Members, chosen in the entry mask.** Jobs never determine the Member count. Two Members with one income is the trailing-partner case and must be expressible; one person with two jobs must not become a household of two.
2. **Frequency is a Household total.** Its default opens at `seed_count x Members` for a Per-person cost item and at `seed_count` for a Shared one. The analysis arithmetic is unchanged: price x count, summed per city. Nothing is materialised per Member, and there is no Member dimension anywhere.
3. **Per-person versus Shared is a property of the Cost item**, defaulted per Cost group and overridable per item. Per-person: Groceries, Restaurant, Mobility, Leisure, Clothing. Shared: Utilities, Housing, Buy Housing, Childcare, Education. Two item-level exceptions: Meal for Two is Shared (already priced and counted for two people), Mobile Phone Plan is Per-person inside an otherwise Shared group.
4. **Untouched counts follow the household; edits keep their value.** A count the user has changed is never silently rewritten. Every count shows its per-Member equivalent so the basis is visible ("40 - 20 per Member" for a couple, and "4 - 4 per Member" for a single person, where nothing looks broken).
5. **The sidebar's job selection controls income only.** It defaults to the configured pair and never moves the Member count.
6. **Rent is untouched by the Member count.** It stays the location selectbox's choice, multiplied by nothing.
7. **The Member count lives in an app-owned `raw_config.settings` key/value table**, read directly by the app with no transform model, defaulting to one Member when the key, the row or the table is missing.
8. **"Additional Cost of Living" becomes "Other monthly cost"**, with rent, other and total shown as separate lines. That column is everything except rent, and broadband is "additional" but Shared.
9. **Dependents are out of scope.** A Household is one or two adults. Childcare and Education stay Shared, which leaves room for a per-child basis later.
10. **The Cost item vocabulary rename rides with the port**, as ADR 0001 schedules. This feature adds no rename; `GLOSSARY.md` already carries the terms.

Two records follow from this and land with the plan: **ADR 0002 - household members are not jobs**, and **ADR 0003 - Frequency is a Household count**.

## Tech Stack

Unchanged. Bruin CLI at the pinned tag, DuckDB as one file at `$DUCKDB_LOCATION`, Streamlit, pytest. No new dependency, Python-side or Bruin-side.

## Commands

```bash
# uv, bruin and pre-commit live in ~/.local/bin, which is not on a
# non-interactive shell's PATH.
export PATH="$HOME/.local/bin:$PATH"
export DUCKDB_LOCATION=database/dwh.duckdb

make test                      # uv run pytest tests -v, also the pre-commit hook
make fmt                       # sqlfmt over pipeline/
uv run streamlit run streamlit/Home.py

bruin validate pipeline
bruin run pipeline --workers 1  # --workers 1: DuckDB takes a single writer

# Failing check, seen failing: break one Cost item's basis, run the transform
# layer against the baseline copy, observe the check fail, then restore.
bruin run pipeline --selector "tag:layer:transform" --workers 1
```

## Project Structure

```
pipeline/assets/seed/seed_activity_mapping.csv   + frequency_basis column
pipeline/assets/seed/seed_activity_mapping.asset.yml  + column type declaration
pipeline/assets/prep/numbeo_cost_of_living.sql   resolves the Cost group default
pipeline/assets/core/activity.sql                carries the resolved column
streamlit/utils.py                               settings read/write, typed accessor
streamlit/Home.py                                Single / Couple in the entry mask
streamlit/pages/Comparison.py                    derived defaults, labels, totals
streamlit/household.py                           NEW: pure counting functions
streamlit/prototypes/                            gone; the prototype is on its own branch
tests/test_household.py                          NEW
tests/test_comparison_page.py                    extended
```

No new transform model: nothing in the pipeline consumes the Member count, and the app reads `raw_config.settings` the way it already reads `raw_config.cities`.

## Code Style

The counting lives in one pure module so it can be tested without Streamlit. `streamlit/household.py`:

```python
PERSON = "person"
HOUSEHOLD = "household"


def default_count(seed_count: int, counted_for: str, members: int) -> int:
    """The Household's opening count. A Per-person count is stated per Member."""
    return seed_count * members if counted_for == PERSON else seed_count


def per_member_figure(count: int, counted_for: str, members: int) -> str:
    """What a count means, for the label beside it."""
    if counted_for == HOUSEHOLD:
        return "shared - paid once for the household"
    return f"{count // members} per Member"
```

SQL keeps the asset header shape the port established - explicit `name:`, `depends:`, a `layer:` tag, and a comment saying why:

```sql
coalesce(
    nullif(mapping.frequency_basis, ''),
    case
        when mapping.activity_type in ('Groceries', 'Restaurant', 'Mobility', 'Leisure', 'Clothing')
        then 'person'
        else 'household'
    end
) as counted_for,
```

Conventions: `snake_case`; `<layer>__<subject>` asset names; the Cost item, Frequency, Household and Member vocabulary from `GLOSSARY.md`; unknown groups default to the safe direction (household, never multiplied).

## Testing Strategy

1. **pytest**, `make test`, and therefore every commit (the pre-commit hook runs it).
   - `tests/test_household.py`: the defaults and the labels. Couple, untouched: cappuccino 8, water 60, broadband 1, mobile phone 2, meal for two 4. Single: nothing differs from today's numbers, item by item. Editing a count keeps it under both household sizes while the label follows the household.
   - `tests/test_comparison_page.py`: an `AppTest` render against a warehouse copy with `raw_config.settings` holding `members = 2` shows doubled per-person defaults and unchanged Shared ones; the same page against a copy without the table still renders, at one Member. Rendered from the warehouse, not asserted against hand-written numbers alone.
   - `tests/test_app_smoke.py`: Home still renders with the selector, and the Couple choice does not break the job editor.
2. **A quality check on the Cost item basis**, in the port's `custom_checks` shape: every `activity_type` in the seed is one the Cost group rule knows, so a new Numbeo category cannot arrive and be silently treated as Shared. It must be **observed failing** on a deliberately added unknown group before it is trusted, and it attaches to the asset that would go wrong (`core__activity`).
3. **Manual**: enter a couple in the mask, run the pipeline, land on the Comparison page, and check that the totals match what the prototype produced for the same inputs.

Nothing here is a coverage gate. Parity against `baseline/` is the port's contract and is not re-run for this feature, because it changes behaviour on purpose.

## Boundaries

**Always**
- Run `make test` before committing, and leave SQL formatted (`make fmt`).
- Keep the counting arithmetic as `price x count`, with the Member factor in the *defaults* only.
- Keep the Member count out of the pipeline's inputs: it is a rendering input, not an ingestion one.
- Default to `household` when a Cost item's basis is unknown.

**Ask first**
- Any further table in `raw_config`, or any other change to the `raw_*` shape. The one exception is `raw_config.settings`, which this spec approves.
- Changing the seed's `activity_count` values. They are the pipeline's input and every city's totals move with them.
- Renaming anything the glossary already names.

**Never**
- Materialise a Member dimension, or multiply costs per Member anywhere other than the derived defaults.
- Write to `raw_*` from Streamlit apart from `raw_config`; only `raw_config` is app-owned.
- Let the sidebar's job selection move the Member count.
- Weaken or delete a check to make a run pass.
- Ship the prototype HTML or its page shell as application code. Its pure functions are the part worth keeping.

## Success Criteria

- The entry mask offers Single and Couple, persists the choice to `raw_config.settings`, and a couple with one income is entered as two Members with one job row. Empty job rows are dropped before anything is written or sent to the model.
- A couple's per-person counts open at `seed x 2` and Shared ones do not move: cappuccino 8, water 60, broadband 1, mobile phone 2, meal for two 4. These are asserted in `tests/test_household.py`.
- No count input can be blocked by its `max_value`: the water default of 60 exceeds today's ceiling of 50, so the ceiling is raised.
- Every count shows its per-Member equivalent next to it, and an edit survives a household change while untouched counts follow it.
- The sidebar's job picker opens on the configured pair, and changing it moves income only.
- Rent is identical for one Member and two.
- "Other monthly cost" replaces "Additional Cost of Living", and rent, other and total appear as separate lines.
- A warehouse with no `raw_config.settings` renders the analysis at one Member instead of failing.
- The new check exists, and has been seen failing on a deliberately unknown Cost group.
- `make test` passes, including the extended page tests and the untouched ones.

## Out of Scope

- Dependents: children, childcare and school fees stay Shared and unmultiplied.
- Households of more than two Members.
- A currency setting, though `raw_config.settings` is now the obvious home for one.
- Telling the city-suggestion prompt about the household.
- Per-Member line items or a per-Member breakdown of the totals.
- Any change to the ingest side, or to the Cost item vocabulary in code.
- Re-running the port's parity gates.

## Open Questions

None outstanding. Anything discovered during the build that contradicts this spec gets raised before the work continues, not worked around.

### Settled during specification

- **A couple with identical job titles is accepted as is.** Two Members with the same title write two identical rows into `raw_config.jobs`, the earnings join doubles the income - correct, that is two earners - and the job label reads the title twice. It is an edge case, and the label being ugly is not worth a dedupe rule.

- **The seed column is `counted_for`, not `frequency_basis`**, with values `person` and `household`. It states whose count it is, which is what it does, and it lines up with the Per-person and Shared cost item terms already in the glossary.
- **The Member count is prefilled, not gathered.** Switching to Couple adds a second empty job row as an affordance; the count itself comes from the selector, so an empty row is never mistaken for a Member.
- **The prototype keeps its `module.exports` hook.** It is what let the counting functions be exercised outside a browser while the numbers were being settled, and the file now lives on the branch that keeps it.
