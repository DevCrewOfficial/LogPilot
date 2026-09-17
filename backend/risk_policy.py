"""Centralized policy and risk assessment for autonomous shipment actions."""

import os
from decimal import Decimal, InvalidOperation



def _money_env(name, default):
    try:
        return Decimal(os.getenv(name, str(default)))
    except InvalidOperation:
        return Decimal(str(default))


AUTONOMOUS_SHIPMENT_VALUE_LIMIT = _money_env("AUTONOMOUS_SHIPMENT_VALUE_LIMIT", 50000)
AUTONOMOUS_REFUND_LIMIT = _money_env("AUTONOMOUS_REFUND_LIMIT", 10000)
SIGNIFICANT_ACTIONS = {
    "initiate_replacement",
    "issue_refund",
    "cancel_order",
    "redirect_shipment",
    "reschedule_delivery",
    "create_ops_ticket",
}


def assess_risk(request, shipment, context=None):
    """Return a policy decision before an operationally significant action."""
    context = context or {}
    action = context.get("requested_action", "")
    value = Decimal(str(shipment.get("value", 0)))
    refund_amount = Decimal(str(context.get("refund_amount", 0)))
    reasons = []
    risk_level = "LOW"

    if value > AUTONOMOUS_SHIPMENT_VALUE_LIMIT:
        reasons.append(f"Shipment value ₹{value:,.0f} exceeds autonomous limit ₹{AUTONOMOUS_SHIPMENT_VALUE_LIMIT:,.0f}")
        risk_level = "HIGH"
    if refund_amount > AUTONOMOUS_REFUND_LIMIT:
        reasons.append(f"Refund amount ₹{refund_amount:,.0f} exceeds autonomous limit ₹{AUTONOMOUS_REFUND_LIMIT:,.0f}")
        risk_level = "HIGH"
    if action in {"initiate_replacement", "issue_refund"} and value > AUTONOMOUS_SHIPMENT_VALUE_LIMIT:
        reasons.append("Replacement or refund affects a high-value shipment")
        risk_level = "HIGH"
    if context.get("policy_exception"):
        reasons.append("Requested action is outside normal company policy")
        risk_level = "HIGH"
    if context.get("suspicious"):
        reasons.append("Request contains suspicious or inconsistent information")
        risk_level = "CRITICAL"
    if context.get("uncertain"):
        reasons.append("Agent does not have enough information to act safely")
        risk_level = "HIGH" if risk_level != "CRITICAL" else risk_level
    if context.get("force_human"):
        reasons.append("This action is configured for human review")
        risk_level = "HIGH" if risk_level == "LOW" else risk_level
    if action in SIGNIFICANT_ACTIONS and context.get("significant_requires_human"):
        reasons.append("Significant operational action is configured for human review")
        risk_level = "HIGH" if risk_level == "LOW" else risk_level

    return {
        "requires_human": bool(reasons),
        "risk_level": risk_level,
        "reason": "; ".join(reasons) if reasons else "Within autonomous policy limits",
        "recommended_action": "HUMAN_APPROVAL" if reasons else "AUTONOMOUS_EXECUTION",
        "requested_action": action,
        "shipment_value": float(value),
        "refund_amount": float(refund_amount),
    }
