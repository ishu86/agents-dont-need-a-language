"""E8a: Live model test. Inject a one-token bug into real files; model fixes it via 3 edit formats.
Success = file restored byte-exact. Measures success rate + output tokens + $."""
import ast, json, random, re, subprocess, sys, zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from llm import call, block

MODEL = sys.argv[1] if len(sys.argv) > 1 else "haiku"
root = Path.home() / "dev/browser-use"
MUT = [(" == ", " != ", "one `!=` should be `==`"), (" is None", " is not None", "one `is not None` should be `is None`"),
       (" and ", " or ", "one `or` should be `and`"), (" > ", " < ", "one `<` should be `>`"), (" not in ", " in ", "one ` in ` membership test should be ` not in `")]
random.seed(1)
files = [f for f in subprocess.run(["git", "-C", root, "ls-files", "browser_use/*.py"], capture_output=True, text=True).stdout.split()]
random.shuffle(files)
tasks = []
for f in files:
    src = (root / f).read_text()
    if not 120 <= src.count("\n") <= 450: continue
    try: tree = ast.parse(src)
    except SyntaxError: continue
    L = src.splitlines(keepends=True)
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    random.shuffle(fns)
    for fn in fns:
        body = "".join(L[fn.lineno - 1:fn.end_lineno])
        for a, b, hint in random.sample(MUT, len(MUT)):
            idx = [i for i in range(fn.lineno - 1, fn.end_lineno) if L[i].count(a) == 1 and not L[i].lstrip().startswith("#")]
            if not idx or body.count(b.strip()) > 0: continue
            i = random.choice(idx); M = L[:]; M[i] = L[i].replace(a, b)
            tasks.append(dict(file=f, func=fn.name, orig=src, mut="".join(M), hint=hint)); break
        else: continue
        break
    if len(tasks) >= 12: break

h = lambda l: f"{zlib.crc32(l.encode()) & 0xff:02x}"
def show_hash(s): return "".join(f"{i+1}:{h(l)}|{l}" for i, l in enumerate(s.splitlines(keepends=True)))
ASK = "File `{file}` has one injected bug in function `{func}`: {hint}. Fix only that.\n\n"

def run(t, fmt):
    if fmt == "str_replace":
        p = ASK.format(**t) + f"```python\n{t['mut']}```\n\nReturn ONLY JSON: {{\"old_string\": <exact unique text copied from the file>, \"new_string\": <replacement>}}"
    elif fmt == "hashline":
        p = ASK.format(**t) + "Each line is shown as LINE:HASH|content.\n```\n" + show_hash(t["mut"]) + "```\n\nReturn ONLY JSON: {\"start\": \"LINE:HASH\", \"end\": \"LINE:HASH\", \"lines\": [<replacement lines, without LINE:HASH| prefix>]}"
    else:
        p = ASK.format(**t) + f"```python\n{t['mut']}```\n\nReturn the complete corrected file in one ```python block."
    out, u = call(p, MODEL); got = None
    try:
        if fmt == "rewrite":
            got = block(out)
        else:
            j = json.loads(re.search(r"\{.*\}", out, re.S).group(0))
            if fmt == "str_replace":
                got = t["mut"].replace(j["old_string"], j["new_string"]) if t["mut"].count(j["old_string"]) == 1 else None
            else:
                L = t["mut"].splitlines(keepends=True)
                (s, sh), (e, eh) = [x.split(":") for x in (j["start"], j["end"])]; s, e = int(s), int(e)
                if h(L[s-1]) == sh and h(L[e-1]) == eh:
                    got = "".join(L[:s-1] + [x if x.endswith("\n") else x + "\n" for x in j["lines"]] + L[e:])
    except Exception: pass
    ok = got is not None and got.strip("\n") == t["orig"].strip("\n")
    return dict(fmt=fmt, file=t["file"], ok=ok, applied=got is not None, **u)

jobs = [(t, f) for t in tasks for f in ("str_replace", "hashline", "rewrite")]
with ThreadPoolExecutor(6) as ex: rows = list(ex.map(lambda a: run(*a), jobs))
summ = {}
for f in ("str_replace", "hashline", "rewrite"):
    r = [x for x in rows if x["fmt"] == f]
    summ[f] = dict(n=len(r), success=sum(x["ok"] for x in r), applied=sum(x["applied"] for x in r),
                   mean_out_tokens=round(sum(x.get("out", 0) for x in r) / len(r)), cost_usd=round(sum(x.get("cost", 0) or 0 for x in r), 4))
print(MODEL, json.dumps(summ, indent=1))
Path(f"results/e8a_{MODEL}.json").write_text(json.dumps(dict(summary=summ, rows=rows), indent=1))
