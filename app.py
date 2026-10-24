"""Advanced chat app on the Anthropic API.

Features: streaming, model picker, web search with sources, image / PDF / text
upload, custom instructions.  Run: python app.py  ->  http://localhost:5000
Set ANTHROPIC_API_KEY, or MOCK=1 to try the interface without a key.
"""
import base64
import json
import os
import time

from flask import Flask, Response, jsonify, request, send_from_directory

MODELS = [m.strip() for m in os.environ.get(
    "CHAT_MODELS", "claude-sonnet-5-5,claude-opus-5-5,claude-haiku-5-5").split(",") if m.strip()]
MOCK = os.environ.get("MOCK") == "1"
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "4096"))
MAX_TURNS = 40
MAX_FILE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
SYSTEM = os.environ.get(
    "SYSTEM_PROMPT",
    "You are a helpful, honest and friendly AI assistant. Answer clearly and "
    "concisely. Use Markdown for lists, tables and code blocks. If you used web "
    "search, rely on what you found and say when sources disagree.",
)

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
_client = None


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def build_content(m: dict):
    """Turn {content, attachments} into API content blocks."""
    text = (m.get("content") or "").strip()
    atts = m.get("attachments") or []
    if m.get("role") != "user" or not atts:
        return text
    blocks = []
    for a in atts:
        kind, name = a.get("type", ""), a.get("name", "file")
        data = a.get("data") or ""
        if kind in IMAGE_TYPES or kind == "application/pdf":
            if not data:
                continue  # file data is not kept after a page reload
            try:
                if len(base64.b64decode(data, validate=False)) > MAX_FILE_BYTES:
                    continue
            except Exception:
                continue
            if kind == "application/pdf":
                blocks.append({"type": "document", "source": {
                    "type": "base64", "media_type": kind, "data": data}})
            else:
                blocks.append({"type": "image", "source": {
                    "type": "base64", "media_type": kind, "data": data}})
        elif a.get("text"):
            blocks.append({"type": "text",
                           "text": f"File: {name}\n```\n{a['text'][:200000]}\n```"})
    blocks.append({"type": "text", "text": text or "Please look at the attached file(s)."})
    return blocks


def clean(messages):
    out = []
    for m in messages or []:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = build_content(m)
        if content:
            out.append({"role": role, "content": content})
    out = out[-MAX_TURNS:]
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/config")
def config():
    return jsonify(models=MODELS, mock=MOCK)


@app.post("/api/chat")
def chat():
    body = request.get_json(silent=True) or {}
    messages = clean(body.get("messages"))
    if not messages or messages[-1]["role"] != "user":
        return jsonify(error="Send at least one user message."), 400
    model = body.get("model") if body.get("model") in MODELS else MODELS[0]
    system = SYSTEM
    extra = (body.get("instructions") or "").strip()[:2000]
    if extra:
        system += "\n\nThe user's custom instructions:\n" + extra
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}] \
        if body.get("web_search") else None

    def generate():
        try:
            if MOCK:
                if tools:
                    yield sse({"status": "Searching the web…"})
                    time.sleep(0.6)
                    yield sse({"status": ""})
                    yield sse({"source": {"url": "https://example.com", "title": "Example source"}})
                last = messages[-1]["content"]
                last = last if isinstance(last, str) else "(message with files)"
                reply = (f"**Mock mode** ({model}). Not a real AI answer.\n\n"
                         f"You said: *{last[:200]}*\n\n```python\nprint('Set ANTHROPIC_API_KEY for the real model')\n```")
                for w in reply.split(" "):
                    yield sse({"text": w + " "})
                    time.sleep(0.02)
            else:
                kwargs = dict(model=model, max_tokens=MAX_TOKENS, system=system, messages=messages)
                if tools:
                    kwargs["tools"] = tools
                seen = set()
                with client().messages.stream(**kwargs) as stream:
                    for ev in stream:
                        t = getattr(ev, "type", "")
                        if t == "content_block_start":
                            cb = ev.content_block
                            if getattr(cb, "type", "") == "server_tool_use":
                                yield sse({"status": "Searching the web…"})
                        elif t == "content_block_delta":
                            d = ev.delta
                            dt = getattr(d, "type", "")
                            if dt == "text_delta":
                                yield sse({"status": ""})
                                yield sse({"text": d.text})
                            elif dt == "citations_delta":
                                c = d.citation
                                url = getattr(c, "url", None)
                                if url and url not in seen:
                                    seen.add(url)
                                    yield sse({"source": {"url": url, "title": getattr(c, "title", "") or url}})
            yield sse({"done": True})
        except Exception as e:
            yield sse({"error": f"{type(e).__name__}: {e}"})

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False, threaded=True)
