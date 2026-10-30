# Check of E15's gap: Claude code reads done through Bash (cat/sed -n/head/tail <code file>), not Read.
import json, re, sys
from pathlib import Path
sys.path.insert(0, "exp"); import e15_read_ceiling as e
CMD = re.compile(r"^\s*(?:cd \S+\s*&&\s*)?(cat|head|tail|sed -n)\b[^|;&>]*?(\S+\.(?:py|ts|tsx|js|jsx|mjs|cjs|rs))\b[^|;&>]*$")
n = raw = out = sym = vis = 0
for path in (Path.home() / ".claude/projects").rglob("*.jsonl"):
    if "subagents" in path.parts: continue
    names = {}
    for line in path.open(errors="ignore"):
        try: m = json.loads(line).get("message")
        except Exception: continue
        if not isinstance(m, dict): continue
        for b in e.claude_blocks(m.get("content")):
            if b.get("type") == "tool_use": names[b.get("id")] = (b.get("name"), b.get("input") or {})
            elif b.get("type") == "tool_result":
                nm, inp = names.get(b.get("tool_use_id"), ("?", {}))
                if nm != "Bash": continue
                mm = CMD.match(inp.get("command", ""))
                if not mm: continue
                text = e.text_of(b.get("content"))
                st, r, o, s = e.classify(text, e.suffix(mm.group(2)), False)
                if st != "code": continue
                n += 1; raw += len(r); out += len(o); sym += len(s)
vis = json.load(open("results/e15.json"))["claude"]["visible_chars"]
print(dict(bash_code_reads=n, raw_chars=raw, outline_chars=out,
           outline_saving_pct_of_visible=round(100 * (raw - out) / vis, 2),
           combined_with_Read_tool_pct=round(100 * (raw - out) / vis + 1.46, 2)))
