"""测试：本地历史只存元数据，统计可聚合。"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from qdoctor import history
from qdoctor.diagnose import diagnose
from qdoctor.history import HistoryLoad, summarize


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "history.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_does_not_store_question_text(self):
        question = "这是绝对不能写进历史记录的敏感原文"
        history.record("check", diagnose(question), path=self.path)

        content = self.path.read_text(encoding="utf-8")
        self.assertNotIn("敏感原文", content)

        entry = json.loads(content.strip())
        self.assertEqual(entry["mode"], "check")
        self.assertGreaterEqual(entry["score"], 0)
        self.assertIn("missing", entry)
        self.assertEqual(entry["chars"], len(question))

    def test_record_review_keeps_problem_type(self):
        history.record(
            "review", diagnose("帮我优化一下"), problem="too_general", path=self.path
        )
        entry = json.loads(self.path.read_text(encoding="utf-8").strip())
        self.assertEqual(entry["problem"], "too_general")

    def test_record_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            history.record("unknown", diagnose("问题"), path=self.path)

    def test_load_skips_corrupt_lines(self):
        self.path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "ts": "t",
                            "mode": "check",
                            "score": 50,
                            "missing": [],
                            "patterns": [],
                        }
                    ),
                    "{broken",
                    "",
                    json.dumps({"mode": "check"}),
                ]
            ),
            encoding="utf-8",
        )
        loaded = history.load(self.path)
        self.assertEqual(len(loaded.entries), 1)
        self.assertEqual(loaded.skipped, 2)

    def test_load_missing_file_returns_empty(self):
        loaded = history.load(self.path / "nope.jsonl")
        self.assertEqual(loaded.entries, ())
        self.assertEqual(loaded.skipped, 0)

    def test_summarize_averages_and_ranks(self):
        entries = (
            {
                "mode": "check",
                "score": 40,
                "missing": ["acceptance", "context"],
                "patterns": ["no_material"],
                "ts": "1",
            },
            {
                "mode": "check",
                "score": 60,
                "missing": ["acceptance"],
                "patterns": [],
                "ts": "2",
            },
        )
        summary = summarize(HistoryLoad(entries, 0), last=10)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["average_score"], 50.0)
        self.assertEqual(
            summary["top_missing"][0],
            {"id": "acceptance", "label": "验收标准", "count": 2},
        )
        self.assertEqual(summary["top_patterns"][0]["label"], "只报现象不报材料")

    def test_summarize_respects_last_window(self):
        entries = tuple(
            {"mode": "check", "score": score, "missing": [], "patterns": [], "ts": str(index)}
            for index, score in enumerate((10, 20, 30))
        )
        summary = summarize(HistoryLoad(entries, 0), last=2)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["average_score"], 25.0)

    def test_summarize_empty(self):
        summary = summarize(HistoryLoad((), 0))
        self.assertEqual(summary["count"], 0)
        self.assertIsNone(summary["average_score"])
        self.assertEqual(summary["top_missing"], [])

    def test_history_path_honours_environment(self):
        with mock.patch.dict(os.environ, {"QDOCTOR_HOME": self._tmp.name}):
            self.assertEqual(
                history.history_path(), Path(self._tmp.name) / "history.jsonl"
            )


if __name__ == "__main__":
    unittest.main()
