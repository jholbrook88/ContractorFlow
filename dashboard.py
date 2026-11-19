"""Shared read-only CRM overview for local and public demo applications."""

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


def render_dashboard(leads, all_tasks, now):
    heading, filters = st.columns([3, 1], vertical_alignment="bottom")
    with heading:
        st.title("Business overview")
        st.caption("Customer requests, follow-ups, and where things stand.")
    with filters:
        period = st.selectbox("Date range", list(DATE_RANGES), index=3)
    report_leads = filter_records(leads, period, now)
    tasks = filter_records(all_tasks, period, now)
    kpis = calculate_kpis(report_leads, tasks, now)

    with st.container(horizontal=True):
        for label, value in [
            ("Total requests", kpis["total_leads"]),
            ("New requests", kpis["new_inquiries"]),
            ("Open follow-ups", kpis["pending_tasks"]),
            ("Overdue follow-ups", kpis["overdue_tasks"]),
        ]:
            st.metric(label, value, border=True)

    missing_lead_dates = sum(parse_utc(lead.get("created_at")) is None for lead in leads)
    missing_task_dates = sum(parse_utc(task.get("created_at")) is None for task in all_tasks)
    if missing_lead_dates or missing_task_dates:
        st.warning(
            f"Missing dates: {missing_lead_dates} requests, {missing_task_dates} follow-ups. "
            "These appear only in All time and are left out of the activity chart."
        )
    if any(task_state(task, now) == "Unknown deadline" for task in tasks):
        st.warning("Some open follow-ups have no valid deadline. Check their dates before acting.")

    followups, pipeline = st.columns([1.5, 1])
    with followups:
        with st.container(border=True, height="stretch"):
            st.subheader("Follow-ups to handle")
            st.caption("Overdue items first. Open includes overdue follow-ups.")
            open_tasks = [
                dict(task, state=task_state(task, now))
                for task in tasks
                if not task.get("completed_at")
            ]
            open_tasks.sort(
                key=lambda task: (
                    task["state"] != "Overdue",
                    parse_utc(task.get("due_at")) is None,
                    parse_utc(task.get("due_at")) or now,
                )
            )
            if open_tasks:
                st.dataframe(
                    pd.DataFrame(localize_records(open_tasks)),
                    column_order=["name", "service", "state", "due_at"],
                    column_config={
                        "name": "Customer",
                        "service": "Service",
                        "state": "Status",
                        "due_at": "Follow up by (New York)",
                    },
                    hide_index=True,
                    height=270,
                    alt="Open follow-ups, with overdue items first",
                )
            else:
                st.info("No open follow-ups in this date range.")
            completion = kpis["completed_followups"] / len(tasks) * 100 if tasks else None
            st.caption(
                f"{kpis['completed_followups']} completed · {completion:.1f}% of follow-ups "
                "created in this date range."
                if completion is not None
                else "No follow-ups were created in this date range."
            )

    with pipeline:
        with st.container(border=True, height="stretch"):
            st.subheader("Request pipeline")
            st.caption("Current status of requests in this date range.")
            st.metric(
                "Requests won",
                f"{kpis['conversion_rate']:.1f}%" if kpis["conversion_rate"] is not None else "N/A",
                help="Requests marked Won divided by all requests in the selected date range.",
            )
            st.dataframe(
                pd.DataFrame(pipeline_report(report_leads)),
                column_config={"Category": "Status", "Leads": "Requests"},
                hide_index=True,
                height=216,
                alt="Request counts by current status",
            )

    requests, activity = st.tabs(["Customer requests", "Activity & charts"])
    with requests:
        st.subheader("Customer requests")
        if report_leads:
            st.dataframe(
                pd.DataFrame(localize_records(report_leads)),
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
                height=320,
                alt="Customer requests in the selected date range",
            )
        else:
            st.info("No requests in this date range. Choose a different date range to see more.")

    with activity:
        with st.container(border=True):
            st.subheader("Requests over time")
            volume = inquiry_volume(report_leads, period, now)
            if volume:
                st.plotly_chart(
                    volume_figure(volume),
                    key="inquiry_volume",
                    alt="Customer requests per New York calendar period",
                )
            else:
                st.info("No dated requests are available for this chart.")

        if report_leads:
            left, right = st.columns(2)
            for container, field, title, order in [
                (left, "service", "Requests by service", ()),
                (right, "urgency", "Requests by priority", ("Low", "Normal", "High", "Emergency")),
            ]:
                with container:
                    with st.container(border=True):
                        st.subheader(title)
                        st.plotly_chart(
                            category_figure(category_counts(report_leads, field, order), field),
                            key=f"leads_{field}",
                            alt=title,
                        )
            with st.container(border=True):
                st.subheader("Requests by status")
                st.plotly_chart(
                    category_figure(pipeline_report(report_leads), "status"),
                    key="pipeline",
                    alt="Request counts by current status",
                )

    st.subheader("Download reports")
    with st.container(horizontal=True):
        st.download_button(
            "Download requests CSV",
            export_csv(report_leads, "leads", now),
            file_name="contractorflow-leads.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        st.download_button(
            "Download follow-ups CSV",
            export_csv(tasks, "tasks", now),
            file_name="contractorflow-tasks.csv",
            mime="text/csv",
            icon=":material/download:",
        )
    st.caption("Both reports use the selected date range. Times are shown in New York time.")

    with st.expander("How these numbers are counted"):
        st.write(
            "Requests are filtered by the date they arrived; follow-ups are filtered separately "
            "by the date they were created. Open follow-ups include overdue items. New requests "
            "are those currently marked New. Requests won means Won divided by all requests."
        )
        st.caption(
            "Date filters use America/New_York. Last N days includes today and the previous N−1 "
            "calendar days. All time includes missing dates, which are left out of the timeline. "
            "Statuses show where requests stand now, not a history of changes. The completion "
            "rate uses follow-ups created in the selected period, regardless of completion date. "
            "Reports include UTC offsets and escape spreadsheet formula-like text."
        )
