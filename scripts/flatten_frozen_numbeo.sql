-- Rebuild the frozen numbeo Raw in the shape the Bruin ingest now produces, so the
-- flat clean/prep models can be exercised against frozen VALUES rather than a
-- fresh scrape.
--
-- Run against a SCRATCH copy of the baseline, never the baseline itself:
--
--   cp baseline/dwh.duckdb /tmp/parity.duckdb
--   duckdb /tmp/parity.duckdb -c "read scripts/flatten_frozen_numbeo.sql"
--
-- Value-preserving: every city/category/cost comes from the frozen child table
-- joined to its parent, so a difference downstream is a port bug, not a data
-- difference. This is the one Raw table whose shape the migration changes, which
-- is why it needs a fixture at all.

create or replace table raw_numbeo.cost_of_living_flat as
select
    city.city as city,
    data.category as category,
    data.cost as cost
from raw_numbeo.cost_of_living__data as data
join raw_numbeo.cost_of_living as city
    on data._dlt_parent_id = city._dlt_id;

drop table raw_numbeo.cost_of_living;

alter table raw_numbeo.cost_of_living_flat rename to cost_of_living;
