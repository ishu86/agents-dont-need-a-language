"""E15: same-trajectory ceiling. What if source reads had been outlines?

Aggregates only. Does not open the files the agents read. Does not call a model.
"""
import json, re, sqlite3, sys
from pathlib import Path

from tree_sitter_language_pack import get_parser

sys.path.insert(0, str(Path(__file__).parent))
from tok import ntok  # noqa: E402  (imported so ./run.sh's tiktoken dep is real; chars are the metric)

FUNCS = {"function_definition", "function_declaration", "method_definition", "function_item", "arrow_function"}
EXT_LANG = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".rs": "rust",
}
CLAUDE_W = dict(input_tokens=1.0, cache_read_input_tokens=0.1, cache_creation_input_tokens=1.25, output_tokens=5.0)
LINE_NO = re.compile(r"^[ ]*\d+(?:\t|\|)")
PARSERS = {}
METHOD = ("same-trajectory ceiling. savings_pct = 100 * (read_chars - new_chars) / visible_chars. "
          "Biased high: system prompt is in the bill and not in the denominator. Negatives kept.")


def parser_for(lang):
    if lang not in PARSERS:
        PARSERS[lang] = get_parser(lang)
    return PARSERS[lang]


def outline(src, root):
    cuts, stack = [], [root]
    while stack:
        n = stack.pop()
        if n.type in FUNCS:
            b = n.child_by_field_name("body")
            if b is not None and b.end_byte - b.start_byte > 40:
                cuts.append((b.start_byte, b.end_byte))
                continue
        stack.extend(n.children)
    out, last = [], 0
    for s, e in sorted(cuts):
        if s < last:
            continue
        out.append(src[last:s])
        out.append(b" ...")
        last = e
    out.append(src[last:])
    return b"".join(out).decode("utf-8", "ignore")


def smallest_symbol(src, root):
    best = None
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in FUNCS:
            size = n.end_byte - n.start_byte
            if size > 40 and (best is None or size < best[0]):
                best = (size, n.start_byte, n.end_byte)
        stack.extend(n.children)
    if best is None:
        return None
    return src[best[1]:best[2]].decode("utf-8", "ignore")


def strip_claude_numbers(text):
    lines = text.splitlines(keepends=True)
    if not lines:
        return text
    hits = sum(1 for ln in lines if LINE_NO.match(ln))
    if hits * 2 < len(lines):
        return text
    out = []
    for ln in lines:
        m = LINE_NO.match(ln)
        out.append(ln[m.end():] if m else ln)
    return "".join(out)


def suffix(path):
    path = str(path or "")
    dot = path.rfind(".")
    if dot < 0 or "/" in path[dot:] or "\\" in path[dot:]:
        return ""
    return path[dot:].lower()


def classify(raw, ext, numbered):
    """Return kind, raw, outline, symbol. raw is the billed text."""
    if len(raw) < 200:
        return "short", raw, raw, raw
    body = strip_claude_numbers(raw) if numbered else raw
    lang = EXT_LANG.get(ext)
    if not lang:
        return "non_code", raw, raw, raw
    try:
        src = body.encode("utf-8", "ignore")
        tree = parser_for(lang).parse(src)
        outlined = outline(src, tree.root_node)
        symbol = smallest_symbol(src, tree.root_node) or body
    except Exception:
        return "unparsed", raw, raw, raw
    return "code", raw, outlined, symbol


def self_check():
    src = b"def tiny():\n    return 1\n" * 8 + b"def mid():\n    x = 1\n    y = 2\n    z = 3\n    return x + y + z\n"
    tree = parser_for("python").parse(src)
    outlined = outline(src, tree.root_node)
    symbol = smallest_symbol(src, tree.root_node)
    assert len(outlined) < len(src.decode()), (len(outlined), len(src))
    assert symbol is not None and len(symbol) < len(outlined), (symbol, outlined)
    short = "x" * 50
    kind, raw, out, sym = classify(short, ".py", False)
    assert kind == "short" and out == short and sym == short
    plain = "no functions here\n" * 5
    kind, raw, out, sym = classify(plain, ".py", False)
    assert kind == "short" and out == plain
    long_plain = "no functions here\n" * 20
    kind, raw, out, sym = classify(long_plain, ".py", False)
    assert kind == "code" and out == long_plain and sym == long_plain
    numbered = "\n".join(f"{i}\tline {i} of a read that is long enough to pass the short check here" for i in range(1, 12))
    stripped = strip_claude_numbers(numbered)
    assert not stripped.splitlines()[0][:2].strip().isdigit() or "\t" not in stripped.splitlines()[0][:4]
    assert stripped.splitlines()[0].startswith("line ")


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return ""


def pct(delta, visible):
    if not visible:
        return 0.0
    return 100.0 * delta / visible


