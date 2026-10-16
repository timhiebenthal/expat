# Implementation Plan: Households - comparing a move for one person or a couple

## Overview

Make the comparison runnable for a Household of two Members. One attribute rides through the pipeline - whether a Cost item's count is stated per Member or for the Household - and the app derives each count's opening value from it and the Member count. The income side is already a sum over jobs; it needs a default and a label, not a rewrite. The contract is `SPEC.md`; the records are ADR 0002 and ADR 0003.

Already in place on this branch: the vocabulary in `GLOSSARY.md`, and the throwaway prototype whose verified numbers the counting tests assert against.

## Architecture Decisions

- **The Member count is a rendering input, never a pipeline input.** Nothing downstream of the app consumes it, so it lives in `raw_config.settings` and is read directly, like `raw_config.cities` and `raw_config.jobs` already are. No transform model, no new asset.
- **The pipeline carries one attribute, not a calculation.** `counted_for` is data: `person` or `household`, stated per Cost item, defaulted from the Cost group in `prep`, carried by `core__activity`. Nothing in the pipeline multiplies anything.
- **Derive in the app, from data.** The counting is three pure functions in `streamlit/household.py`, ported from the prototype's module, so it is testable without Streamlit and identical to what the prototype proved.
- **Build the analysis before the mask.** With no `raw_config.settings` the app reads one Member, so the page work is behaviour-identical until the mask starts writing a count. Each phase leaves a working system, and the couple only becomes reachable in Phase 4.
- **Order the seed's meaning, not its values.** For one Member every default is what it is today, which is what makes the single-person case the regression test for the whole feature.

## Dependency Graph

```
Task 1  seed + prep + core carry counted_for   (pipeline lane, no app files)
            |
Task 2  streamlit/household.py, tests first    (app lane)
            |
Task 3  counts open at the household's size  <- needs Task 1's column in the warehouse
            |
Task 4  honest totals + the configured pair    (same file as Task 3, sequential)
            |
Task 5  Single / Couple in the entry mask      (settings writer, page unchanged)
            |
Task 6  the unknown Cost group check           (asset header + seed, temporary break)
            |
Task 7  capture the prototype, retire the README line
```

Task 3 both reads Task 1's column and writes between Tasks 2 and 4; nothing else crosses the two lanes.

## Task List

### Phase 1: The Cost item basis

- [ ] Task 1 `[transform]` Seed, prep and core carry `counted_for`

### Checkpoint A: Basis

- [ ] The transform layer runs against the frozen baseline copy and `core__activity` resolves a basis for every row
- [ ] The two exception items resolve as specified and every other row follows its Cost group
- [ ] `make test` passes

### Phase 2: The counting model

- [ ] Task 2 `[app]` `streamlit/household.py`, tests first

### Checkpoint B: Counting

- [ ] The couple and single-person numbers match the prototype exactly
- [ ] `make test` passes

### Phase 3: The analysis surface

- [ ] Task 3 `[app]` Counts open at the household's size, labelled per Member
- [ ] Task 4 `[app]` Honest totals and the configured pair

### Checkpoint C: Analysis

- [ ] With a two-Member settings row, the page opens at doubled per-person defaults and unchanged shared ones
- [ ] With no settings row, the page renders exactly as it does today
- [ ] An edited count survives a rerun and is not overwritten by a household change
- [ ] `make test` passes

### Phase 4: The entry mask

- [ ] Task 5 `[app]` Single / Couple in the entry mask

### Checkpoint D: End to end

- [ ] Mask to pipeline to page: a couple entered in the mask reaches the comparison at two Members
- [ ] An empty job row never reaches `raw_config.jobs` or the earnings retrieval
- [ ] `make test` passes

### Phase 5: Guards and capture

- [ ] Task 6 `[quality]` The unknown Cost group check, seen failing
- [ ] Task 7 `[docs]` Capture the prototype, retire the README line

### Checkpoint E: Complete

- [ ] Every Success Criterion in `SPEC.md` holds
- [ ] The check has been observed failing on a deliberately unknown Cost group
- [ ] `make test` passes and the SQL is formatted

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Streamlit's widget identity silently drops an edited count when its default changes | High - the app quietly loses the user's numbers | Keyed `number_input`s plus a session-state record of which counts were edited; an `AppTest` rerun that changes a value and re-renders proves it survives |
| The current `max_value=50` blocks a couple's water default of 60 | High - the page raises instead of rendering | Raise the ceiling to 400 and assert a 60 default renders |
| Adding the column changes what the seed means, and a single person's numbers move | High - silent regression for the main use case | One Member is the regression test: every default asserted unchanged, item by item, in Task 2 |
| A new Numbeo Cost group arrives and is silently treated as Household | Medium - understated costs, in every city equally, so it looks correct | The check from Task 6, attached to `core__activity`, seen failing before it is trusted |
| The app holds the DuckDB write lock while a run wants it | Medium - the run dies on the file lock | Pipeline runs stay in a subprocess with `--workers 1`; page tests copy the warehouse |
| An existing warehouse has no `raw_config.settings` | Low - a page error on first load after the change | Default to one Member, asserted in Task 3 |
| A settings value outside one or two | Low - nonsense cost totals | Coerce to the range and fall back to one Member |

## Parallelization Opportunities

None worth taking. Task 1 and Task 2 touch disjoint files, but Task 2 is small and Task 3 - which reads Task 1's column - is the next step either way. Everything from Task 3 on shares `streamlit/pages/Comparison.py`, `streamlit/utils.py` or `streamlit/Home.py`, so one worker per file means one lane, sequential.

## Noticed, not fixed

- `utils.save_config` still writes `config.yml` for the Configuration tab's "Save Changes", and nothing reads that file since the loaders were removed. Out of scope here; it is a dead branch of the app, not a household concern.

## Open Questions

None. The identical-job-titles case was settled during specification and is recorded in `SPEC.md`.
