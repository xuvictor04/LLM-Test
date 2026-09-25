"""Paired per-seed differences between arms (same seed = same stream, same text LM, same codec-phase checkpoint).
Usage: python paired.py"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "aggregate.json")))
pairs = [("live25", "frozen25"), ("live25free", "frozen25"), ("live25free", "live25"), ("live50bpe", "live50def"), ("live50bpe", "frozen25"), ("live50def", "frozen25")]
keys = ["text_afterA", "text_final", "A_bps@A", "A_bps@end", "B_bps@end", "A_capb@A", "B_capb@end", "A_mel@A", "A_mel@end", "B_mel@end",
        "A_recx@end", "B_recx@end", "B_und@end", "B_gen.7@end", "wA@end", "wB@end", "windows"]
for a, b in pairs:
    if a not in d or b not in d:
        continue
    sa, sb = d[a]["seeds"], d[b]["seeds"]
    common = [s for s in sa if s in sb]
    print(f"== {a} - {b}  seeds {common}")
    for k in keys:
        diffs = []
        for s in common:
            va, vb = d[a][k][sa.index(s)], d[b][k][sb.index(s)]
            diffs.append(None if va is None or vb is None else round(va - vb, 4))
        print(f"  {k:12s} {diffs}")
