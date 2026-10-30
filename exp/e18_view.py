"""E18 deterministic Python code index (stdlib ast only, repo-agnostic). Lazy: View(root) parses on first query, then caches in memory
(ponytail: not refreshed after edits; rebuild = new View)."""
import ast, os, re, threading, time

CAP = 6000
SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "site-packages", "build", "dist", ".tox", ".mypy_cache"}

def cap(s):
    return s if len(s) <= CAP else s[:CAP] + f"\n...[truncated: {len(s)} chars total, showing first {CAP}]"

def dotted(n):
    if isinstance(n, ast.Name): return n.id
    if isinstance(n, ast.Attribute):
        b = dotted(n.value); return f"{b}.{n.attr}" if b else None
    if isinstance(n, ast.Subscript): return dotted(n.value)  # Generic[T]
    return None

def targets(node):
    ts = node.targets if isinstance(node, ast.Assign) else [node.target]
    return [t for t in ts if isinstance(t, ast.Name)]

class Index(ast.NodeVisitor):
    def __init__(self, root):
        self.root = root; self.defs = []; self.classes = []; self.refs = {}; self.strs = []; self.n_files = 0
        self.skip = set(); self.path = ""; self.is_test = False; self.cls = []; self.fn = None
        for d, ds, fs in os.walk(root):
            ds[:] = sorted(x for x in ds if x not in SKIP)
            for f in sorted(fs):
                if f.endswith(".py"): self.add(os.path.join(d, f))
        self.by_name = {}
        for c in self.classes: self.by_name.setdefault(c["name"], []).append(c)
        for c in self.classes: c["bases_r"] = [self.resolve(b, c) for b in c["bases"]]
        self.subs = {}
        for c in self.classes:
            for b in c["bases_r"]:
                for t in b: self.subs.setdefault(id(t), []).append(c)

    def add(self, full):
        try: tree = ast.parse(open(full, "rb").read().decode("utf8", "replace"))
        except (SyntaxError, ValueError, RecursionError): return
        self.n_files += 1; self.path = os.path.relpath(full, self.root)
        self.is_test = self.path.startswith("tests" + os.sep) or (os.sep + "tests" + os.sep) in self.path
        self.cls, self.fn = [], None
        self.visit(tree)

    def ref(self, name, line):
        self.refs.setdefault(name, {}).setdefault(self.path, set()).add((line, self.fn if self.is_test else None))

    def resolve(self, base, c):
        """Resolve a base expression to class records by name; prefer qualified match, then top-level, then same file."""
        name = base.rsplit(".", 1)[-1]; cands = self.by_name.get(name, [])
        if "." in base:
            q = [x for x in cands if ("." + x["qual"]).endswith("." + base)]  # Postgres.Parser -> nested class
            if q: return q
        top = [x for x in cands if x["qual"] == x["name"]]
        same = [x for x in top if x["path"] == c["path"]]
        return same or top

    def visit_ClassDef(self, n):
        qual = ".".join(self.cls + [n.name]); mem = []
        for s in n.body:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): mem.append(s.name)
            elif isinstance(s, (ast.Assign, ast.AnnAssign)):
                for t in targets(s): mem.append(t.id); self.skip.add(id(t)); self.defs.append(dict(path=self.path, line=s.lineno, owner=qual, name=t.id, kind="attr"))
        bases = [b for b in map(dotted, n.bases) if b]
        c = dict(path=self.path, line=n.lineno, qual=qual, name=n.name, bases=bases, members=sorted(set(mem)))
        self.classes.append(c); self.defs.append(dict(path=self.path, line=n.lineno, owner=qual.rpartition(".")[0], name=n.name, kind="class", bases=bases))
        self.cls.append(n.name); save = self.fn
        self.generic_visit(n); self.cls.pop(); self.fn = save

    def visit_FunctionDef(self, n):
        owner = ".".join(self.cls)
        self.defs.append(dict(path=self.path, line=n.lineno, owner=owner, name=n.name, kind="def"))
        save = self.fn
        if self.fn is None: self.fn = (owner + "." if owner else "") + n.name
        self.generic_visit(n); self.fn = save
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, n):
        if not self.cls and self.fn is None:
            for t in targets(n): self.defs.append(dict(path=self.path, line=n.lineno, owner="", name=t.id, kind="attr")); self.skip.add(id(t))
        self.generic_visit(n)
    visit_AnnAssign = visit_Assign

    def visit_Name(self, n):
        if id(n) not in self.skip: self.ref(n.id, n.lineno)
    def visit_Attribute(self, n):
        self.ref(n.attr, n.lineno); self.generic_visit(n)
    def visit_Import(self, n):
        for a in n.names: self.ref(a.name.split(".")[0] if not a.asname else a.name.rsplit(".", 1)[-1], n.lineno)
    def visit_ImportFrom(self, n):
        for a in n.names: self.ref(a.name, n.lineno)
    def visit_Constant(self, n):
        if self.is_test and isinstance(n.value, str) and len(n.value) < 2000: self.strs.append((self.path, n.lineno, self.fn, n.value))

