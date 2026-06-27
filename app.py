"""
Streamlit UI for the IT Helpdesk Ticket Triage Bot.

Run:  streamlit run app.py
Works in mock mode out of the box; pick a provider in the sidebar to use a live LLM.
"""

import streamlit as st
from triage import classify_ticket

st.set_page_config(page_title="IT Helpdesk Triage Bot", page_icon="🎫", layout="centered")

st.title("🎫 IT Helpdesk Ticket Triage Bot")
st.caption("Paste a support ticket and get an instant category, priority, routing, and draft reply.")

provider = st.sidebar.selectbox("LLM provider", ["mock", "anthropic", "openai"], index=0)
st.sidebar.markdown(
    "**mock** needs no API key.\n\n"
    "**anthropic / openai** read the key from your environment or `.env`."
)

example = "Outlook won't open on my laptop. It hangs on 'loading profile'. I can see email on my phone."
ticket = st.text_area("Ticket text", value=example, height=140)

if st.button("Triage ticket", type="primary"):
    with st.spinner("Analyzing..."):
        result = classify_ticket(ticket, provider)
    c1, c2, c3 = st.columns(3)
    c1.metric("Category", result.get("category"))
    c2.metric("Priority", result.get("priority"))
    c3.metric("Confidence", f"{float(result.get('confidence', 0)):.0%}")
    st.markdown(f"**Suggested team:** {result.get('suggested_team')}")
    st.markdown(f"**Summary:** {result.get('summary')}")
    st.markdown("**Draft response**")
    st.info(result.get("draft_response", ""))
    with st.expander("Raw JSON"):
        st.json(result)
