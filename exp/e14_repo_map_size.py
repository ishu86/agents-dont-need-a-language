"""E14: How big is a whole-repo map at different detail levels? (Does it fit in fixed context?)"""
import json, subprocess, sys
from pathlib import Path
from tree_sitter_language_pack import get_parser
sys.path.insert(0, str(Path(__file__).parent)); from tok import ntok
REPOS = {"browser-use": ("python", "*.py"), "cmux": ("typescript", "*.ts"), "gigatoken": ("rust", "*.rs")}
DEFS = {"function_definition", "class_definition", "function_declaration", "class_declaration", "method_definition",
        "interface_declaration", "function_item", "struct_item", "enum_item", "trait_item", "impl_item"}
res = {}
for repo, (lang, g) in REPOS.items():
    root = Path.home() / "dev" / repo; p = get_parser(lang)
    files = [f for f in subprocess.run(["git", "-C", root, "ls-files", g], capture_output=True, text=True).stdout.split() if "node_modules" not in f]
    tree, names, sigs = [], [], []
    for f in files:
        src = (root / f).read_bytes()
        if len(src) > 400_000: continue
        tree.append(f); ns, ss, st = [], [], [p.parse(src).root_node]
        while st:
            n = st.pop()
            if n.type in DEFS:
                nm = n.child_by_field_name("name") or n.child_by_field_name("type")
                if nm is not None: ns.append(nm.text.decode(errors="ignore"))
                ss.append(src[n.start_byte:n.end_byte].split(b"\n")[0].decode(errors="ignore").strip()[:120])
            st.extend(n.children)
        names.append(f"{f}: {', '.join(ns)}"); sigs.append(f + "\n" + "\n".join("  " + s for s in ss))
    res[repo] = dict(files=len(tree), file_list=ntok("\n".join(tree)), names_per_file=ntok("\n".join(names)), signatures=ntok("\n".join(sigs)))
    print(repo, res[repo])
Path("results/e14.json").write_text(json.dumps(res, indent=1))
