"""E13: How big is the context on each model call? Cost ~ sum over calls of context size."""
import json, statistics
from pathlib import Path
ctx = []
for f in (Path.home() / ".claude/projects").rglob("*.jsonl"):
    if "subagents" in f.parts: continue
    last = None
    for line in f.open(errors="ignore"):
        try: r = json.loads(line)
        except Exception: continue
        m = r.get("message")
        if r.get("type") != "assistant" or not isinstance(m, dict) or not isinstance(m.get("usage"), dict) or m.get("id") == last: continue
        last = m.get("id"); u = m["usage"]
        ctx.append(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))
ctx.sort(); T = sum(ctx); q = statistics.quantiles(ctx, n=10)
res = dict(calls=len(ctx), mean=round(T / len(ctx)), median=statistics.median(ctx), p10=q[0], p90=q[-1],
           pct_of_input_from_calls_over_200k=round(100 * sum(c for c in ctx if c > 200_000) / T, 1),
           calls_over_200k_pct=round(100 * sum(c > 200_000 for c in ctx) / len(ctx), 1),
           input_if_capped_at_100k_pct=round(100 * sum(min(c, 100_000) for c in ctx) / T, 1))
print(json.dumps(res, indent=1)); Path("results/e13.json").write_text(json.dumps(res, indent=1))
