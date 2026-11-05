"""纯函数：把一段提问文本诊断成槽位与反模式。"""

from __future__ import annotations

import re

from .model import FOUND, MISSING, WEAK, Diagnosis, PatternFinding, SlotFinding
from .rules import PATTERN_BY_ID, SLOT_BY_ID, SLOTS, SlotSpec

_CLAUSE_SPLIT = re.compile(r"[。！？!?；;\n，,]+")
_SNIPPET_RADIUS = 10
_MAX_EXCERPT = 80
_MAX_FOLLOWUPS = 5

# 反模式检测用的词表。放在这里而不是 rules.py，是因为它们需要组合判断。
_SYMPTOM = re.compile(r"报错|错误|失败|不行|没反应|崩溃|异常")
_MATERIAL = re.compile(
    r"```|traceback|exception|\w+error\b|error\s*:|errno|https?\s*\d{3}|状态码|"
    r"\d+\s*行|日志|截图|"
    r"\.(?:py|js|ts|tsx|jsx|java|go|rs|cpp|cs|php|rb|sql|json|yaml|yml|toml|md)\b|"
    r"[`“\"].{4,}[`”\"]",
    re.IGNORECASE,
)
_UNVERIFIABLE = re.compile(
    r"好一点|更好|优化一下|改进一下|提升一下|调整一下|美化|润色|"
    r"差不多|看着办|随便|处理一下|搞一下|弄一下|整一下"
)
_VAGUE_VERB = re.compile(r"(?:搞|弄|整|处理|看|安排)(?:一下|下)?(?:[。！!，,？?\s]|$)|帮个忙|帮我看?看")
_ASSUMED = re.compile(r"为什么.{0,20}(?:不行|不能|失败|没用|不生效|报错)|是不是.{0,10}(?:因为|由于)|既然.{0,20}为什么")
_NO_SCOPE = re.compile(r"怎么(?:学|做|选|开始|提升|入门|赚钱)|如何(?:学|做|选|开始|提升|入门)|有什么(?:好|推荐).{0,6}(?:书|工具|方法)")
_CONNECTOR = re.compile(r"另外|还有|顺便|以及|同时|再者")
_QUESTION_MARK = re.compile(r"[?？]")


def diagnose(text: str) -> Diagnosis:
    """返回诊断结果。空文本视为所有要素缺失，不抛异常。"""
    source = text or ""
    slots = tuple(_slot_finding(spec, source) for spec in SLOTS)

    if source.strip():
        patterns = _pattern_findings(source)
        raw = 100.0
        for finding in slots:
            if finding.status == MISSING:
                raw -= finding.weight
            elif finding.status == WEAK:
                raw -= finding.weight * 0.5
        raw -= sum(pattern.penalty for pattern in patterns)
        score = max(0, min(100, int(round(raw))))
    else:
        patterns = ()
        score = 0

    return Diagnosis(
        text=source,
        score=score,
        slots=slots,
        patterns=patterns,
        followups=_followups(slots, patterns),
    )


def _slot_finding(spec: SlotSpec, text: str) -> SlotFinding:
    strong = _matches(spec.strong, text)
    weak = _matches(spec.weak, text)
    if strong:
        status = FOUND
    elif weak:
        status = WEAK
    else:
        status = MISSING

    evidence = (strong + weak)[:2]
    return SlotFinding(
        slot_id=spec.id,
        label=spec.label,
        status=status,
        weight=spec.weight,
        evidence=evidence,
        excerpt=_excerpt(text, spec) if status != MISSING else "",
        advice=spec.advice,
        question=spec.question,
        placeholder=spec.placeholder,
    )


def _matches(patterns: tuple[re.Pattern[str], ...], text: str) -> tuple[str, ...]:
    found: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            snippet = _snippet(text, match.start(), match.end())
            if snippet and snippet not in found:
                found.append(snippet)
    return tuple(found)


def _excerpt(text: str, spec: SlotSpec) -> str:
    """取包含该槽位标记的第一个短句，用于回填改写稿。"""
    clauses = [clause.strip() for clause in _CLAUSE_SPLIT.split(text) if clause.strip()]
    for patterns in (spec.strong, spec.weak):
        for clause in clauses:
            if any(pattern.search(clause) for pattern in patterns):
                return _truncate(clause)
    return ""


def _snippet(text: str, start: int, end: int) -> str:
    left = max(0, start - _SNIPPET_RADIUS)
    right = min(len(text), end + _SNIPPET_RADIUS)
    return _truncate(re.sub(r"\s+", " ", text[left:right]).strip(), limit=40)


def _truncate(text: str, limit: int = _MAX_EXCERPT) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


def _pattern_findings(text: str) -> tuple[PatternFinding, ...]:
    hits: list[PatternFinding] = []

    question_count = len(_QUESTION_MARK.findall(text))
    connector = _CONNECTOR.search(text)
    if question_count >= 3 or (question_count >= 2 and connector):
        evidence = [f"检测到 {question_count} 个问号"]
        if connector:
            evidence.append(_snippet(text, connector.start(), connector.end()))
        hits.append(_finding("multi_question", evidence))

    symptom = _SYMPTOM.search(text)
    if symptom and not _MATERIAL.search(text):
        hits.append(_finding("no_material", [_snippet(text, symptom.start(), symptom.end())]))

    vague = _UNVERIFIABLE.search(text)
    if vague and not _has_acceptance(text):
        hits.append(_finding("unverifiable", [_snippet(text, vague.start(), vague.end())]))

    weak_verb = _VAGUE_VERB.search(text)
    if weak_verb:
        hits.append(_finding("vague_verb", [_snippet(text, weak_verb.start(), weak_verb.end())]))

    premise = _ASSUMED.search(text)
    if premise:
        hits.append(_finding("assumed_premise", [_snippet(text, premise.start(), premise.end())]))

    scope = _NO_SCOPE.search(text)
    if scope and len(text) < 80 and not _has_constraints(text):
        hits.append(_finding("no_scope", [_snippet(text, scope.start(), scope.end())]))

    return tuple(sorted(hits, key=lambda item: (-item.penalty, item.pattern_id)))


def _finding(pattern_id: str, evidence: list[str]) -> PatternFinding:
    spec = PATTERN_BY_ID[pattern_id]
    unique = tuple(dict.fromkeys(item for item in evidence if item))
    return PatternFinding(
        pattern_id=spec.id,
        label=spec.label,
        penalty=spec.penalty,
        evidence=unique[:2],
        advice=spec.advice,
        followup=spec.followup,
    )


def _has_acceptance(text: str) -> bool:
    return any(pattern.search(text) for pattern in SLOT_BY_ID["acceptance"].strong)


def _has_constraints(text: str) -> bool:
    return any(pattern.search(text) for pattern in SLOT_BY_ID["constraints"].strong)


def _followups(
    slots: tuple[SlotFinding, ...], patterns: tuple[PatternFinding, ...]
) -> tuple[str, ...]:
    candidates: list[str] = [
        finding.question for finding in slots if finding.status in (MISSING, WEAK)
    ]
    candidates.extend(pattern.followup for pattern in patterns)

    result: list[str] = []
    for question in candidates:
        if question and question not in result:
            result.append(question)
        if len(result) >= _MAX_FOLLOWUPS:
            break
    return tuple(result)
