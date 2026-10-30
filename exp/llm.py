"""Headless model call via `claude -p` (no tools, fixed short system prompt, no CLAUDE.md effects on cwd)."""
import json, subprocess, tempfile
SYS = "You are a precise coding assistant. Follow the output format exactly. No commentary."
TMP = tempfile.mkdtemp()

def call(prompt, model="haiku"):
    p = subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", "--no-session-persistence",
                        "--tools", "", "--system-prompt", SYS], input=prompt, capture_output=True, text=True, cwd=TMP, timeout=600)
    try: d = json.loads(p.stdout)
    except Exception: return "", dict(error=p.stderr[-300:])
    u = d.get("usage", {})
    return d.get("result") or "", dict(out=u.get("output_tokens", 0), cost=d.get("total_cost_usd", 0), reason=d.get("terminal_reason"))

def block(text):  # first fenced block, else whole text
    import re
    m = re.search(r"```[\w-]*\n(.*?)```", text, re.S)
    return m.group(1) if m else text
