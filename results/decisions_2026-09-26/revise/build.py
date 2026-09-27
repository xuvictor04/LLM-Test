import json, re
fields = ["title","kind","ruling","basis","deciding_test","owner_ruling_touched","escalate_if","register_places","changes_from_draft"]
out = []
for oid in ["O6","O7","O8","O9","O10"]:
    txt = open(f"{oid.lower()}.txt").read()
    parts = re.split(r"^@@(\w+)\n", txt, flags=re.M)
    d = {"id": oid}
    for i in range(1, len(parts), 2):
        d[parts[i]] = parts[i+1].strip()
    assert set(fields) <= set(d), (oid, set(fields) - set(d))
    out.append({k: d[k] for k in ["id"] + fields})
json.dump({"rulings": out}, open("revised_O6_O10.json", "w"), ensure_ascii=False, indent=1)
for r in out:
    print(r["id"], {k: len(v) for k, v in r.items()})
