"""可选的 OpenAI 兼容 LLM 适配器。

默认不参与运行；只有显式要求且配置了环境变量时才会发请求。
发送内容仅限当前问题、规则诊断摘要和（复盘时）上一轮回答，不含历史记录。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Callable

from .model import Diagnosis
from .rules import STATUS_LABELS, ProblemSpec

Transport = Callable[[str, dict[str, str], dict, float], str]

_SYSTEM_REWRITE = (
    "你是提问教练。把用户的原始问题重写成一条信息完整的中文提问。"
    "要求：保留原意，不编造未知信息；缺失处用【待补：…】标出；"
    "按 目标/背景/约束/期望输出/验收标准/受众/示例 分段；"
    "只输出改写后的问题，不要解释。"
)

_SYSTEM_REVIEW = (
    "你是提问教练。根据原问题、上一轮回答和用户不满意的类型，写出下一轮追问。"
    "要求：只输出可以直接发给 AI 的中文追问；分点、具体、可执行；不要解释。"
)


class LlmError(RuntimeError):
    """LLM 调用失败；调用方应降级为规则结果。"""


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float = 30.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LlmConfig | None:
        source = os.environ if env is None else env
        base = (source.get("QDOCTOR_LLM_BASE_URL") or "").strip()
        key = (source.get("QDOCTOR_LLM_API_KEY") or "").strip()
        model = (source.get("QDOCTOR_LLM_MODEL") or "").strip()
        if not (base and key and model):
            return None
        try:
            timeout = float(source.get("QDOCTOR_LLM_TIMEOUT") or 30)
        except ValueError:
            timeout = 30.0
        return cls(base_url=base.rstrip("/"), api_key=key, model=model, timeout=timeout)


def is_configured(env: Mapping[str, str] | None = None) -> bool:
    return LlmConfig.from_env(env) is not None


def complete(
    messages: list[dict[str, str]],
    config: LlmConfig,
    transport: Transport | None = None,
) -> str:
    url = config.base_url + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
    }
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1200,
    }

    sender = transport or _urllib_transport
    try:
        raw = sender(url, headers, payload, config.timeout)
    except urllib.error.HTTPError as exc:
        raise LlmError(f"LLM 返回 HTTP {exc.code}") from exc
    except Exception as exc:
        raise LlmError(f"LLM 请求失败：{exc}") from exc

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LlmError("LLM 返回格式无法解析") from exc

    if not isinstance(content, str) or not content.strip():
        raise LlmError("LLM 返回了空内容")
    return content.strip()


def rewrite_question(
    question: str,
    diagnosis: Diagnosis,
    config: LlmConfig,
    transport: Transport | None = None,
) -> str:
    lines = []
    for slot in diagnosis.slots:
        status = STATUS_LABELS.get(slot.status, slot.status)
        excerpt = f"（原文：{slot.excerpt}）" if slot.excerpt else ""
        lines.append(f"- {slot.label}：{status}{excerpt}")
    user = f"原始问题：\n{question}\n\n规则诊断：\n" + "\n".join(lines)
    return complete(
        [{"role": "system", "content": _SYSTEM_REWRITE}, {"role": "user", "content": user}],
        config,
        transport,
    )


def review_next_round(
    question: str,
    answer: str,
    wanted: str,
    problem: ProblemSpec,
    config: LlmConfig,
    transport: Transport | None = None,
) -> str:
    user = "\n".join(
        [
            f"原问题：\n{_clip(question, 800)}",
            f"上一轮回答（节选）：\n{_clip(answer, 1500)}",
            f"我真正想要的：\n{_clip(wanted, 500) or '（未填写）'}",
            f"不满意类型：{problem.label}（{problem.description}）",
            f"这次的要求：{problem.instruction}",
        ]
    )
    return complete(
        [{"role": "system", "content": _SYSTEM_REVIEW}, {"role": "user", "content": user}],
        config,
        transport,
    )


def _urllib_transport(url: str, headers: dict[str, str], payload: dict, timeout: float) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _clip(text: str, limit: int) -> str:
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"
