"""Shared read-only dashboard presentation for local and public demo applications."""

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
    st.title("Business intelligence")
    st.caption("A clear view of your inquiries, pipeline and follow-up workload.")
    period = st.selectbox("Date range", list(DATE_RANGES), index=3)
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
