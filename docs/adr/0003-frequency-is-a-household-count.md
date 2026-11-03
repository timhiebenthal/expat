# Frequency is a Household count

**Status:** accepted

A Cost item's Frequency - how many times a month it is consumed - is a Household total, and the count a Cost item is *stated* in is either per Member or for the whole Household. For a Per-person cost item the Household total opens at the stated count times the Members; for a Shared one it opens at the stated count unchanged. The cost itself stays `price x Frequency`.

A per-Member rate was the obvious alternative and it was rejected on two counts. It would imply a Member dimension that buys nothing: every Member consumes identically, so the only thing the dimension could do is be summed back out. And it cannot express the habits that actually differ - one of you drinks twenty beers a month and the other none, which one Household number states exactly and a per-Member rate of ten each cannot.

## Consequences

- Every Cost item carries which of the two counts it is stated in, defaulted from its Cost group and overridable per item, because two items in the dashboard are exceptions: a meal priced for two, and a phone plan inside the otherwise shared utilities group.
- A Cost item's default count now means one thing for a single person and two for a couple, so the number an input opens at is derived rather than stored.
- Renaming the seed column changes no data: for a Household of one Member, every default is what it always was.
