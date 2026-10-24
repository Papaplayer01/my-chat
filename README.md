# My Chat

A ChatGPT-style web chat built on the Anthropic API: streaming answers, Markdown and code blocks with a copy button, multiple saved chats, stop and regenerate.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key      # from console.anthropic.com
python app.py
```

Open http://localhost:5000. To try the interface without a key: `MOCK=1 python app.py`.

## How it works

- `app.py` (Flask) exposes `POST /api/chat`. It receives the conversation, calls the model and streams the reply back as server-sent events.
- `static/index.html` is the whole interface. Chats are stored in your browser (localStorage), so the server keeps no data.
- Your API key stays on the server and is never sent to the browser.

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `CHAT_MODEL` | `claude-sonnet-5-5` | model name |
| `SYSTEM_PROMPT` | helpful assistant | the assistant's role and rules |
| `MAX_TOKENS` | `2048` | maximum reply length |

## Not included yet

Login and per-user history, file uploads, web search and other tools, and a database. See the roadmap in the chat that created this project.

## Advanced features (v2)

- **Model picker**: choose between the models in `CHAT_MODELS` (comma-separated, set in the environment).
- **Web search**: tick the box and the model searches the web, answers from what it found, and shows source links under the reply. Needs web search enabled for your Anthropic API account.
- **Attachments**: images (also paste with Ctrl/Cmd+V), PDFs and text or code files, up to 5 MB each. File contents are kept only for the current session, not after a page reload.
- **Custom instructions**: set once, applied to every chat.
- **Export**: download any chat as Markdown.