def claude_blocks(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def scan_claude():
    usage = dict(input_tokens=0, output_tokens=0, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    visible = 0
    image_chars = 0
    sessions = 0
    reads = dict(image=0, text=0, code_outlined=0, non_code=0, short=0, unparsed=0, partial=0, whole=0)
    chars = dict(read_raw=0, outline=0, symbol=0)
    split = dict(whole_raw=0, whole_outline=0, partial_raw=0, partial_outline=0)
    root = Path.home() / ".claude" / "projects"
    files = [p for p in root.rglob("*.jsonl") if "subagents" not in p.parts]
    for i, path in enumerate(files, 1):
        sessions += 1
        if i % 20 == 0:
            print(f"claude {i}/{len(files)}", file=sys.stderr)
        names = {}
        seen = set()
        for line in path.open(errors="ignore"):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            if rec.get("type") == "assistant" and isinstance(msg.get("usage"), dict) and msg.get("id") not in seen:
                seen.add(msg.get("id"))
                u = msg["usage"]
                for k in usage:
                    usage[k] += u.get(k) or 0
            for block in claude_blocks(msg.get("content")):
                kind = block.get("type")
                if kind == "text":
                    visible += len(block.get("text") or "")
                elif kind == "thinking":
                    visible += len(block.get("thinking") or "")
                elif kind == "tool_use":
                    names[block.get("id")] = (block.get("name"), block.get("input") or {})
                    visible += len(json.dumps(block.get("input") or {}))
                elif kind == "tool_result":
                    name, inp = names.get(block.get("tool_use_id"), ("?", {}))
                    rc = block.get("content")
                    if isinstance(rc, list):
                        image_chars += sum(len(json.dumps(x)) for x in rc if isinstance(x, dict) and x.get("type") != "text")
                        text = "".join(x.get("text", "") for x in rc if isinstance(x, dict) and x.get("type") == "text")
                        image_only = not any(isinstance(x, dict) and x.get("type") == "text" for x in rc)
                    else:
                        text = rc if isinstance(rc, str) else json.dumps(rc)
                        image_only = False
                    if name == "Read" and image_only:
                        reads["image"] += 1
                        continue
                    visible += len(text)
                    if name != "Read":
                        continue
                    if not text:
                        reads["image"] += 1
                        continue
                    reads["text"] += 1
                    partial = bool(inp.get("offset") or inp.get("limit"))
                    reads["partial" if partial else "whole"] += 1
                    ext = suffix(inp.get("file_path"))
                    status, raw, outlined, symbol = classify(text, ext, True)
                    if status != "code":
                        reads[status] += 1
                        continue
                    reads["code_outlined"] += 1
                    chars["read_raw"] += len(raw)
                    chars["outline"] += len(outlined)
                    chars["symbol"] += len(symbol)
                    bucket = "partial" if partial else "whole"
                    split[f"{bucket}_raw"] += len(raw)
                    split[f"{bucket}_outline"] += len(outlined)
    return dict(sessions=sessions, usage=usage, visible_chars=visible, image_chars=image_chars,
                reads=reads, chars=chars, split=split)


def anchor(claude):
    published = json.loads(Path("results/e2.json").read_text())
    exp = published["usage"]
    for k, v in exp.items():
        got = claude["usage"][k]
        if abs(got - v) / max(v, 1) > 0.01:
            print(f"e2 anchor fail {k}: got {got} published {v}", file=sys.stderr)
            return False
    cost = sum(claude["usage"][k] * CLAUDE_W[k] for k in CLAUDE_W)
    share = 100 * claude["usage"]["cache_read_input_tokens"] * CLAUDE_W["cache_read_input_tokens"] / cost
    if not 72.0 <= share <= 73.0:
        print(f"e2 anchor fail cache-read share {share:.2f}", file=sys.stderr)
        return False
    text = claude["reads"]["text"]
    if not 100 <= text <= 400:
        print(f"claude text reads {text} outside 100-400", file=sys.stderr)
        return False
    return True


def codex_item_text(item):
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def scan_codex():
    usage = dict(input_tokens=0, cached_input_tokens=0, cache_write_input_tokens=0, output_tokens=0, reasoning_output_tokens=0)
    visible = 0
    shell_stdout = 0
    read_stdout = 0
    sessions = 0
    failing = 0
    checked = 0
    reads = dict(pure_read=0, mixed_shell=0, code_outlined=0, non_code=0, short=0, unparsed=0)
    chars = dict(read_raw=0, outline=0, symbol=0)
    files = list((Path.home() / ".codex" / "sessions").rglob("*.jsonl"))
    for i, path in enumerate(files, 1):
        sessions += 1
        if i % 20 == 0:
            print(f"codex {i}/{len(files)}", file=sys.stderr)
        last = None
        for line in path.open(errors="ignore"):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            payload = rec.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("type") == "token_count":
                info = payload.get("info") or {}
                total = info.get("total_token_usage")
                if isinstance(total, dict):
                    last = total
                continue
            item = payload.get("item")
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            if kind in ("UserMessage", "AgentMessage"):
                visible += len(codex_item_text(item))
            elif kind == "CommandExecution":
                body = item.get("stdout") or item.get("aggregated_output") or ""
                if not isinstance(body, str):
                    body = ""
                visible += len(body)
                shell_stdout += len(body)
                parsed = item.get("parsed_cmd")
                if not isinstance(parsed, list) or not parsed or not all(isinstance(c, dict) for c in parsed):
                    continue
                types = [c.get("type") for c in parsed]
                if any(t == "read" for t in types) and any(t != "read" for t in types):
                    reads["mixed_shell"] += 1
                    continue
                if not types or any(t != "read" for t in types):
                    continue
                reads["pure_read"] += 1
                read_stdout += len(body)
                ext = suffix(parsed[0].get("path") or parsed[0].get("name"))
                status, raw, outlined, symbol = classify(body, ext, False)
                if status != "code":
                    reads[status] += 1
                    continue
                reads["code_outlined"] += 1
                chars["read_raw"] += len(raw)
                chars["outline"] += len(outlined)
                chars["symbol"] += len(symbol)
        if last is None:
            continue
        checked += 1
        inp = last.get("input_tokens") or 0
        cached = last.get("cached_input_tokens") or 0
        write = last.get("cache_write_input_tokens") or 0
        if abs(inp - cached - write) / max(inp, 1) >= 0.02:
            failing += 1
        for k in usage:
            usage[k] += last.get(k) or 0
    dollar_ok = checked > 0 and failing / checked <= 0.05
    return dict(sessions=sessions, usage=usage, visible_chars=visible, shell_stdout_chars=shell_stdout,
                read_stdout_chars=read_stdout, sessions_failing_identity=failing, sessions_with_usage=checked,
                dollar_ok=dollar_ok, reads=reads, chars=chars)


def scan_cursor():
    visible = 0
    stores = 0
    reads = dict(read=0, read_file=0, code_outlined=0, non_code=0, short=0, unparsed=0, odd_result=0, partial=0, whole=0)
    chars = dict(read_raw=0, outline=0, symbol=0)
    dbs = list((Path.home() / ".cursor" / "chats").rglob("store.db"))
    for i, db in enumerate(dbs, 1):
        stores += 1
        if i % 20 == 0:
            print(f"cursor {i}/{len(dbs)}", file=sys.stderr)
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            blobs = [row[0] for row in con.execute("SELECT data FROM blobs")]
        except Exception:
            continue
        calls = {}
        messages = []
        for blob in blobs:
            if not isinstance(blob, (bytes, str)):
                continue
            raw = blob.decode("utf-8", "ignore") if isinstance(blob, bytes) else blob
            if not raw.startswith("{"):
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if not isinstance(obj, dict) or not isinstance(obj.get("content"), (str, list)):
                continue
            messages.append(obj)
            content = obj.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool-call" and block.get("toolName") in ("Read", "ReadFile"):
                    calls[block.get("toolCallId")] = block.get("args") if isinstance(block.get("args"), dict) else {}
        for obj in messages:
            role = obj.get("role")
            content = obj.get("content")
            if role in ("user", "assistant"):
                visible += len(text_of(content))
                continue
            if role != "tool" or not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool-result":
                    continue
                result = block.get("result")
                if not isinstance(result, str):
                    if block.get("toolName") in ("Read", "ReadFile"):
                        reads["odd_result"] += 1
                    continue
                visible += len(result)
                name = block.get("toolName")
                if name not in ("Read", "ReadFile"):
                    continue
                reads["read" if name == "Read" else "read_file"] += 1
                args = calls.get(block.get("toolCallId")) or {}
                partial = bool(args.get("offset") or args.get("limit"))
                reads["partial" if partial else "whole"] += 1
                ext = suffix(args.get("path") or args.get("file_path"))
                status, raw, outlined, symbol = classify(result, ext, False)
                if status != "code":
                    reads[status] += 1
                    continue
                reads["code_outlined"] += 1
                chars["read_raw"] += len(raw)
                chars["outline"] += len(outlined)
                chars["symbol"] += len(symbol)
        con.close()
    return dict(stores=stores, visible_chars=visible, reads=reads, chars=chars)


def main():
    self_check()
    claude = scan_claude()
    if not anchor(claude):
        print("e2 anchor: fail", file=sys.stderr)
        sys.exit(1)
    codex = scan_codex()
    cursor = scan_cursor()

    c_cost = (claude["usage"]["input_tokens"] * 1
              + claude["usage"]["cache_read_input_tokens"] * 0.1
              + claude["usage"]["cache_creation_input_tokens"] * 1.25)
    c_vis = claude["visible_chars"]
    c_out = pct(claude["chars"]["read_raw"] - claude["chars"]["outline"], c_vis)
    c_sym = pct(claude["chars"]["read_raw"] - claude["chars"]["symbol"], c_vis)
    c_whole = pct(claude["split"]["whole_raw"] - claude["split"]["whole_outline"], c_vis)
    c_part = pct(claude["split"]["partial_raw"] - claude["split"]["partial_outline"], c_vis)

    uncached = (codex["usage"]["input_tokens"] - codex["usage"]["cached_input_tokens"]
                - codex["usage"]["cache_write_input_tokens"])
    x_cost = uncached * 1 + codex["usage"]["cached_input_tokens"] * 0.1 + codex["usage"]["cache_write_input_tokens"] * 1
    x_cost_alt = uncached * 1 + codex["usage"]["cached_input_tokens"] * 0.5 + codex["usage"]["cache_write_input_tokens"] * 1
    x_vis = codex["visible_chars"]
    x_out = pct(codex["chars"]["read_raw"] - codex["chars"]["outline"], x_vis)
    x_sym = pct(codex["chars"]["read_raw"] - codex["chars"]["symbol"], x_vis)

    u_vis = cursor["visible_chars"]
    u_out = pct(cursor["chars"]["read_raw"] - cursor["chars"]["outline"], u_vis)
    u_sym = pct(cursor["chars"]["read_raw"] - cursor["chars"]["symbol"], u_vis)

    kill = c_out < 10
    out = {
        "method": METHOD,
        "kill_threshold_pct": 10,
        "claude": {
            "sessions": claude["sessions"],
            "usage": claude["usage"],
            "e2_anchor_ok": True,
            "input_side_cost_units": round(c_cost, 1),
            "visible_chars": c_vis,
            "image_chars": claude["image_chars"],
            "reads": claude["reads"],
            "chars": claude["chars"],
            "savings_pct_of_input_side": {
                "outline": round(c_out, 2), "symbol": round(c_sym, 2),
                "outline_whole_only": round(c_whole, 2), "outline_partial_only": round(c_part, 2),
            },
            "dollars_saved_units": {"outline": round(c_cost * c_out / 100, 1), "symbol": round(c_cost * c_sym / 100, 1)},
        },
        "codex": {
            "sessions": codex["sessions"],
            "dollar_ok": codex["dollar_ok"],
            "sessions_failing_identity": codex["sessions_failing_identity"],
            "sessions_with_usage": codex["sessions_with_usage"],
            "usage_sum_of_last_totals": codex["usage"],
            "input_side_cost_units": None if not codex["dollar_ok"] else {"cached_0.1": round(x_cost, 1), "cached_0.5": round(x_cost_alt, 1)},
            "visible_chars": x_vis,
            "shell_stdout_chars": codex["shell_stdout_chars"],
            "read_stdout_chars": codex["read_stdout_chars"],
            "reads": codex["reads"],
            "chars": codex["chars"],
            "savings_pct_of_input_side": None if not codex["dollar_ok"] else {"outline_at_0.1": round(x_out, 2), "symbol_at_0.1": round(x_sym, 2)},
        },
        "cursor": {
            "stores": cursor["stores"],
            "dollar": None,
            "visible_chars": u_vis,
            "reads": cursor["reads"],
            "chars": cursor["chars"],
            "savings_pct_of_visible_chars": {"outline": round(u_out, 2), "symbol": round(u_sym, 2)},
        },
        "kill": kill,
    }
    Path("results").mkdir(exist_ok=True)
    Path("results/e15.json").write_text(json.dumps(out, indent=1) + "\n")
    cr = claude["reads"]
    xr = codex["reads"]
    ur = cursor["reads"]
    codex_line = (f"codex outline: {x_out:.1f}% of input-side at cached 0.1 (dollar_ok=true)  symbol: {x_sym:.1f}%"
                  if codex["dollar_ok"] else "codex outline: no dollar line (dollar_ok=false)")
    print(f"e2 anchor: ok")
    print(f"claude outline: {c_out:.1f}% of input-side bill (whole {c_whole:.1f}%, partial {c_part:.1f}%)  symbol: {c_sym:.1f}%")
    print(f"claude reads: text={cr['text']} image={cr['image']} code={cr['code_outlined']} partial={cr['partial']}")
    print(codex_line)
    print(f"codex reads: pure={xr['pure_read']} mixed_skipped={xr['mixed_shell']} code={xr['code_outlined']}")
    print(f"cursor outline: {u_out:.1f}% of visible chars, no bill in the log  symbol: {u_sym:.1f}%")
    print(f"cursor reads: read={ur['read']} code={ur['code_outlined']} partial={ur['partial']}")
    print(f"KILL: {'yes' if kill else 'no'}")


if __name__ == "__main__":
    main()
