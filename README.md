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
- **raw_data**
    contains raw data loaded into DuckDB 
- **database**
    contains the DuckDB database(s)
- **dbt**
    contains the dbt-project for data transformations
- **data_viz**
    contains various forms of data visualization and interaction
<!-- - llm -->