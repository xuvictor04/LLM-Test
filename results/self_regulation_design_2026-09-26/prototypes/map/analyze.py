import json, sys, collections, math
d = json.load(open(sys.argv[1]))
L, A, D = d["loss"], d["area"], d["did"]
n = min(len(L), len(A), len(D))
print("windows", d["windows"], "loss rows", len(L), "loop_s", round(d["loop_s"],1), "protocol", d["protocol"], "schedule", d["schedule"], "areas", d["area_names"])
print("per_area_drawn", d["per_area_drawn"])
ln2 = math.log(2)
# per-area mean loss (bits/token) by quarter of the run
q = max(1, n // 4)
for a in d["area_names"]:
    row = []
    for k in range(4):
        vals = [L[i]/ln2 for i in range(k*q, min(n, (k+1)*q)) if A[i] == a]
        row.append(f"{(sum(vals)/len(vals)):.3f}(n={len(vals)})" if vals else "  --  ")
    print(f"  area {a:<5} bits/token by quarter:", "  ".join(row))
# area x domain contingency
ct = collections.Counter(zip(A[:n], D[:n]))
dids = sorted(set(D[:n]))
print("distinct dids", len(dids))
for a in d["area_names"]:
    tot = sum(v for (aa, _), v in ct.items() if aa == a)
    top = sorted(((v, dd) for (aa, dd), v in ct.items() if aa == a), reverse=True)[:4]
    print(f"  area {a:<5} windows {tot:4d}  top dids {[(dd, v) for v, dd in top]}  n_dids {len([1 for (aa,_) in ct if aa==a])}")
pur = 0
for dd in dids:
    tot = sum(v for (_, x), v in ct.items() if x == dd)
    pur += max(v for (_, x), v in ct.items() if x == dd)
print("did->area purity (window-weighted)", round(pur / n, 3))
rep = d["report"]
keys = ["fab.", "part.", "store.", "tok.", "sig.", "cap.", "opt."]
want = ["fab.halt_mass_train","fab.hops_taken","fab.grown","fab.grow_asks","fab.spawned","fab.culled","fab.merged","fab.depth","part.n_created","part.n_boundaries","part.n_merged","part.n_culled","part.n_folded","part.n_competence_updates","store.n_written","store.n_promoted","store.n_evict_main","tok.mint","tok.due_dropped","sig.floor_skips","sig.train_steps","sig.cadence_idle","sig.cadence_dense","cap.lifts","opt.shift.notifications"]
flat = {}
for row, body in rep.items():
    if isinstance(body, dict):
        for k, v in body.items(): flat[k] = v
for k in sorted(flat):
    if any(k.startswith(w) for w in want):
        print(f"   {k:<44} {str(flat[k])[:100]}")
print("ledger", d["ledger"])
