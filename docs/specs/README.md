# Archived specs

Finished features, moved out of the repo root once they land. Read-only history -
start the next feature from a clean root and write a new spec.

## 2026-10-14 - Migrate the pipeline from dlt + dbt to Bruin

Outcome: `feat/migrate-to-bruin` (`343fd58..d90d8c0`) - dlt, dbt and the
hand-rolled orchestration in `streamlit/utils.py` replaced by one Bruin
pipeline. Exact parity on the three app-read tables, the four dbt checks ported
to Bruin checks, and the app running `bruin run pipeline --workers 1`. The cutover
shipped as #19: `loading/` and `dbt/` deleted, the dependencies removed, the pinned
CLI installed in the image, and the dlt-era `raw_*` tables dropped. Spec:
`docs/specs/2026-10-14-bruin-migration/`.

## 2026-10-16 - Human-in-the-loop city resolution for Numbeo

Outcome: `feature/numbeo-hitl` (`c902992..1139109`, PR #26) - app cities are
resolved to Numbeo's canonical slugs through Numbeo's own search at Submit, with
an on-page panel for ambiguous and unmatched names, and the slug stored on
`raw_config.cities` so the cost-of-living ingest stops failing on names Numbeo
spells differently. Spec: `docs/specs/2026-10-16-numbeo-hitl/`.

## 2026-10-16 - Persist scraped numbeo records

Outcome: `feature/numbeo-cache` (`df775c3..92674a1`, PR #27, stacked on #26) -
`raw_numbeo.cost_of_living` keeps a `scraped_at` and the ingest reuses a city
until its rows are 180 days old, so a re-run with unchanged cities costs no
numbeo requests against the monthly quota. Spec:
`docs/specs/2026-10-16-numbeo-cache/`.
