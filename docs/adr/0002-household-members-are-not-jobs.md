# Household members are not jobs

**Status:** accepted

The number of Members a comparison runs for is entered in the entry mask and stored in the app's own config. It is never derived from the number of job rows.

Deriving it was the tempting simplification - two jobs, two people - and it breaks two real cases. A partner who has not found work in the new city still pays rent and eats, so a household of two with one income must be expressible; deriving from jobs silently reports that household at single-person costs, which flatters every city equally and so looks correct. And one person with a second job would be counted as a household of two, doubling costs that only one person incurs.

## Considered options

- **Two job rows mean two Members.** Rejected: it cannot represent the trailing partner, which is the case an expat comparison exists to answer.
- **A Member count on the analysis page, defaulted from the rows.** Rejected as the primary shape: the count survives the pipeline run and should be set once with the rest of the config, not re-guessed on every render.
- **Derive the Member count with the LLM from the free-text criteria.** Rejected: one number that drives every cost total would become non-deterministic and invisible, and this pipeline has already been bitten twice by model drift in values it was trusted to infer.

## Consequences

- Jobs are a list of incomes, length zero to n, and the app-owned config gains a settings table for scalars of this kind.
- Costs scale on the Member count and income scales on the jobs, so the two axes have to be read from different places, and the analysis sidebar's job selection can only ever move income.
