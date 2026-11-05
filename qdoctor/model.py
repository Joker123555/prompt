"""结果类型与序列化。领域层只依赖标准库，不做 I/O。"""

from __future__ import annotations

from dataclasses import asdict, dataclass

FOUND = "found"
WEAK = "weak"
MISSING = "missing"


@dataclass(frozen=True)
class SlotFinding:
    """一个提问要素的检测结果。"""

    slot_id: str
    label: str
    status: str
    weight: int
    evidence: tuple[str, ...] = ()
    excerpt: str = ""
    advice: str = ""
    question: str = ""
    placeholder: str = ""


@dataclass(frozen=True)
class PatternFinding:
    """一个反模式的命中结果。"""

    pattern_id: str
    label: str
    penalty: int
    evidence: tuple[str, ...] = ()
    advice: str = ""
    followup: str = ""


@dataclass(frozen=True)
class Diagnosis:
    text: str
    score: int
    slots: tuple[SlotFinding, ...]
    patterns: tuple[PatternFinding, ...]
    followups: tuple[str, ...]

    @property
    def summary(self) -> str:
        if self.score >= 95:
            return "要素齐全，可以直接问。"
        if self.score >= 80:
            return "基本齐全，补一两处会更稳。"
        if self.score >= 50:
            return "缺了几个关键要素，答案容易跑偏。"
        return "缺的信息较多，建议先回答下面的追问，再重新组织问题。"

    @property
    def missing(self) -> tuple[SlotFinding, ...]:
        return tuple(item for item in self.slots if item.status == MISSING)

    @property
    def weak(self) -> tuple[SlotFinding, ...]:
        return tuple(item for item in self.slots if item.status == WEAK)

    def slot(self, slot_id: str) -> SlotFinding:
        for item in self.slots:
            if item.slot_id == slot_id:
                return item
        raise KeyError(slot_id)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "score": self.score,
            "summary": self.summary,
            "slots": [asdict(item) for item in self.slots],
            "patterns": [asdict(item) for item in self.patterns],
            "followups": list(self.followups),
        }


@dataclass(frozen=True)
class ReviewResult:
    """复盘模式的结果：诊断 + 下一轮追问。"""

    question: str
    answer: str
    wanted: str
    problem: str
    problem_label: str
    diagnosis: Diagnosis
    followups: tuple[str, ...]
    next_prompt: str

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "wanted": self.wanted,
            "problem": self.problem,
            "problem_label": self.problem_label,
            "diagnosis": self.diagnosis.to_dict(),
            "followups": list(self.followups),
            "next_prompt": self.next_prompt,
        }
