"""本地历史记录。只存元数据，不存问题原文。

路径默认是 ~/.qdoctor/history.jsonl，可用 QDOCTOR_HOME 覆盖。
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .model import Diagnosis
from .rules import PATTERN_BY_ID, SLOT_BY_ID

_MODES = {"check", "review"}


@dataclass(frozen=True)
class HistoryLoad:
    entries: tuple[dict, ...]
    skipped: int


def history_path() -> Path:
    root = os.environ.get("QDOCTOR_HOME")
    base = Path(root) if root else Path.home() / ".qdoctor"
    return base / "history.jsonl"


def record(
    mode: str,
    diagnosis: Diagnosis,
    *,
    used_llm: bool = False,
    problem: str = "",
    path: Path | None = None,
) -> Path:
    """追加一条记录并返回文件路径。调用方负责捕获 OSError。"""
    if mode not in _MODES:
        raise ValueError(f"未知模式：{mode}")

    target = path or history_path()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "score": diagnosis.score,
        "missing": [item.slot_id for item in diagnosis.slots if item.status == "missing"],
        "weak": [item.slot_id for item in diagnosis.slots if item.status == "weak"],
        "patterns": [item.pattern_id for item in diagnosis.patterns],
        "chars": len(diagnosis.text),
        "llm": bool(used_llm),
    }
    if problem:
        entry["problem"] = problem

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return target


def load(path: Path | None = None) -> HistoryLoad:
    """读取记录；损坏的行跳过并计数。"""
    target = path or history_path()
    if not target.exists():
        return HistoryLoad((), 0)

    entries: list[dict] = []
    skipped = 0
    for line in target.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(item, dict) or not isinstance(item.get("score"), int):
            skipped += 1
            continue
        if item.get("mode") not in _MODES:
            skipped += 1
            continue
        entries.append(item)
    return HistoryLoad(tuple(entries), skipped)


def summarize(loaded: HistoryLoad, last: int = 30) -> dict:
    window = loaded.entries[-last:] if last > 0 else loaded.entries
    scores = [entry["score"] for entry in window]
    missing: Counter[str] = Counter()
    patterns: Counter[str] = Counter()
    for entry in window:
        missing.update(_ids(entry.get("missing")))
        patterns.update(_ids(entry.get("patterns")))

    return {
        "total": len(loaded.entries),
        "count": len(window),
        "skipped": loaded.skipped,
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "top_missing": _top(missing, SLOT_BY_ID),
        "top_patterns": _top(patterns, PATTERN_BY_ID),
        "first": window[0].get("ts") if window else None,
        "last": window[-1].get("ts") if window else None,
    }


def _ids(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _top(counter: Counter[str], specs: dict) -> list[dict]:
    def rank(item: tuple[str, int]) -> tuple[int, int, str]:
        key, count = item
        spec = specs.get(key)
        importance = getattr(spec, "weight", getattr(spec, "penalty", 0))
        return (-count, -importance, key)

    ordered = sorted(counter.items(), key=rank)[:5]
    return [
        {"id": key, "label": getattr(specs.get(key), "label", key), "count": count}
        for key, count in ordered
    ]
