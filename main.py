
import streamlit as st
import pandas as pd
import os
from charts import category_figure, volume_figure
from database import (initialize_database, add_lead, get_leads, update_lead_status,
                      get_tasks, complete_task)
from followups import utc_now
from analytics import (DATE_RANGES, filter_records, calculate_kpis, category_counts,
                       pipeline_report, inquiry_volume, export_csv, localize_records,
                       parse_utc, report_task_state as task_state)

# Initialize the CRM database
initialize_database()

# Configure the application
st.set_page_config(
    page_title="ContractorFlow",
    page_icon=":material/handyman:",
    layout="wide"
)

# Sidebar navigation
st.sidebar.title("ContractorFlow")
st.sidebar.caption("Small Business Automation Platform")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Customer Inquiries", "Lead Management", "Task Management", "Settings"]
)

if os.environ.get("CONTRACTORFLOW_DEMO") == "1":
    st.info("Demo workspace · Fictional customer data. Changes affect only this demo database.", icon=":material/science:")

# Retrieve customer leads
leads = get_leads()

# DASHBOARD
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
        st.caption("Dates use America/New_York. Last N days includes today through now and the preceding N−1 calendar days. "
               "Leads are filtered by submission date; tasks independently by task creation date. "
               "All time includes records with unknown dates. Counts show current statuses, not historical transitions.")
        st.caption("Conversion = Won ÷ all filtered leads. New inquiries = leads currently New. "
                   "Pending includes all unfinished tasks; overdue is a subset. Completed counts tasks created in the selected period, regardless of completion date.")

    for columns, metrics in [
        (st.columns(3), [("Total Leads", kpis["total_leads"]),
                         ("New Inquiries", kpis["new_inquiries"]),
                         ("Conversion rate", f"{kpis['conversion_rate']:.1f}%" if kpis["conversion_rate"] is not None else "N/A")]),
        (st.columns(3), [("Pending Follow-Ups", kpis["pending_tasks"]),
                         ("Overdue Follow-Ups", kpis["overdue_tasks"]),
                         ("Completed follow-ups", kpis["completed_followups"])])]:
        for column, (label, value) in zip(columns, metrics):
            column.metric(label, value, border=True)
    st.caption("Current pipeline · Won ÷ total leads · Pending includes overdue tasks · New York calendar dates")
    missing_lead_dates = sum(parse_utc(lead.get("created_at")) is None for lead in leads)
    missing_task_dates = sum(parse_utc(task.get("created_at")) is None for task in all_tasks)
    if missing_lead_dates or missing_task_dates:
        st.warning(f"Unknown creation dates: {missing_lead_dates} leads, {missing_task_dates} tasks. "
                   "These records appear only in All time and are excluded from the inquiry timeline.")
    if any(task_state(task, now) == "Unknown deadline" for task in tasks):
        st.warning("Some unfinished tasks have unknown deadlines. They count as pending but cannot be classified as overdue.")

    with st.container(border=True):
        st.subheader("Inquiry volume over time")
        volume = inquiry_volume(report_leads, period, now)
        if volume:
            fig = volume_figure(volume)
            st.plotly_chart(fig, key="inquiry_volume", alt="Inquiries per New York calendar period")
            st.caption("Zero periods are included between dates. Spans longer than a year use monthly counts.")
        else:
            st.info("No valid inquiry dates are available for a timeline.")


    st.subheader("Inquiry breakdown")
    if not report_leads:
        st.info("No inquiries in this date range. Choose All time or submit a customer inquiry to begin.")
    else:
        if len(report_leads) < 2:
            st.info("Only one inquiry is available. Counts are shown, but there is not enough data to establish a trend.")
        left, right = st.columns(2)
        for container, field, title, order in [
            (left, "service", "Leads by service", ()),
            (right, "urgency", "Leads by urgency", ("Low", "Normal", "High", "Emergency"))]:
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
        st.dataframe(pipeline.rename(columns={"Category": "Status"}), hide_index=True, alt="Pipeline counts")
        st.caption("Stages are independent current counts, not a cumulative funnel or stage-to-stage conversion.")

    st.divider()
    st.subheader("Follow-up work queue")
    open_tasks = [dict(task, state=task_state(task, now)) for task in tasks if not task.get("completed_at")]
    if open_tasks:
        st.dataframe(pd.DataFrame(localize_records(open_tasks))[
            ["id", "lead_id", "name", "service", "urgency", "due_at", "state"]],
            hide_index=True, alt="Unfinished follow-up tasks")
    else:
        st.info("No pending follow-ups in this date range.")
    st.divider()
    st.subheader("Customer inquiries")
    if report_leads:
        st.dataframe(pd.DataFrame(localize_records(report_leads))[
            ["id", "name", "service", "urgency", "status", "created_at"]],
            hide_index=True, alt="Customer inquiries in the selected period")
    st.caption("All displayed timestamps use America/New_York with UTC offsets. Refresh to update task states.")

    st.divider()
    st.subheader("Reports")
    left, right = st.columns(2)
    left.download_button("Export leads CSV", export_csv(report_leads, "leads", now),
                         file_name="contractorflow-leads.csv", mime="text/csv")
    right.download_button("Export tasks CSV", export_csv(tasks, "tasks", now),
                          file_name="contractorflow-tasks.csv", mime="text/csv")
    st.caption("Exports match the selected date range and include New York UTC offsets. Spreadsheet formula-like text is escaped.")


