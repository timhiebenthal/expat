-- Parity gate 2 for the entity tables the app reads: bidirectional EXCEPT ALL.
-- It is multiset equality, so it catches row loss and duplicate-count drift that
-- `bruin data-diff` (schema + row counts) can miss.
--
-- Run against the frozen baseline copy, one table at a time. Set both variables
-- first - `parity_columns` is the projection compared on BOTH sides:
--
--   duckdb baseline/dwh.duckdb -c "set variable table_name='core__job_earnings';
--                                  set variable parity_columns='*';
--                                  read scripts/parity.sql"
--
-- A projection narrower than `*` is an explicit, reviewable exclusion - it is how
-- a column the migration deliberately drops (dlt's `city_id` in
-- core__cost_of_living) is kept visible instead of hidden. Gate 1 (data-diff)
-- still reports the schema difference.

select
    getvariable('table_name') as table_name,
    (
        select count(*) from (
            select * from query(
                format(
                    'select {0} from baseline.{1}',
                    getvariable('parity_columns'),
                    getvariable('table_name')
                )
            )
            except all
            select * from query(
                format(
                    'select {0} from analytics.{1}',
                    getvariable('parity_columns'),
                    getvariable('table_name')
                )
            )
        )
    ) as only_in_baseline,
    (
        select count(*) from (
            select * from query(
                format(
                    'select {0} from analytics.{1}',
                    getvariable('parity_columns'),
                    getvariable('table_name')
                )
            )
            except all
            select * from query(
                format(
                    'select {0} from baseline.{1}',
                    getvariable('parity_columns'),
                    getvariable('table_name')
                )
            )
        )
    ) as only_in_bruin;
