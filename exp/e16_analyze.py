"""E16 analysis: per model x arm, pass rate and read volume; strict vs loose ratios paired by task, bootstrap 95% CI."""
import json, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from tok import ntok

rows = [json.loads(l) for l in open("results/e16_runs.jsonl")]
size = {a: sum(ntok(p.read_text()) for p in Path("data/e16/arms", a, "src").rglob("*") if p.is_file())
        for a in ("strict_ts", "loose_ts", "loose_js")}
M = ("tool_result_tokens", "total_input_tokens", "cost_usd", "turns", "files_read")
g = defaultdict(list)
for r in rows: g[(r["model"], r["arm"])].append(r)

def boot_ratio(model, a, b, m, n=4000):
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["model"] == model and r["arm"] in (a, b): per[r["task"]][r["arm"]].append(r[m])
    tasks = [t for t in per if per[t][a] and per[t][b]]
    mean = lambda xs: sum(xs) / len(xs)
    ratio = lambda ts: sum(mean(per[t][a]) for t in ts) / max(sum(mean(per[t][b]) for t in ts), 1e-9)
    random.seed(0); bs = sorted(ratio(random.choices(tasks, k=len(tasks))) for _ in range(n))
    return round(ratio(tasks), 2), (round(bs[int(.025 * n)], 2), round(bs[int(.975 * n)], 2))

out = dict(codebase_tokens=size, arms={}, ratios={}, per_task_pass={})
for (model, arm), rs in sorted(g.items()):
    d = dict(n=len(rs), pass_rate=round(sum(r["pass_"] for r in rs) / len(rs), 2))
    for m in M: d[f"mean_{m}"] = round(st.mean(r[m] for r in rs), 4 if m == "cost_usd" else 1)
    d["read_tokens_per_codebase"] = round(d["mean_tool_result_tokens"] / size[arm], 2)
    out["arms"][f"{model}/{arm}"] = d
for model in sorted({r["model"] for r in rows}):
    for b in ("loose_js", "loose_ts"):
        for m in ("tool_result_tokens", "total_input_tokens", "cost_usd", "turns"):
            out["ratios"][f"{model} strict_ts/{b} {m}"] = boot_ratio(model, "strict_ts", b, m)
    out["ratios"][f"{model} loose_ts/loose_js tool_result_tokens"] = boot_ratio(model, "loose_ts", "loose_js", "tool_result_tokens")
    for t in sorted({r["task"] for r in rows}):
        out["per_task_pass"][f"{model} {t}"] = {a: f"{sum(r['pass_'] for r in rows if r['model']==model and r['task']==t and r['arm']==a)}/{sum(1 for r in rows if r['model']==model and r['task']==t and r['arm']==a)}" for a in size}
print(json.dumps(out, indent=1)); Path("results/e16_analysis.json").write_text(json.dumps(out, indent=1))
