"""E3: Cost of reading code: whole file vs outline (signatures only) vs one symbol."""
import json, statistics, subprocess, sys
from pathlib import Path
from tree_sitter_language_pack import get_parser
sys.path.insert(0, str(Path(__file__).parent)); from tok import ntok

REPOS = {"python": ("browser-use", "*.py"), "typescript": ("cmux", "*.ts"), "rust": ("gigatoken", "*.rs")}
FUNCS = {"function_definition", "function_declaration", "method_definition", "function_item", "arrow_function"}

def outline(src, root):
    cuts, funcs, stack = [], [], [root]
    while stack:
        n = stack.pop()
        if n.type in FUNCS:
            funcs.append(n.end_byte - n.start_byte)
            b = n.child_by_field_name("body")
            if b is not None and b.end_byte - b.start_byte > 40:
                cuts.append((b.start_byte, b.end_byte)); continue
        stack.extend(n.children)
    out, last = [], 0
    for s, e in sorted(cuts):
        if s < last: continue
        out.append(src[last:s]); out.append(b" ..."); last = e
    out.append(src[last:])
    return b"".join(out).decode("utf8", "ignore"), funcs

res = {}
for lang, (repo, g) in REPOS.items():
    root = Path.home() / "dev" / repo
    files = [f for f in subprocess.run(["git", "-C", root, "ls-files", g], capture_output=True, text=True).stdout.split() if "node_modules" not in f]
    p = get_parser(lang); full = outl = 0; fsizes = []; ratios = []
    for f in files[:400]:
        src = (root / f).read_bytes()
        if not 2000 < len(src) < 400_000: continue
        o, funcs = outline(src, p.parse(src).root_node)
        a, b = ntok(src.decode("utf8", "ignore")), ntok(o)
        full += a; outl += b; ratios.append(b / a)
        fsizes += [x / len(src) * a for x in funcs]  # approx tokens per function
    res[lang] = dict(files=len(ratios), full_tokens=full, outline_tokens=outl,
                     outline_pct_of_full=round(100 * outl / full, 1),
                     mean_file_tokens=round(full / len(ratios)),
                     median_function_tokens=round(statistics.median(fsizes)) if fsizes else None,
                     p90_function_tokens=round(statistics.quantiles(fsizes, n=10)[-1]) if fsizes else None)
    print(lang, res[lang])
Path("results/e3.json").write_text(json.dumps(res, indent=1))
