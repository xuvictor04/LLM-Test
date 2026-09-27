import json, re
fields = ["title","kind","ruling","basis","deciding_test","owner_ruling_touched","escalate_if","register_places","changes_from_draft"]
out = []
for oid, fn in [("O16","o16.txt"),("O17","o17.txt"),("O18","o18.txt"),("O19","o19.txt"),("O20","o20.txt"),("D-CONFIRM","dconfirm.txt")]:
    parts = re.split(r"^@@(\w+)\n", open(fn).read(), flags=re.M)
    d = {"id": oid}
    for i in range(1, len(parts), 2):
        d[parts[i]] = parts[i+1].strip()
    assert set(fields) <= set(d), (oid, set(fields) - set(d))
    assert d["kind"] in ("resolved_now","decided_by_test","escalate_to_owner")
    out.append({k: d[k] for k in ["id"] + fields})
json.dump({"rulings": out}, open("revised_O16_DC.json", "w"), ensure_ascii=False, indent=1)
for r in out:
    print(r["id"], r["kind"], sum(len(v) for v in r.values()), {k: len(v) for k, v in r.items() if k not in ("id","kind")})
