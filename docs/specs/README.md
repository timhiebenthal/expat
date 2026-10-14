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
