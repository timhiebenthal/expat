-- Parity gate 2 for the entity tables the app reads: bidirectional EXCEPT ALL.
-- It is multiset equality, so it catches row loss and duplicate-count drift that
-- `bruin data-diff` (schema, row counts, statistics) can miss.
--
-- Run against the frozen baseline copy, one table at a time:
--
--   duckdb baseline/dwh.duckdb -c "set variable table_name='core__job_earnings';
--                                  read scripts/parity.sql"
--
-- Both counts must be 0. Gate 1 is the data-diff invocation in SPEC.md.

select
    getvariable('table_name') as table_name,
    (
        select count(*) from (
            select * from query(format('select * from baseline.{0}', getvariable('table_name')))
            except all
            select * from query(format('select * from analytics.{0}', getvariable('table_name')))
        )
    ) as only_in_baseline,
    (
        select count(*) from (
            select * from query(format('select * from analytics.{0}', getvariable('table_name')))
            except all
            select * from query(format('select * from baseline.{0}', getvariable('table_name')))
        )
    ) as only_in_bruin;
