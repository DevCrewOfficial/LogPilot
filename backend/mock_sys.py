"""Deterministic shipment system with a Supabase-backed data source and optional demo fallback."""

import os
from copy import deepcopy
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from supabase_client import supabase


IST = ZoneInfo("Asia/Kolkata")
DEMO_TODAY = date(2026, 8, 29)


def _normalize_supabase_row(row):
	if not row:
		return {}
	shipment_id = str(row.get("shipment_id") or row.get("id") or "").strip().upper()
	eta = row.get("eta") or row.get("estimated_delivery") or "2026-09-03"
	estimated_delivery = row.get("estimated_delivery") or eta
	return {
		"shipment_id": shipment_id,
		"order_id": row.get("order_id") or f"ORD-{shipment_id}",
		"customer_id": row.get("customer_id") or f"CUST-{shipment_id}",
		"order_date": row.get("order_date") or "2026-08-29",
		"customer": row.get("customer") or "Guest Customer",
		"product": row.get("product") or "Shipment",
		"status": row.get("status") or "In transit",
		"issue": row.get("issue"),
		"location": row.get("location") or "Unknown location",
		"carrier": row.get("carrier") or "Carrier",
		"eta": eta,
		"estimated_delivery": estimated_delivery,
		"address": row.get("address") or "Address unavailable",
		"value": float(row.get("value") or 0),
		"damage_status": row.get("damage_status") or "none",
		"required_document": row.get("required_document") or "Commercial invoice",
		"events": row.get("events") or [{"timestamp": datetime.now(IST).isoformat(timespec="seconds"), "event": "Shipment created"}],
		"actions": row.get("actions") or [],
	}


def _load_shipments_from_supabase():
	if not supabase:
		return None
	try:
		result = supabase.table("shipments").select("*").execute()
		rows = result.data or []
		shipments = {}
		for row in rows:
			normalized = _normalize_supabase_row(row)
			shipment_id = normalized.get("shipment_id")
			if shipment_id:
				shipments[shipment_id] = normalized
		if shipments:
			return shipments
	except Exception:
		return None
	return None


def _display_date(value):
	try:
		return datetime.fromisoformat(value).strftime("%d %b %Y")
	except (TypeError, ValueError):
		return value


_TRACKING_DATA = [
	("In transit", "Bengaluru sorting facility", "2026-09-03"),
	("In transit", "Mumbai distribution center", "2026-08-31"),
	("In transit", "Delhi logistics hub", "2026-09-04"),
	("In transit", "Hyderabad last-mile hub", "2026-09-05"),
	("In transit", "Kolkata distribution center", "2026-09-02"),
]


def _build_shipments():
	shipments = {}
	for index in range(30):
		status, location, eta = _TRACKING_DATA[index % len(_TRACKING_DATA)]
		if index == 5:
			status, location, eta = "Carrier investigation overdue", "Pune transit hub", "2026-07-20"
		shipment_id = f"SHIP{index + 1:03d}"
		shipments[shipment_id] = {
			"shipment_id": shipment_id,
			"order_id": f"ORD-{2026_0001 + index}",
			"customer_id": f"CUST-{index + 1:03d}",
			"order_date": f"2026-08-{(index % 20) + 1:02d}",
			"customer": ["Aarav Mehta", "Maya Chen", "Noah Williams", "Isha Patel", "Liam Garcia"][index % 5],
			"product": ["Wireless headphones", "Standing desk", "Running shoes", "Coffee machine", "Monitor"][index % 5],
			"status": status,
			"issue": None,
			"location": location,
			"carrier": ["Delhivery", "Blue Dart", "DTDC", "Ecom Express", "India Post"][index % 5],
			"eta": eta,
			"estimated_delivery": eta,
			"address": [
				f"{100 + index}, MG Road, Bengaluru, Karnataka 560001",
				f"{100 + index}, Andheri East, Mumbai, Maharashtra 400069",
				f"{100 + index}, Connaught Place, New Delhi 110001",
				f"{100 + index}, Banjara Hills, Hyderabad, Telangana 500034",
				f"{100 + index}, Park Street, Kolkata, West Bengal 700016",
			][index % 5],
			"value": 2000 if index == 0 else 85000 if index == 1 else 4900 + (index * 3700) % 42000,
			"damage_status": "none",
			"required_document": ["Commercial invoice", "GST invoice", "KYC identity proof", "Import declaration", "Proof of delivery"][index % 5],
			"events": [
				{"timestamp": "2026-08-28T10:30:00+05:30", "event": "Shipment picked up by carrier"},
				{"timestamp": "2026-08-29T16:45:00+05:30", "event": location},
			],
			"actions": [],
		}
	return shipments


