"""E8b: Live model test. Same buggy file, two error feeds: raw checker output vs compact one-line-per-error.
Success = checker passes AND all 8 print calls survive (no deleting the problem)."""
import json, os, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from llm import call, block

MODEL = sys.argv[1] if len(sys.argv) > 1 else "haiku"; REPS = 5
B = Path(__file__).resolve().parent.parent / "data/bugs"; R = B.parent.parent / "results"
S = os.environ.get("SCRATCH", "/tmp/agent-lang-lab")
env = dict(os.environ, RUSTUP_HOME=f"{S}/rustup", CARGO_HOME=f"{S}/cargo", NO_COLOR="1")
LANG = {"py": ("app.py", "pyright", "uvx -q pyright app.py", "print("), "rs": ("src/main.rs", "cargo", f"{S}/cargo/bin/cargo check -q", "println!")}

def feeds(d, tool):
    raw, comp = (R / f"e4_raw_{d}_{tool}.txt").read_text().split("\n---compact---\n")
    return {"raw": raw.strip(), "compact": comp.strip()}

def run(d, arm, rep):
    f, tool, check, pr = LANG[d]; src = (B / d / f).read_text(); err = feeds(d, tool)[arm]
    p = (f"Fix all type errors in this file. Keep every print statement and the program's intent; don't delete code to silence errors.\n\n"
         f"```\n{src}```\n\nChecker output:\n```\n{err}\n```\n\nReturn the complete fixed file in one fenced block.")
    out, u = call(p, MODEL); fixed = block(out)
    w = Path(tempfile.mkdtemp()); shutil.copytree(B / d, w, dirs_exist_ok=True); (w / f).write_text(fixed)
    ok = subprocess.run(check, shell=True, cwd=w, capture_output=True, env=env).returncode == 0
    kept = fixed.count(pr) >= src.count(pr)
    return dict(lang=d, arm=arm, ok=ok and kept, check_ok=ok, kept_prints=kept, text=fixed, **u)

jobs = [(d, a, i) for d in LANG for a in ("raw", "compact") for i in range(REPS)]
with ThreadPoolExecutor(6) as ex: rows = list(ex.map(lambda j: run(*j), jobs))
summ = {}
for d in LANG:
    for a in ("raw", "compact"):
        r = [x for x in rows if x["lang"] == d and x["arm"] == a]
        summ[f"{d}/{a}"] = dict(success=f"{sum(x['ok'] for x in r)}/{len(r)}", feed_tokens=None,
                               mean_out=round(sum(x.get("out", 0) for x in r) / len(r)), cost=round(sum(x.get("cost") or 0 for x in r), 4))
sys.path.insert(0, str(Path(__file__).parent))
try:
    from tok import ntok
    for d in LANG:
        for a, t in feeds(d, LANG[d][1]).items(): summ[f"{d}/{a}"]["feed_tokens"] = ntok(t)
except ImportError: pass
print(MODEL, json.dumps(summ, indent=1)); (R / f"e8b_{MODEL}.json").write_text(json.dumps(dict(summary=summ, rows=rows), indent=1))
