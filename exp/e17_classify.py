"""E17 failure classifier. uv run --with openai --with tiktoken python exp/e17_classify.py [--root data/e17] [--results results]"""
import argparse, collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); LAB = os.path.dirname(HERE)
ap = argparse.ArgumentParser(); ap.add_argument("--root", default=os.path.join(LAB, "data/e17")); ap.add_argument("--results", default=os.path.join(LAB, "results"))
A = ap.parse_args()
from e17_agent import client, create, MODEL
LABELS = ["missed_nonlocal_fact", "wrong_logic", "incomplete", "env_or_harness", "other"]
OUT = os.path.join(A.results, "e17_failures.jsonl")
T = {t["id"]: t for t in map(json.loads, open(os.path.join(A.root, "tasks.jsonl")))}
R = {}
for l in open(os.path.join(A.results, "e17_runs.jsonl")): r = json.loads(l); R[r["key"]] = r
done = {json.loads(l)["key"] for l in open(OUT)} if os.path.exists(OUT) else set()
c = client()
for key, r in R.items():
    if r["passed"] or key in done: continue
    t = T.get(r["task"], {}); tp = os.path.join(A.results, "e17_traj", key + ".json")
    tr = json.load(open(tp)) if os.path.exists(tp) else {"steps": []}
    fix = open(os.path.join(A.root, "tasks", r["task"], "fix.patch")).read() if os.path.exists(os.path.join(A.root, "tasks", r["task"], "fix.patch")) else "(missing)"
    traj = "\n".join(f"{i+1}. {s['tool']} {json.dumps(s['args'])[:150]}" for i, s in enumerate(tr["steps"]))
    p = f"""An AI coding agent attempted this task and FAILED the grading tests. Classify why.
Labels: missed_nonlocal_fact (agent missed a fact outside the code it looked at: side effect, inheritance/override, global state, coupled module it never read), wrong_logic (saw the right code, wrote wrong fix), incomplete (ran out of steps / gave up), env_or_harness (tooling/test-env/flaky/grader problem), other.
TASK PROMPT:\n{t.get('prompt')}\n\nTRUE FIX DIFF:\n{fix}\n\nAGENT DIFF:\n{r.get('diff') or '(empty)'}\n
RUN: stop_reason={r.get('stop_reason')} steps={r.get('steps')} f2p_pass={r.get('f2p_pass')} p2p_pass={r.get('p2p_pass')} failed_tests={r.get('failed_tests')} error={r.get('error')}
TRAJECTORY (tool calls in order):\n{traj}
Reply with JSON only: {{"label": one of {LABELS}, "reason": "one line", "nonlocal_fact": "the missed fact or null"}}"""
    try:
        resp = create(c, model=MODEL, input=p, reasoning={"effort": "high"}, text={"format": {"type": "json_object"}})
        d = json.loads(resp.output_text)
        if d.get("label") not in LABELS: d["label"] = "other"
    except Exception as e: d = dict(label="other", reason=f"classifier error {type(e).__name__}", nonlocal_fact=None)
    with open(OUT, "a") as f: f.write(json.dumps(dict(key=key, task=r["task"], effort=r["effort"], **d)) + "\n")
    print(key, d["label"], flush=True)
rows = [json.loads(l) for l in open(OUT)] if os.path.exists(OUT) else []
print(dict(collections.Counter(x["label"] for x in rows)))
for e in sorted({x["effort"] for x in rows}): print(e, dict(collections.Counter(x["label"] for x in rows if x["effort"] == e)))
