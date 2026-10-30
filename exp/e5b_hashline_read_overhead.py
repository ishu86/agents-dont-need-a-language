"""E5b: input-side cost of hashline: tokens to READ a file plain vs cat -n (Claude Code Read) vs hashline tags."""
import json, subprocess, sys, zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from tok import ntok
root = Path.home() / "dev/browser-use"
files = [f for f in subprocess.run(["git", "-C", root, "ls-files", "*.py"], capture_output=True, text=True).stdout.split()][:150]
t = dict(plain=0, cat_n=0, hashline=0)
for f in files:
    L = (root / f).read_text(errors="ignore").splitlines()
    t["plain"] += ntok("\n".join(L))
    t["cat_n"] += ntok("\n".join(f"{i+1:>6}\t{l}" for i, l in enumerate(L)))
    t["hashline"] += ntok("\n".join(f"{i+1}:{zlib.crc32(l.encode()) & 0xff:02x}|{l}" for i, l in enumerate(L)))
r = {k: round(100 * v / t["plain"], 1) for k, v in t.items()}
print(r); Path("results/e5b.json").write_text(json.dumps(dict(tokens=t, pct_of_plain=r), indent=1))
