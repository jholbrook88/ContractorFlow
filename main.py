
import streamlit as st
import pandas as pd
from database import initialize_database, add_lead, get_leads, update_lead_status

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
    ["Dashboard", "Customer Inquiries", "Lead Management", "Settings"]
)

# Retrieve customer leads
leads = get_leads()

# DASHBOARD
if page == "Dashboard":
    st.title("ContractorFlow Dashboard")
    st.write("Welcome to your business automation dashboard.")

    total_leads = len(leads)
    new_leads = sum(1 for lead in leads if lead["status"] == "New")
    pending_followups = new_leads

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Leads", total_leads)

    with col2:
        st.metric("New Inquiries", new_leads)

    with col3:
        st.metric("Pending Follow-Ups", pending_followups)

    st.divider()
    st.subheader("Recent Customer Inquiries")

    if leads:
        df = pd.DataFrame(leads)
        st.dataframe(
            df[["id", "name", "service", "urgency", "status", "created_at"]],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No customer inquiries have been submitted yet.")

# CUSTOMER INQUIRIES
elif page == "Customer Inquiries":
    st.title("Customer Inquiries")
    st.write("Submit a new service request using the form below.")

    with st.form("customer_inquiry_form", clear_on_submit=True):
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
                f"Inquiry #{lead_id} submitted successfully for {name}!"
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
            use_container_width=True
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


# SETTINGS
elif page == "Settings":
    st.title("Settings")
    st.write("ContractorFlow Application Settings")

    st.info("Additional configuration options are coming soon.")

    st.subheader("System Information")
    st.write("Application: ContractorFlow")
    st.write("Database: SQLite")
    st.write("Framework: Streamlit")
    st.write("Version: 0.1.0")
