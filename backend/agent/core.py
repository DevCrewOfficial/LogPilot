"""Shipment support orchestration with a deterministic local demo agent."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .tools import execute_tool
from .llm import MODEL, generate_customer_response, plan_resolution
from risk_policy import assess_risk
import approvals


IST = ZoneInfo("Asia/Kolkata")


def _display_date(value):
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value


def _shipment_id(text):
    match = re.search(r"\bSHIP\d{3}\b", text.upper())
    return match.group(0) if match else None



def _issue_type(text, fallback=None):
    lowered = text.lower()
    if "damaged" in lowered or "broken" in lowered:
        return "damaged"
    if "failed" in lowered or "delivery attempt" in lowered:
        return "failed_delivery"
    if "document" in lowered or "customs" in lowered:
        return "missing_documentation"
    if "address" in lowered:
        return "bad_address"
    if "delay" in lowered or "did not receive" in lowered or "late" in lowered:
        return "delayed"
    return fallback


def _run_tool(name, args, trail, request="", approval_id=None):
    result = execute_tool(name, args, approval_id=approval_id, request=request)
    trail.append({"tool": name, "args": args, "result": result})
    return result


def _action_or_approval(name, args, request, shipment, trail, context=None):
    risk = assess_risk(request, shipment, {"requested_action": name, **(context or {})})
    trail.append({"type": "risk_assessment", "action": name, "result": risk})
    if risk["requires_human"]:
        approval = approvals.create_or_get(shipment, request, name, args, risk)
        return {"pending": True, "approval": approval, "risk": risk}
    return {"pending": False, "result": _run_tool(name, args, trail, request)}


def run_agent(user_input, verbose=False, evidence=None, new_address=None, document_type=None, document_evidence=None, resolution_choice=None, order_value=None, order_date=None):
    """Resolve an issue using shipment tools and return an answer plus trace."""
    trail = []
    shipment_id = _shipment_id(user_input)
    if not shipment_id:
        return {"answer": "Please provide a valid shipment ID such as SHIP001.", "trail": trail}

    status_result = _run_tool("get_shipment_status", {"shipment_id": shipment_id}, trail)
    if not status_result.get("success"):
        return {"answer": status_result["error"], "trail": trail}

    shipment = status_result["shipment"]
    case_result = _run_tool("create_issue_case", {"shipment_id": shipment_id, "request": user_input}, trail, user_input)
    case_token = case_result.get("case", {}).get("case_token")
    carrier_result = _run_tool("get_carrier_tracking", {"shipment_id": shipment_id}, trail)
    verification = _run_tool("verify_order_details", {"shipment_id": shipment_id, "order_value": order_value if order_value is not None else shipment["value"], "order_date": order_date or shipment["order_date"]}, trail)
    if not verification.get("verified"):
        return {"answer": "I could not verify the order details. Please check the price and order date against your confirmation email and try again.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "verification": verification, "case_token": case_token}
    actions = []
    model_plan = plan_resolution(user_input, shipment, carrier_result)
    if model_plan:
        trail.append({"type": "model_plan", "model": MODEL, "result": model_plan})
        issue = model_plan.get("issue")
    else:
        issue = _issue_type(user_input, shipment.get("issue"))
        trail.append({"type": "model_fallback", "model": MODEL, "result": {"reason": "Model plan unavailable; deterministic safety fallback used.", "issue": issue}})
    if not issue:
        return {"answer": "Please select one of the supported issue types so I can take the right action.", "trail": trail, "shipment": shipment}
    # A severe overdue shipment takes priority over ordinary delivery handling.
    if shipment.get("days_overdue", 0) > 21 and issue in {"delayed", "failed_delivery"}:
        decision = _action_or_approval("cancel_order", {"shipment_id": shipment_id, "reason": "More than 21 days past estimated delivery"}, user_input, shipment, trail)
        if decision["pending"]:
            approval = decision["approval"]
            return {"answer": f"I checked {shipment_id}. The order cancellation is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval}
        cancel = decision["result"]
        actions.append(cancel.get("message", "The current order has been cancelled"))
        if resolution_choice == "Refund":
            decision = _action_or_approval("issue_refund", {"shipment_id": shipment_id, "amount": shipment["value"]}, user_input, shipment, trail)
            if decision["pending"]:
                approval = decision["approval"]
                return {"answer": f"The order is cancelled. Your refund is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval}
            actions.append(decision["result"].get("message", "Your refund has been issued"))
        elif resolution_choice == "Send again":
            decision = _action_or_approval("initiate_replacement", {"shipment_id": shipment_id}, user_input, shipment, trail)
            if decision["pending"]:
                approval = decision["approval"]
                return {"answer": f"The order is cancelled. A resend is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval}
            actions.append(decision["result"].get("message", "A replacement has been created"))
        else:
            actions.append("Would you like a refund or should we send the product again?")
    elif issue == "damaged":
        if evidence:
            _run_tool("upload_damage_evidence", {"shipment_id": shipment_id, "filename": evidence["name"], "file_size": evidence["size"]}, trail)
            actions.append("Your photo is attached to the case")
        decision = _action_or_approval("initiate_replacement", {"shipment_id": shipment_id}, user_input, shipment, trail)
        if decision["pending"]:
            approval = decision["approval"]
            message = f"I checked {shipment_id}. Replacement is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}."
            return {"answer": message, "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval, "case_token": case_token}
        replacement = decision["result"]
        actions.append(replacement.get("message", "A replacement has been initiated"))
        if replacement.get("replacement_id"):
            actions.append(f"Replacement ID: {replacement['replacement_id']}")
    elif issue == "failed_delivery":
        new_date = (datetime.now(IST).date() + timedelta(days=2)).isoformat()
        decision = _action_or_approval("reschedule_delivery", {"shipment_id": shipment_id, "new_date": new_date}, user_input, shipment, trail)
        if decision["pending"]:
            approval = decision["approval"]
            return {"answer": f"I checked {shipment_id}. Delivery rescheduling is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval}
        result = decision["result"]
        actions.append(result.get("message", "Delivery has been rescheduled"))
    elif issue == "missing_documentation":
        doc = document_type or shipment.get("required_document") or "the required customs document"
        if document_evidence:
            upload = _run_tool("upload_required_document", {"shipment_id": shipment_id, "filename": document_evidence["name"], "file_size": document_evidence["size"], "doc_type": doc}, trail)
            actions.append(upload.get("message", f"{doc} attached"))
        else:
            actions.append(f"Please upload your {doc}")
            result = _run_tool("request_missing_document", {"shipment_id": shipment_id, "doc_type": doc}, trail)
            actions.append(result.get("message", f"Please provide {doc}"))
    elif issue == "bad_address":
        if new_address:
            decision = _action_or_approval("redirect_shipment", {"shipment_id": shipment_id, "new_address": new_address}, user_input, shipment, trail)
            if decision["pending"]:
                approval = decision["approval"]
                return {"answer": f"I checked {shipment_id}. Address redirection is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval}
            result = decision["result"]
            actions.append(result.get("message", "Shipment redirected"))
        else:
            actions.append("Please reply with the complete address so we can redirect it")
    else:
        if shipment.get("days_overdue", 0) > 21:
            decision = _action_or_approval("cancel_order", {"shipment_id": shipment_id, "reason": "More than 21 days past estimated delivery"}, user_input, shipment, trail)
            if decision["pending"]:
                approval = decision["approval"]
                return {"answer": f"I checked {shipment_id}. The order cancellation is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval, "case_token": case_token}
            cancel = decision["result"]
            actions.append(cancel.get("message", "The current order has been cancelled"))
            if resolution_choice == "Refund":
                decision = _action_or_approval("issue_refund", {"shipment_id": shipment_id, "amount": shipment["value"]}, user_input, shipment, trail)
                if decision["pending"]:
                    approval = decision["approval"]
                    return {"answer": f"The order is cancelled. Your refund is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval, "case_token": case_token}
                actions.append(decision["result"].get("message", "Your refund has been issued"))
            elif resolution_choice == "Send again":
                decision = _action_or_approval("initiate_replacement", {"shipment_id": shipment_id}, user_input, shipment, trail)
                if decision["pending"]:
                    approval = decision["approval"]
                    return {"answer": f"The order is cancelled. A resend is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval, "case_token": case_token}
                actions.append(decision["result"].get("message", "A replacement has been created"))
            else:
                actions.append("Would you like a refund or should we send the product again?")
        else:
            decision = _action_or_approval("create_ops_ticket", {"shipment_id": shipment_id, "reason": "Carrier delay investigation"}, user_input, shipment, trail)
            if decision["pending"]:
                approval = decision["approval"]
                return {"answer": f"I checked {shipment_id}. The operations investigation is paused pending human approval because: {decision['risk']['reason']}. Approval ID: {approval['id']}.", "trail": trail, "shipment": shipment, "carrier_tracking": carrier_result, "approval": approval, "case_token": case_token}
            ticket = decision["result"]
            actions.append(f"Our operations team is investigating (ticket {ticket.get('ticket', {}).get('ticket_id', 'created')})")

    refreshed = _run_tool("get_shipment_status", {"shipment_id": shipment_id}, trail)
    current = refreshed.get("shipment", shipment)
    action_summary = " ".join(actions)
    if action_summary and action_summary[-1] not in ".!?":
        action_summary += "."
    message = (
        f"I checked {shipment_id} for you. It is currently **{current['status']}** at "
        f"**{current['location']}** with {current['carrier']}. "
        f"The latest ETA is **{_display_date(current['eta'])} (IST)**. {action_summary}"
    )
    model_message = generate_customer_response(user_input, current, carrier_result, actions)
    if model_message:
        message = model_message
    _run_tool("notify_customer", {"shipment_id": shipment_id, "message": message}, trail)
    return {"answer": message, "trail": trail, "shipment": current, "carrier_tracking": carrier_result, "model": MODEL if model_message else None, "case_token": case_token}


def resume_approval(approval_id):
    approval = approvals.get(approval_id)
    if not approval:
        return {"success": False, "error": "Approval request was not found"}
    if approval["status"] == "REJECTED":
        return {"success": False, "message": "Request rejected. The dangerous action was not executed.", "approval": approval}
    if approval["status"] != "APPROVED":
        return {"success": False, "error": "Approval must be approved before execution"}
    result = _run_tool(approval["requested_action"], approval["action_args"], [], approval["request"], approval_id)
    approvals.record_execution(approval_id, result)
    return {"success": result.get("success", False), "message": "AI resumed and executed the approved action.", "result": result, "approval": approval}
