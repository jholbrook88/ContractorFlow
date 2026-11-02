import logging
import os
import sqlite3
from uuid import uuid4

import pandas as pd
import streamlit as st

from analytics import (
    DATE_RANGES,
    calculate_kpis,
    category_counts,
    export_csv,
    filter_records,
    inquiry_volume,
    localize_records,
    parse_utc,
    pipeline_report,
)
from analytics import report_task_state as task_state
from charts import category_figure, volume_figure
from config import SERVICES
from database import (
    add_lead,
    complete_task,
    get_leads,
    get_tasks,
    initialize_database,
    update_lead_status,
)
from followups import utc_now
from intake import inquiry_fingerprint, validate_inquiry
from notifications import get_notifications, process_outbox, queue_reminders, retry_notification

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
try:
    initialize_database()
    queue_reminders()
except sqlite3.Error:
    logging.getLogger(__name__).error("Database initialization or reminder check failed")
    st.error(
        "Local storage is unavailable. Verify the database location and permissions, then retry."
    )
    st.stop()

st.set_page_config(page_title="ContractorFlow", page_icon=":material/handyman:", layout="wide")

st.sidebar.title("ContractorFlow")
st.sidebar.caption("Leads, follow-ups and reporting")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Customer Inquiries",
        "Lead Management",
        "Task Management",
        "Notification Center",
        "Settings",
    ],
)

if os.environ.get("CONTRACTORFLOW_DEMO") == "1":
    st.info(
        "Demo workspace · Fictional customer data. Changes affect only this demo database.",
        icon=":material/science:",
    )

leads = get_leads()

