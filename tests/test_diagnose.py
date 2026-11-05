"""测试：问题文本 -> 槽位与反模式。"""

import unittest

from qdoctor.diagnose import diagnose
from qdoctor.model import FOUND, MISSING, WEAK
from qdoctor.rules import SLOTS

SPECIFIED = (
    "我在做一个 Python 3.12 的 CLI 工具，我想把同步代码改成 asyncio，"
    "必须只用标准库，输出一个可直接替换的函数和三条注意事项，"
    "跑通现有 unittest 就算完成，这份说明是给同事看的，"
    "例如 tests/test_api.py 里的写法。"
)


class DiagnoseTest(unittest.TestCase):
    def test_empty_text_marks_every_slot_missing(self):
        result = diagnose("")
        self.assertEqual(result.score, 0)
        self.assertEqual(len(result.slots), len(SLOTS))
        self.assertTrue(all(slot.status == MISSING for slot in result.slots))
        self.assertEqual(result.patterns, ())
        self.assertGreater(len(result.followups), 0)

    def test_well_specified_question_scores_high(self):
        result = diagnose(SPECIFIED)
        self.assertGreaterEqual(result.score, 95)
        self.assertTrue(all(slot.status == FOUND for slot in result.slots), result.slots)
        self.assertEqual(result.patterns, ())

    def test_goal_marker_is_reported_with_evidence(self):
        result = diagnose("我想把这段代码改成异步的")
        goal = result.slot("goal")
        self.assertEqual(goal.status, FOUND)
        self.assertTrue(goal.evidence)
        self.assertIn("我想", goal.evidence[0])

    def test_missing_acceptance_is_flagged(self):
        text = (
            "我在做一个 CLI 工具，我想把代码改成异步的，必须只用标准库，"
            "输出一个函数，给同事看，例如 tests/test_api.py 的写法。"
        )
        result = diagnose(text)
        self.assertEqual(result.slot("acceptance").status, MISSING)
        self.assertIn("验收标准", [slot.label for slot in result.missing])

    def test_naming_code_as_object_is_not_an_output_request(self):
        result = diagnose("帮我优化一下这段代码，报错了，怎么办？")
        self.assertEqual(result.slot("output").status, MISSING)
        self.assertEqual(result.slot("context").excerpt, "报错了")

    def test_output_request_is_detected(self):
        result = diagnose("输出一个可直接替换的函数")
        self.assertEqual(result.slot("output").status, FOUND)

    def test_use_case_is_detected(self):
        result = diagnose("这份清单给我自己用")
        self.assertEqual(result.slot("audience").status, FOUND)

    def test_excerpt_comes_from_the_matching_clause(self):
        result = diagnose("我想把代码改成异步的，必须只用标准库。")
        self.assertEqual(result.slot("goal").excerpt, "我想把代码改成异步的")
        self.assertEqual(result.slot("constraints").excerpt, "必须只用标准库")

    def test_multi_question_pattern(self):
        result = diagnose("怎么装？怎么配？怎么跑？")
        self.assertIn("multi_question", [pattern.pattern_id for pattern in result.patterns])

    def test_two_questions_without_connector_is_not_multi_question(self):
        result = diagnose("怎么装？怎么配？")
        self.assertNotIn("multi_question", [pattern.pattern_id for pattern in result.patterns])

    def test_no_material_pattern(self):
        result = diagnose("报错了，怎么办？")
        self.assertIn("no_material", [pattern.pattern_id for pattern in result.patterns])

    def test_error_material_suppresses_no_material(self):
        result = diagnose("报错了：TypeError: expected str，怎么办？")
        self.assertNotIn("no_material", [pattern.pattern_id for pattern in result.patterns])

    def test_unverifiable_pattern(self):
        result = diagnose("帮我优化一下")
        self.assertIn("unverifiable", [pattern.pattern_id for pattern in result.patterns])

    def test_unverifiable_pattern_yields_to_acceptance(self):
        result = diagnose("帮我优化一下，要求跑通现有测试。")
        self.assertNotIn("unverifiable", [pattern.pattern_id for pattern in result.patterns])

    def test_vague_verb_pattern(self):
        result = diagnose("帮我看一下")
        self.assertIn("vague_verb", [pattern.pattern_id for pattern in result.patterns])

    def test_assumed_premise_pattern(self):
        result = diagnose("为什么 Python 的 GIL 不行？")
        self.assertIn("assumed_premise", [pattern.pattern_id for pattern in result.patterns])

    def test_no_scope_pattern(self):
        result = diagnose("怎么学编程？")
        self.assertIn("no_scope", [pattern.pattern_id for pattern in result.patterns])

    def test_constraints_suppress_no_scope(self):
        result = diagnose("怎么学 Python？我每天只有 1 小时，三个月内想做出一个爬虫。")
        self.assertNotIn("no_scope", [pattern.pattern_id for pattern in result.patterns])

    def test_score_stays_in_range(self):
        texts = [
            "",
            "？",
            "帮我优化一下",
            "报错了，怎么办？",
            SPECIFIED,
            "我想" + "很长的一段背景" * 20000,
        ]
        for text in texts:
            with self.subTest(text=text[:20]):
                self.assertGreaterEqual(diagnose(text).score, 0)
                self.assertLessEqual(diagnose(text).score, 100)

    def test_chinese_punctuation_is_handled(self):
        result = diagnose("报错了，怎么办？")
        self.assertEqual(result.slot("context").status, WEAK)
        self.assertTrue(result.followups)

    def test_followups_are_unique(self):
        result = diagnose("帮我优化一下")
        self.assertEqual(len(result.followups), len(set(result.followups)))


if __name__ == "__main__":
    unittest.main()