USE_DEMO_FALLBACK = os.getenv("USE_DEMO_FALLBACK", "false").lower() not in {"0", "false", "no", "off"}

SHIPMENTS = _load_shipments_from_supabase()
if SHIPMENTS is None:
	if USE_DEMO_FALLBACK:
		SHIPMENTS = _build_shipments()
	else:
		raise RuntimeError("Supabase shipment data is unavailable and demo fallback is disabled.")

NOTIFICATIONS = []
OPERATIONS_TICKETS = []
ISSUE_CASES = []


def get_shipment_status(shipment_id: str):
	shipment = SHIPMENTS.get(shipment_id.strip().upper())
	if not shipment:
		return {"success": False, "error": f"Shipment {shipment_id} was not found."}
	result = deepcopy(shipment)
	result["days_overdue"] = max(0, (DEMO_TODAY - date.fromisoformat(result["estimated_delivery"])).days)
	return {"success": True, "shipment": result}


def create_issue_case(shipment_id: str, request: str):
	"""Create a customer-facing case token for a valid shipment issue."""
	shipment = _get(shipment_id)
	case = {
		"case_token": f"CASE-{uuid4().hex[:10].upper()}",
		"shipment_id": shipment["shipment_id"],
		"customer_id": shipment["customer_id"],
		"request": request,
		"status": "OPEN",
		"created_at": datetime.now(IST).isoformat(timespec="seconds"),
	}
	ISSUE_CASES.append(case)
	return {"success": True, "case": case}


def get_carrier_tracking(shipment_id: str):
	"""Return raw carrier scans, like a carrier tracking API would."""
	shipment = SHIPMENTS.get(shipment_id.strip().upper())
	if not shipment:
		return {"success": False, "error": f"Carrier has no record for {shipment_id}."}
	return {
		"success": True,
		"carrier": shipment["carrier"],
		"tracking_id": shipment["shipment_id"],
		"current_scan": shipment["events"][-1],
		"scans": deepcopy(shipment["events"]),
		"eta": shipment["eta"],
	}


def verify_order_details(shipment_id: str, order_value: float, order_date: str):
	"""Verify customer-provided order details against the order database."""
	shipment = SHIPMENTS.get(shipment_id.strip().upper())
	if not shipment:
		return {"success": False, "verified": False, "error": "Order was not found."}
	value_matches = abs(float(shipment["value"]) - float(order_value)) < 0.01
	date_matches = shipment["order_date"] == order_date
	if not value_matches or not date_matches:
		return {
			"success": True,
			"verified": False,
			"error": "The price or order date does not match our order records.",
			"fields_checked": {"price_match": value_matches, "order_date_match": date_matches},
		}
	return {"success": True, "verified": True, "message": "Order details verified."}


def _get(shipment_id):
	shipment = SHIPMENTS.get(shipment_id.strip().upper())
	if not shipment:
		raise ValueError(f"Shipment {shipment_id} was not found")
	return shipment


def reschedule_delivery(shipment_id: str, new_date: str):
	shipment = _get(shipment_id)
	shipment["eta"] = new_date
	shipment["status"] = "Delivery rescheduled"
	shipment["actions"].append({"action": "reschedule_delivery", "new_date": new_date})
	return {"success": True, "message": f"Delivery rescheduled for {_display_date(new_date)} (IST).", "shipment_id": shipment["shipment_id"]}


