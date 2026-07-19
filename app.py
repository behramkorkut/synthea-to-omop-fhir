"""Cohort explorer over the OMOP CDM (Streamlit).

Every figure comes from the governed cohort operations — no raw SQL on patient
data. Run:  make dashboard   (http://localhost:8501)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from synthea_omop_fhir.cohort import builder

st.set_page_config(page_title="OMOP Cohort Explorer", page_icon="🩺", layout="wide")


@st.cache_data(ttl=300, show_spinner=False)
def prevalence(top_n: int) -> pd.DataFrame:
    return pd.DataFrame(builder.condition_prevalence(top_n))


@st.cache_data(ttl=300, show_spinner=False)
def cohort(term: str) -> dict:
    return builder.condition_cohort(term)


@st.cache_data(ttl=300, show_spinner=False)
def measurement(term: str) -> dict:
    return builder.measurement_summary(term)


with st.sidebar:
    st.header("OMOP CDM · synthetic patients")
    st.caption(
        "Governed cohort operations only — no free-form SQL on patient data. "
        "Data is 100% synthetic (Synthea)."
    )
    st.metric("Patients", f"{builder.total_patients():,}")

st.title("🩺 OMOP Cohort Explorer")

left, right = st.columns(2)

with left:
    st.subheader("Condition cohort")
    term = st.text_input("Condition contains…", value="lung cancer")
    if term:
        c = cohort(term)
        st.metric(f'Patients with "{term}"', c["patient_count"])
        if c["by_gender"]:
            st.bar_chart(
                pd.DataFrame(
                    {
                        "gender": list(c["by_gender"]),
                        "patients": list(c["by_gender"].values()),
                    }
                ),
                x="gender",
                y="patients",
            )

    st.subheader("Measurement summary")
    mterm = st.text_input("Measurement contains…", value="Hemoglobin A1c")
    if mterm:
        m = measurement(mterm)
        if m["n"]:
            a, b, cc = st.columns(3)
            a.metric("n", f"{m['n']:,}")
            b.metric("mean", f"{m['mean']} {m['unit'] or ''}")
            cc.metric("range", f"{m['min']}–{m['max']}")
        else:
            st.info("No matching measurement.")

with right:
    st.subheader("Most frequent conditions")
    top_n = st.slider("Top N", 5, 30, 12)
    df = prevalence(top_n)
    if not df.empty:
        st.bar_chart(df, x="description", y="patient_count", horizontal=True)
        st.dataframe(df, width="stretch", hide_index=True)
