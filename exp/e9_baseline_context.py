"""E9: Fixed context each session starts with (system prompt + tools + CLAUDE.md + hooks/skills),
and what share of all input tokens is that prefix being re-read. From local transcripts."""
import json, statistics
from pathlib import Path
base, turns, reread, total = [], [], 0, 0
for f in (Path.home() / ".claude/projects").rglob("*.jsonl"):
    if "subagents" in f.parts: continue
    us, seen = [], set()  # usage repeats on every content-block line of a message
    for line in f.open(errors="ignore"):
        try: r = json.loads(line)
        except Exception: continue
        m = r.get("message")
        if r.get("type") == "assistant" and isinstance(m, dict) and isinstance(m.get("usage"), dict) and m.get("id") not in seen:
            seen.add(m.get("id")); u = m["usage"]
            us.append(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))
    if us: base.append(us[0]); turns.append(len(us)); reread += us[0] * len(us); total += sum(us)
res = dict(sessions=len(base), median_first_turn_context=statistics.median(base), p90_first_turn_context=statistics.quantiles(base, n=10)[-1],
           median_model_calls_per_session=statistics.median(turns), mean_model_calls=round(statistics.mean(turns)),
           baseline_pct_of_all_input=round(100 * reread / total, 1))
print(json.dumps(res, indent=1)); Path("results/e9.json").write_text(json.dumps(res, indent=1))
