"""测试：本地网页接口。"""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from qdoctor import history, web

_ENV_KEYS = (
    "QDOCTOR_HOME",
    "QDOCTOR_LLM_BASE_URL",
    "QDOCTOR_LLM_API_KEY",
    "QDOCTOR_LLM_MODEL",
    "QDOCTOR_LLM_TIMEOUT",
)


class WebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._saved = {key: os.environ.get(key) for key in _ENV_KEYS}
        cls._tmp = tempfile.TemporaryDirectory()
        os.environ["QDOCTOR_HOME"] = cls._tmp.name
        for key in ("QDOCTOR_LLM_BASE_URL", "QDOCTOR_LLM_API_KEY", "QDOCTOR_LLM_MODEL"):
            os.environ[key] = ""

        cls.server = web.make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=10)
        cls.server.server_close()
        for key, value in cls._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls._tmp.cleanup()

    def setUp(self):
        path = history.history_path()
        if path.exists():
            path.unlink()

    def request(self, path, data=None, content_type="application/json", method=None):
        headers = {"Content-Type": content_type} if content_type else {}
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), exc.headers

    def get_json(self, path):
        status, body, _ = self.request(path, method="GET")
        return status, json.loads(body.decode("utf-8"))

    def post_json(self, path, payload, content_type="application/json"):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self.request(path, data=data, content_type=content_type)

    def test_index_served_with_security_headers(self):
        status, body, headers = self.request("/", method="GET")
        self.assertEqual(status, 200)
        self.assertIn("提问体检", body.decode("utf-8"))
        self.assertIn("default-src 'self'", headers.get("Content-Security-Policy", ""))

    def test_static_assets(self):
        status, body, _ = self.request("/static/app.js", method="GET")
        self.assertEqual(status, 200)
        self.assertIn("DOMContentLoaded", body.decode("utf-8"))
        status, _, _ = self.request("/static/style.css", method="GET")
        self.assertEqual(status, 200)

    def test_health(self):
        status, data = self.get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertFalse(data["llm"])
        self.assertEqual(data["max_chars"], 20000)

    def test_check(self):
        status, body, _ = self.post_json("/api/check", {"text": "帮我优化一下"})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIsInstance(data["score"], int)
        self.assertEqual(len(data["slots"]), 7)
        self.assertTrue(data["rewrite"])
        self.assertTrue(data["followups"])
        self.assertIsNone(data["llm"])

    def test_check_empty_text(self):
        status, _, _ = self.post_json("/api/check", {"text": "  "})
        self.assertEqual(status, 400)

    def test_check_too_long(self):
        status, _, _ = self.post_json("/api/check", {"text": "a" * 20001})
        self.assertEqual(status, 413)

    def test_check_with_llm_unconfigured_reports_error(self):
        status, body, _ = self.post_json(
            "/api/check", {"text": "帮我优化一下", "use_llm": True}
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIsNone(data["llm"])
        self.assertIn("未配置 LLM", data["llm_error"])

    def test_wrong_content_type(self):
        status, _, _ = self.post_json("/api/check", {"text": "问题"}, content_type="text/plain")
        self.assertEqual(status, 415)

    def test_bad_json(self):
        status, _, _ = self.request(
            "/api/check", data=b"{oops", content_type="application/json"
        )
        self.assertEqual(status, 400)

    def test_review(self):
        status, body, _ = self.post_json(
            "/api/review",
            {
                "question": "帮我优化一下",
                "answer": "一些通用建议",
                "problem": "too_general",
            },
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["problem_label"], "太泛")
        self.assertTrue(data["next_prompt"])
        self.assertTrue(data["followups"])

    def test_review_unknown_problem(self):
        status, _, _ = self.post_json(
            "/api/review",
            {"question": "问题", "answer": "回答", "problem": "nope"},
        )
        self.assertEqual(status, 400)

    def test_review_empty_answer(self):
        status, _, _ = self.post_json(
            "/api/review", {"question": "问题", "answer": "  ", "problem": "other"}
        )
        self.assertEqual(status, 400)

    def test_stats_after_check(self):
        self.post_json("/api/check", {"text": "帮我优化一下"})
        status, data = self.get_json("/api/stats?last=10")
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 1)
        self.assertIsNotNone(data["average_score"])

    def test_stats_invalid_last_falls_back(self):
        status, data = self.get_json("/api/stats?last=abc")
        self.assertEqual(status, 200)
        self.assertIn("count", data)

    def test_unknown_route(self):
        status, _, _ = self.request("/nope", method="GET")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
