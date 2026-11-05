"""测试：复盘上一轮回答，生成下一轮追问。"""

import unittest

from qdoctor.review import review
from qdoctor.rules import PROBLEM_BY_ID


class ReviewTest(unittest.TestCase):
    def test_each_problem_type_produces_its_instruction(self):
        for problem in PROBLEM_BY_ID.values():
            with self.subTest(problem=problem.id):
                result = review("帮我优化一下", "这里是一些通用建议", problem=problem.id)
                self.assertEqual(result.problem_label, problem.label)
                self.assertIn(problem.instruction, result.next_prompt)
                self.assertTrue(result.followups)

    def test_too_general_asks_to_narrow_the_scope(self):
        result = review("帮我优化一下", "通用建议", problem="too_general")
        self.assertIn("范围", result.followups[0])
        self.assertIn("只针对我的具体场景回答", result.next_prompt)

    def test_next_prompt_keeps_the_original_question_and_answer(self):
        result = review("帮我优化一下", "上一轮的回答内容", wanted="要能跑通的步骤")
        self.assertIn("帮我优化一下", result.next_prompt)
        self.assertIn("上一轮的回答内容", result.next_prompt)
        self.assertIn("要能跑通的步骤", result.next_prompt)

    def test_missing_slots_are_merged_into_followups(self):
        result = review("帮我优化一下", "通用建议", problem="other")
        labels = [slot.label for slot in result.diagnosis.missing]
        self.assertIn("验收标准", labels)
        self.assertIn("仍然缺的信息", result.next_prompt)
        self.assertIn("验收标准", result.next_prompt)

    def test_followups_are_unique_and_capped(self):
        result = review("帮我优化一下", "通用建议", problem="too_general")
        self.assertEqual(len(result.followups), len(set(result.followups)))
        self.assertLessEqual(len(result.followups), 5)

    def test_unknown_problem_raises(self):
        with self.assertRaises(ValueError):
            review("问题", "回答", problem="not-a-problem")

    def test_long_answer_is_truncated(self):
        result = review("问题", "答" * 1000, problem="other")
        self.assertIn("…", result.next_prompt)

    def test_empty_wanted_gets_a_placeholder(self):
        result = review("问题", "回答", problem="other")
        self.assertIn("（待补：用一句话说清你要的结果和验收标准）", result.next_prompt)


if __name__ == "__main__":
    unittest.main()
