"""测试：可选 LLM 层的请求构造与降级。"""

import json
import unittest
import urllib.error

from qdoctor import llm
from qdoctor.diagnose import diagnose
from qdoctor.rules import PROBLEM_BY_ID

CONFIG = llm.LlmConfig(
    base_url="https://api.example.com/v1",
    api_key="secret",
    model="model-x",
    timeout=5.0,
)


class LlmConfigTest(unittest.TestCase):
    def test_from_env_returns_none_when_incomplete(self):
        self.assertIsNone(llm.LlmConfig.from_env({}))
        self.assertIsNone(
            llm.LlmConfig.from_env({"QDOCTOR_LLM_BASE_URL": "https://x"})
        )
        self.assertIsNone(
            llm.LlmConfig.from_env(
                {"QDOCTOR_LLM_BASE_URL": "https://x", "QDOCTOR_LLM_API_KEY": "k"}
            )
        )

    def test_from_env_strips_and_defaults(self):
        config = llm.LlmConfig.from_env(
            {
                "QDOCTOR_LLM_BASE_URL": " https://x/v1/ ",
                "QDOCTOR_LLM_API_KEY": " k ",
                "QDOCTOR_LLM_MODEL": " m ",
            }
        )
        self.assertEqual(config.base_url, "https://x/v1")
        self.assertEqual(config.api_key, "k")
        self.assertEqual(config.model, "m")
        self.assertEqual(config.timeout, 30.0)

    def test_is_configured(self):
        self.assertFalse(llm.is_configured({}))
        self.assertTrue(
            llm.is_configured(
                {
                    "QDOCTOR_LLM_BASE_URL": "https://x",
                    "QDOCTOR_LLM_API_KEY": "k",
                    "QDOCTOR_LLM_MODEL": "m",
                }
            )
        )


class CompleteTest(unittest.TestCase):
    def test_request_shape(self):
        captured = {}

        def transport(url, headers, payload, timeout):
            captured.update(url=url, headers=headers, payload=payload, timeout=timeout)
            return json.dumps({"choices": [{"message": {"content": "结果"}}]})

        text = llm.complete([{"role": "user", "content": "hi"}], CONFIG, transport)
        self.assertEqual(text, "结果")
        self.assertEqual(captured["url"], "https://api.example.com/v1/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(captured["payload"]["model"], "model-x")
        self.assertEqual(captured["timeout"], 5.0)

    def test_transport_error_becomes_llm_error(self):
        def boom(*args):
            raise RuntimeError("网络断了")

        with self.assertRaises(llm.LlmError):
            llm.complete([], CONFIG, boom)

    def test_http_error_reports_status(self):
        def unauthorized(*args):
            raise urllib.error.HTTPError("https://x", 401, "Unauthorized", {}, None)

        with self.assertRaises(llm.LlmError) as ctx:
            llm.complete([], CONFIG, unauthorized)
        self.assertIn("401", str(ctx.exception))

    def test_bad_json_becomes_llm_error(self):
        with self.assertRaises(llm.LlmError):
            llm.complete([], CONFIG, lambda *args: "not json")

    def test_empty_content_becomes_llm_error(self):
        payload = json.dumps({"choices": [{"message": {"content": "  "}}]})
        with self.assertRaises(llm.LlmError):
            llm.complete([], CONFIG, lambda *args: payload)


class PromptTest(unittest.TestCase):
    def test_rewrite_question_sends_diagnosis(self):
        captured = {}

        def transport(url, headers, payload, timeout):
            captured.update(payload)
            return json.dumps({"choices": [{"message": {"content": "改写"}}]})

        text = llm.rewrite_question("帮我优化一下", diagnose("帮我优化一下"), CONFIG, transport)
        self.assertEqual(text, "改写")
        user = captured["messages"][1]["content"]
        self.assertIn("原始问题", user)
        self.assertIn("帮我优化一下", user)
        self.assertIn("验收标准", user)

    def test_review_next_round_sends_problem(self):
        captured = {}

        def transport(url, headers, payload, timeout):
            captured.update(payload)
            return json.dumps({"choices": [{"message": {"content": "追问"}}]})

        text = llm.review_next_round(
            "问题", "回答", "想要的", PROBLEM_BY_ID["too_general"], CONFIG, transport
        )
        self.assertEqual(text, "追问")
        user = captured["messages"][1]["content"]
        self.assertIn("太泛", user)
        self.assertIn("这次的要求", user)


if __name__ == "__main__":
    unittest.main()