if page == "Dashboard":
    st.title("Business intelligence")
    st.caption("A clear view of your inquiries, pipeline and follow-up workload.")
    period = st.selectbox("Date range", list(DATE_RANGES), index=3)
    now = utc_now()
    all_tasks = get_tasks()
    report_leads = filter_records(leads, period, now)
    tasks = filter_records(all_tasks, period, now)
    kpis = calculate_kpis(report_leads, tasks, now)
    with st.expander("How to read this dashboard"):
        st.caption(
            "Dates use America/New_York. Last N days includes today through now and the preceding N−1 calendar days. "
            "Leads are filtered by submission date; tasks independently by task creation date. "
            "All time includes records with unknown dates. Counts show current statuses, not historical transitions."
        )
        st.caption(
            "Conversion = Won ÷ all filtered leads. New inquiries = leads currently New. "
            "Pending includes all unfinished tasks; overdue is a subset. Completed counts tasks created in the selected period, regardless of completion date."
        )

    for columns, metrics in [
        (
            st.columns(3),
            [
                ("Total Leads", kpis["total_leads"]),
                ("New Inquiries", kpis["new_inquiries"]),
                (
                    "Conversion rate",
                    f"{kpis['conversion_rate']:.1f}%"
                    if kpis["conversion_rate"] is not None
                    else "N/A",
                ),
            ],
        ),
        (
            st.columns(3),
            [
                ("Pending Follow-Ups", kpis["pending_tasks"]),
                ("Overdue Follow-Ups", kpis["overdue_tasks"]),
                ("Completed follow-ups", kpis["completed_followups"]),
            ],
        ),
    ]:
        for column, (label, value) in zip(columns, metrics):
            column.metric(label, value, border=True)
    completion_rate = kpis["completed_followups"] / len(tasks) * 100 if tasks else None
    st.caption(
        f"Follow-up completion rate: {completion_rate:.1f}% of tasks created in this period."
        if completion_rate is not None
        else "Follow-up completion rate: N/A — no tasks in this period."
    )
    st.caption(
        "Current pipeline · Won ÷ total leads · Pending includes overdue tasks · New York calendar dates"
    )
    missing_lead_dates = sum(parse_utc(lead.get("created_at")) is None for lead in leads)
    missing_task_dates = sum(parse_utc(task.get("created_at")) is None for task in all_tasks)
    if missing_lead_dates or missing_task_dates:
        st.warning(
            f"Unknown creation dates: {missing_lead_dates} leads, {missing_task_dates} tasks. "
            "These records appear only in All time and are excluded from the inquiry timeline."
        )
    if any(task_state(task, now) == "Unknown deadline" for task in tasks):
        st.warning(
            "Some unfinished tasks have unknown deadlines. They count as pending but cannot be classified as overdue."
        )

    with st.container(border=True):
        st.subheader("Inquiry volume over time")
        volume = inquiry_volume(report_leads, period, now)
        if volume:
            fig = volume_figure(volume)
            st.plotly_chart(fig, key="inquiry_volume", alt="Inquiries per New York calendar period")
            st.caption(
                "Zero periods are included between dates. Spans longer than a year use monthly counts."
            )
        else:
            st.info("No valid inquiry dates are available for a timeline.")

    st.subheader("Inquiry breakdown")
    if not report_leads:
        st.info(
            "No inquiries in this date range. Choose All time or submit a customer inquiry to begin."
        )
    else:
        if len(report_leads) < 2:
            st.info(
                "Only one inquiry is available. Counts are shown, but there is not enough data to establish a trend."
            )
        left, right = st.columns(2)
        for container, field, title, order in [
            (left, "service", "Leads by service", ()),
            (right, "urgency", "Leads by urgency", ("Low", "Normal", "High", "Emergency")),
        ]:
            with container:
                with st.container(border=True):
                    st.subheader(title)
                    fig = category_figure(category_counts(report_leads, field, order), field)
                    st.plotly_chart(fig, key=f"leads_{field}", alt=title)

    with st.container(border=True):
        st.subheader("Lead pipeline · current status")
        pipeline = pd.DataFrame(pipeline_report(report_leads))
        if report_leads:
            fig = category_figure(pipeline_report(report_leads), "status")
            st.plotly_chart(fig, key="pipeline", alt="Lead counts by current pipeline status")
        st.dataframe(
            pipeline.rename(columns={"Category": "Status"}), hide_index=True, alt="Pipeline counts"
        )
        st.caption(
            "Stages are independent current counts, not a cumulative funnel or stage-to-stage conversion."
        )

    st.divider()
    st.subheader("Follow-up work queue")
    open_tasks = [
        dict(task, state=task_state(task, now)) for task in tasks if not task.get("completed_at")
    ]
    if open_tasks:
        st.dataframe(
            pd.DataFrame(localize_records(open_tasks))[
                ["id", "lead_id", "name", "service", "urgency", "due_at", "state"]
            ],
            hide_index=True,
            alt="Unfinished follow-up tasks",
        )
    else:
        st.info("No pending follow-ups in this date range.")
    st.divider()
    st.subheader("Customer inquiries")
    if report_leads:
        st.dataframe(
            pd.DataFrame(localize_records(report_leads))[
                ["id", "name", "service", "urgency", "status", "created_at"]
            ],
            hide_index=True,
            alt="Customer inquiries in the selected period",
        )
    st.caption(
        "All displayed timestamps use America/New_York with UTC offsets. Refresh to update task states."
    )

    st.divider()
    st.subheader("Reports")
    left, right = st.columns(2)
    left.download_button(
        "Export leads CSV",
        export_csv(report_leads, "leads", now),
        file_name="contractorflow-leads.csv",
        mime="text/csv",
    )
    right.download_button(
        "Export tasks CSV",
        export_csv(tasks, "tasks", now),
        file_name="contractorflow-tasks.csv",
        mime="text/csv",
    )
    st.caption(
        "Exports match the selected date range and include New York UTC offsets. Spreadsheet formula-like text is escaped."
    )


