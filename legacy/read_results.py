"""read_results.py -- turn the run's JSONL logs into the decision, robust to partial/failed runs.

  python3 read_results.py                  # auto-discovers cont_*/ and v1_*/ dirs here
  python3 read_results.py cont_off cont_mir cont_rep v1_dyn v1_frz

Reports two things the experiment is FOR:
  1) CONTINUAL: backward transfer per arm (does memory reduce forgetting without replay?)
  2) STATIONARY: final bits/byte per arm (does the tokenizer lower the floor?)
Missing or empty logs are reported as such -- no silent gaps.
"""
import os, sys, json, glob


def _read_jsonl(path):
    if not os.path.exists(path): return None
    out = []
    for line in open(path):
        line = line.strip()
        if not line: continue
        try: out.append(json.loads(line))
        except Exception: pass
    return out


def continual_summary(run_dir):
    recs = _read_jsonl(os.path.join(run_dir, "continual_log.jsonl"))
    if recs is None: return f"{run_dir:16s} : no continual_log.jsonl (run didn't start / crashed before logging)"
    if not recs:     return f"{run_dir:16s} : empty log"
    done = next((r for r in reversed(recs) if r.get("phase") == "done"), None)
    shifts = [r for r in recs if r.get("phase") == "shift"]
    if done is not None:
        bwt = done.get("mean_backward_transfer_old_domains")
        verdict = "old domains IMPROVED" if (bwt is not None and bwt < 0) else "old domains FORGOT"
        return (f"{run_dir:16s} : mean backward transfer = {bwt:+.3f}  ({verdict})  "
                f"| phases completed {len(shifts)}")
    # partial: no final rollup, but per-phase drift may exist
    if shifts:
        last = shifts[-1]
        drift = last.get("drift_vs_first_seen", {})
        old = {k: v for k, v in drift.items() if k != last.get("domain")}
        mean_old = round(sum(old.values()) / max(1, len(old)), 3) if old else None
        return (f"{run_dir:16s} : PARTIAL ({len(shifts)} phases, no final) "
                f"| last-phase mean drift on earlier domains = {mean_old}")
    return f"{run_dir:16s} : started, no phase results yet"


def stationary_summary(run_dir):
    recs = _read_jsonl(os.path.join(run_dir, "train_log.jsonl"))
    if recs is None: return f"{run_dir:16s} : no train_log.jsonl (crashed before first eval)"
    if not recs:     return f"{run_dir:16s} : empty log"
    last = recs[-1]
    ih, od, st = last.get("in_held"), last.get("ood"), last.get("step")
    nodes = last.get("nodes")
    return f"{run_dir:16s} : in_held {ih} | OOD {od} bits/byte  (step {st}, {nodes} nodes, {len(recs)} evals)"


def main():
    args = sys.argv[1:]
    if args:
        cont = [d for d in args if d.startswith("cont")]
        stat = [d for d in args if not d.startswith("cont")]
    else:
        cont = sorted(d for d in glob.glob("cont_*") if os.path.isdir(d))
        stat = sorted(d for d in (glob.glob("big_full") + glob.glob("greg") + glob.glob("barry") + glob.glob("barry_scale") + glob.glob("eco_*") + glob.glob("ts_*") + glob.glob("v1_*") + glob.glob("abl_*") + glob.glob("reenc_*") + glob.glob("lean_*") + glob.glob("runs*")) if os.path.isdir(d))

    print("=" * 64)
    print("CONTINUAL  -- backward transfer (negative = old knowledge improved = good)")
    print("=" * 64)
    if not cont: print("  (no cont_* dirs found)")
    for d in cont: print("  " + continual_summary(d))
    if len(cont) >= 2:
        print("\n  read: if cont_mir* beats cont_off* (more negative / less positive), memory")
        print("        reduced forgetting WITHOUT replay -- the project's headline.")

    print("\n" + "=" * 64)
    print("STATIONARY -- final bits/byte (lower = better; compare dynamic vs frozen vs byte)")
    print("=" * 64)
    if not stat: print("  (no stationary dirs found)")
    for d in stat: print("  " + stationary_summary(d))
    print()


if __name__ == "__main__":
    main()
