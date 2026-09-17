"""Streamlit UI for the shipment support agent."""

from datetime import datetime

import streamlit as st

from agent.core import run_agent
from mock_sys import SHIPMENTS
import approvals
from agent.core import resume_approval


def display_date(value):
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value


def display_timestamp(value):
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y, %I:%M %p IST")
    except (TypeError, ValueError):
        return value


def show_status_value(column, label, value):
    column.markdown(
        f"<div class='status-value'><div class='status-label'>{label}</div>"
        f"<div class='status-text'>{value}</div></div>",
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="AgentHive Logistics", page_icon="📦", layout="wide")

st.markdown(
    """<style>
    :root { --ink: #f6f7fb; --muted: #9aa4b2; --line: #2d3542; --accent: #ff5b61; }
    .block-container { max-width: 1440px; padding-top: 2rem; }
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    .hero { padding: 1.5rem 1.75rem; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(120deg, #171d28, #11151d); margin-bottom: 1.5rem; }
    .hero-kicker { color: #ff8f75; font-size: .78rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .hero-title { color: var(--ink); font-size: 2.5rem; font-weight: 750; line-height: 1.05; margin: .35rem 0; }
    .hero-copy { color: var(--muted); max-width: 700px; margin: 0; }
    .section-label { color: #ff8f75; font-size: .75rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
    .status-value { min-height: 76px; padding: 0.25rem 0; }
    .status-label { color: #9aa0aa; font-size: 0.85rem; margin-bottom: 0.35rem; }
    .status-text { font-size: 1.25rem; line-height: 1.25; overflow-wrap: anywhere; word-break: normal; }
</style>""",
    unsafe_allow_html=True,
)

st.title("AgentHive Logistics Support")
st.caption("Shipment exception resolution powered by a tool-using operations agent")
st.markdown("<div class='hero'><div class='hero-kicker'>Agentic logistics control</div><div class='hero-title'>Resolve the exception, not just the tracking event.</div><p class='hero-copy'>AgentHive reads carrier signals, verifies the order, assesses risk, and takes the safest next action. High-impact decisions pause for a human.</p></div>", unsafe_allow_html=True)

if "cases" not in st.session_state:
    st.session_state.cases = []

with st.sidebar:
    st.header("Shipment lookup")
    st.write(f"{len(SHIPMENTS)} demo shipments available")
    st.caption("Try SHIP001 through SHIP030")
    st.divider()
    st.subheader("Supported exceptions")
    st.write("Damaged package")
    st.write("Failed delivery")
    st.write("Missing documentation")
    st.write("Bad or incomplete address")
    st.write("Delayed shipment")
    if st.button("Clear conversation"):
        st.session_state.cases = []
        st.rerun()

    all_approvals = approvals.list_all()
    approval_count = len(all_approvals)
    pending_count = sum(1 for item in all_approvals if item["status"] == "PENDING")
    approved_count = sum(1 for item in all_approvals if item["status"] == "APPROVED")
    rejected_count = sum(1 for item in all_approvals if item["status"] == "REJECTED")
    resolved_count = sum(1 for case in st.session_state.cases if case.get("shipment"))
    metric_cols = st.columns(3)
    metric_cols[0].metric("Shipments monitored", len(SHIPMENTS))
    metric_cols[1].metric("Pending human reviews", pending_count)
    metric_cols[2].metric("Cases processed", resolved_count)

    st.header("Human Approval Dashboard")
    approval_filter = st.radio("Approval queue", ["All", "PENDING", "APPROVED", "REJECTED"], horizontal=True)
    pending_approvals = [item for item in all_approvals if approval_filter == "All" or item["status"] == approval_filter]
    st.caption(f"{pending_count} pending · {approved_count} approved · {rejected_count} rejected")
if not pending_approvals:
    st.info("No approval requests. Low-risk actions run automatically.")
for approval in pending_approvals:
    with st.container(border=True):
        st.markdown(f"**{approval['status']} · {approval['risk_level']}**")
        st.write(f"Shipment: {approval['shipment_id']} · Customer: {approval['customer']}")
        st.write(f"Value: ₹{approval['shipment_value']:,.0f} · Action: {approval['requested_action']}")
        st.write(f"Reason: {approval['reason']}")
        st.caption(f"Created: {approval['created_at']}")
        if approval["status"] == "PENDING":
            reviewer = st.text_input("Reviewer", value="operations-agent", key=f"reviewer_{approval['id']}")
            approve_col, reject_col = st.columns(2)
            with approve_col:
                if st.button("Approve", key=f"approve_{approval['id']}", type="primary"):
                    try:
                        approvals.approve(approval["id"], reviewer)
                        outcome = resume_approval(approval["id"])
                        st.success(outcome["message"])
                    except (KeyError, ValueError, PermissionError) as error:
                        st.error(str(error))
                    st.rerun()
            with reject_col:
                reason = st.text_input("Rejection reason", key=f"reject_reason_{approval['id']}")
                if st.button("Reject", key=f"reject_{approval['id']}"):
                    try:
                        approvals.reject(approval["id"], reviewer, reason)
                        st.warning("Rejected. The dangerous action was not executed.")
                    except (KeyError, ValueError) as error:
                        st.error(str(error))
                    st.rerun()

