"""E2: Where do coding-agent tokens actually go? Mined from local Claude Code transcripts.
Content shares by char count; billing totals from real `usage` fields."""
import json, collections
from pathlib import Path

chars = collections.Counter()      # category -> chars
calls = collections.Counter()
usage = collections.Counter()
sessions = 0
for f in (Path.home() / ".claude/projects").rglob("*.jsonl"):
    if "subagents" in f.parts: continue
    sessions += 1
    names = {}; seen_ids = set()  # usage repeats on every content-block line of a message
    for line in f.open(errors="ignore"):
        try: r = json.loads(line)
        except Exception: continue
        m = r.get("message")
        if not isinstance(m, dict): continue
        if r.get("type") == "assistant" and isinstance(m.get("usage"), dict) and m.get("id") not in seen_ids:
            seen_ids.add(m.get("id"))
            u = m["usage"]
            for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                usage[k] += u.get(k) or 0
        c = m.get("content")
        if isinstance(c, str):
            chars["user_text" if r.get("type") == "user" else "assistant_text"] += len(c); continue
        for b in c or []:
            t = b.get("type")
            if t == "text": chars[("user" if r.get("type") == "user" else "assistant") + "_text"] += len(b.get("text", ""))
            elif t == "thinking": chars["assistant_thinking"] += len(b.get("thinking", ""))
            elif t == "tool_use":
                n = b.get("name", "?"); names[b.get("id")] = n; calls[n] += 1
                inp = b.get("input") or {}
                if n in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
                    chars["written_code(Write/Edit input)"] += len(json.dumps(inp))
                else:
                    chars["tool_call_args(other)"] += len(json.dumps(inp))
            elif t == "tool_result":
                n = names.get(b.get("tool_use_id"), "?")
                rc = b.get("content")
                if isinstance(rc, list):
                    chars["result:images(base64)"] += sum(len(json.dumps(x)) for x in rc if x.get("type") != "text")
                    s = "".join(x.get("text", "") for x in rc if x.get("type") == "text")
                else: s = rc if isinstance(rc, str) else json.dumps(rc)
                k = n if n in ("Read", "Bash", "Grep", "Glob", "Edit", "Write", "WebFetch", "WebSearch", "Agent", "Task") else ("mcp" if n.startswith("mcp__") else "other")
                chars["result:" + k] += len(s)

T = sum(chars.values())
share = {k: round(100 * v / T, 1) for k, v in chars.most_common()}
billed_in = usage["input_tokens"] + usage["cache_read_input_tokens"] + usage["cache_creation_input_tokens"]
img = chars.pop("result:images(base64)", 0); T = sum(chars.values())
share = {k: round(100 * v / T, 1) for k, v in chars.most_common()}
# relative price weights (Anthropic list: cache read 0.1x, cache write 1.25x, output 5x input)
w = dict(input_tokens=1, cache_read_input_tokens=0.1, cache_creation_input_tokens=1.25, output_tokens=5)
cost = {k: usage[k] * w[k] for k in w}; C = sum(cost.values())
out = dict(cost_share_pct={k: round(100 * v / C, 1) for k, v in cost.items()}, image_chars_excluded=img,
           sessions=sessions, content_share_pct=share, tool_calls=dict(calls.most_common(15)),
           usage=dict(usage), input_to_output_ratio=round(billed_in / max(usage["output_tokens"], 1), 1),
           cache_read_share_of_input_pct=round(100 * usage["cache_read_input_tokens"] / max(billed_in, 1), 1))
print(json.dumps(out, indent=1))
Path("results/e2.json").write_text(json.dumps(out, indent=1))
