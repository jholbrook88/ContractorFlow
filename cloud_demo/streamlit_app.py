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
st.sidebar.caption("A small CRM for contractors")
st.caption(":material/science: Demo workspace · Fictional customer information · Read-only")


@st.cache_data(ttl=3600, max_entries=1, show_spinner=False)
def snapshot():
    return build_snapshot()


with st.spinner("Preparing the fictional workspace..."):
    data = snapshot()
leads, tasks, messages, reference = data["leads"], data["tasks"], data["messages"], data["as_of"]
page = st.sidebar.radio(
    "Workspace",
    [
        "Overview",
        "Customers & requests",
        "Follow-ups",
        "Messages",
        "Intake example",
        "About this demo",
    ],
)
st.sidebar.markdown("[View source on GitHub](https://github.com/jholbrook88/ContractorFlow)")

if page == "Overview":
    render_dashboard(leads, tasks, reference)
elif page == "Customers & requests":
    st.title("Customers & requests")
    st.caption("Find a customer, check their request, and see where it stands.")
    search_col, status_col = st.columns([2, 1])
    with search_col:
        search = st.text_input("Search customers", placeholder="Customer name or service")
    with status_col:
        statuses = st.multiselect("Request status", ["New", "Contacted", "Quoted", "Won", "Lost"])
    visible = [
        lead
        for lead in leads
        if (not statuses or lead["status"] in statuses)
        and search.strip().casefold() in f"{lead['name']} {lead['service']}".casefold()
    ]
    st.caption(f"{len(visible)} of {len(leads)} requests")
    if visible:
        st.dataframe(
            pd.DataFrame(localize_records(visible)),
            column_order=["id", "name", "service", "status", "urgency", "created_at"],
            column_config={
                "id": "Request #",
                "name": "Customer",
                "service": "Service",
                "status": "Status",
                "urgency": "Priority",
                "created_at": "Received (New York)",
            },
            hide_index=True,
            alt="Fictional customer inquiries matching your filters",
        )
        selected = st.selectbox(
            "Open a request",
            visible,
            format_func=lambda lead: f"#{lead['id']} · {lead['name']} · {lead['service']}",
        )
        with st.container(border=True):
            st.subheader(f"{selected['service']} request")
            st.write(selected["description"])
            st.caption(f"Priority: {selected['urgency']} · Status: {selected['status']}")
            st.write(f"**Email:** {selected['email']}  \n**Phone:** {selected['phone']}")
            st.button("Update status", disabled=True, help="Editing is available in the local app.")
    else:
        st.info("No inquiries match. Clear your search or choose another status.")
elif page == "Follow-ups":
    st.title("Follow-ups")
    st.caption("See who needs a response and when to follow up.")
    state = st.selectbox("Show follow-ups", ["Open", "Overdue", "Completed", "All"])
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
            column_order=["name", "service", "state", "due_at", "completed_at"],
            column_config={
                "name": "Customer",
                "service": "Service",
                "state": "Status",
                "due_at": "Follow up by (New York)",
                "completed_at": "Completed (New York)",
            },
            hide_index=True,
            alt="Fictional follow-up deadlines and completion outcomes",
        )
    else:
        st.info("No follow-ups match this view.")
    st.button("Mark as complete", disabled=True, help="Editing is available in the local app.")
    with st.expander("How follow-up dates work"):
        st.write(
            "Follow-up deadlines depend on priority: Emergency 1 hour, High 4 hours, "
            "Normal 24 hours, and Low 72 hours. Open includes overdue items. "
            "Completing a follow-up does not change the request's status."
        )
elif page == "Messages":
    st.title("Messages")
    st.caption("Sample confirmations, owner alerts, and follow-up reminders. Nothing is sent.")
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
            "Open a message",
            visible,
            format_func=lambda message: f"#{message['id']} · {message['subject']}",
        )
        with st.container(border=True):
            st.subheader(message["subject"])
            st.caption(f"To: {message['recipient']} · Preview only")
            st.text(message["body"])
    else:
        st.info("No message previews match this filter.")
elif page == "Intake example":
    st.title("Intake example")
    st.write(
        "A customer sends a request. Their details stay together, a follow-up is scheduled, "
        "and confirmation and owner-alert messages are prepared."
    )
    example = leads[0]
    st.dataframe(
        pd.DataFrame([example])[["name", "email", "phone", "service", "description", "urgency"]],
        column_config={
            "name": "Customer",
            "email": "Email",
            "phone": "Phone",
            "service": "Service",
            "description": "Request details",
            "urgency": "Priority",
        },
        hide_index=True,
        alt="Example fictional customer intake",
    )
    st.button("Submit request", disabled=True, help="This page shows a saved sample request.")
    st.caption("This is a saved example. New requests can be submitted in the local app.")
else:
    st.title("About this demo")
    st.write(
        "ContractorFlow is a small CRM for contractors: keep customer requests together, "
        "track their status, and follow up without losing the details."
    )
    st.markdown("""**Try this short tour:**

1. Start with Overview to see requests and follow-ups.
2. Open Customers & requests to find a customer and read their request.
3. Check Follow-ups and Messages to see the next steps and sample replies.
4. Use the date filter and download CSV reports from Overview.
""")
    st.write(
        "All 150 customers are fictional. You can search, filter, and download reports. "
        "Editing and new submissions are available in the local application. No messages "
        "are sent from this demo."
    )
    with st.expander("Sample data & technical details"):
        st.caption(f"Sample data updated: {local_timestamp(reference)} (New York time).")
        st.write(
            "The sample is generated in memory and refreshed after up to one hour. Reports "
            "use the sample's fixed time so deadlines stay consistent while you explore. "
            "No operational database is opened. Filters affect only your view."
        )
        st.caption(
            "Dates are stored as UTC and displayed in America/New_York. Pipeline counts "
            "show current statuses, not historical conversions. No revenue is inferred."
        )
    st.markdown(
        "[Source code and local installation instructions](https://github.com/jholbrook88/ContractorFlow)"
    )
