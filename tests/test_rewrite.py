"""测试：诊断结果 -> 七段式改写稿。"""

import unittest

from qdoctor.diagnose import diagnose
from qdoctor.rewrite import build_rewrite

LABELS = ("目标", "背景", "约束", "期望输出", "验收标准", "受众/用途", "示例")


class RewriteTest(unittest.TestCase):
    def test_all_sections_are_present(self):
        text = build_rewrite(diagnose("帮我优化一下"))
        for label in LABELS:
            self.assertIn(f"【{label}】", text)

    def test_missing_slots_are_marked_as_placeholders(self):
        text = build_rewrite(diagnose("帮我优化一下"))
        self.assertIn("（待补：", text)
        self.assertIn("待补：怎样算解决", text)

    def test_detected_content_is_filled_in(self):
        text = build_rewrite(diagnose("我想把代码改成异步的，必须只用标准库。"))
        self.assertIn("我想把代码改成异步的", text)
        self.assertIn("必须只用标准库", text)

    def test_header_tells_the_model_to_ask_instead_of_guess(self):
        text = build_rewrite(diagnose("帮我优化一下"))
        self.assertIn("信息不足时先向我提问", text)

    def test_footer_asks_for_self_check(self):
        text = build_rewrite(diagnose("帮我优化一下"))
        self.assertIn("对照【验收标准】自检", text)

    def test_empty_input_still_produces_a_full_template(self):
        text = build_rewrite(diagnose(""))
        for label in LABELS:
            self.assertIn(f"【{label}】", text)


if __name__ == "__main__":
    unittest.main()
