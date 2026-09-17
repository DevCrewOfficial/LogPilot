from . import shipment


# These are the tools given to Groq
TOOLS = shipment.TOOLS


def execute_tool(name: str, tool_input: dict, approval_id: str = None, request: str = ""):
    """Execute a shipment tool by name."""

    if name not in shipment.FUNCTIONS:
        return {
            "success": False,
            "error": f"Unknown tool: {name}"
        }

    try:
        if name in {"initiate_replacement", "issue_refund", "cancel_order", "redirect_shipment", "reschedule_delivery", "create_ops_ticket"}:
            from risk_policy import assess_risk
            import mock_sys
            from approvals import assert_approved
            shipment_result = mock_sys.get_shipment_status(tool_input.get("shipment_id", ""))
            if not shipment_result.get("success"):
                return shipment_result
            risk = assess_risk(request, shipment_result["shipment"], {"requested_action": name})
            if risk["requires_human"] and not approval_id:
                return {"success": False, "blocked": True, "requires_human": True, "risk": risk, "error": "Human approval is required before this action can execute."}
            if approval_id:
                assert_approved(approval_id, name, tool_input.get("shipment_id", ""))
        result = shipment.FUNCTIONS[name](**tool_input)
        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }