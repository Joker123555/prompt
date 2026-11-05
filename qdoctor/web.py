"""本地网页入口。默认只绑定回环地址，静态资源只有三个文件。"""

from __future__ import annotations

import json
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__, history, llm
from .diagnose import diagnose
from .review import review
from .rewrite import build_rewrite
from .rules import MAX_INPUT_CHARS, PROBLEM_BY_ID

_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
}
_MAX_BODY_BYTES = 100_000
_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; "
    "script-src 'self'; connect-src 'self'"
)


class Handler(BaseHTTPRequestHandler):
    server_version = "qdoctor/" + __version__

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in _STATIC:
            name, content_type = _STATIC[parsed.path]
            self._send_static(name, content_type)
            return

        if parsed.path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "llm": llm.is_configured(),
                    "max_chars": MAX_INPUT_CHARS,
                },
            )
            return

        if parsed.path == "/api/stats":
            raw = parse_qs(parsed.query).get("last", ["30"])[0]
            try:
                last = max(1, min(500, int(raw)))
            except ValueError:
                last = 30
            try:
                summary = history.summarize(history.load(), last)
            except OSError as exc:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": f"读不到历史记录：{exc}"},
                )
                return
            self._send_json(HTTPStatus.OK, summary)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "没有这个路径"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ("/api/check", "/api/review"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "没有这个路径"})
            return

        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": "Content-Type 必须是 application/json"},
            )
            return

        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length is not None else -1
        except ValueError:
            length = -1
        if length < 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "缺少 Content-Length"})
            return
        if length > _MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "请求体太大"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请求体不是合法 JSON"})
            return
        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请求体必须是 JSON 对象"})
            return

        if path == "/api/check":
            self._handle_check(payload)
        else:
            self._handle_review(payload)

    def _handle_check(self, payload: dict) -> None:
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "text 不能为空"})
            return
        if len(text) > MAX_INPUT_CHARS:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": f"text 超过 {MAX_INPUT_CHARS} 字符"},
            )
            return

        diagnosis = diagnose(text)
        rewrite = build_rewrite(diagnosis)
        llm_text, llm_error = _maybe_llm_check(bool(payload.get("use_llm")), text, diagnosis)
        _record_quietly("check", diagnosis, used_llm=bool(llm_text))

        data = diagnosis.to_dict()
        data.update(
            {
                "mode": "check",
                "rewrite": rewrite,
                "llm": llm_text,
                "llm_error": llm_error,
            }
        )
        self._send_json(HTTPStatus.OK, data)

    def _handle_review(self, payload: dict) -> None:
        question = payload.get("question")
        answer = payload.get("answer")
        wanted = payload.get("wanted", "")
        problem = payload.get("problem", "other")

        if not isinstance(question, str) or not question.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "question 不能为空"})
            return
        if not isinstance(answer, str) or not answer.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "answer 不能为空"})
            return
        if not isinstance(wanted, str):
            wanted = ""
        if not isinstance(problem, str) or problem not in PROBLEM_BY_ID:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "未知的 problem"})
            return
        if len(question) > MAX_INPUT_CHARS or len(answer) > MAX_INPUT_CHARS:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": f"question 或 answer 超过 {MAX_INPUT_CHARS} 字符"},
            )
            return

        result = review(question, answer, wanted, problem)
        llm_text, llm_error = _maybe_llm_review(
            bool(payload.get("use_llm")), result, problem
        )
        _record_quietly(
            "review", result.diagnosis, used_llm=bool(llm_text), problem=problem
        )

        data = result.to_dict()
        data.update({"llm": llm_text, "llm_error": llm_error})
        self._send_json(HTTPStatus.OK, data)

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, name: str, content_type: str) -> None:
        path = Path(__file__).with_name("static") / name
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "静态文件缺失"})
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", _CSP)


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = make_server(host, port)
    actual_host, actual_port = server.server_address[0], server.server_address[1]
    url = f"http://{actual_host}:{actual_port}/"
    print(f"qdoctor 已启动：{url}")
    if actual_host not in ("127.0.0.1", "localhost", "::1"):
        print("警告：当前监听非回环地址，局域网内可访问，且没有鉴权。")
    print("按 Ctrl+C 停止。")
    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


def _maybe_llm_check(requested: bool, question: str, diagnosis) -> tuple[str | None, str | None]:
    if not requested:
        return None, None
    config = llm.LlmConfig.from_env()
    if config is None:
        return None, _missing_llm_message()
    try:
        return llm.rewrite_question(question, diagnosis, config), None
    except llm.LlmError as exc:
        return None, str(exc)


def _maybe_llm_review(requested: bool, result, problem: str) -> tuple[str | None, str | None]:
    if not requested:
        return None, None
    config = llm.LlmConfig.from_env()
    if config is None:
        return None, _missing_llm_message()
    try:
        return (
            llm.review_next_round(
                result.question,
                result.answer,
                result.wanted,
                PROBLEM_BY_ID[problem],
                config,
            ),
            None,
        )
    except llm.LlmError as exc:
        return None, str(exc)


def _missing_llm_message() -> str:
    return (
        "未配置 LLM：请设置 QDOCTOR_LLM_BASE_URL、QDOCTOR_LLM_API_KEY、"
        "QDOCTOR_LLM_MODEL"
    )


def _record_quietly(mode: str, diagnosis, *, used_llm: bool, problem: str = "") -> None:
    try:
        history.record(mode, diagnosis, used_llm=used_llm, problem=problem)
    except OSError as exc:
        print(f"[qdoctor] 历史记录写入失败：{exc}", file=sys.stderr)
