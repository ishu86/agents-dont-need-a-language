"""E11: Live model test. A never-seen surface syntax ("Pyx": Python semantics, new keywords/braces),
taught only by a ~250-token spec in the prompt. Transpiled to Python and run against E10's tests."""
import json, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from llm import call, block; from tok import ntok
src10 = (Path(__file__).parent / "e10_lang_model_written.py").read_text()
T = eval(src10.split("T = ", 1)[1].split("\nLANGS", 1)[0])  # reuse task table without running E10
MODEL = sys.argv[1] if len(sys.argv) > 1 else "haiku"; REPS = 2

SPEC = """Pyx language spec (Python semantics, different surface syntax):
- function: fn name(a, b) {   ...   }      (no type hints)
- return: ret expr
- branches: if cond {  } ef cond {  } el {  }
- loops: for x in xs {  }   while cond {  }
- operators: && || ! instead of and/or/not ; T F nil instead of True False None
- a block opens with `{` at the end of its header line and closes with `}` on its own line
- one statement per line, no colons after headers, indentation is ignored
- everything else (lists, dicts, comprehensions, slicing, builtins, imports, strings) is plain Python
Example:
fn count_pos(xs) {
  n = 0
  for x in xs {
    if x > 0 && !(x == 99) {
      n += 1
    }
  }
  ret n
}"""

STR = re.compile(r"(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')")
KW = {"fn": "def", "ef": "elif", "el": "else", "ret": "return"}
def sub_code(s):
    s = s.replace("&&", " and ").replace("||", " or ")
    s = re.sub(r"!(?!=)", " not ", s)
    return re.sub(r"\b(T|F|nil)\b", lambda m: {"T": "True", "F": "False", "nil": "None"}[m.group(1)], s)
def to_py(code):
    out, ind = [], 0
    for raw in code.splitlines():
        line = "".join(p if i % 2 else sub_code(p) for i, p in enumerate(STR.split(raw.strip())))
        while line.startswith("}"): ind -= 1; line = line[1:].strip()
        if not line: continue
        m = re.match(r"(\w+)\b(.*)", line)
        if m and m.group(1) in KW: line = KW[m.group(1)] + m.group(2)
        if line.endswith("{") and re.match(r"(def|if|elif|else|for|while|try|except|with|class|finally)\b", line):
            out.append("    " * ind + line[:-1].rstrip() + ":"); ind += 1
        else: out.append("    " * ind + line)
    return "\n".join(out)

def run(t, rep):
    name, desc, sigs, cases = t
    p = (f"{SPEC}\n\nWrite this function in Pyx: `{name}` with the parameters of `{sigs[0]}` — {desc}.\n"
         "Return only Pyx code in one fenced block.")
    out, u = call(p, MODEL); code = block(out)
    py = to_py(code); ns = {}
    try:
        exec(compile(py, "pyx", "exec"), ns)
        ok = all(ns[name](*a) == e for a, e in cases); err = ""
    except Exception as ex: ok, err = False, f"{type(ex).__name__}: {ex}"
    return dict(task=name, ok=ok, pyx_tokens=ntok(code), err=err, pyx=code, **u)

jobs = [(t, r) for t in T for r in range(REPS)]
with ThreadPoolExecutor(6) as ex: rows = list(ex.map(lambda j: run(*j), jobs))
e10 = json.loads(Path(f"results/e10_{MODEL}.json").read_text())["summary"]["python"]["code_tokens"]
summ = dict(pass_=f"{sum(r['ok'] for r in rows)}/{len(rows)}", spec_tokens=ntok(SPEC),
            pyx_tokens_per_run=round(sum(r["pyx_tokens"] for r in rows) / REPS), python_tokens_e10=e10)
summ["pyx_pct_of_python"] = round(100 * summ["pyx_tokens_per_run"] / e10)
print(MODEL, json.dumps(summ, indent=1))
for r in rows:
    if not r["ok"]: print("FAIL", r["task"], r["err"][:150])
Path(f"results/e11_{MODEL}.json").write_text(json.dumps(dict(summary=summ, rows=rows), indent=1))
