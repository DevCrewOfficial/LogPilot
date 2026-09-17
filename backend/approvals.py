"""HITL approval repository with optional Supabase persistence."""

from datetime import datetime
from hashlib import sha256
from threading import RLock
from uuid import uuid4
from zoneinfo import ZoneInfo

from supabase_client import supabase


IST = ZoneInfo("Asia/Kolkata")
_LOCK = RLock()


def _load_approvals_from_supabase():
    if not supabase:
        return {}
    try:
        response = supabase.table("approvals").select("*").execute()
        approvals = {}
        for row in response.data or []:
            approval_id = str(row.get("id") or row.get("approval_id") or "")
            if approval_id:
                approvals[approval_id] = dict(row)
        return approvals
    except Exception:
        return {}


_APPROVALS = _load_approvals_from_supabase()


def _now():
    return datetime.now(IST).isoformat(timespec="seconds")


def _key(shipment_id, action, request):
    return sha256(f"{shipment_id}|{action}|{request}".encode()).hexdigest()


def _persist_approval(approval):
    if not supabase:
        return approval
    try:
        payload = dict(approval)
        payload["created_at"] = payload.get("created_at") or _now()
        payload["reviewed_at"] = payload.get("reviewed_at")
        payload["reviewed_by"] = payload.get("reviewed_by")
        payload["human_comment"] = payload.get("human_comment")
        payload["execution_result"] = payload.get("execution_result")
        payload["shipment_value"] = float(payload.get("shipment_value") or 0)
        supabase.table("approvals").upsert(payload, on_conflict="id").execute()
    except Exception:
        pass
    return approval


def create_or_get(shipment, request, action, action_args, risk):
    key = _key(shipment["shipment_id"], action, request)
    with _LOCK:
        for approval in _APPROVALS.values():
            if approval.get("dedupe_key") == key:
                return approval
        approval = {
            "id": f"APR-{uuid4().hex[:10].upper()}",
            "shipment_id": shipment["shipment_id"],
            "customer_id": shipment.get("customer_id"),
            "customer": shipment.get("customer"),
            "request": request,
            "requested_action": action,
            "action_args": action_args,
            "shipment_value": shipment.get("value", 0),
            "risk_level": risk["risk_level"],
            "reason": risk["reason"],
            "status": "PENDING",
            "created_at": _now(),
            "reviewed_at": None,
            "reviewed_by": None,
            "human_comment": None,
            "execution_result": None,
            "dedupe_key": key,
        }
        _APPROVALS[approval["id"]] = approval
        _persist_approval(approval)
        return approval


def list_all():
    with _LOCK:
        return [dict(item) for item in reversed(list(_APPROVALS.values()))]


def get(approval_id):
    return _APPROVALS.get(approval_id)


def approve(approval_id, reviewer):
    with _LOCK:
        approval = _APPROVALS.get(approval_id)
        if not approval:
            raise KeyError("Approval request was not found")
        if approval["status"] != "PENDING":
            raise ValueError(f"Approval is already {approval['status']}")
        approval["status"] = "APPROVED"
        approval["reviewed_at"] = _now()
        approval["reviewed_by"] = reviewer or "operations-agent"
        _persist_approval(approval)
        return approval


def reject(approval_id, reviewer, comment):
    with _LOCK:
        approval = _APPROVALS.get(approval_id)
        if not approval:
            raise KeyError("Approval request was not found")
        if approval["status"] != "PENDING":
            raise ValueError(f"Approval is already {approval['status']}")
        if not comment:
            raise ValueError("A rejection reason is required")
        approval["status"] = "REJECTED"
        approval["reviewed_at"] = _now()
        approval["reviewed_by"] = reviewer or "operations-agent"
        approval["human_comment"] = comment
        approval["execution_result"] = {"success": False, "blocked": True, "message": "Dangerous action was not executed."}
        _persist_approval(approval)
        return approval


def record_execution(approval_id, result):
    with _LOCK:
        approval = _APPROVALS[approval_id]
        approval["execution_result"] = result
        _persist_approval(approval)
        return approval


def assert_approved(approval_id, action, shipment_id):
    approval = _APPROVALS.get(approval_id)
    if not approval or approval["status"] != "APPROVED":
        raise PermissionError("Human approval is required before this action can execute")
    if approval["requested_action"] != action or approval["shipment_id"] != shipment_id:
        raise PermissionError("Approval does not match this action")
