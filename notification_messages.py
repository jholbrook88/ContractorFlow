"""Plain-text notification snapshots; no transport or network operations."""

from analytics import local_timestamp
from followups import timestamp


def insert_message(
    conn, *, event_key, kind, lead_id, task_id, recipient, subject, body, now, due_at=None
):
    return conn.execute(
        """INSERT INTO notification_outbox
        (event_key,kind,lead_id,task_id,recipient,subject,body,created_at,reminder_due_at)
        VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(event_key) DO NOTHING""",
        (event_key, kind, lead_id, task_id, recipient, subject, body, timestamp(now), due_at),
    ).rowcount


def lead_details(lead, due_at):
    return (
        f"Inquiry #{lead['id']}\nCustomer: {lead['name']}\nEmail: {lead['email']}\n"
        f"Phone: {lead.get('phone') or 'Not provided'}\nService: {lead['service']}\n"
        f"Urgency: {lead['urgency']}\nDescription: {lead.get('description') or 'Not provided'}\n"
        f"Follow-up deadline (America/New_York): {local_timestamp(due_at)}"
    )


def inquiry_messages(conn, lead, task_id, due_at, now):
    details = lead_details(lead, due_at)
    insert_message(
        conn,
        event_key=f"lead:{lead['id']}:confirmation",
        kind="Customer confirmation",
        lead_id=lead["id"],
        task_id=task_id,
        recipient=lead["email"],
        subject=f"We received your {lead['service']} inquiry",
        body=f"Hello {lead['name']},\n\nThank you for contacting ContractorFlow. "
        f"We received your request and will review it.\n\n{details}\n\n"
        "This confirms receipt; it is not an appointment or a guaranteed service time.",
        now=now,
    )
    insert_message(
        conn,
        event_key=f"lead:{lead['id']}:owner",
        kind="Owner inquiry",
        lead_id=lead["id"],
        task_id=task_id,
        recipient="Business owner (local inbox)",
        subject=f"New {lead['urgency']} inquiry #{lead['id']} - {lead['service']}",
        body=f"A customer inquiry needs your attention.\n\n{details}",
        now=now,
    )
