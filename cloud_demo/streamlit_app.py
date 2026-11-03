"""Public portfolio entry point; generated fictional data and read-only exploration."""

import sys
from pathlib import Path

# Community Cloud runs from the repository root; support direct local entry-point runs too.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from analytics import local_timestamp, localize_records, report_task_state
from dashboard import render_dashboard
from public_demo import build_snapshot

st.set_page_config(
    page_title="ContractorFlow | Portfolio demo", page_icon=":material/handyman:", layout="wide"
)
st.sidebar.title("ContractorFlow")
st.sidebar.caption("Business automation for small contractors")
st.info(
    "Demo Mode · All 150 customers and their contact details are fictional. This demonstration is read-only. No messages are sent.",
    icon=":material/science:",
)


@st.cache_data(ttl=3600, max_entries=1, show_spinner=False)
def snapshot():
    return build_snapshot()


with st.spinner("Preparing the fictional workspace..."):
    data = snapshot()
leads, tasks, messages, reference = data["leads"], data["tasks"], data["messages"], data["as_of"]
st.sidebar.caption(
    f"Snapshot: {local_timestamp(reference)} (America/New_York). Reports use this same time so deadlines and counts stay consistent while you explore."
)
page = st.sidebar.radio(
    "Explore the demo",
    [
        "Dashboard",
        "Lead management",
        "Follow-up tasks",
        "Notification previews",
        "Customer intake",
        "About this demo",
    ],
)
st.sidebar.markdown("[View source on GitHub](https://github.com/jholbrook88/ContractorFlow)")
st.sidebar.caption(
    "Filters affect only your view. Changes and customer submissions are unavailable in the public demo."
)

if page == "Dashboard":
    render_dashboard(leads, tasks, reference)
elif page == "Lead management":
    st.title("Lead management")
    st.caption(
        "Explore fictional inquiries across New, Contacted, Quoted, Won and Lost. Status editing is available in the local application."
    )
    search = st.text_input("Search fictional leads", placeholder="Customer name or service")
    statuses = st.multiselect("Lead status", ["New", "Contacted", "Quoted", "Won", "Lost"])
    visible = [
        lead
        for lead in leads
        if (not statuses or lead["status"] in statuses)
        and search.strip().casefold() in f"{lead['name']} {lead['service']}".casefold()
    ]
    st.caption(f"{len(visible)} of 150 fictional inquiries")
    if visible:
        st.dataframe(
            pd.DataFrame(localize_records(visible)),
            hide_index=True,
            alt="Fictional customer inquiries matching your filters",
        )
        selected = st.selectbox(
            "Inspect an inquiry",
            visible,
            format_func=lambda lead: f"#{lead['id']} · {lead['name']} · {lead['service']}",
        )
        with st.container(border=True):
            st.subheader(f"{selected['service']} request")
            st.write(selected["description"])
            st.caption(f"Urgency: {selected['urgency']} | Current status: {selected['status']}")
            st.button("Status editing is unavailable in this demo", disabled=True)
    else:
        st.info("No inquiries match. Clear your search or choose another status.")
elif page == "Follow-up tasks":
    st.title("Follow-up tasks")
    st.caption(
        "Deadlines follow the same urgency rules as the local application: Emergency 1 hour, High 4 hours, Normal 24 hours, Low 72 hours. Completion does not change a lead status."
    )
    state = st.selectbox("Show tasks", ["Open", "Overdue", "Completed", "All"])
    visible = [dict(task, state=report_task_state(task, reference)) for task in tasks]
    visible = [
        task
        for task in visible
        if state == "All"
        or (state == "Open" and task["state"] != "Completed")
        or task["state"] == state
    ]
    if visible:
        st.dataframe(
            pd.DataFrame(localize_records(visible)),
            hide_index=True,
            alt="Fictional follow-up deadlines and completion outcomes",
        )
    else:
        st.info("No follow-ups match this view.")
    st.button("Task completion is unavailable in this demo", disabled=True)
elif page == "Notification previews":
    st.title("Notification previews")
    st.info(
        "Fictional message history only. Previewed means a local preview, never an email or text delivery. There is no delivery provider in this demo."
    )
    kinds = st.multiselect(
        "Message type",
        ["Customer confirmation", "Owner inquiry", "Upcoming reminder", "Overdue reminder"],
    )
    visible = [message for message in messages if not kinds or message["kind"] in kinds]
    if visible:
        st.dataframe(
            pd.DataFrame(localize_records(visible))[
                ["id", "kind", "lead_id", "recipient", "subject", "status", "created_at"]
            ],
            hide_index=True,
            alt="Fictional message history; no messages were sent",
        )
        message = st.selectbox(
            "Read a preview",
            visible,
            format_func=lambda message: f"#{message['id']} · {message['subject']}",
        )
        with st.container(border=True):
            st.subheader(message["subject"])
            st.caption(f"Fictional recipient: {message['recipient']}")
            st.text(message["body"])
    else:
        st.info("No message previews match this filter.")
elif page == "Customer intake":
    st.title("Customer intake")
    st.write(
        "In the local application, submitting an inquiry creates a lead, an urgency-based follow-up and two local message snapshots in one transaction."
    )
    st.info(
        "Submissions are disabled here. Please do not enter real customer details. This page shows an existing fictional inquiry instead."
    )
    example = leads[0]
    st.dataframe(
        pd.DataFrame([example])[["name", "email", "phone", "service", "description", "urgency"]],
        hide_index=True,
        alt="Example fictional customer intake",
    )
    st.button("Customer submissions are unavailable in this demo", disabled=True)
else:
    st.title("About this demo")
    st.write(
        "ContractorFlow combines customer intake, a sales pipeline, follow-up scheduling, business intelligence and local notification previews for small contractors."
    )
    st.markdown("""**Try this short tour:**

1. Change the dashboard date range and inspect the service and pipeline charts.
2. Search lead records and compare pending, overdue and completed follow-ups.
3. Read a customer confirmation, owner alert or reminder preview.
4. Download a fictional CSV report from the dashboard.
""")
    st.caption(
        "All timestamps are stored as UTC and displayed in America/New_York. No revenue is inferred. Pipeline stages show current counts, not historical conversions between stages."
    )
    st.write(
        "The public demo generates its 150 customers in a disposable in-memory SQLite database. It does not open operational databases, accept customer submissions, change records, or send communications. The generated snapshot is cached for up to one hour; the next visit or rerun after expiry creates a fresh snapshot. No visitor reset is necessary."
    )
    st.markdown(
        "[Source code and local installation instructions](https://github.com/jholbrook88/ContractorFlow)"
    )
