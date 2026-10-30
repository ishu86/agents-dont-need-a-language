"""E17 minimal coding agent: gpt-6-luna, OpenAI Responses API, function tools, state kept by passing output items back."""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from tok import ntok

MODEL = "gpt-6-luna"
MAX_STEPS, CAP = 60, 8000
SYSTEM = ("You are fixing a bug in a Python repository checked out in the current workspace. Make the failing tests pass "
          "by editing the source code. Do not modify tests. Do not break other tests. Call finish when done.")

def load_key():
    for l in open(os.path.expanduser("~/.config/agent-lab/openai.env")):
        k, _, v = l.strip().partition("=")
        if k == "OPENAI_API_KEY": return v.strip().strip("'\"")
    raise SystemExit("no OPENAI_API_KEY")

def client():
    from openai import OpenAI
    return OpenAI(api_key=load_key(), max_retries=0)  # we do our own retries

def _fn(name, desc, props, req):
    return dict(type="function", name=name, description=desc, strict=False,
                parameters=dict(type="object", properties=props, required=req, additionalProperties=False))
S, I = {"type": "string"}, {"type": "integer"}
TOOLS = [
    _fn("list_dir", "List entries of a directory (relative to repo root).", {"path": S}, ["path"]),
    _fn("read_file", "Read a file with line numbers; optional 1-based inclusive line range.", {"path": S, "start_line": I, "end_line": I}, ["path"]),
    _fn("grep", "Regex search (ripgrep) over the repo or a subpath. Returns file:line:text.", {"pattern": S, "path": S}, ["pattern"]),
    _fn("edit_file", "Replace `old` with `new` in a file. `old` must match exactly once.", {"path": S, "old": S, "new": S}, ["path", "old", "new"]),
    _fn("run_tests", "Run pytest with the given args (string, e.g. 'tests/test_x.py -k foo -x').", {"args": S}, ["args"]),
    _fn("finish", "Declare the task done.", {"summary": S}, ["summary"]),
]

VIEW_SENTENCE = " Before editing, use definitions/hierarchy/references to find overrides and coupled code in other files."
VIEW_TOOLS = [  # E18: only registered for the +view arm
    _fn("definitions", "Every def, class attribute assignment and class named `name` across the repo (bare `name` or `Class.attr`), as path:line Class(bases).name. Shows overrides across the class hierarchy in one call.", {"name": S}, ["name"]),
    _fn("hierarchy", "Base chain and all (transitive) subclasses of a class, with path:line and the members each defines/overrides. Bases resolved by name within the repo.", {"class_name": S}, ["class_name"]),
    _fn("references", "AST-level uses (names, attributes, imports) of `name`, grouped by file with line numbers; definitions excluded.", {"name": S}, ["name"]),
    _fn("tests_for", "Test files/functions under tests/ that reference `name` (including SQL-like string literals mentioning it).", {"name": S}, ["name"]),
]

def cap(s):
    if len(s) <= CAP: return s
    return s[:CAP] + f"\n...[output truncated: {len(s)} chars total, showing first {CAP}]"