def fmt_def(d):
    if d["kind"] == "class":
        return f"{d['path']}:{d['line']} class {d['name']}({', '.join(d['bases'])})" + (f" in {d['owner']}" if d["owner"] else "")
    return f"{d['path']}:{d['line']} {d['owner'] + '.' if d['owner'] else ''}{d['name']} [{d['kind']}]"

class View:
    def __init__(self, root): self.root = os.path.realpath(root); self._ix = None; self._lk = threading.Lock(); self.build_s = None
    @property
    def ix(self):
        with self._lk:
            if self._ix is None:
                t = time.time(); self._ix = Index(self.root); self.build_s = round(time.time() - t, 2)
        return self._ix

    def definitions(self, name):
        owner, _, last = name.rpartition(".")
        out = sorted((d for d in self.ix.defs if d["name"] == last and (not owner or d["owner"] == owner or d["owner"].endswith("." + owner)
                      )), key=lambda d: (d["path"], d["line"]))
        return cap("\n".join(map(fmt_def, out)) or f"(no definitions of {name})")

    def _find(self, name):
        cs = self.ix.by_name.get(name.rpartition(".")[2], [])
        cs = [c for c in cs if c["qual"] == name or c["qual"].endswith("." + name) or "." not in name]
        top = [c for c in cs if c["qual"] == c["name"]]
        return sorted(top or cs, key=lambda c: (c["path"], c["line"]))

    def hierarchy(self, class_name):
        cs = self._find(class_name)
        if not cs: return f"(no class {class_name})"
        def line(c):
            m = c["members"]; ms = ", ".join(m[:25]) + (f", +{len(m) - 25} more" if len(m) > 25 else "")
            return f"{c['path']}:{c['line']} {c['qual']}({', '.join(c['bases'])}) members: [{ms}]"
        out = []
        for c in cs:
            out.append(f"== {c['qual']} ({c['path']}:{c['line']})\nBASES (nearest first):")
            seen, cur, d = set(), c, 0
            while True:
                nxt = [b for bs in cur["bases_r"] for b in bs if id(b) not in seen]
                if not nxt: break
                for b in nxt: seen.add(id(b)); out.append("  " * d + "- " + line(b))
                cur, d = nxt[0], d + 1
            out.append("SUBCLASSES (transitive):")
            def walk(k, depth, seen):
                for s in sorted(self.ix.subs.get(id(k), []), key=lambda x: (x["path"], x["line"])):
                    if id(s) in seen: continue
                    out.append("  " * depth + "- " + line(s)); walk(s, depth + 1, seen | {id(s)})
            walk(c, 0, {id(c)})
        return cap("\n".join(out))

    def references(self, name):
        last = name.rpartition(".")[2]; by = self.ix.refs.get(last, {})
        if not by: return f"(no references to {name})"
        out = []
        for p in sorted(by):
            ls = sorted({l for l, _ in by[p]}); out.append(f"{p}: " + ", ".join(map(str, ls[:15])) + (f", +{len(ls) - 15} more" if len(ls) > 15 else ""))
        return cap(f"{len(by)} files\n" + "\n".join(out))

    def tests_for(self, name):
        last = name.rpartition(".")[2]; hit = {}
        for p, v in self.ix.refs.get(last, {}).items():
            for l, fn in v:
                if fn is not None or p.startswith("tests"): hit.setdefault((p, fn or "<module>"), set()).add(l)
        out = [f"{p}::{fn} lines {', '.join(map(str, sorted(ls)[:8]))}" for (p, fn), ls in sorted(hit.items())]
        if len(last) >= 3:
            rx = re.compile(r"\b" + re.escape(last) + r"\b", re.I); sh = {}
            for p, l, fn, s in self.ix.strs:
                if rx.search(s): sh.setdefault((p, fn or "<module>"), set()).add(l)
            if sh: out.append("-- in string literals (e.g. SQL in tests):"); out += [f"{p}::{fn} lines {', '.join(map(str, sorted(ls)[:8]))}" for (p, fn), ls in sorted(sh.items())]
        return cap("\n".join(out) or f"(no tests reference {name})")

if __name__ == "__main__":
    import sys; v = View(sys.argv[1]); print(getattr(v, sys.argv[2])(sys.argv[3])); print(f"[index build {v.build_s}s, {v.ix.n_files} files]")
