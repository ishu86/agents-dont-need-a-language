"""E8c: Live model test. Can the agent find the right function from an outline instead of the full file?
Question = a function's docstring summary; answer = function name. Arms: full / outline+doc / bare outline."""
import ast, json, random, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from llm import call; from tok import ntok

MODEL = sys.argv[1] if len(sys.argv) > 1 else "haiku"
root = Path.home() / "dev/browser-use"; random.seed(2)
files = subprocess.run(["git", "-C", root, "ls-files", "browser_use/*.py"], capture_output=True, text=True).stdout.split()
random.shuffle(files)

def outline(src, tree, doc):
    L = src.splitlines(keepends=True); drop = set(); notes = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.body:
            b0 = n.body[0].lineno - 1
            if isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) and doc:
                d = str(n.body[0].value.value).strip().splitlines()[0]
                notes[b0] = " " * n.body[0].col_offset + f'"""{d}"""\n'
            drop |= set(range(b0, n.end_lineno)); notes.setdefault(b0, "")
            notes[b0] += " " * n.body[0].col_offset + "...\n"
    return "".join(notes.get(i, "") if i in drop else l for i, l in enumerate(L) if i not in drop or i in notes)

tasks = []
for f in files:
    src = (root / f).read_text()
    if not 250 <= src.count("\n") <= 900: continue
    tree = ast.parse(src)
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(n)
           and not n.name.startswith("__") and len(ast.get_docstring(n).split()) >= 6]
    names = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    fns = [n for n in fns if names.count(n.name) == 1]
    if len(fns) < 3: continue
    fn = random.choice(fns); q = ast.get_docstring(fn).splitlines()[0]
    q = re.sub(r"\b" + re.escape(fn.name) + r"\b", "this", q)
    tasks.append(dict(file=f, answer=fn.name, q=q, full=src, outline_doc=outline(src, tree, True), outline=outline(src, tree, False)))
    if len(tasks) >= 15: break

def run(t, arm):
    p = (f"File `{t['file']}`:\n```python\n{t[arm]}```\n\nWhich function does this: \"{t['q']}\"?\n"
         "Answer with ONLY the function name.")
    out, u = call(p, MODEL)
    name = re.sub(r"[`()\s]", "", out.strip().splitlines()[-1] if out.strip() else "").split(".")[-1]
    return dict(arm=arm, ok=name == t["answer"], got=name, want=t["answer"], in_tokens=ntok(t[arm]), **u)

jobs = [(t, a) for t in tasks for a in ("full", "outline_doc", "outline")]
with ThreadPoolExecutor(6) as ex: rows = list(ex.map(lambda j: run(*j), jobs))
summ = {a: dict(success=f"{sum(r['ok'] for r in rows if r['arm']==a)}/{len(tasks)}",
                mean_input_tokens=round(sum(r["in_tokens"] for r in rows if r["arm"] == a) / len(tasks)))
        for a in ("full", "outline_doc", "outline")}
print(MODEL, json.dumps(summ, indent=1)); Path(f"results/e8c_{MODEL}.json").write_text(json.dumps(dict(summary=summ, rows=rows), indent=1))
