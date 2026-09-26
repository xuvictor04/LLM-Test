"""Exposure audit: in the tags arm's stream (tag_drop 0.25), how many fact records for Qc/Wc entities state the
TRUE vs the LIE value, overall and in UNTAGGED segments only (the MLE target of the null condition).
Usage: python exposure.py SEED"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "testbed"))
import testbed as tb
seed = int(sys.argv[1]); w = tb.World(seed)
st = tb.Stream(seed, 4_000_000, tb.PlannedPolicy(), w, 0.25, "area"); st.fill(4_000_000)
buf, tag = bytes(st.buf), st.tag
cnt = {}
for m in re.finditer(rb"@([a-p]{3})=([0-7]);", buf):
    e, v = m.group(1), m.group(2)[0] - 48
    if e not in w.flipped: continue
    c = w.cls(e); un = tag[m.start()] == 0
    for key in (("all", c), ("untagged", c)) if un else (("all", c),):
        d = cnt.setdefault(key, [0, 0]); d[0] += v == w.true[e]; d[1] += v == w.lie[e]
for k, (t, f) in sorted(cnt.items()):
    print(seed, k, "true", t, "lie", f, "true share %.3f" % (t / (t + f)))
un = sum(1 for t in tag if t == 0) / len(tag)
print(seed, "untagged byte fraction %.3f" % un)
