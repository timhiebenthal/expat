# Expat

A personal tool for comparing the cost of living and local salaries across candidate cities, so a move between them can be planned on numbers rather than impressions.

## Language

### Layers

**Raw**:
The schemas Ingest writes into, named `raw_<source>`. Rows mirror what the source served.

**Clean**:
The first transformation layer. One model per Raw table, doing renaming and typing only.
_Avoid_: staging, bronze

**Prep**:
Joins and calculations that more than one Core entity needs.
_Avoid_: preprocess, intermediate, silver

**Core**:
One entity per model, at that entity's natural grain.
_Avoid_: entity, gold

**Mart**:
Presentation-ready tables, each shaped for a single consumer.
_Avoid_: dataset, presentation

### Cost of living

**Cost item**:
A good or service priced in a city. Everything priced is paid for, so free items are out of scope by definition.
_Avoid_: activity, expense, line item

**Frequency**:
How many times per month a Cost item is consumed. A one-off purchase is a Frequency of 1.
_Avoid_: count, activity count

**Monthly cost**:
A Cost item's city price multiplied by its Frequency.

**Cost group**:
The bucket a Cost item is filtered by - restaurant, groceries, housing, mobility and so on.
_Avoid_: activity type, activity category, category

### Movement

**Ingest**:
Moving data from a source into Raw. Ingest never reshapes, joins or denormalises.
_Avoid_: load, extract, EL

**Transform**:
Everything that turns Raw into Clean, Prep, Core and Mart.

### False friends

**Source**:
An upstream origin that Ingest reads - a website, an API, a form. Never use it for a warehouse table the pipeline reads but does not produce; that is a Raw table or an external table.
_Avoid_: using "source" for a declared table
