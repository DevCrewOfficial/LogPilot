import os
import unittest

os.environ["AGENT_LLM_ENABLED"] = "false"

import approvals
import mock_sys
from agent.core import resume_approval, run_agent
from agent.tools import execute_tool
from risk_policy import assess_risk


class HitlTests(unittest.TestCase):
    def setUp(self):
        approvals._APPROVALS.clear()
        mock_sys.SHIPMENTS["SHIP001"]["value"] = 2000
        mock_sys.SHIPMENTS["SHIP001"]["order_date"] = "2026-08-10"
        mock_sys.SHIPMENTS["SHIP002"]["value"] = 85000
        mock_sys.SHIPMENTS["SHIP002"]["order_date"] = "2026-08-12"
        mock_sys.SHIPMENTS["SHIP002"].pop("replacement_id", None)

    def test_low_value_replacement_is_automatic(self):
        result = run_agent("SHIP001 damaged package, please replace it")
        self.assertNotIn("approval", result)
        self.assertTrue(result["shipment"].get("replacement_id"))

    def test_high_value_replacement_is_blocked(self):
        result = run_agent("SHIP002 damaged package, please replace it")
        self.assertEqual(result["approval"]["status"], "PENDING")
        self.assertFalse(mock_sys.SHIPMENTS["SHIP002"].get("replacement_id"))

    def test_high_value_refund_is_blocked_at_tool_boundary(self):
        result = execute_tool("issue_refund", {"shipment_id": "SHIP002", "amount": 20000}, request="refund request")
        self.assertTrue(result["requires_human"])
        self.assertFalse(mock_sys.SHIPMENTS["SHIP002"].get("refund_amount"))

    def test_policy_exception_suspicious_and_uncertain_escalate(self):
        shipment = mock_sys.SHIPMENTS["SHIP001"]
        self.assertTrue(assess_risk("request", shipment, {"requested_action": "redirect_shipment", "policy_exception": True})["requires_human"])
        self.assertEqual(assess_risk("request", shipment, {"requested_action": "initiate_replacement", "suspicious": True})["risk_level"], "CRITICAL")
        self.assertTrue(assess_risk("request", shipment, {"requested_action": "initiate_replacement", "uncertain": True})["requires_human"])

    def test_approval_executes_and_cannot_repeat(self):
        result = run_agent("SHIP002 damaged package, replace it approval test")
        approval_id = result["approval"]["id"]
        approvals.approve(approval_id, "reviewer")
        resumed = resume_approval(approval_id)
        self.assertTrue(resumed["success"])
        with self.assertRaises(ValueError):
            approvals.approve(approval_id, "reviewer")

    def test_rejection_never_executes(self):
        result = run_agent("SHIP002 damaged package, reject test")
        approval_id = result["approval"]["id"]
        approvals.reject(approval_id, "reviewer", "Not eligible")
        rejected = resume_approval(approval_id)
        self.assertFalse(rejected["success"])
        self.assertFalse(mock_sys.SHIPMENTS["SHIP002"].get("replacement_id"))
        with self.assertRaises(ValueError):
            approvals.reject(approval_id, "reviewer", "Again")

    def test_duplicate_request_reuses_approval(self):
        first = run_agent("SHIP002 damaged package, duplicate test")
        second = run_agent("SHIP002 damaged package, duplicate test")
        self.assertEqual(first["approval"]["id"], second["approval"]["id"])
        self.assertEqual(len(approvals.list_all()), 1)

    def test_severe_delay_cancels_and_requests_customer_choice(self):
        result = run_agent("SHIP006 delayed shipment, I did not receive my product")
        self.assertEqual(result["shipment"]["status"], "Order cancelled")
        answer = result["answer"].lower()
        self.assertIn("refund", answer)
        self.assertTrue("again" in answer or "sent" in answer)

    def test_price_and_order_date_must_match_database(self):
        verified = run_agent("SHIP001 damaged package, replace it", order_value=2000, order_date="2026-08-10")
        self.assertNotIn("verification", verified)
        invalid = run_agent("SHIP001 damaged package, replace it", order_value=999, order_date="2026-08-10")
        self.assertFalse(invalid["verification"]["verified"])
        self.assertNotIn("initiate_replacement", [step["tool"] for step in invalid["trail"]])


if __name__ == "__main__":
    unittest.main()
