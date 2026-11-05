"""纯函数：复盘上一轮回答，生成下一轮追问。"""

from __future__ import annotations

from .diagnose import diagnose
from .model import Diagnosis, ReviewResult
from .rules import PROBLEM_BY_ID, ProblemSpec

_MAX_ANSWER_IN_PROMPT = 600
_MAX_QUESTION_IN_PROMPT = 400
_MAX_FOLLOWUPS = 5


def review(question: str, answer: str, wanted: str = "", problem: str = "other") -> ReviewResult:
    spec = PROBLEM_BY_ID.get(problem)
    if spec is None:
        raise ValueError(f"未知的问题类型：{problem}")

    diagnosis = diagnose(question)
    followups = _merge_followups(spec, diagnosis.followups)
    next_prompt = _build_next_prompt(question, answer, wanted, spec, diagnosis)

    return ReviewResult(
        question=question,
        answer=answer,
        wanted=wanted,
        problem=problem,
        problem_label=spec.label,
        diagnosis=diagnosis,
        followups=followups,
        next_prompt=next_prompt,
    )


def _merge_followups(spec: ProblemSpec, slot_questions: tuple[str, ...]) -> tuple[str, ...]:
    candidates = list(spec.questions) + list(slot_questions)
    result: list[str] = []
    for question in candidates:
        if question and question not in result:
            result.append(question)
        if len(result) >= _MAX_FOLLOWUPS:
            break
    return tuple(result)


def _build_next_prompt(
    question: str,
    answer: str,
    wanted: str,
    spec: ProblemSpec,
    diagnosis: Diagnosis,
) -> str:
    blocks = [
        "关于上一个问题，你的回答没有满足我的需求。",
        f"问题类型：{spec.label}（{spec.description}）。",
        "",
        "【我真正想要的】",
        wanted.strip() or "（待补：用一句话说清你要的结果和验收标准）",
        "",
        "【原问题】",
        _truncate(question, _MAX_QUESTION_IN_PROMPT),
    ]

    if answer.strip():
        blocks += ["", "【上一轮回答（节选）】", _truncate(answer, _MAX_ANSWER_IN_PROMPT)]

    missing = [slot.label for slot in diagnosis.missing]
    weak = [slot.label for slot in diagnosis.weak]
    if missing:
        blocks += ["", "【仍然缺的信息】", "、".join(missing)]
    if weak:
        blocks += ["", "【需要更具体的信息】", "、".join(weak)]

    blocks += [
        "",
        "【这次的要求】",
        spec.instruction,
        "",
        "如果信息不足，请先向我提问，不要猜测。",
    ]
    return "\n".join(blocks)


def _truncate(text: str, limit: int) -> str:
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"
