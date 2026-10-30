"""E4: Same 8 bugs in py/ts/rs. Per checker: warm wall time, bugs caught, raw output tokens,
and tokens after converting to one compact line per error (the `agentc` idea)."""
import json, os, re, statistics, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from tok import ntok

B = Path(__file__).resolve().parent.parent / "data/bugs"
S = os.environ.get("SCRATCH", "")
env = dict(os.environ, RUSTUP_HOME=f"{S}/rustup", CARGO_HOME=f"{S}/cargo", NO_COLOR="1", CARGO_TERM_COLOR="never")
CHECKERS = {
    "tsc5 (ts)":      ("ts", "npx -y -p typescript@5 tsc -p ."),
    "tsc7/Go (ts)":   ("ts", "npx -y -p typescript@7 tsc -p ."),
    "pyright (py)":   ("py", "uvx -q pyright app.py"),
    "mypy (py)":      ("py", "uvx -q mypy --strict --no-incremental app.py"),
    "ty (py)":        ("py", "uvx -q ty check app.py"),
    "pyrefly basic (py)":  ("py", "uvx -q pyrefly check app.py"),
    "pyrefly strict (py)": ("py", "uvx -q pyrefly check -p strict app.py"),
    "cargo check (rs)": ("rs", f"touch src/main.rs && {S}/cargo/bin/cargo check -q"),
}
BUG_LINES = {"py": [20, 21, 22, 23, 24, 25, 26, 27], "ts": [12, 13, 14, 15, 16, 17, 18, 19], "rs": [12, 13, 14, 15, 16, 17, 18, 19]}
LOC = re.compile(r"(?:app\.(?:py|ts)|main\.rs)[:(](\d+)")

def compact(raw):  # one line per error: file:line message (first line only, no snippets/notes)
    out = []
    for line in raw.splitlines():
        m = re.search(r"(app\.(?:py|ts)|main\.rs)[:(](\d+)[:,]?(\d+)?\)?[: -]*(?:error|-\s*error)?:?\s*(.*)", line)
        if m and m.group(4).strip(): out.append(f"{m.group(1)}:{m.group(2)} {m.group(4).strip()[:120]}")
    if not out:  # rustc/ty style: "error[E..]: msg" then " --> src/main.rs:12:5"
        msg = None
        for line in raw.splitlines():
            if re.match(r"^(error|warning)(\[[\w-]+\])?:", line, re.I): msg = line.split(":", 1)[1].strip()
            elif re.match(r"^ERROR ", line): msg = line[6:].strip()
            m = re.search(r"--> \S*?(app\.\w+|main\.rs):(\d+)", line)
            if m and msg: out.append(f"{m.group(1)}:{m.group(2)} {msg[:120]}"); msg = None
    return "\n".join(dict.fromkeys(out))

res = {}
for name, (d, cmd) in CHECKERS.items():
    times, raw = [], ""
    for i in range(4):
        t = time.perf_counter()
        p = subprocess.run(cmd, shell=True, cwd=B / d, capture_output=True, text=True, env=env)
        times.append(time.perf_counter() - t); raw = p.stdout + p.stderr
    seen = {int(x) for x in LOC.findall(raw)}
    c = compact(raw)
    res[name] = dict(warm_seconds=round(statistics.median(times[1:]), 2),
                     bug_lines_caught=f"{len(seen & set(BUG_LINES[d]))}/8",
                     raw_tokens=ntok(raw), compact_tokens=ntok(c),
                     compact_pct_of_raw=round(100 * ntok(c) / max(ntok(raw), 1)))
    (B.parent.parent / "results" / f"e4_raw_{d}_{name.split()[0].replace('/', '_')}.txt").write_text(raw + "\n---compact---\n" + c)
    print(name, res[name])
Path(B.parent.parent / "results/e4.json").write_text(json.dumps(res, indent=1))
