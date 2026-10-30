"""E10: Live model test. Same 8 tasks, model writes them in Python / TypeScript / Rust.
Measures pass rate (hidden tests) and tokens of the code the MODEL wrote (not hand-written)."""
import json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from llm import call, block; from tok import ntok

MODEL = sys.argv[1] if len(sys.argv) > 1 else "haiku"
S = os.environ.get("SCRATCH", "/tmp/agent-lang-lab")
env = dict(os.environ, RUSTUP_HOME=f"{S}/rustup", CARGO_HOME=f"{S}/cargo")
# name, desc, (py sig, ts sig, rs sig), cases [(args, expected)]
T = [
 ("is_pal", "true if s is a palindrome ignoring case and non-alphanumeric chars",
  ("def is_pal(s: str) -> bool", "function is_pal(s: string): boolean", "fn is_pal(s: &str) -> bool"),
  [(["A man, a plan, a canal: Panama"], True), (["race a car"], False), ([""], True)]),
 ("rle", "run-length encode: 'aaab' -> 'a3b1'",
  ("def rle(s: str) -> str", "function rle(s: string): string", "fn rle(s: &str) -> String"),
  [(["aaab"], "a3b1"), ([""], ""), (["abc"], "a1b1c1")]),
 ("merge", "merge overlapping closed intervals, return sorted by start",
  ("def merge(iv: list[list[int]]) -> list[list[int]]", "function merge(iv: number[][]): number[][]", "fn merge(iv: Vec<Vec<i64>>) -> Vec<Vec<i64>>"),
  [([[[1, 3], [2, 6], [8, 10]]], [[1, 6], [8, 10]]), ([[[1, 4], [4, 5]]], [[1, 5]]), ([[]], [])]),
 ("roman", "convert a roman numeral to an integer",
  ("def roman(s: str) -> int", "function roman(s: string): number", "fn roman(s: &str) -> i64"),
  [(["MCMXCIV"], 1994), (["III"], 3), (["LVIII"], 58)]),
 ("two_sum", "indices [i, j], i < j, of the two numbers that add to target (exactly one answer)",
  ("def two_sum(nums: list[int], target: int) -> list[int]", "function two_sum(nums: number[], target: number): number[]", "fn two_sum(nums: Vec<i64>, target: i64) -> Vec<i64>"),
  [([[2, 7, 11, 15], 9], [0, 1]), ([[3, 2, 4], 6], [1, 2])]),
 ("lcp", "longest common prefix of the strings ('' if none or empty list)",
  ("def lcp(xs: list[str]) -> str", "function lcp(xs: string[]): string", "fn lcp(xs: Vec<String>) -> String"),
  [([["flower", "flow", "flight"]], "fl"), ([["dog", "car"]], ""), ([[]], "")]),
 ("balanced", "true if brackets ()[]{} are balanced; other chars ignored",
  ("def balanced(s: str) -> bool", "function balanced(s: string): boolean", "fn balanced(s: &str) -> bool"),
  [(["{[()]}x"], True), (["(]"], False), (["(("], False)]),
 ("primes", "all primes <= n in ascending order",
  ("def primes(n: int) -> list[int]", "function primes(n: number): number[]", "fn primes(n: i64) -> Vec<i64>"),
  [([10], [2, 3, 5, 7]), ([1], []), ([2], [2])]),
]
LANGS = ("python", "typescript", "rust")

def rs_lit(v, sig_arg=None):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, int): return str(v)
    if isinstance(v, str): return json.dumps(v)
    if isinstance(v, list):
        inner = ", ".join(rs_lit(x) for x in v)
        return f"vec![{inner}]" if not (v and isinstance(v[0], str)) else f"vec![{', '.join(json.dumps(x) + '.to_string()' for x in v)}]"

def test(lang, t, code):
    name, _, sigs, cases = t; d = Path(tempfile.mkdtemp())
    if lang == "python":
        body = code + "\n" + "\n".join(f"assert {name}(*{json.dumps(a)}) == {json.dumps(e) if not isinstance(e, bool) else e}" for a, e in cases)
        (d / "t.py").write_text(body.replace("true", "True").replace("false", "False") if False else body)
        cmd = ["python3", "t.py"]
    elif lang == "typescript":
        body = code + "\n" + "\n".join(f"if (JSON.stringify({name}(...{json.dumps(a)})) !== {json.dumps(json.dumps(e, separators=(",", ":")))}) throw new Error('fail {i}');" for i, (a, e) in enumerate(cases))
        (d / "t.ts").write_text(body); cmd = ["deno", "run", "-q", "t.ts"]
    else:
        def arg(a, sig):
            s = rs_lit(a)
            return s if not isinstance(a, list) or a or "String" in sig else ("Vec::new()")
        calls = "\n".join(f"    assert_eq!({name}({', '.join(rs_lit(x) if not (isinstance(x, list) and not x) else 'vec![]' for x in a)}), {rs_lit(e) if not (isinstance(e, list) and not e) else 'Vec::<Vec<i64>>::new()' if name == 'merge' else 'Vec::<i64>::new()' if isinstance(e, list) else rs_lit(e)}{'.to_string()' if isinstance(e, str) else ''});" for a, e in cases)
        (d / "t.rs").write_text(code + "\n#[allow(dead_code)]\nfn main() {\n" + calls + "\n}\n")
        b = subprocess.run([f"{S}/cargo/bin/rustc", "--edition", "2021", "-O", "t.rs", "-o", "t"], cwd=d, capture_output=True, text=True, env=env)
        if b.returncode: return False, b.stderr[-400:]
        cmd = ["./t"]
    r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=60)
    return r.returncode == 0, r.stderr[-400:]

def run(t, li):
    lang = LANGS[li]; p = (f"Write this {lang} function: `{t[2][li]}` — {t[1]}.\n"
                           f"Return only the code (function plus any imports it needs; no main, no tests) in one fenced block.")
    out, u = call(p, MODEL); code = block(out)
    if lang == "rust": code = code.replace("fn main()", "fn _unused_main()")
    ok, err = test(lang, t, code)
    return dict(lang=lang, task=t[0], ok=ok, code_tokens=ntok(code), err=err if not ok else "", **u)

jobs = [(t, i) for t in T for i in range(3)]
with ThreadPoolExecutor(6) as ex: rows = list(ex.map(lambda j: run(*j), jobs))
summ = {l: dict(pass_=f"{sum(r['ok'] for r in rows if r['lang']==l)}/{len(T)}",
                code_tokens=sum(r["code_tokens"] for r in rows if r["lang"] == l)) for l in LANGS}
for l in LANGS: summ[l]["pct_of_python"] = round(100 * summ[l]["code_tokens"] / summ["python"]["code_tokens"])
print(MODEL, json.dumps(summ, indent=1)); Path(f"results/e10_{MODEL}.json").write_text(json.dumps(dict(summary=summ, rows=rows), indent=1))