left, right = st.columns([1, 1.35], gap="large")
with left:
    st.subheader("Submit a shipment issue")
    shipment_id = st.text_input("Shipment ID", placeholder="SHIP003").strip().upper()
    shipment_preview = SHIPMENTS.get(shipment_id)
    issue = st.selectbox("Issue type", [
        "Damaged package", "Failed delivery", "Missing documentation",
        "Bad or incomplete address", "Delayed shipment",
    ])
    problem = st.text_area("What happened?", placeholder="Tell us what went wrong...", height=130)
    new_address = None
    document_type = None
    evidence = None
    resolution_choice = None
    if issue == "Bad or incomplete address":
        new_address = st.text_input("Correct delivery address", placeholder="42 Lake Road, Bengaluru 560001")
    elif issue == "Missing documentation":
        document_type = st.text_input("Document type", placeholder="Commercial invoice")
        if shipment_preview:
            st.info(f"For {shipment_id}, please provide: {shipment_preview['required_document']}")
        st.caption("Send a clear PDF or photo of the requested invoice, identity proof, customs form, or delivery proof.")
        document = st.file_uploader("Attach the document", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=False)
        if document:
            st.success(f"Ready to send: {document.name}")
            document_evidence = {"name": document.name, "size": document.size}
    elif issue == "Damaged package":
        photo = st.file_uploader("Upload damage photos", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=False)
        if photo:
            evidence = {"name": photo.name, "size": photo.size}
            st.image(photo, caption=photo.name, width=180)
    elif issue in {"Delayed shipment", "Failed delivery"}:
        if shipment_preview:
            overdue_days = max(0, (datetime(2026, 8, 29).date() - datetime.fromisoformat(shipment_preview["estimated_delivery"]).date()).days)
            if overdue_days > 21:
                st.warning(f"This order is {overdue_days} days past its estimated delivery date. The order will be cancelled and you can choose what happens next.")
                resolution_choice = st.selectbox("After cancellation", ["Ask me later", "Refund", "Send again"])

    submitted = st.button("Resolve issue", type="primary", use_container_width=True)
    if submitted:
        if not shipment_id:
            st.warning("Enter a shipment ID first.")
        elif not problem:
            st.warning("Describe the issue so the agent can investigate it.")
        else:
            request = f"Shipment ID: {shipment_id}\nIssue Type: {issue}\nCustomer Problem: {problem}"
            with st.spinner("Agent is checking the shipment and coordinating next steps..."):
                result = run_agent(request, evidence=evidence, new_address=new_address, document_type=document_type, document_evidence=locals().get("document_evidence"), resolution_choice=resolution_choice if resolution_choice != "Ask me later" else None)
            st.session_state.cases.append({"request": request, **result})
            st.rerun()

with right:
    st.subheader("Agent response")
    if shipment_preview:
        with st.container(border=True):
            st.markdown("**Registered order details**")
            st.caption("Loaded from the shipment database after entering the ID")
            preview_cols = st.columns(3)
            preview_cols[0].write(f"Customer\n\n**{shipment_preview['customer']}**")
            preview_cols[1].write(f"Order value\n\n**₹{shipment_preview['value']:,.0f}**")
            preview_cols[2].write(f"Ordered on\n\n**{display_date(shipment_preview['order_date'])}**")
    if not st.session_state.cases:
        st.info("Submit an issue to see the shipment investigation here.")
    for case in reversed(st.session_state.cases):
        with st.container(border=True):
            st.markdown(case["answer"])
            if case.get("case_token"):
                st.caption(f"Support case token: {case['case_token']}")
            if case.get("model"):
                st.caption(f"Response generated by {case['model']}")
            shipment = case.get("shipment")
            if shipment:
                st.caption(f"{shipment['shipment_id']} · {shipment['product']} · {shipment['order_id']}")
                status_cols = st.columns(3)
                show_status_value(status_cols[0], "Current status", shipment["status"])
                show_status_value(status_cols[1], "Location", shipment["location"])
                show_status_value(status_cols[2], "ETA (IST)", display_date(shipment["eta"]))

                carrier = case.get("carrier_tracking")
                if carrier and carrier.get("success"):
                    st.markdown("#### Carrier tracking")
                    st.caption("Facts and scans from the carrier")
                    st.write(f"**{carrier['carrier']}** · {carrier['tracking_id']}")
                    st.write(f"Latest scan: {carrier['current_scan']['event']}")
                    for scan in carrier["scans"]:
                        st.write(f"{display_timestamp(scan['timestamp'])}  |  {scan['event']}")
            with st.expander(f"Agent reasoning trail ({len(case['trail'])} steps)"):
                for step in case["trail"]:
                    if step.get("type") == "model_plan":
                        st.write(f"**{step['model']}** · selected resolution plan")
                        st.json(step["result"], expanded=False)
                        continue
                    if step.get("type") == "model_fallback":
                        st.write(f"**{step['model']}** · fallback resolution")
                        st.caption(step["result"]["reason"])
                        continue
                    if step.get("type") == "risk_assessment":
                        risk = step["result"]
                        st.write(f"**Risk gate: {step['action']}** · {risk['risk_level']} · {risk['recommended_action']}")
                        st.caption(risk["reason"])
                        continue
                    result = step["result"]
                    label = "completed" if result.get("success") else "needs attention"
                    st.write(f"**{step['tool']}** · {label}")
                    st.json({"input": step["args"], "result": result}, expanded=False)
            st.divider()
