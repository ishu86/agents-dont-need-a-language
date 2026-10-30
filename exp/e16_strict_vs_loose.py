"""E16 runner: agent (claude -p, tools) on shopcore tasks across arms; grade with hidden tests. See data/e16/PLAN.md."""
import argparse, json, os, shutil, statistics as st, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from tok import ntok

REPO = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ.get("SCRATCH", "/tmp/agent-lang-lab"))
SUFFIX = "\n\nThe project is in the current directory. You can run the visible tests with `deno test`. Make the change."
GIT = ["git", "-c", "user.name=x", "-c", "user.email=x@x"]
METRICS = ["files_read", "read_calls", "grep_glob", "tool_result_tokens", "read_tool_tokens", "bash_calls", "bash_tokens", "total_input_tokens", "cost_usd", "turns", "wall_s"]
lock = threading.Lock()

def sh(cmd, cwd, **kw): return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)

def agent(prompt, model, wd, raw):
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "stream-json", "--verbose", "--tools", "Read,Grep,Glob,Edit,Write,Bash",
           "--allowedTools", "Read", "Grep", "Glob", "Edit", "Write", "Bash(deno test:*)", "Bash(deno check:*)",
           "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--disable-slash-commands", "--max-budget-usd", "1.5", "--no-session-persistence"]
    try:
        p = subprocess.run(cmd, cwd=wd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
        out, err = p.stdout, p.stderr[-300:]
    except subprocess.TimeoutExpired as e:
        out, err = (e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout) or "", "timeout"
    Path(raw).write_text(out)
    return out, err

def parse(out):
    names, calls, reads, ttok, res = {}, {}, set(), {}, {}
    for l in out.splitlines():
        try: d = json.loads(l)
        except Exception: continue
        t = d.get("type")
        if t == "assistant":
            for b in d["message"].get("content", []):
                if b.get("type") == "tool_use":
                    n = b["name"]; names[b["id"]] = n; calls[n] = calls.get(n, 0) + 1
                    if n == "Read": reads.add(b["input"].get("file_path", ""))
        elif t == "user" and isinstance(d["message"].get("content"), list):
            for b in d["message"]["content"]:
                if b.get("type") == "tool_result":
                    c = b.get("content")
                    if isinstance(c, list): c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
                    n = names.get(b.get("tool_use_id"), "?"); ttok[n] = ttok.get(n, 0) + ntok(c or "")
        elif t == "result": res = d
    u = res.get("usage", {})
    return dict(calls=calls, files_read=len(reads), read_calls=calls.get("Read", 0), grep_glob=calls.get("Grep", 0) + calls.get("Glob", 0),
                tool_tokens=ttok, tool_result_tokens=sum(ttok.values()), read_tool_tokens=ttok.get("Read", 0), bash_calls=calls.get("Bash", 0), bash_tokens=ttok.get("Bash", 0),
                total_input_tokens=sum(u.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
                output_tokens=u.get("output_tokens", 0), cost_usd=res.get("total_cost_usd", 0), turns=res.get("num_turns", 0),
                is_error=res.get("is_error", True if not res else False), reason=res.get("terminal_reason") or res.get("subtype"))

def deno(wd, f):
    p = sh(["deno", "test", "--no-check", "-A", f], wd, timeout=300)
    return p.returncode == 0

def run(root, task, arm, model, rep, scratch):
    key = f"{task}|{arm}|{model}|{rep}"
    wd = scratch / "e16runs" / key.replace("|", "_")
    if wd.exists(): shutil.rmtree(wd)
    shutil.copytree(root / "arms" / arm, wd)
    bug = root / "tasks" / task / f"{arm}.bug.patch"
    if bug.exists(): sh(["patch", "-p1", "-i", str(bug)], wd).check_returncode()
    sh(["git", "init", "-q"], wd); sh(["git", "add", "-A"], wd); sh(GIT + ["commit", "-qm", "start"], wd)
    prompt = (root / "tasks" / task / "task.md").read_text() + SUFFIX
    raw = str(wd) + ".stream.jsonl"
    t0 = time.time(); out, err = agent(prompt, model, wd, raw); wall = time.time() - t0
    m = parse(out)
    sh(["git", "add", "-A"], wd)
    ns = [l.split("\t") for l in sh(["git", "diff", "--cached", "--numstat", "HEAD"], wd).stdout.splitlines()]
    m["diff_files"] = len(ns); m["diff_lines"] = sum(int(a) + int(b) for a, b, _ in ns if a != "-")
    th = wd / "tests_hidden"; th.mkdir()
    ent = "../src/index.ts" if (wd / "src/index.ts").exists() else "../src/index.js"
    for src, dst in ((root / "hidden/base.test.ts", "base.test.ts"), (root / "tasks" / task / "hidden.test.ts", "hidden.test.ts")):
        (th / dst).write_text(src.read_text().replace("__ENTRY__", ent))
    tp, bp = deno(wd, "tests_hidden/hidden.test.ts"), deno(wd, "tests_hidden/base.test.ts")
    row = dict(key=key, task=task, arm=arm, model=model, rep=rep, task_pass=tp, base_pass=bp, pass_=tp and bp, wall_s=round(wall, 1),
               stderr=err, workdir=str(wd), **m)
    return row

def rel(p): 
    try: return str(Path(p).relative_to(REPO))
    except ValueError: return str(p)

def summarize(rows, path):
    g, gt, out = {}, {}, {}
    for r in rows:
        g.setdefault((r["model"], r["arm"]), []).append(r)
        gt.setdefault((r["model"], r["arm"], r["task"]), []).append(r["pass_"])
    for (mo, arm), rs in sorted(g.items()):
        e = dict(n=len(rs), pass_rate=round(sum(r["pass_"] for r in rs) / len(rs), 3))
        for k in METRICS:
            v = [r[k] for r in rs]; e[k] = dict(mean=round(st.mean(v), 4), median=round(st.median(v), 4))
        e["per_task_pass"] = {t: f"{sum(p)}/{len(p)}" for (m2, a2, t), p in sorted(gt.items()) if (m2, a2) == (mo, arm)}
        out[f"{mo}/{arm}"] = e
    Path(path).write_text(json.dumps(out, indent=1))
    print(f"{'model/arm':22}{'n':>3}{'pass':>6}" + "".join(f"{k[:9]:>10}" for k in METRICS))
    for k, e in out.items(): print(f"{k:22}{e['n']:>3}{e['pass_rate']:>6}" + "".join(f"{e[m]['mean']:>10}" for m in METRICS))

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--models", default="haiku,sonnet"); a.add_argument("--reps", type=int, default=2)
    a.add_argument("--arms", default="strict_ts,loose_ts,loose_js"); a.add_argument("--tasks", default="all")
    a.add_argument("--workers", type=int, default=4); a.add_argument("--summary-only", action="store_true")
    a.add_argument("--root", default=str(REPO / "data/e16")); a.add_argument("--results-prefix", default=str(REPO / "results/e16"))
    a.add_argument("--scratch", default=str(SCRATCH))
    o = a.parse_args()
    root, runs, summ = Path(o.root), Path(o.results_prefix + "_runs.jsonl"), Path(o.results_prefix + ".json")
    runs.parent.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in runs.read_text().splitlines() if l.strip()] if runs.exists() else []
    done = {r["key"] for r in rows}
    tasks = sorted(p.name for p in (root / "tasks").iterdir() if p.is_dir()) if o.tasks == "all" else o.tasks.split(",")
    todo = [(t, ar, m, r) for t in tasks for ar in o.arms.split(",") for m in o.models.split(",") for r in range(o.reps) if f"{t}|{ar}|{m}|{r}" not in done]
    def go(j):
        try: row = run(root, *j, Path(o.scratch))
        except Exception as e: print("FAIL", j, repr(e), file=sys.stderr); return
        row["workdir"] = rel(row["workdir"])
        with lock:
            rows.append(row); runs.open("a").write(json.dumps(row) + "\n")
            print(f"{row['key']}: pass={row['pass_']} cost=${row['cost_usd']:.3f} turns={row['turns']} reads={row['files_read']} wall={row['wall_s']}s", flush=True)
    if not o.summary_only:
        print(f"{len(todo)} runs to do, {len(done)} done"); 
        with ThreadPoolExecutor(o.workers) as ex: list(ex.map(go, todo))
    if rows: summarize(rows, summ)
main()
