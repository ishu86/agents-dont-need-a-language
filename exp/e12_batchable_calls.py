"""E12: Cost scales with (#model calls x context). How many calls are read-only tool hops that a
'code mode' batch (one script doing several reads) could merge? From local transcripts."""
import json, re
from pathlib import Path
RO_BASH = re.compile(r"^\s*(cd [^;&]+&&\s*)?(ls|cat|head|tail|grep|rg|find|wc|sed -n|git (status|log|diff|show|ls-files)|pwd|echo|which|stat|du|tree)\b")
RO_TOOLS = {"Read", "Grep", "Glob", "WebFetch", "WebSearch", "ToolSearch"}
calls = ro_calls = merged_away = ctx_total = ctx_saved = 0
for f in (Path.home() / ".claude/projects").rglob("*.jsonl"):
    if "subagents" in f.parts: continue
    seq = []  # [message_id, context_tokens, blocks]
    for line in f.open(errors="ignore"):
        try: r = json.loads(line)
        except Exception: continue
        m = r.get("message")
        if r.get("type") != "assistant" or not isinstance(m, dict) or not isinstance(m.get("usage"), dict): continue
        u = m["usage"]; ctx = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        blocks = [b for b in (m.get("content") or []) if isinstance(b, dict)]
        if seq and seq[-1][0] == m.get("id"): seq[-1][2].extend(blocks)   # one line per block, same message id
        else: seq.append([m.get("id"), ctx, blocks])
    dedup = []
    for _, ctx, blocks in seq:
        tools = [b for b in blocks if b.get("type") == "tool_use"]
        ro = bool(tools) and all(b["name"] in RO_TOOLS or (b["name"] == "Bash" and RO_BASH.match((b.get("input") or {}).get("command", ""))) for b in tools)
        dedup.append((ro, ctx))
    calls += len(dedup); ctx_total += sum(c for _, c in dedup)
    run = 0
    for ro, c in dedup:
        if ro:
            ro_calls += 1; run += 1
            if run > 1: merged_away += 1; ctx_saved += c   # 2nd+ consecutive read-only hop could join the 1st
        else: run = 0
res = dict(model_calls=calls, read_only_tool_calls_pct=round(100 * ro_calls / calls, 1),
           calls_mergeable_pct=round(100 * merged_away / calls, 1), context_tokens_saved_pct=round(100 * ctx_saved / ctx_total, 1))
print(json.dumps(res, indent=1)); Path("results/e12.json").write_text(json.dumps(res, indent=1))