# CUSTOMER INQUIRIES
elif page == "Customer Inquiries":
    st.title("Customer Inquiries")
    st.write("Submit a new service request using the form below.")

    with st.form("customer_inquiry_form", clear_on_submit=False):
        name = st.text_input("Customer Name")
        email = st.text_input("Email Address")
        phone = st.text_input("Phone Number")

        service = st.selectbox(
            "Requested Service",
            [
                "Plumbing",
                "Electrical",
                "HVAC",
                "Landscaping",
                "Roofing",
                "General Contracting",
                "Other"
            ]
        )

        description = st.text_area("Project Description")

        urgency = st.selectbox(
            "Project Urgency",
            ["Low", "Normal", "High", "Emergency"]
        )

        submitted = st.form_submit_button("Submit Inquiry")

    st.caption("Follow-up deadlines: Emergency 1 hour, High 4 hours, Normal 24 hours, Low 72 hours. Elapsed time, including weekends.")

    if submitted:
        if not name.strip() or not email.strip():
            st.error("Please enter a customer name and email address.")
        else:
            lead_id = add_lead(
                name.strip(),
                email.strip(),
                phone.strip(),
                service,
                description.strip(),
                urgency
            )

            st.success(
                f"Inquiry #{lead_id} submitted successfully for {name}! A follow-up task was created."
            )

            st.info(
                f"Service: {service} | Priority: {urgency}"
            )


# LEAD MANAGEMENT
elif page == "Lead Management":
    st.title("Lead Management")
    st.write("View and manage customer inquiries.")
    st.caption("Timestamps use America/New_York with UTC offsets.")

    if leads:
        df = pd.DataFrame(localize_records(leads))

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
                    "created_at"
                ]
            ],
            hide_index=True,
            width="stretch",
            alt="Customer inquiries"
        )

        st.success(f"Currently tracking {len(leads)} customer leads.")

        # Lead status management
        st.divider()
        st.subheader("Update Lead Status")

        lead_options = {
            f"#{lead['id']} - {lead['name']}": lead['id']
            for lead in leads
        }

        selected_lead = st.selectbox(
            "Select a lead",
            list(lead_options.keys())
        )

        new_status = st.selectbox(
            "New Status",
            ["New", "Contacted", "Quoted", "Won", "Lost"]
        )

        if st.button("Update Status"):
            update_lead_status(
                lead_options[selected_lead],
                new_status
            )
            st.success("Lead status updated successfully!")
            st.rerun()

    else:
        st.info("No leads found. Submit an inquiry to get started.")


# TASK MANAGEMENT
elif page == "Task Management":
    st.title("Task management")
    st.caption("Deadlines and completion times use America/New_York with UTC offsets. Completing a task does not change its lead status.")
    task_filter = st.selectbox("Show tasks", ["Open", "Overdue", "Completed", "All"])
    now = utc_now()
    tasks = [dict(task, state=task_state(task, now)) for task in get_tasks()]
    visible = [task for task in tasks if task_filter == "All"
               or (task_filter == "Open" and task["state"] != "Completed")
               or task["state"] == task_filter]
    if visible:
        st.dataframe(pd.DataFrame(localize_records(visible))[
            ["id", "lead_id", "name", "email", "phone", "service", "urgency",
             "due_at", "state", "completed_at"]], hide_index=True,
            width="stretch", alt="Follow-up tasks with customer contact details")
        options = {f"#{task['id']} — {task['name']}": task["id"]
                   for task in visible if not task["completed_at"]}
        if options:
            selected = st.selectbox("Select a follow-up", list(options))
            if st.button("Complete follow-up"):
                complete_task(options[selected])
                st.session_state["task_notice"] = "Follow-up completed."
                st.rerun()
    else:
        st.info("No tasks match this view.")
    if "task_notice" in st.session_state:
        st.success(st.session_state.pop("task_notice"))

# SETTINGS
elif page == "Settings":
    st.title("Settings")
    st.write("ContractorFlow Application Settings")

    st.info("Additional configuration options are coming soon.")

    st.subheader("System Information")
    st.write("Application: ContractorFlow")
    st.write("Database: SQLite")
    st.write("Framework: Streamlit")
    st.write("Version: 0.4.0")
