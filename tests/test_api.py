import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import api


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("api.run_agent")
    def test_non_pro_stream_returns_ui_compatible_final_event(self, run_agent):
        run_agent.return_value = {
            "status": "success",
            "sql": "SELECT customer_id FROM customers LIMIT 1;",
            "columns": ["customer_id"],
            "data": [(1,)],
            "summary": "One customer.",
            "judge_approved": True,
            "judge_feedback": "Approved.",
            "attempts": {"judge": 1},
        }
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://example.invalid/test",
                "DEFAULT_EXECUTION_MODE": "non_pro",
            },
        ):
            response = self.client.post(
                "/deep-agent/stream",
                json={
                    "context_id": "test-context",
                    "human_query": "Show one customer",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: start", response.text)
        self.assertIn("event: sql_generated", response.text)
        self.assertIn("event: judge_approved", response.text)
        self.assertIn("event: final", response.text)
        self.assertIn('"customer_id": 1', response.text)

    @patch("api.run_agent")
    def test_pro_stream_returns_approval_event(self, run_agent):
        run_agent.return_value = {
            "status": "needs_human_approval",
            "thread_id": "graph-thread",
            "sql": "SELECT 1;",
            "judge_feedback": "Approved.",
            "attempts": {"judge": 1},
        }
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://example.invalid/test",
                "DEFAULT_EXECUTION_MODE": "pro",
            },
        ):
            response = self.client.post(
                "/deep-agent/stream",
                json={
                    "context_id": "test-context",
                    "human_query": "Run a safe query",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: judge_approved", response.text)
        self.assertNotIn("event: judge_rejected", response.text)
        self.assertIn("event: approval_required", response.text)
        self.assertIn('"execution_mode": "pro"', response.text)

    @patch("api.run_agent")
    def test_approval_retry_returns_a_new_pending_approval(self, run_agent):
        run_agent.return_value = {
            "status": "needs_human_approval",
            "thread_id": "graph-thread",
            "sql": "SELECT customer_id FROM customers LIMIT 10;",
            "judge_feedback": "Regenerated query is safe.",
        }
        with api._pending_lock:
            api._pending_approvals["original-approval"] = {
                "thread_id": "graph-thread",
                "context_id": "test-context",
            }

        response = self.client.post(
            "/approvals/original-approval/approve",
            json={"reviewer_comment": "Approved"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "needs_human_approval")
        self.assertNotEqual(payload["approval_id"], "original-approval")
        self.assertEqual(
            payload["generated_sql"],
            "SELECT customer_id FROM customers LIMIT 10;",
        )


if __name__ == "__main__":
    unittest.main()