class Env:
    def __init__(self, workdir):
        self.root = os.path.realpath(workdir)
        v = os.path.join(self.root, ".venv", "bin", "python")
        self.py = os.environ.get("E17_PY") or (v if os.path.exists(v) else sys.executable)
    def p(self, rel):
        full = os.path.realpath(os.path.join(self.root, rel or "."))
        if full != self.root and not full.startswith(self.root + os.sep): raise ValueError(f"path escapes workdir: {rel}")
        return full
    def call(self, name, a):
        try: return cap(getattr(self, "t_" + name)(**a))
        except Exception as e: return f"ERROR: {type(e).__name__}: {e}"
    def t_list_dir(self, path="."):
        d = self.p(path)
        return "\n".join(sorted(e + ("/" if os.path.isdir(os.path.join(d, e)) else "") for e in os.listdir(d) if e != ".git")) or "(empty)"
    def t_read_file(self, path, start_line=None, end_line=None):
        L = open(self.p(path), errors="replace").read().split("\n")
        s, e = max(1, start_line or 1), min(len(L), end_line or len(L))
        return "\n".join(f"{i}\t{L[i-1]}" for i in range(s, e + 1))
    def t_grep(self, pattern, path="."):
        r = subprocess.run(["rg", "-n", "--no-heading", "-g", "!.git", "-g", "!.venv", "-e", pattern, self.p(path)], capture_output=True, text=True, timeout=60, cwd=self.root)
        return (r.stdout.replace(self.root + os.sep, "") or r.stderr or "(no matches)")
    def t_edit_file(self, path, old, new):
        f = self.p(path); t = open(f).read(); n = t.count(old)
        if n != 1: return f"ERROR: `old` matched {n} times (need exactly 1)"
        open(f, "w").write(t.replace(old, new)); return "ok"
    def t_run_tests(self, args):
        import shlex
        try:
            r = subprocess.run([self.py, "-m", "pytest", *shlex.split(args)], capture_output=True, text=True, timeout=300, cwd=self.root,
                               env=dict(os.environ, PYTHONPATH=self.root, PATH=os.path.dirname(self.py) + os.pathsep + os.environ.get("PATH", "")))  # sqlglot runs from source
        except subprocess.TimeoutExpired: return "ERROR: pytest timed out after 300s"
        out = r.stdout + r.stderr
        return out[-CAP:] if len(out) > CAP else out  # tail holds the failure summary
    def t_finish(self, summary): return "done"
    def _view(self):
        if not hasattr(self, "view"):
            from e18_view import View
            self.view = View(self.root)
        return self.view
    def t_definitions(self, name): return self._view().definitions(name)
    def t_hierarchy(self, class_name): return self._view().hierarchy(class_name)
    def t_references(self, name): return self._view().references(name)
    def t_tests_for(self, name): return self._view().tests_for(name)

def create(c, **kw):
    for i in range(8):
        try: return c.responses.create(**kw)
        except Exception as e:
            name = type(e).__name__; code = getattr(e, "status_code", None)
            if name in ("RateLimitError", "APIConnectionError", "APITimeoutError", "InternalServerError") or (code and code >= 500):
                time.sleep(min(60, 2 ** i + 1)); continue
            raise
    raise RuntimeError("API retries exhausted")

def usage(u):
    g = lambda o, k: (getattr(o, k, 0) or 0) if o is not None else 0
    return dict(input_tokens=g(u, "input_tokens"), cached_tokens=g(getattr(u, "input_tokens_details", None), "cached_tokens"),
                output_tokens=g(u, "output_tokens"), reasoning_tokens=g(getattr(u, "output_tokens_details", None), "reasoning_tokens"))

def run_agent(workdir, prompt, effort, max_steps=MAX_STEPS, view=False):
    c, env, t0 = client(), Env(workdir), time.time()
    traj = dict(model=MODEL, effort=effort, prompt=prompt, steps=[], responses=[], stop_reason=None)
    inp = [dict(role="user", content=prompt)]
    tools, system = (TOOLS + VIEW_TOOLS, SYSTEM + VIEW_SENTENCE) if view else (TOOLS, SYSTEM)
    try:
        while True:
            if len(traj["steps"]) >= max_steps: traj["stop_reason"] = "max_steps"; break
            r = create(c, model=MODEL, instructions=system, input=inp, tools=tools, reasoning={"effort": effort}, store=False,
                       include=["reasoning.encrypted_content"])
            traj["responses"].append(usage(r.usage) | dict(status=r.status))
            inp += [it.model_dump(exclude_none=True) for it in r.output]  # includes reasoning items (encrypted) passed back verbatim
            calls = [it for it in r.output if it.type == "function_call"]
            if not calls: traj["stop_reason"] = "no_tool_call"; break
            done = False
            for it in calls:
                try: a = json.loads(it.arguments)
                except Exception: a = {}
                out = env.call(it.name, a) if len(traj["steps"]) < max_steps else "ERROR: step limit reached"
                traj["steps"].append(dict(tool=it.name, args=a, output_chars=len(out), output_tokens=ntok(out)))
                inp.append(dict(type="function_call_output", call_id=it.call_id, output=out))
                done |= it.name == "finish"
            if done: traj["stop_reason"] = "finish"; break
    except Exception as e:
        traj["stop_reason"] = "error"; traj["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    traj["wall_s"] = round(time.time() - t0, 1)
    traj["usage"] = {k: sum(x[k] for x in traj["responses"]) for k in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens")}
    return traj

if __name__ == "__main__":
    wd, eff = sys.argv[1], sys.argv[2]
    print(json.dumps(run_agent(wd, sys.stdin.read(), eff), indent=1))
