import tiktoken
_e = tiktoken.get_encoding("o200k_base")
def ntok(s): return len(_e.encode(s, disallowed_special=()))
