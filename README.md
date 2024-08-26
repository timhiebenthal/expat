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


### Potential Features / To Do List:

- integrate other cost of living beyond rent
- allow for multi-select in jobs to simulate couple / group
- let LLM find fitting cities for you