def redirect_shipment(shipment_id: str, new_address: str):
	shipment = _get(shipment_id)
	shipment["address"] = new_address
	shipment["status"] = "Address correction in progress"
	shipment["actions"].append({"action": "redirect_shipment", "new_address": new_address})
	return {"success": True, "message": "Shipment redirected to the new address.", "shipment_id": shipment["shipment_id"]}


def initiate_replacement(shipment_id: str):
	shipment = _get(shipment_id)
	replacement_id = f"RPL-{uuid4().hex[:8].upper()}"
	shipment["status"] = "Replacement approved"
	shipment["replacement_id"] = replacement_id
	shipment["actions"].append({"action": "initiate_replacement", "replacement_id": replacement_id})
	return {"success": True, "message": "Replacement shipment created.", "replacement_id": replacement_id}


def issue_refund(shipment_id: str, amount: float):
	shipment = _get(shipment_id)
	if amount <= 0 or amount > shipment["value"]:
		return {"success": False, "error": "Refund amount is invalid for this shipment."}
	shipment["status"] = "Refund issued"
	shipment["refund_amount"] = amount
	shipment["actions"].append({"action": "issue_refund", "amount": amount})
	return {"success": True, "message": f"Refund of ₹{amount:,.0f} issued.", "shipment_id": shipment["shipment_id"]}


def cancel_order(shipment_id: str, reason: str):
	shipment = _get(shipment_id)
	shipment["status"] = "Order cancelled"
	shipment["cancellation_reason"] = reason
	shipment["actions"].append({"action": "cancel_order", "reason": reason})
	return {"success": True, "message": "The current order has been cancelled.", "shipment_id": shipment["shipment_id"]}


def upload_damage_evidence(shipment_id: str, filename: str, file_size: int):
	shipment = _get(shipment_id)
	shipment["damage_evidence"] = {"filename": filename, "file_size": file_size}
	shipment["actions"].append({"action": "upload_damage_evidence", "filename": filename})
	return {"success": True, "message": "Damage photo attached to the shipment case.", "filename": filename}


def upload_required_document(shipment_id: str, filename: str, file_size: int, doc_type: str):
	shipment = _get(shipment_id)
	shipment["document_evidence"] = {"filename": filename, "file_size": file_size, "doc_type": doc_type}
	shipment["status"] = "Documentation received"
	shipment["actions"].append({"action": "upload_required_document", "filename": filename, "doc_type": doc_type})
	return {"success": True, "message": f"{doc_type} attached to the shipment case.", "filename": filename}


def request_missing_document(shipment_id: str, doc_type: str):
	shipment = _get(shipment_id)
	shipment["status"] = "Awaiting customer document"
	shipment["required_document"] = doc_type
	shipment["actions"].append({"action": "request_missing_document", "doc_type": doc_type})
	return {"success": True, "message": f"Requested document: {doc_type}."}


def notify_customer(shipment_id: str, message: str):
	shipment = _get(shipment_id)
	notification = {"shipment_id": shipment["shipment_id"], "message": message}
	NOTIFICATIONS.append(notification)
	shipment["actions"].append({"action": "notify_customer", "message": message})
	return {"success": True, "message": "Customer notification queued."}


def create_ops_ticket(shipment_id: str, reason: str):
	shipment = _get(shipment_id)
	ticket = {"ticket_id": f"OPS-{len(OPERATIONS_TICKETS) + 1001}", "shipment_id": shipment["shipment_id"], "reason": reason, "status": "open"}
	OPERATIONS_TICKETS.append(ticket)
	shipment["actions"].append({"action": "create_ops_ticket", "ticket_id": ticket["ticket_id"]})
	return {"success": True, "ticket": ticket}


def escalate_to_human(shipment_id: str, reason: str):
	ticket = create_ops_ticket(shipment_id, reason)
	return {"success": True, "message": "Escalated to a human operations agent.", "ticket": ticket["ticket"]}
