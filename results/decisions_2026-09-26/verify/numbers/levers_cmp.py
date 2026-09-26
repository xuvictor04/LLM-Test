import sys, re, json
sys.path.insert(0, "/home/user/LLM-Test/src")
from spine import assemble, registry
sets = registry.all_sets()
tree = {}
for pfx, s in sets.items():
    for f, lv in s._levers.items():
        tree["%s_%s" % (pfx, f.upper())] = lv.default
json.dump({k: repr(v) for k, v in tree.items()}, open("tree_levers.json", "w"), indent=0)
doc = open("/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/dec/DECISIONS.md").read()
names = sorted(set(re.findall(r"`([A-Z][A-Z0-9]+_[A-Z0-9_]+)`", doc)))
print("lever-like names in doc:", len(names))
intree = [n for n in names if n in tree]
notin = [n for n in names if n not in tree]
print("in tree:", len(intree)); print("NOT in tree:", notin)
# value checks: `NAME` <val> patterns
pat = re.compile(r"`([A-Z][A-Z0-9]+_[A-Z0-9_]+)`\s*(?:=\s*)?('?[A-Za-z0-9.\-]+'?)")
seen = {}
for m in pat.finditer(doc):
    n, v = m.group(1), m.group(2)
    if n in tree:
        seen.setdefault(n, set()).add(v)
for n in sorted(seen):
    print(f"{n:28s} tree={tree[n]!r:14s} doc-values={sorted(seen[n])}")
pat2 = re.compile(r"`([A-Z][A-Z0-9]+_[A-Z0-9_]+)=([A-Za-z0-9.'\-]+)`")
for m in pat2.finditer(doc):
    n, v = m.group(1), m.group(2)
    print("ASSIGN", n, v, "tree=", repr(tree.get(n, "NOT-IN-TREE")))
