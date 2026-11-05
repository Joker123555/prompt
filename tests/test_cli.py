"""测试：CLI 的输入来源、输出与退出码。"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_KEYS = (
    "QDOCTOR_HOME",
    "QDOCTOR_LLM_BASE_URL",
    "QDOCTOR_LLM_API_KEY",
    "QDOCTOR_LLM_MODEL",
    "QDOCTOR_LLM_TIMEOUT",
)


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args, input_text=None):
        env = os.environ.copy()
        for key in _ENV_KEYS:
            env.pop(key, None)
        env["QDOCTOR_HOME"] = str(self.home)
        return subprocess.run(
            [sys.executable, "-m", "qdoctor", *args],
            cwd=REPO_ROOT,
            env=env,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def test_check_prints_diagnosis_and_rewrite(self):
        result = self.run_cli("check", "帮我优化一下")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("提问体检", result.stdout)
        self.assertIn("改写后的提问", result.stdout)
        self.assertIn("【验收标准】", result.stdout)

    def test_check_json(self):
        result = self.run_cli("check", "报错了，怎么办？", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["mode"], "check")
        self.assertIsInstance(data["score"], int)
        self.assertEqual(len(data["slots"]), 7)
        self.assertTrue(data["rewrite"])
        self.assertIsNone(data["llm_error"])

    def test_check_reads_file(self):
        path = self.home / "question.txt"
        path.write_text("帮我优化一下", encoding="utf-8")
        result = self.run_cli("check", "--file", str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("提问体检", result.stdout)

    def test_check_reads_stdin(self):
        result = self.run_cli("check", input_text="报错了，怎么办？")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("提问体检", result.stdout)

    def test_empty_input_is_usage_error(self):
        result = self.run_cli("check", input_text="")
        self.assertEqual(result.returncode, 2)
        self.assertIn("问题文本为空", result.stderr)

    def test_missing_file_is_runtime_error(self):
        result = self.run_cli("check", "--file", str(self.home / "nope.txt"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("读不到文件", result.stderr)

    def test_positional_and_file_together_is_usage_error(self):
        path = self.home / "question.txt"
        path.write_text("问题", encoding="utf-8")
        result = self.run_cli("check", "问题", "--file", str(path))
        self.assertEqual(result.returncode, 2)

    def test_llm_without_config_keeps_rule_output(self):
        result = self.run_cli("check", "帮我优化一下", "--llm")
        self.assertEqual(result.returncode, 1)
        self.assertIn("提问体检", result.stdout)
        self.assertIn("QDOCTOR_LLM_API_KEY", result.stderr)

    def test_review_prints_next_round(self):
        result = self.run_cli(
            "review", "-q", "帮我优化一下", "-a", "通用建议", "-p", "too_general"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("复盘 · 太泛", result.stdout)
        self.assertIn("下一轮追问", result.stdout)

    def test_review_reads_at_files(self):
        question = self.home / "q.txt"
        answer = self.home / "a.txt"
        question.write_text("帮我优化一下", encoding="utf-8")
        answer.write_text("通用建议", encoding="utf-8")
        result = self.run_cli(
            "review", "-q", "@" + str(question), "-a", "@" + str(answer)
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("复盘", result.stdout)

    def test_stats_empty_then_after_check(self):
        empty = self.run_cli("stats")
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertIn("还没有记录", empty.stdout)

        self.run_cli("check", "帮我优化一下")
        stats = self.run_cli("stats")
        self.assertEqual(stats.returncode, 0, stats.stderr)
        self.assertIn("平均分", stats.stdout)
        self.assertIn("最常缺的要素", stats.stdout)

    def test_stats_json(self):
        self.run_cli("check", "帮我优化一下")
        result = self.run_cli("stats", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["count"], 1)
        self.assertIsInstance(data["average_score"], (int, float))

    def test_stats_rejects_non_positive_last(self):
        result = self.run_cli("stats", "--last", "0")
        self.assertEqual(result.returncode, 2)

    def test_version(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("qdoctor 0.1.0", result.stdout)


if __name__ == "__main__":
    unittest.main()
