"""STR Researcher - Main Streamlit Application."""

import streamlit as st


st.set_page_config(
    page_title="STR Researcher",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("STR Researcher")
st.subheader("Short-Term Rental Investment Analysis")

st.markdown("""
Welcome to STR Researcher. This tool helps you evaluate properties for their
potential as short-term rentals by analyzing market data, comparable properties,
and financial projections.

**How it works:**
1. **Analyze** — Configure a region and criteria, then run the analysis
2. **Rankings** — View all properties ranked by investment potential
3. **Property Detail** — Deep dive into individual properties
4. **Settings** — Configure API keys, financing terms, and cost assumptions

Use the sidebar to navigate between pages.
""")

# Initialize session state
if "results" not in st.session_state:
    st.session_state.results = None
if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False
if "config" not in st.session_state:
    st.session_state.config = None
