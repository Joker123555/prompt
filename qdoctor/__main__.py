"""命令行入口：check / review / stats / serve。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__, history, llm
from .diagnose import diagnose
from .model import Diagnosis, ReviewResult
from .review import review
from .rewrite import build_rewrite
from .rules import MAX_INPUT_CHARS, PROBLEM_BY_ID, STATUS_LABELS


class InputError(RuntimeError):
    """输入或配置有误；由 main 转成退出码 1。"""


class UsageError(InputError):
    """用法错误；由 main 转成退出码 2。"""


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            return _cmd_check(args)
        if args.command == "review":
            return _cmd_review(args)
        if args.command == "stats":
            return _cmd_stats(args)
        if args.command == "serve":
            return _cmd_serve(args)
    except UsageError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except InputError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qdoctor",
        description="提问体检与复盘：先补齐信息，再问 AI。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="体检一条提问")
    check.add_argument("text", nargs="?", help="问题文本；省略时读 --file 或 stdin")
    check.add_argument("-f", "--file", help="从 UTF-8 文件读取问题")
    check.add_argument("--llm", action="store_true", help="用 LLM 润色改写稿（需配置环境变量）")
    check.add_argument("--json", action="store_true", help="输出 JSON")

    review_parser = sub.add_parser("review", help="复盘上一轮回答，生成下一轮追问")
    review_parser.add_argument("-q", "--question", required=True, help="原问题；用 @路径 读文件")
    review_parser.add_argument("-a", "--answer", required=True, help="上一轮回答；用 @路径 读文件")
    review_parser.add_argument("-w", "--wanted", default="", help="你本来想要什么；用 @路径 读文件")
    review_parser.add_argument(
        "-p",
        "--problem",
        choices=list(PROBLEM_BY_ID),
        default="other",
        help="不满意类型（默认 other）",
    )
    review_parser.add_argument("--llm", action="store_true", help="用 LLM 生成下一轮追问")
    review_parser.add_argument("--json", action="store_true", help="输出 JSON")

    stats = sub.add_parser("stats", help="查看本地提问统计")
    stats.add_argument("--last", type=int, default=30, help="只看最近 N 条（默认 30）")
    stats.add_argument("--json", action="store_true", help="输出 JSON")

    serve = sub.add_parser("serve", help="启动本地网页")
    serve.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    serve.add_argument("--port", type=int, default=8765, help="监听端口（默认 8765）")
    serve.add_argument("--open", action="store_true", dest="open_browser", help="启动后打开浏览器")

    return parser


def _cmd_check(args: argparse.Namespace) -> int:
    question = _read_question(args.text, args.file)
    _ensure_question(question)

    diagnosis = diagnose(question)
    rewrite = build_rewrite(diagnosis)
    llm_text, llm_error, exit_code = _maybe_llm_check(args.llm, question, diagnosis)
    _record_quietly("check", diagnosis, used_llm=bool(llm_text))

    if args.json:
        payload = diagnosis.to_dict()
        payload.update(
            {
                "mode": "check",
                "rewrite": rewrite,
                "llm": llm_text,
                "llm_error": llm_error,
            }
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_check(diagnosis, rewrite, llm_text)
    return exit_code


def _cmd_review(args: argparse.Namespace) -> int:
    question = _read_arg(args.question, "原问题")
    answer = _read_arg(args.answer, "回答")
    wanted = _read_arg(args.wanted, "期望") if args.wanted else ""
    _ensure_question(question)
    if not answer.strip():
        raise UsageError("上一轮回答为空。")

    result = review(question, answer, wanted, args.problem)
    llm_text, llm_error, exit_code = _maybe_llm_review(args.llm, result, args.problem)
    _record_quietly(
        "review",
        result.diagnosis,
        used_llm=bool(llm_text),
        problem=args.problem,
    )

    if args.json:
        payload = result.to_dict()
        payload.update({"llm": llm_text, "llm_error": llm_error})
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_review(result, llm_text)
    return exit_code


def _cmd_stats(args: argparse.Namespace) -> int:
    if args.last < 1:
        raise UsageError("--last 必须大于 0。")

    summary = history.summarize(_load_history(), args.last)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if summary["count"] == 0:
        print("还没有记录。先跑一次 check 或 review。")
        return 0

    print(f"提问统计（最近 {summary['count']} 条 / 共 {summary['total']} 条）")
    if summary["skipped"]:
        print(f"已跳过 {summary['skipped']} 行损坏记录")
    print(f"平均分：{summary['average_score']}")

    if summary["top_missing"]:
        print("\n最常缺的要素：")
        for index, item in enumerate(summary["top_missing"], 1):
            print(f"  {index}. {item['label']} — {item['count']} 次")

    if summary["top_patterns"]:
        print("\n最常见的反模式：")
        for index, item in enumerate(summary["top_patterns"], 1):
            print(f"  {index}. {item['label']} — {item['count']} 次")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from . import web

    try:
        web.serve(args.host, args.port, args.open_browser)
    except OSError as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        print("端口可能被占用，试试 --port 0 或换一个端口。", file=sys.stderr)
        return 1
    return 0


def _load_history():
    try:
        return history.load()
    except OSError as exc:
        raise InputError(f"读不到历史记录：{exc}") from exc


def _maybe_llm_check(
    requested: bool, question: str, diagnosis: Diagnosis
) -> tuple[str | None, str | None, int]:
    if not requested:
        return None, None, 0

    config = llm.LlmConfig.from_env()
    if config is None:
        message = _missing_llm_message()
        print(f"[警告] {message}", file=sys.stderr)
        return None, message, 1

    try:
        return llm.rewrite_question(question, diagnosis, config), None, 0
    except llm.LlmError as exc:
        print(f"[警告] {exc}；已保留规则结果。", file=sys.stderr)
        return None, str(exc), 1


def _maybe_llm_review(
    requested: bool, result: ReviewResult, problem: str
) -> tuple[str | None, str | None, int]:
    if not requested:
        return None, None, 0

    config = llm.LlmConfig.from_env()
    if config is None:
        message = _missing_llm_message()
        print(f"[警告] {message}", file=sys.stderr)
        return None, message, 1

    try:
        text = llm.review_next_round(
            result.question,
            result.answer,
            result.wanted,
            PROBLEM_BY_ID[problem],
            config,
        )
        return text, None, 0
    except llm.LlmError as exc:
        print(f"[警告] {exc}；已保留规则结果。", file=sys.stderr)
        return None, str(exc), 1


def _missing_llm_message() -> str:
    return (
        "未配置 LLM：请设置 QDOCTOR_LLM_BASE_URL、QDOCTOR_LLM_API_KEY、"
        "QDOCTOR_LLM_MODEL"
    )


def _print_check(diagnosis: Diagnosis, rewrite: str, llm_text: str | None) -> None:
    print(f"提问体检 · {diagnosis.score}/100")
    print(diagnosis.summary)
    print()

    for slot in diagnosis.slots:
        print(f"[{STATUS_LABELS[slot.status]}] {slot.label} — {_slot_line(slot)}")

    if diagnosis.patterns:
        print()
        for pattern in diagnosis.patterns:
            detail = pattern.advice
            if pattern.evidence:
                detail += f"（{pattern.evidence[0]}）"
            print(f"[反模式] {pattern.label} — {detail}")

    if diagnosis.followups:
        print()
        print(f"先补这 {len(diagnosis.followups)} 个信息（按顺序回答）：")
        for index, question in enumerate(diagnosis.followups, 1):
            print(f"  {index}. {question}")

    print()
    print("改写后的提问（可直接粘贴）：")
    print()
    print(rewrite)

    if llm_text:
        print()
        print("LLM 改写（可选）：")
        print()
        print(llm_text)


def _print_review(result: ReviewResult, llm_text: str | None) -> None:
    print(f"复盘 · {result.problem_label}")
    print(f"原问题体检：{result.diagnosis.score}/100")
    missing = [slot.label for slot in result.diagnosis.missing]
    weak = [slot.label for slot in result.diagnosis.weak]
    if missing:
        print("缺失要素：" + "、".join(missing))
    if weak:
        print("薄弱要素：" + "、".join(weak))

    if result.followups:
        print()
        print(f"先补这 {len(result.followups)} 个信息：")
        for index, question in enumerate(result.followups, 1):
            print(f"  {index}. {question}")

    print()
    print("下一轮追问（可直接粘贴）：")
    print()
    print(result.next_prompt)

    if llm_text:
        print()
        print("LLM 追问（可选）：")
        print()
        print(llm_text)


def _slot_line(slot) -> str:
    if slot.status == "found":
        return f"已检测到：{slot.excerpt}" if slot.excerpt else "已检测到"
    if slot.excerpt:
        return f"{slot.advice}（原文：{slot.excerpt}）"
    return slot.advice


def _read_question(text: str | None, file_path: str | None) -> str:
    if text and file_path:
        raise UsageError("位置参数和 --file 只能给一个。")
    if file_path:
        return _read_file(Path(file_path))
    if text:
        return text
    if sys.stdin.isatty():
        raise UsageError("没有输入。传入问题文本、--file，或用管道从 stdin 输入。")
    return sys.stdin.read()


def _read_arg(value: str, label: str) -> str:
    if value.startswith("@"):
        return _read_file(Path(value[1:]))
    return value


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"读不到文件 {path}：{exc}") from exc


def _ensure_question(question: str) -> None:
    if not question.strip():
        raise UsageError("问题文本为空。")
    if len(question) > MAX_INPUT_CHARS:
        raise UsageError(f"问题超过 {MAX_INPUT_CHARS} 字符；请先精简，或分段处理。")


def _record_quietly(
    mode: str, diagnosis: Diagnosis, *, used_llm: bool, problem: str = ""
) -> None:
    try:
        history.record(mode, diagnosis, used_llm=used_llm, problem=problem)
    except OSError as exc:
        print(f"[警告] 历史记录写入失败：{exc}", file=sys.stderr)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


if __name__ == "__main__":
    raise SystemExit(main())
