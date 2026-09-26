"""d2: conditioning + model-side selective learning on the shared mm3 testbed.

Arms (all use the testbed's BASELINE draw -- this design never changes the data draw):
  base        no tags, uniform token weights (the tree today)
  tags        source-id channel (true area id per segment, dropped to 0 w.p. --tag_drop), uniform weights
  sel         token weights from |L_cur - L_ref| (lagged-self excess loss; ref = EMA of weights)
  tags_sel    both (the full d2 design)
  loss        control: weights ~ L_cur (surprise-seeking, the noisy-TV-prone rule)
  sel_pos     ablation: weights ~ relu(L_cur - L_ref) (Rho-1 sign: only where current is WORSE than lagged self)
  tags_nodrop tags with tag_drop 0 (never untagged)
Usage: python run.py --arm tags_sel --seed 0 [--bytes 2000000]
"""
import sys, os, json, copy, argparse, math, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "testbed"))
import torch, torch.nn.functional as F
import testbed as tb

torch.set_num_threads(1)
ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--bytes", type=int, default=4_000_000)
ap.add_argument("--tag_drop", type=float, default=0.25)
ap.add_argument("--ema", type=float, default=0.99)      # ref EMA decay per optimizer step
ap.add_argument("--floor", type=float, default=0.25)    # minimum token weight share (anti-starvation)
ap.add_argument("--cap", type=float, default=4.0)       # max token weight
ap.add_argument("--tag", default="")
args = ap.parse_args()
arm = args.arm
tags = arm.startswith("tags")
tag_drop = 0.0 if arm == "tags_nodrop" else args.tag_drop
sel_mode = {"sel": "abs", "tags_sel": "abs", "loss": "loss", "sel_pos": "pos"}.get(arm)

counters = {"sel.batches": 0, "sel.floor_bound_frac": 0.0, "sel.cap_bound_frac": 0.0, "sel.ref_updates": 0}
state = {"ref": None}


def weight_fn(model, x, s, nats, step):
    if sel_mode is None:
        return None
    if sel_mode == "loss":
        r = nats
    else:
        if state["ref"] is None:
            state["ref"] = copy.deepcopy(model).requires_grad_(False)
        with torch.no_grad():
            lr_ = F.cross_entropy(state["ref"](x[:, :-1], s).reshape(-1, 256), x[:, 1:].reshape(-1),
                                  reduction="none").view_as(nats)
        d = nats - lr_
        r = d.abs() if sel_mode == "abs" else d.clamp(min=0)
    r = r / (r.mean() + 1e-8)
    w = args.floor + (1 - args.floor) * r
    counters["sel.cap_bound_frac"] += float((w > args.cap).float().mean())
    counters["sel.floor_bound_frac"] += float((r < 1e-3).float().mean())
    w = w.clamp(max=args.cap)
    w = w / w.mean()
    counters["sel.batches"] += 1
    return w


def after_step(model, step):
    if state["ref"] is not None:
        with torch.no_grad():
            for pr, pm in zip(state["ref"].parameters(), model.parameters()):
                pr.mul_(args.ema).add_(pm, alpha=1 - args.ema)
        counters["sel.ref_updates"] += 1


def truth_discovery(probs, world, keys):
    """Model-internal truth discovery: each prompt condition in `keys` is a 'source'; its claim on entity e
    is the model's value distribution p_s(.|e). Iterate truth = argmax_v sum_s rel_s p_s(v|e);
    rel_s = mean_e p_s(truth_e|e). Returns rel per source and accuracy of the weighted answer per class."""
    P = torch.stack([probs[k] for k in keys])  # S,E,8
    rel = torch.ones(len(keys))
    for _ in range(10):
        agg = (rel[:, None, None] * P).sum(0)
        truth = agg.argmax(-1)
        rel = P.gather(2, truth[None, :, None].expand(len(keys), -1, 1)).squeeze(-1).mean(1)
    acc = {}
    for i, e in enumerate(world.names):
        c = world.cls(e)
        a = acc.setdefault(c, [0, 0]); a[0] += int(truth[i]) == world.true[e]; a[1] += 1
    best = keys[int(rel.argmax())]
    return {"rel": {k: float(r) for k, r in zip(keys, rel)}, "acc_weighted": {c: a[0] / a[1] for c, a in acc.items()},
            "trusted_source": best}


def loss_rank(summ, keys):
    return min(keys, key=lambda k: summ["bpb_end_tag" if "bpb_end_tag" in summ else "bpb_end_null"][k])


t0 = time.time()
logf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", f"{arm}{args.tag}_s{args.seed}.log"), "w")
res = tb.train(args.seed, args.bytes, tag_mode="area" if tags else "off", tag_drop=tag_drop,
               weight_fn=weight_fn, extra={"after_step": after_step}, log=logf)
summ = tb.summarize(res)
world = res["world"]
summ["td_style"] = truth_discovery(res["probs"], world, ["null_c", "null_f", "null_r"])
if tags:
    summ["td_tag"] = truth_discovery(res["probs"], world, ["tag_c", "tag_f", "tag_r"])
summ["loss_ranked_most_credible"] = loss_rank(summ, ["cred", "false", "corrob"])
if tags:
    # steering gap: held-out bits/byte under a WRONG tag (the next area's id) minus under the true tag
    ho = tb.Heldout(args.seed, world)
    m = res["model"].eval()
    steer = {}
    with torch.no_grad():
        for i, n in enumerate(tb.AREAS):
            x = ho.win[n]
            wrong = torch.full_like(x[:, :-1], (i + 1) % len(tb.AREAS) + 1)
            lo = m(x[:, :-1], wrong)
            steer[n] = F.cross_entropy(lo.reshape(-1, 256), x[:, 1:].reshape(-1)).item() / math.log(2) - summ["bpb_end_tag"][n]
    summ["steer_gap_wrong_minus_true"] = steer
    # trusted-tag prompting: answer every entity under the tag the model-internal TD ranks most reliable
    best = summ["td_tag"]["trusted_source"]
    summ["trusted_tag_acc"] = {k: summ["facts_end"][best][k]["acc_true"] for k in ("Qc", "Wc", "Qa", "Wa")}
# per-phase mean token weight by area (emergent focus gauge)
summ["phase_mean_w"] = [{n: (pb[n]["w"] / pb[n]["tok"] if pb[n]["tok"] else None) for n in tb.AREAS}
                        for pb in res["phase_books"]]
summ["counters"] = dict(counters)
if counters["sel.batches"]:
    summ["counters"]["sel.cap_bound_frac"] /= counters["sel.batches"]
    summ["counters"]["sel.floor_bound_frac"] /= counters["sel.batches"]
summ["curve"] = [{"frac": r["frac"], "null": {n: r["heldout"][n]["null"] for n in tb.AREAS},
                  "tag": ({n: r["heldout"][n]["tag"] for n in tb.AREAS} if tags else None),
                  "facts_Qc": {c: r["facts"][c]["Qc"] for c in r["facts"]},
                  "facts_Wc": {c: r["facts"][c]["Wc"] for c in r["facts"]}} for r in res["evals"]]
summ.update(arm=arm, seed=args.seed, bytes=args.bytes, tag_drop=tag_drop, ema=args.ema, floor=args.floor,
            cap=args.cap, n_steps=res["n_steps"], wall=time.time() - t0, segments=res["segments"])
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"), exist_ok=True)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", f"{arm}{args.tag}_s{args.seed}.json"), "w") as f:
    json.dump(summ, f, indent=1)
print(json.dumps({k: summ[k] for k in ("arm", "seed", "wall", "gap_end", "forget_hard")}), flush=True)
