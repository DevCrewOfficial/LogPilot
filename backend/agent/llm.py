"""Groq model adapter for customer-facing logistics responses."""

import json
import os

from dotenv import load_dotenv
from groq import Groq

from .prompt import MASTER_SYSTEM_PROMPT, build_master_prompt


load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=API_KEY) if API_KEY else None


def _enabled():
    return os.getenv("AGENT_LLM_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "select_resolution_plan",
        "description": "Select the customer issue and intended logistics resolution after reviewing verified data.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue": {"type": "string", "enum": ["damaged", "failed_delivery", "missing_documentation", "bad_address", "delayed"]},
                "requested_action": {"type": "string", "enum": ["initiate_replacement", "reschedule_delivery", "request_missing_document", "redirect_shipment", "create_ops_ticket", "cancel_order"]},
                "reasoning": {"type": "string"},
            },
            "required": ["issue", "requested_action", "reasoning"],
        },
    },
}


def plan_resolution(customer_request, shipment, carrier_tracking):
    """Use Groq function calling to interpret the request after facts are verified."""
    if client is None or not _enabled():
        return None
    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {"role": "user", "content": build_master_prompt(customer_request, shipment, carrier_tracking)},
            ],
            tools=[PLAN_TOOL],
            tool_choice={"type": "function", "function": {"name": "select_resolution_plan"}},
        )
        calls = response.choices[0].message.tool_calls or []
        if not calls:
            return None
        return json.loads(calls[0].function.arguments)
    except (Exception, json.JSONDecodeError):
        return None


def generate_customer_response(customer_request, shipment, carrier_tracking, actions, approval=None):
    """Ask the configured model to explain verified facts and completed actions."""
    if client is None or not _enabled():
        return None

    context = {
        "actions_taken": actions,
        "approval": approval,
        "response_mode": "approval_pending" if approval else "completed",
    }
    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {"role": "user", "content": build_master_prompt(customer_request, shipment, carrier_tracking, context)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        summary = result.get("summary") or result.get("next_step")
        location = result.get("current_location")
        eta = result.get("eta_ist")
        if not summary or result.get("shipment_id") != shipment["shipment_id"] or location != shipment["location"]:
            return None
        return f"{summary} Current location: {location}. ETA (IST): {eta or shipment['eta']}."
    except (Exception, json.JSONDecodeError):
        return None
