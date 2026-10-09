"""Exercise actual Agent/WebUI callback code without importing either runtime.

Usage: python3 check_clarify_agent_compat.py WEBUI_ROOT AGENT_ROOT
Only pure functions are extracted; no services, credentials or state are loaded.
"""
import ast
import inspect
import json
from pathlib import Path
import sys
import threading
import unittest


def extract(path, names, namespace):
    tree = ast.parse(Path(path).read_text())
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in functions} == set(names)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *functions], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)


webui, agent = map(Path, sys.argv[1:3])
sys.argv = sys.argv[:1]
tool = {"json": json, "inspect": inspect, "RECOMMENDED_LABEL": "(Recommended)",
        "TIMEOUT_RESPONSE": "The user did not provide a response within the time limit. "
                            "Use your best judgement to make the choice and proceed."}
extract(agent / "tools/clarify_tool.py", ["_run_batch", "_batch_result", "_is_timeout",
        "_accepts_kwarg", "_json_as", "_clean_answer", "strip_recommended",
        "_parse_multi_select_response", "_invoke_callback"], tool)


class ClarifyCompatibility(unittest.TestCase):
    def bridge(self, responses, cancelled=False):
        self.shown = []
        iterator = iter(responses)
        cancel = threading.Event()
        if cancelled:
            cancel.set()

        def ask(question, choices, *_):
            self.shown.append((question, choices))
            return next(iterator)

        ns = {"session_id": "isolated-test", "cancel_event": cancel, "put": None,
              "_clarify_ask_one": ask, "_CLARIFY_NO_RESPONSE_TEXT": tool["TIMEOUT_RESPONSE"]}
        extract(webui / "api/streaming.py", ["_clarify_callback", "_clarify_callback_impl",
                "_clarify_batch_reply"], ns)
        return ns["_clarify_callback"]

    @staticmethod
    def questions():
        return [{"qid": "q0", "id": None, "question": "Which database should we use?",
                 "choices": ["Postgres (Recommended)", "SQLite"],
                 "choices_offered": ["Postgres", "SQLite"], "multi_select": False},
                {"qid": "q1", "id": "timing", "question": "When should we start?",
                 "choices": None, "choices_offered": None, "multi_select": False}]

    def test_current_agent_batch_displays_questions_and_returns_answers(self):
        result = json.loads(tool["_run_batch"](self.questions(),
                            self.bridge([("Postgres (Recommended)", False), ("Now", False)]), ""))
        self.assertEqual([q for q, _ in self.shown], [q["question"] for q in self.questions()])
        self.assertEqual([r["user_response"] for r in result["responses"]], ["Postgres", "Now"])
        self.assertEqual(self.shown[0][1], self.questions()[0]["choices"])

    def test_timeout_keeps_earlier_answer_and_marks_unanswered_batch(self):
        result = json.loads(tool["_run_batch"](self.questions(),
                            self.bridge([("Postgres", False), ("", True)]), ""))
        self.assertTrue(result["timed_out"])
        self.assertEqual([r["user_response"] for r in result["responses"]], ["Postgres", ""])

    def test_cancellation_is_not_timeout(self):
        result = json.loads(tool["_run_batch"](self.questions(),
                            self.bridge([("", False)], cancelled=True), ""))
        self.assertNotIn("timed_out", result)
        self.assertEqual(len(self.shown), 1)

    def test_undelivered_prompt_reports_reason(self):
        result = json.loads(tool["_run_batch"](self.questions(), self.bridge([None]), ""))
        self.assertTrue(result["timed_out"])
        self.assertIn("not available", result["notice"])

    def test_legacy_single_and_positional_batch_remain_supported(self):
        self.assertEqual(self.bridge([("Now", False)])("When?", None), "Now")
        reply = self.bridge([("Postgres", False), ("Now", False)])(self.questions())
        self.assertEqual(reply["answers"], {"q0": "Postgres", "q1": "Now"})


if __name__ == "__main__":
    unittest.main()