elif page == "Customer Inquiries":
    st.title("Customer Inquiries")
    st.write("Submit a new service request using the form below.")

    with st.form("customer_inquiry_form", clear_on_submit=False):
        name = st.text_input("Customer Name")
        email = st.text_input("Email Address")
        phone = st.text_input("Phone Number")

        service = st.selectbox("Requested Service", SERVICES)

        description = st.text_area("Project Description")

        urgency = st.selectbox("Project Urgency", ["Low", "Normal", "High", "Emergency"])

        submitted = st.form_submit_button("Submit Inquiry")

    st.caption(
        "Follow-up deadlines: Emergency 1 hour, High 4 hours, Normal 24 hours, Low 72 hours. Elapsed time, including weekends."
    )

    if submitted:
        try:
            values = validate_inquiry(name, email, phone, service, description, urgency)
            fingerprint = inquiry_fingerprint(values)
            if st.session_state.get("inquiry_fingerprint") != fingerprint:
                st.session_state["inquiry_fingerprint"] = fingerprint
                st.session_state["inquiry_key"] = uuid4().hex
            lead_id = add_lead(*values, submission_key=st.session_state["inquiry_key"])
        except ValueError as exc:
            st.error(str(exc))
        except sqlite3.Error:
            logging.getLogger(__name__).error("Inquiry transaction failed", exc_info=False)
            st.error(
                "The inquiry could not be saved. Please try again; no partial inquiry was saved."
            )
        else:
            st.success(
                f"Inquiry #{lead_id} saved. A follow-up and two local notifications are available."
            )
            st.caption(
                "Submitting this unchanged form again will return the same inquiry. Edit the request to submit a different inquiry."
            )


elif page == "Lead Management":
    st.title("Lead Management")
    st.write("View and manage customer inquiries.")
    if "lead_notice" in st.session_state:
        st.success(st.session_state.pop("lead_notice"))
    st.caption("Timestamps use America/New_York with UTC offsets.")

    search = st.text_input(
        "Search leads", placeholder="Name, email, phone or service", key="lead_search"
    )
    selected_statuses = st.multiselect("Lead status", ["New", "Contacted", "Quoted", "Won", "Lost"])
    sort_order = st.selectbox(
        "Sort leads", ["Newest first", "Oldest first", "Customer name"], key="lead_sort"
    )
    filtered_leads = [
        lead
        for lead in leads
        if (not selected_statuses or lead["status"] in selected_statuses)
        and (
            not search.strip()
            or search.casefold().strip()
            in " ".join(
                str(lead.get(field) or "") for field in ("name", "email", "phone", "service")
            ).casefold()
        )
    ]
    if sort_order == "Oldest first":
        filtered_leads.reverse()
    elif sort_order == "Customer name":
        filtered_leads.sort(key=lambda lead: lead["name"].casefold())
    if filtered_leads:
        df = pd.DataFrame(localize_records(filtered_leads))

        st.dataframe(
            df[
                [
                    "id",
                    "name",
                    "email",
                    "phone",
                    "service",
                    "description",
                    "urgency",
                    "status",
                    "created_at",
                ]
            ],
            hide_index=True,
            width="stretch",
            alt="Customer inquiries",
        )

        st.success(f"Currently tracking {len(leads)} customer leads.")

        st.divider()
        st.subheader("Update Lead Status")

        lead_options = {f"#{lead['id']} - {lead['name']}": lead["id"] for lead in filtered_leads}

        selected_lead = st.selectbox("Select a lead", list(lead_options.keys()))

        new_status = st.selectbox("New Status", ["New", "Contacted", "Quoted", "Won", "Lost"])

        if st.button("Update Status"):
            try:
                updated = update_lead_status(lead_options[selected_lead], new_status)
            except sqlite3.Error:
                logging.getLogger(__name__).error("Lead status update failed")
                st.error("The status could not be saved. Please retry.")
            else:
                if updated:
                    st.session_state["lead_notice"] = "Lead status updated."
                    st.rerun()
                else:
                    st.warning("This lead is no longer available. Refresh the view.")

    else:
        st.info("No leads match this view. Clear the filters or submit an inquiry.")


