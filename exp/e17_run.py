"""E17 runner. uv run --with openai --with tiktoken python exp/e17_run.py --tasks all --efforts low,high --reps 1 --workers 4"""
import argparse, json, os, shutil, subprocess, sys, tempfile, threading, collections
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
LAB = os.path.dirname(HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--tasks", default="all"); ap.add_argument("--efforts", default="low,high")
ap.add_argument("--reps", type=int, default=1); ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--arms", default=None, help="e.g. low,low+view (overrides --efforts); arm = effort[+view]")
ap.add_argument("--exp", default="e17", help="prefix for results files")
ap.add_argument("--summary-only", action="store_true")
ap.add_argument("--root", default=os.path.join(LAB, "data/e17"), help="dir with tasks.jsonl, setup_task.sh, grade.sh")
ap.add_argument("--results", default=os.path.join(LAB, "results"))
A = ap.parse_args()
RUNS, TRAJ = os.path.join(A.results, A.exp + "_runs.jsonl"), os.path.join(A.results, A.exp + "_traj")
lock = threading.Lock()

def tasks():
    return {t["id"]: t for t in map(json.loads, open(os.path.join(A.root, "tasks.jsonl")))}
def rows():
    return [json.loads(l) for l in open(RUNS)] if os.path.exists(RUNS) else []
def sh(*a, **k): return subprocess.run(a, capture_output=True, text=True, **k)

def one(t, arm, rep):
    from e17_agent import run_agent, VIEW_TOOLS
    effort, _, v = arm.partition("+"); view = v == "view"
    key = f"{t['id']}__{arm}__{rep}"
    wd = tempfile.mkdtemp(prefix=f"e17_{key}_")
    row = dict(key=key, task=t["id"], effort=effort, rep=rep, **({"arm": arm} if A.arms else {}))
    try:
        s = sh("bash", os.path.join(A.root, "setup_task.sh"), t["id"], wd)
        if s.returncode: raise RuntimeError("setup failed: " + (s.stderr or s.stdout)[-300:])
        tr = run_agent(wd, t["prompt"], effort, view=view)
        diff = sh("git", "-C", wd, "diff").stdout
        g = sh("bash", os.path.join(A.root, "grade.sh"), t["id"], wd)
        try: grade = json.loads(g.stdout.strip().splitlines()[-1])
        except Exception: grade = dict(f2p_pass=False, p2p_pass=False, failed_tests=[], grade_error=(g.stderr or g.stdout)[-300:])
        steps = tr["steps"]
        row |= dict(f2p_pass=bool(grade.get("f2p_pass")), p2p_pass=bool(grade.get("p2p_pass")), failed_tests=grade.get("failed_tests", []),
                    passed=bool(grade.get("f2p_pass") and grade.get("p2p_pass")),
                    regression=bool(grade.get("f2p_pass") and not grade.get("p2p_pass")),
                    steps=len(steps), files_read=len({s["args"].get("path") for s in steps if s["tool"] == "read_file"}),
                    stop_reason=tr["stop_reason"], **({"view_calls": sum(s["tool"] in {x["name"] for x in VIEW_TOOLS} for s in steps)} if A.arms else {}), wall_s=tr["wall_s"], diff=diff, **tr["usage"])
        if tr.get("error"): row["error"] = tr["error"]
        tr["diff"], tr["grade"] = diff, grade
        os.makedirs(TRAJ, exist_ok=True); json.dump(tr, open(os.path.join(TRAJ, key + ".json"), "w"), indent=1)
    except Exception as e:
        row |= dict(passed=False, regression=False, stop_reason="runner_error", error=f"{type(e).__name__}: {e}"[:400])
    finally: shutil.rmtree(wd, ignore_errors=True)
    with lock, open(RUNS, "a") as f: f.write(json.dumps(row) + "\n")
    print(key, "PASS" if row["passed"] else "FAIL", row.get("stop_reason"), flush=True)

def summary():
    R = {}
    for r in rows(): R[r["key"]] = r  # last row per key wins
    R = list(R.values()); out = dict(per_effort={}, per_task={}); arm = lambda r: r.get("arm", r["effort"])
    for e in sorted({arm(r) for r in R}):
        X = [r for r in R if arm(r) == e]; m = lambda k: round(sum(r.get(k, 0) for r in X) / len(X), 1)
        out["per_effort"][e] = dict(n=len(X), pass_rate=round(sum(r["passed"] for r in X) / len(X), 3), regressions=sum(r["regression"] for r in X),
            mean_steps=m("steps"), mean_files_read=m("files_read"), mean_input_tokens=m("input_tokens"), mean_cached_tokens=m("cached_tokens"),
            mean_output_tokens=m("output_tokens"), mean_reasoning_tokens=m("reasoning_tokens"), mean_wall_s=m("wall_s"),
            **({"mean_view_calls": m("view_calls")} if A.arms else {}), max_steps_hit=sum(r.get("stop_reason") == "max_steps" for r in X), errors=sum(r.get("stop_reason") in ("error", "runner_error") for r in X))
    for r in R: out["per_task"].setdefault(r["task"], {})[f"{arm(r)}#{r['rep']}"] = dict(passed=r["passed"], regression=r["regression"], steps=r.get("steps"), stop=r.get("stop_reason"))
    json.dump(out, open(os.path.join(A.results, A.exp + ".json"), "w"), indent=1); print(json.dumps(out["per_effort"], indent=1))

if not A.summary_only:
    T = tasks(); ids = list(T) if A.tasks == "all" else A.tasks.split(",")
    done = {r["key"] for r in rows() if r.get("stop_reason") not in ("error", "runner_error")}
    jobs = [(T[i], e, n) for i in ids for e in (A.arms or A.efforts).split(",") for n in range(A.reps) if f"{i}__{e}__{n}" not in done]
    os.makedirs(A.results, exist_ok=True)
    with ThreadPoolExecutor(A.workers) as ex: list(ex.map(lambda j: one(*j), jobs))
summary()
