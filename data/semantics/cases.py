import math
def safe(f):
    try: return f()
    except Exception as e: return "ERR:" + type(e).__name__
cases = [
 ("int_overflow 2**31*2", lambda: 2**31 * 2),
 ("big_int 2**64+1", lambda: 2**64 + 1),
 ("div 7/2", lambda: 7 / 2),
 ("int_div -7//2", lambda: -7 // 2),
 ("mod -7%3", lambda: -7 % 3),
 ("round 2.5", lambda: round(2.5)),
 ("round 0.5", lambda: round(0.5)),
 ("len emoji 'a👍'", lambda: len("a👍")),
 ("upper 'ß'", lambda: "ß".upper()),
 ("sort [10,9,1]", lambda: sorted([10, 9, 1])),
 ("index out of range", lambda: [1, 2][5]),
 ("0.1+0.2", lambda: 0.1 + 0.2),
 ("float fmt 1.0", lambda: str(1.0)),
 ("1/0", lambda: 1 / 0),
 ("max empty", lambda: max([])),
 ("str*3", lambda: "ab" * 3),
 ("'10' < '9'", lambda: "10" < "9"),
 ("int('08')", lambda: int("08")),
]
for n, f in cases: print(f"{n}\t{safe(f)}")