elif page == "Task Management":
    st.title("Task management")
    st.caption(
        "Deadlines and completion times use America/New_York with UTC offsets. Completing a task does not change its lead status."
    )
    task_filter = st.selectbox("Show tasks", ["Open", "Overdue", "Completed", "All"])
    now = utc_now()
    tasks = [dict(task, state=task_state(task, now)) for task in get_tasks()]
    visible = [
        task
        for task in tasks
        if task_filter == "All"
        or (task_filter == "Open" and task["state"] != "Completed")
        or task["state"] == task_filter
    ]
    if visible:
        st.dataframe(
            pd.DataFrame(localize_records(visible))[
                [
                    "id",
                    "lead_id",
                    "name",
                    "email",
                    "phone",
                    "service",
                    "urgency",
                    "due_at",
                    "state",
                    "completed_at",
                ]
            ],
            hide_index=True,
            width="stretch",
            alt="Follow-up tasks with customer contact details",
        )
        options = {
            f"#{task['id']} — {task['name']}": task["id"]
            for task in visible
            if not task["completed_at"]
        }
        if options:
            selected = st.selectbox("Select a follow-up", list(options))
            if st.button("Complete follow-up"):
                try:
                    complete_task(options[selected])
                except sqlite3.Error:
                    logging.getLogger(__name__).error("Task completion failed")
                    st.error("The task could not be completed. Please retry.")
                else:
                    st.session_state["task_notice"] = "Follow-up completed."
                    st.rerun()
    else:
        st.info("No tasks match this view.")
    if "task_notice" in st.session_state:
        st.success(st.session_state.pop("task_notice"))

elif page == "Notification Center":
    st.title("Notification center")
    st.info(
        "Local preview only. No email is sent. Previewed means processed locally; Sent is reserved for a future approved provider."
    )
    if "notification_notice" in st.session_state:
        st.success(st.session_state.pop("notification_notice"))
    left, right = st.columns(2)
    if left.button("Check reminders"):
        count = queue_reminders()
        st.session_state["notification_notice"] = (
            f"Reminder check complete: {count} new notifications."
        )
        st.rerun()
    if right.button("Process local previews"):
        try:
            outcome = process_outbox()
        except sqlite3.Error:
            st.error("Notification storage is temporarily unavailable. Please retry.")
        except ValueError:
            st.error(
                "Only local preview delivery is supported. Set CONTRACTORFLOW_DELIVERY_MODE to local."
            )
        else:
            st.session_state["notification_notice"] = (
                f"Local processing: {outcome['previewed']} previewed, {outcome['failed']} failed, {outcome['cancelled']} cancelled. No messages sent."
            )
            st.rerun()
    status_filter = st.selectbox(
        "Notification status", ["All", "Pending", "Previewed", "Failed", "Cancelled", "Sent"]
    )
    history = get_notifications()
    visible = [
        message
        for message in history
        if status_filter == "All" or message["status"] == status_filter
    ]
    if visible:
        st.dataframe(
            pd.DataFrame(localize_records(visible))[
                [
                    "id",
                    "kind",
                    "lead_id",
                    "recipient",
                    "subject",
                    "status",
                    "created_at",
                    "processed_at",
                    "attempts",
                    "last_error",
                ]
            ],
            hide_index=True,
            alt="Local notification history",
        )
        options = {f"#{message['id']} - {message['subject']}": message for message in visible}
        selected = st.selectbox("Preview notification", list(options))
        message = options[selected]
        st.caption(
            f"To: {message['recipient']} · Mode: {message['delivery_mode']} · Status: {message['status']}"
        )
        st.text(message["subject"])
        st.text(message["body"])
        if message["last_error"]:
            st.warning(message["last_error"])
        if message["status"] == "Failed" and st.button("Retry local preview"):
            retry_notification(message["id"])
            st.rerun()
    else:
        st.info(
            "No notifications match this view. New inquiries automatically create confirmation and owner messages."
        )

elif page == "Settings":
    st.title("Settings")
    st.write("ContractorFlow Application Settings")

    st.info("Local SQLite storage and preview-only notifications. External delivery is disabled.")

    st.subheader("System Information")
    st.write("Application: ContractorFlow")
    st.write("Database: SQLite")
    st.write("Framework: Streamlit")
    st.write("Version: 0.5.0")
