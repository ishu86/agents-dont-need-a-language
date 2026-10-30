"""E6: How much of real Bash tool output is compressible noise? Lossless-ish filters only."""
import json, random, re, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from tok import ntok

outs = []
for f in (Path.home() / ".claude/projects").rglob("*.jsonl"):
    names = {}
    for line in f.open(errors="ignore"):
        try: m = json.loads(line).get("message")
        except Exception: continue
        if not isinstance(m, dict) or not isinstance(m.get("content"), list): continue
        for b in m["content"]:
            if b.get("type") == "tool_use": names[b.get("id")] = b.get("name")
            elif b.get("type") == "tool_result" and names.get(b.get("tool_use_id")) == "Bash":
                c = b.get("content"); c = c if isinstance(c, str) else "".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                if c: outs.append(c)
random.seed(0); sample = random.sample(outs, min(4000, len(outs)))

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
def f_ansi(s): return ANSI.sub("", s)
def f_cr(s): return "\n".join(l.split("\r")[-1] for l in s.split("\n"))           # progress bars
def f_dedupe(s):  # collapse runs of lines identical after masking numbers/hex
    out, prev, n = [], None, 0
    for l in s.split("\n"):
        k = re.sub(r"[0-9a-f]{6,}|\d+", "#", l)
        if k == prev: n += 1; continue
        if n: out.append(f"  [... {n} similar lines]")
        out.append(l); prev, n = k, 0
    if n: out.append(f"  [... {n} similar lines]")
    return "\n".join(out)
def f_ws(s): return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", s))
def f_cap(s, h=60, t=40):  # lossy: keep head+tail of very long output
    L = s.split("\n"); return s if len(L) <= h + t else "\n".join(L[:h] + [f"[... {len(L)-h-t} lines cut]"] + L[-t:])

raw = [ntok(s) for s in sample]
stages, cur = {}, sample
for name, fn in [("strip_ansi", f_ansi), ("progress_bars", f_cr), ("trailing_ws", f_ws), ("dedupe_similar", f_dedupe), ("cap_head60_tail40(lossy)", f_cap)]:
    cur = [fn(s) for s in cur]; stages[name] = round(100 * sum(ntok(s) for s in cur) / sum(raw), 1)
R = sum(raw); big = sorted(raw, reverse=True)
res = dict(bash_outputs_total=len(outs), sampled=len(sample), median_tokens=statistics.median(raw),
           p90_tokens=statistics.quantiles(raw, n=10)[-1], max_tokens=big[0],
           share_of_tokens_from_top5pct_outputs=round(100 * sum(big[:len(big)//20]) / R, 1),
           cumulative_pct_after_filter=stages)
print(json.dumps(res, indent=1)); Path("results/e6.json").write_text(json.dumps(res, indent=1))
