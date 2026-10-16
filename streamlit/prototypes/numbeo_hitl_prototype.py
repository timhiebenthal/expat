"""Throwaway mock of the HITL city-resolution panel. No API, no LLM, no DB.

Run it:
    uv run streamlit run streamlit/prototypes/numbeo_hitl_prototype.py

It answers one design question: what does the resolution surface look like on the
same page as the editor, without cramming the decision into the editable table.
All the "Numbeo" calls are a hardcoded dict - nothing leaves the process.
"""

import pandas as pd
import streamlit as st

# --- Stubbed "Numbeo" ------------------------------------------------------
# What CitySearchJson would return, per typed name.
SEARCH = {
    "munich": [{"label": "Munich, Germany", "value": "1111"}],
    "tel aviv": [{"label": "Tel Aviv-Yafo, Israel", "value": "6845"}],
    "london": [
        {"label": "London, United Kingdom", "value": "1000"},
        {"label": "London, Canada", "value": "2000"},
    ],
    "washington, dc": [{"label": "Washington, DC, United States", "value": "3497"}],
    "nowhereville": [],
}

# What dispatcher.jsp would resolve a city_id to (the canonical slug).
SLUG = {
    "1111": "Munich",
    "6845": "Tel-Aviv-Yafo",
    "1000": "London",
    "2000": "London-Canada",
    "3497": "Washington",
}

SUGGESTIONS = [
    {"name": "Munich", "country": "Germany", "description": "Current home."},
    {"name": "Tel Aviv", "country": "Israel", "description": "Warm, tech, transit."},
    {"name": "London", "country": "", "description": "Big job market."},
    {"name": "Washington, DC", "country": "United States", "description": "Mild."},
    {"name": "Nowhereville", "country": "", "description": "Made up."},
]


def resolve(name, country=""):
    """Return (state, matches). state is 'resolved' | 'ambiguous' | 'unresolved'."""
    key = name.strip().lower()
    matches = SEARCH.get(key) or SEARCH.get(key.split(",")[0].strip())
    if not matches:
        return "unresolved", []
    if len(matches) == 1:
        return "resolved", matches
    if country:
        narrowed = [m for m in matches if country.lower() in m["label"].lower()]
        if len(narrowed) == 1:
            return "resolved", narrowed
    return "ambiguous", matches


def slug_for(city_id):
    return SLUG.get(city_id, f"unknown-{city_id}")


st.set_page_config(page_title="Numbeo HITL mock", layout="wide")
st.title("Expat Planning App - Numbeo resolution mock")
st.caption("Throwaway prototype. Stubbed Numbeo, no LLM, no writes.")

for key, default in [
    ("cities", SUGGESTIONS),
    ("resolution", None),
    ("picks", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

with st.form("inputs"):
    st.text_input("Where do you live currently?", value="Berlin, Germany")
    st.text_area("Cities you enjoyed", value="London, New York")
    st.text_area("What matters to you", value="Warm, walkable, safe at night")
    st.form_submit_button("Find Cities (stubbed)")

st.subheader("Cities to compare")
edited = st.data_editor(
    data=pd.DataFrame(st.session_state.cities), num_rows="dynamic", hide_index=True
)
st.session_state.cities = edited.to_dict("records")

simulate_throttle = st.checkbox("Simulate Numbeo 'Access Restricted'")

if st.button("Submit Cities", type="primary"):
    if simulate_throttle:
        st.session_state.resolution = {"throttled": True}
    else:
        rows = []
        for city in st.session_state.cities:
            state, matches = resolve(city.get("name", ""), city.get("country", ""))
            rows.append({**city, "state": state, "matches": matches})
        st.session_state.resolution = {"throttled": False, "rows": rows}
        st.session_state.picks = {}

res = st.session_state.resolution

if res and res["throttled"]:
    st.error(
        "Numbeo is rate-limiting us (Access Restricted). Nothing was written - "
        "your previous city list is unchanged. Retry in a few minutes, or paste "
        "slugs manually."
    )

elif res:
    st.divider()
    rows = res["rows"]
    resolved = [r for r in rows if r["state"] == "resolved"]
    ambiguous = [r for r in rows if r["state"] == "ambiguous"]
    unresolved = [r for r in rows if r["state"] == "unresolved"]

    st.subheader("Resolution")
    st.caption(
        "Each city is matched to Numbeo's own listing. Anything that did not match "
        "cleanly needs a quick decision below. Nothing is saved until you confirm."
    )
    if resolved:
        pairs = "\n".join(
            f"- {r['name']} -> {slug_for(r['matches'][0]['value'])}"
            for r in resolved
        )
        st.success(f"Resolved:\n\n{pairs}")

    # Deliberately NOT inside the data_editor above: these need widgets, not cells.
    if ambiguous:
        st.warning(
            f"{len(ambiguous)} name(s) match more than one place - pick the one you mean."
        )
        for i, r in enumerate(ambiguous):
            options = [m["label"] for m in r["matches"]]
            choice = st.radio(
                f"Which **{r['name']}**?",
                options,
                index=0,  # Numbeo's own order, as a default - not as truth
                key=f"amb-{i}",
            )
            st.session_state.picks[r["name"]] = next(
                m["value"] for m in r["matches"] if m["label"] == choice
            )

    if unresolved:
        st.warning(
            f"Numbeo has no match for {len(unresolved)} name(s) - rename, paste a slug, or remove."
        )
        for i, r in enumerate(unresolved):
            with st.expander(f"**{r['name']}** - no Numbeo match", expanded=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                new_name = c1.text_input("Rename", value=r["name"], key=f"ren-{i}")
                manual = c2.text_input(
                    "or paste a Numbeo slug", placeholder="e.g. Tel-Aviv-Yafo", key=f"slug-{i}"
                )
                drop = c3.checkbox("Remove", key=f"drop-{i}")
                st.session_state.picks[r["name"]] = {
                    "rename": new_name,
                    "manual": manual,
                    "drop": drop,
                }

    blocked = bool(ambiguous or unresolved)
    if st.button("Confirm and run pipeline", disabled=blocked):
        final = []
        for r in rows:
            if r["state"] == "resolved":
                final.append(
                    {**r, "numbeo_slug": slug_for(r["matches"][0]["value"])}
                )
            elif r["state"] == "ambiguous":
                final.append(
                    {**r, "numbeo_slug": slug_for(st.session_state.picks[r["name"]])}
                )
        st.success("Would write raw_config.cities:")
        st.dataframe(final)
    if blocked:
        st.caption("Confirm is disabled until every city is resolved. Nothing is written.")
