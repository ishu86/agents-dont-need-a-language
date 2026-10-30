"""E1: In real code, how many tokens go to comments, type annotations, indentation?
Upper bound on what a new syntax could save by changing surface form."""
import json, re, subprocess, sys
from pathlib import Path
from tree_sitter_language_pack import get_parser
sys.path.insert(0, str(Path(__file__).parent)); from tok import ntok

REPOS = {  # language -> (repo, globs)
    "python": ("browser-use", ["*.py"]),
    "typescript": ("cmux", ["*.ts"]),
    "rust": ("gigatoken", ["*.rs"]),
}
COMMENT = {"comment", "line_comment", "block_comment"}
TYPE_FIELDS = ("type", "return_type")

def spans(root, want):
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        if want(n): out.append((n.start_byte, n.end_byte)); continue
        stack.extend(n.children)
    return out

def type_spans(root):
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        for f in TYPE_FIELDS:
            c = n.child_by_field_name(f)
            if c is not None and n.type not in ("type_alias_declaration", "type_item", "interface_declaration"):
                out.append((c.start_byte, c.end_byte))
        stack.extend(n.children)
    return out

def blank(src, sp):
    b = bytearray(src)
    for s, e in sp: b[s:e] = b" " * (e - s)
    return b.decode("utf8", "ignore")

def squeeze(t):  # drop indentation + blank-only space runs
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t))

res = {}
for lang, (repo, globs) in REPOS.items():
    root = Path.home() / "dev" / repo
    files = subprocess.run(["git", "-C", root, "ls-files", *globs], capture_output=True, text=True).stdout.split()
    files = [f for f in files if "test" not in f.lower() and "node_modules" not in f][:400]
    p = get_parser(lang if lang != "typescript" else "typescript")
    tot = dict(files=0, tokens=0, no_comments=0, no_types=0, no_ws=0, lines=0)
    for f in files:
        src = (root / f).read_bytes()
        if len(src) > 400_000: continue
        t = p.parse(src).root_node
        text = src.decode("utf8", "ignore")
        tot["files"] += 1; tot["lines"] += text.count("\n")
        tot["tokens"] += ntok(text)
        tot["no_comments"] += ntok(blank(src, spans(t, lambda n: n.type in COMMENT)))
        tot["no_types"] += ntok(blank(src, type_spans(t)))
        tot["no_ws"] += ntok(squeeze(text))
    T = tot["tokens"]
    tot["pct_comments"] = round(100 * (T - tot["no_comments"]) / T, 1)
    tot["pct_type_annotations"] = round(100 * (T - tot["no_types"]) / T, 1)
    tot["pct_whitespace"] = round(100 * (T - tot["no_ws"]) / T, 1)
    tot["tokens_per_line"] = round(T / tot["lines"], 2)
    res[lang] = tot
    print(lang, json.dumps(tot))
Path("results/e1.json").write_text(json.dumps(res, indent=1))
