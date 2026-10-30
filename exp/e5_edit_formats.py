"""E5: Output-token cost of expressing real commits in 4 edit formats.
Replays the last N single-language file changes from real repos."""
import difflib, json, statistics, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from tok import ntok

REPOS = {"python": ("browser-use", ".py"), "typescript": ("finance-bus", (".ts", ".tsx")), "rust": ("gigatoken", ".rs")}
N = 300
def git(root, *a): return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True, errors="ignore").stdout

def cost(old, new):
    a, b = old.splitlines(keepends=True), new.splitlines(keepends=True)
    ops = [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal"]
    if not ops: return None
    sr = hl = 0
    for _, i1, i2, j1, j2 in ops:
        lo, hi = i1, i2  # grow context until old_string is unique and non-empty (str_replace rule)
        while True:
            s = "".join(a[lo:hi])
            if s.strip() and old.count(s) == 1: break
            if lo == 0 and hi == len(a): break
            lo, hi = max(0, lo - 1), min(len(a), hi + 1)
        ctx_new = "".join(a[lo:i1]) + "".join(b[j1:j2]) + "".join(a[i2:hi])
        sr += ntok(s) + ntok(ctx_new) + 12           # old_string + new_string + JSON/tool overhead
        hl += ntok("".join(b[j1:j2])) + 10           # "replace 41:a3..44:9f with" + new lines
    ud = ntok("".join(difflib.unified_diff(a, b, n=3)))
    return dict(rewrite=ntok(new) + 8, str_replace=sr, unified_diff=ud, hashline=hl, hunks=len(ops))

res = {}
for lang, (repo, ext) in REPOS.items():
    root = Path.home() / "dev" / repo
    rows = []
    for line in git(root, "log", "--no-merges", "--format=%H", "-n", "2000").split():
        if len(rows) >= N: break
        files = [f for f in git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", line).split() if f.endswith(ext)]
        for f in files[:2]:
            old, new = git(root, "show", f"{line}^:{f}"), git(root, "show", f"{line}:{f}")
            if not old or not new or len(new) > 200_000: continue
            c = cost(old, new)
            if c: rows.append(c)
    tot = {k: sum(r[k] for r in rows) for k in ("rewrite", "str_replace", "unified_diff", "hashline")}
    res[lang] = dict(edits=len(rows), median_hunks=statistics.median(r["hunks"] for r in rows),
                     total_tokens=tot, pct_of_rewrite={k: round(100 * v / tot["rewrite"], 1) for k, v in tot.items()},
                     hashline_vs_str_replace_pct=round(100 * tot["hashline"] / tot["str_replace"], 1),
                     median_tokens={k: statistics.median(r[k] for r in rows) for k in tot})
    print(lang, json.dumps(res[lang]))
Path("results/e5.json").write_text(json.dumps(res, indent=1))
