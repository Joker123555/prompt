"""纯函数：把诊断结果拼成可直接粘贴的七段式提问。"""

from __future__ import annotations

from .model import MISSING, WEAK, Diagnosis

_HEADER = "请基于以下信息回答。信息不足时先向我提问，不要猜测。"
_FOOTER = "回答后请逐条对照【验收标准】自检；有做不到的地方直接说明。"


def build_rewrite(diagnosis: Diagnosis) -> str:
    lines = [_HEADER, ""]
    for slot in diagnosis.slots:
        lines.append(f"【{slot.label}】")
        if slot.status == MISSING or not slot.excerpt:
            lines.append(f"（待补：{slot.placeholder}）")
        elif slot.status == WEAK:
            lines.append(f"{slot.excerpt}（建议补充更具体的信息）")
        else:
            lines.append(slot.excerpt)
        lines.append("")
    lines.append(_FOOTER)
    return "\n".join(lines).strip()
