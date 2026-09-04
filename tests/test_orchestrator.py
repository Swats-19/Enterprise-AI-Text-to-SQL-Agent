import unittest
from unittest.mock import patch

from skills.orchestrator import node_judge, route_after_judge


class JudgeStateTests(unittest.TestCase):
    def _state(self, attempts=0, maximum=3):
        return {
            "judge_attempts": attempts,
            "max_judge_attempts": maximum,
            "human_attempts": 0,
            "human_feedback": None,
            "feedback": None,
            "metrics": {},
            "status": "pending",
        }

    @patch("skills.orchestrator.sql_judge")
    def test_rejection_feedback_is_persisted_for_regeneration(self, judge):
        judge.return_value = {
            "judge_approved": False,
            "judge_feedback": "Include the requested price column.",
            "status": "pending",
            "metrics": {},
        }
        state = node_judge(self._state())

        self.assertEqual(state["feedback"], "Include the requested price column.")
        self.assertEqual(route_after_judge(state), "node_generator")

    @patch("skills.orchestrator.sql_judge")
    def test_final_rejection_persists_failed_status(self, judge):
        judge.return_value = {
            "judge_approved": False,
            "judge_feedback": "Still incorrect.",
            "status": "pending",
            "metrics": {},
        }
        state = node_judge(self._state(attempts=2))

        self.assertEqual(state["status"], "judge_failed")
        self.assertEqual(route_after_judge(state), "end")

    @patch("skills.orchestrator.sql_judge")
    def test_approval_persists_human_attempt_count(self, judge):
        judge.return_value = {
            "judge_approved": True,
            "judge_feedback": "Approved.",
            "status": "pending",
            "metrics": {},
        }
        state = node_judge(self._state())

        self.assertEqual(state["human_attempts"], 1)
        self.assertEqual(route_after_judge(state), "node_human")


if __name__ == "__main__":
    unittest.main()
