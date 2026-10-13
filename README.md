## Expat Analytics

This repository can be considered an end-to-end data pipleine covering the areas of
* Data Retrieval
* Data Transformation & Modelling
* Data Analysis & Visualization

The scope & purpose of this project is not commercial, but should be rather considered a fun and learning project.
This reflects also in the choice of tooling: the pipeline isn't meant to scale to large data volumes or organizations

### Different directories and their purpose

- **loading**
    contains python scripts to retrieve data and - mostly - load it into DuckDB
- **database**
    contains the DuckDB database(s)
- **dbt**
    contains the dbt-project for data transformations
- **app**
    contains the streamlit app acting as the UI for the end user
<!-- - llm -->

### Development

Dependencies are managed with [uv](https://docs.astral.sh/uv/). `pyproject.toml` is
the single source of truth and `uv.lock` is committed.

```bash
uv sync          # install
uv run pytest    # run the tests
```

The SQL formatter `harlequin` is a standalone CLI and is deliberately not a project
dependency - every published version either pins `numpy<2` (1.x) or forces
`duckdb>=1.1.1` (2.x), both of which break the pinned runtime. Install it separately:

```bash
uv tool install harlequin
```


### Potential Features / To Do List:

- integrate other cost of living beyond rent
- allow for multi-select in jobs to simulate couple / group
- let LLM find fitting cities for you