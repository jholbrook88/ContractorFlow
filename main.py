
import streamlit as st
import pandas as pd
from database import (initialize_database, add_lead, get_leads, update_lead_status,
                      get_tasks, complete_task)
from followups import task_state, utc_now

# Initialize the CRM database
initialize_database()

# Configure the application
st.set_page_config(
    page_title="ContractorFlow",
    page_icon="🔧",
    layout="wide"
)

# Sidebar navigation
st.sidebar.title("🔧 ContractorFlow")
st.sidebar.caption("Small Business Automation Platform")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Customer Inquiries", "Lead Management", "Task Management", "Settings"]
)

# Retrieve customer leads
leads = get_leads()

# DASHBOARD
if page == "Dashboard":
    st.title("ContractorFlow Dashboard")
    st.write("Welcome to your business automation dashboard.")

    total_leads = len(leads)
    new_leads = sum(1 for lead in leads if lead["status"] == "New")
    tasks = get_tasks()
    now = utc_now()
    open_tasks = [dict(task, state=task_state(task, now))
                  for task in tasks if not task["completed_at"]]
    pending_followups = len(open_tasks)
    overdue_followups = sum(task["state"] == "Overdue" for task in open_tasks)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Leads", total_leads)

    with col2:
        st.metric("New Inquiries", new_leads)

    with col3:
        st.metric("Pending Follow-Ups", pending_followups)

    with col4:
        st.metric("Overdue Follow-Ups", overdue_followups)

    st.subheader("Pending and overdue follow-ups")
    st.caption("Pending includes all unfinished tasks. Deadlines are displayed in UTC; refresh to update overdue status.")
    if open_tasks:
        st.dataframe(pd.DataFrame(open_tasks)[
            ["id", "lead_id", "name", "service", "urgency", "due_at", "state"]],
            hide_index=True, width="stretch", alt="Unfinished follow-up tasks")
    else:
        st.info("No pending follow-ups.")

    st.divider()
    st.subheader("Recent Customer Inquiries")

    if leads:
        df = pd.DataFrame(leads)
        st.dataframe(
            df[["id", "name", "service", "urgency", "status", "created_at"]],
            hide_index=True,
            width="stretch",
            alt="Customer inquiries"
        )
    else:
        st.info("No customer inquiries have been submitted yet.")

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

    if leads:
        df = pd.DataFrame(leads)

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
    st.caption("Deadlines and completion times are UTC. Completing a task does not change its lead status.")
    task_filter = st.selectbox("Show tasks", ["Open", "Overdue", "Completed", "All"])
    now = utc_now()
    tasks = [dict(task, state=task_state(task, now)) for task in get_tasks()]
    visible = [task for task in tasks if task_filter == "All"
               or (task_filter == "Open" and task["state"] != "Completed")
               or task["state"] == task_filter]
    if visible:
        st.dataframe(pd.DataFrame(visible)[
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
    st.write("Version: 0.2.0")
