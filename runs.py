#!/usr/bin/env python3
"""runs.py -- the record of what has actually been measured, in a CSV instead of in comments.

Results used to be written into source comments next to the code they were about. That put them in
the right PLACE and the wrong FORM: a comment cannot be sorted, cannot be diffed against a new run,
cannot say which knobs produced it, and above all cannot be checked when a DEFAULT MOVES. Several
recorded numbers in this repo were measured under a learning-rate schedule that no longer exists,
and nothing said so -- they read as current.

    python3 runs.py add <log> [--tag NAME]   parse a finished run log and append a row
    python3 runs.py list [--arm X]           the table, newest last
    python3 runs.py stale                    rows whose config no longer matches today's defaults

Every column is read out of the log, never supplied by hand, so a row cannot claim a configuration
the run did not have. `stale` compares each row's knobs against the CURRENT registry defaults and
reports what would have to be overridden to reproduce it -- which is the question that matters when
a baseline is years of runs old.
"""
import argparse
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(ROOT, "runs.csv")

# The knobs that have been shown to change a result. Kept short on purpose: a row that records every
# knob is unreadable, and the ones omitted here have never moved a number in this project.
KNOBS = ["EPOCHS", "LR_EPOCHS", "LR_RESTARTS", "VMAX", "SEED_VOCAB", "TOK_MINT_UNTIL",
         "TOK_MINT_PMIN", "TOK_COMPOSE", "DROPOUT", "WEIGHT_DECAY", "FAB_NMAX"]
COLS = (["tag", "commit", "date"] + [k.lower() for k in KNOBS]
        + ["steps", "vocab", "minted", "never_minted", "held_out", "train", "gap",
           "uniform", "order1", "words_pct", "past_min", "notes"])


def _grab(pat, text, cast=str, default=""):
    m = re.search(pat, text, re.M)
    if not m:
        return default
    try:
        return cast(m.group(1))
    except (ValueError, TypeError):
        return default


def parse(path):
    t = open(path, errors="replace").read()
    row = {c: "" for c in COLS}
    row["commit"] = _grab(r"^\[build\] branch \S+ \| commit (\w+)", t)
    row["date"] = _grab(r"^\[build\].*\| (\d{4}-\d{2}-\d{2})", t)

    eff = _grab(r"^\[config\] EFFECTIVE  (.*)$", t)
    for k in KNOBS:                                   # from the EFFECTIVE line = what RAN, not what was asked
        m = re.search(rf"\b{k}=(\S+)", eff)
        row[k.lower()] = m.group(1) if m else ""
    # VMAX and SEED_VOCAB are not on the EFFECTIVE line; they show up in the tokenizer banner instead.
    if not row["vmax"]:
        row["vmax"] = _grab(r"model sized to vocab (\d+)", t)
    if not row["seed_vocab"]:
        row["seed_vocab"] = _grab(r"SEEDED \(will keep minting live\) 256 -> (\d+)", t)

    row["steps"] = _grab(r"SAMPLED FROM: the FINAL model, step (\d+)", t)
    row["vocab"] = _grab(r"^\[vocab\] softmax width (\d+)", t)
    row["minted"] = _grab(r"^\[vocab\] softmax width \d+ \| minted (\d+)", t)
    row["never_minted"] = _grab(r"never minted\s+(\d+)", t)
    row["train"] = _grab(r"train ([\d.]+) \| held-out", t)
    row["held_out"] = _grab(r"train [\d.]+ \| held-out ([\d.]+)", t)
    row["gap"] = _grab(r"gap ([+-][\d.]+) bits/byte", t)
    row["uniform"] = _grab(r"uniform ([\d.]+) \|", t)
    row["order1"] = _grab(r"order-1 ([\d.]+) \|", t)
    row["words_pct"] = _grab(r"(\d+)% of generated words appear", t)
    row["past_min"] = _grab(r"([+-][\d.]+) since its own minimum", t)
    return row


def load():
    if not os.path.exists(CSV):
        return []
    with open(CSV, newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})


def spec_defaults():
    """Today's declared defaults, read from _SPEC so this cannot drift from the code."""
    src = open(os.path.join(ROOT, "self_organize.py")).read()
    out = {}
    for k in KNOBS:
        m = re.search(rf'^\s*"{k}": \("[ifenv]+", ([^)]+)\),', src, re.M)
        if m:
            v = m.group(1).strip()
            out[k] = None if v == "None" else v.strip('"')
    return out


def cmd_add(a):
    if not os.path.exists(a.log):
        raise SystemExit(f"!! {a.log} not found")
    row = parse(a.log)
    if not row["held_out"]:
        raise SystemExit(f"!! {a.log} has no 'train ... | held-out ...' line -- did the run reach its report?")
    row["tag"] = a.tag or os.path.splitext(os.path.basename(a.log))[0]
    row["notes"] = a.notes or ""
    rows = load()
    rows = [r for r in rows if r.get("tag") != row["tag"]]      # re-adding a tag replaces it
    rows.append(row)
    save(rows)
    print(f"added {row['tag']}: held-out {row['held_out']} | {row['words_pct']}% words | "
          f"EPOCHS={row['epochs']} LR_EPOCHS={row['lr_epochs']} vocab {row['minted']}/{row['vocab']}")
    return 0


def cmd_list(a):
    rows = load()
    if a.arm:
        rows = [r for r in rows if a.arm in r.get("tag", "")]
    if not rows:
        print("(no rows)")
        return 0
    hdr = ["tag", "held_out", "words_pct", "past_min", "epochs", "lr_epochs", "lr_restarts",
           "vmax", "minted", "tok_mint_pmin", "commit"]
    w = {h: max(len(h), *(len(str(r.get(h, ""))) for r in rows)) for h in hdr}
    print("  " + "  ".join(h.ljust(w[h]) for h in hdr))
    for r in rows:
        print("  " + "  ".join(str(r.get(h, "")).ljust(w[h]) for h in hdr))
    return 0


def cmd_stale(a):
    """Which recorded results would NOT reproduce under today's defaults, and what to override."""
    dflt = spec_defaults()
    rows = load()
    if not rows:
        print("(no rows)")
        return 0
    any_stale = False
    for r in rows:
        diffs = []
        manual = r.get("commit") == "(no log)"
        # THE SCHEDULE IS BIT-IDENTICAL WHEN THE RUN IS NO LONGER THAN ONE WAVELENGTH. LR_EPOCHS is clamped
        # to min(default, EPOCHS) and LR_RESTARTS fits a whole number of cycles, so at EPOCHS <= the default
        # wavelength there is exactly one cycle and no wrapping: measured max |restarts - hold| = 0.000e+00
        # over a whole 8-epoch run. Flagging those rows as stale would be false, and the false positive is
        # expensive -- it is precisely the 8-epoch baselines that are worth reproducing.
        try:
            _sched_same = float(r.get("epochs") or 0) <= float(dflt.get("LR_EPOCHS") or 0)
        except ValueError:
            _sched_same = False
        for k in KNOBS:
            if _sched_same and k in ("LR_EPOCHS", "LR_RESTARTS"):
                continue
            d, got = dflt.get(k), r.get(k.lower(), "")
            if d is None:
                continue
            if got == "":
                # ABSENT IS NOT "MATCHES" -- for a PARSED row. A blank column there means the run predates
                # the knob, so it ran with whatever the code did before the knob existed, which is exactly
                # the case that reads as current and is not. A MANUAL row is blank because nobody typed the
                # value, which says nothing about the run; flagging those would bury the real differences.
                if not manual and str(d) not in ("0", "0.0"):
                    diffs.append(f"{k}=<predates this knob>")
                continue
            try:
                same = abs(float(d) - float(got)) < 1e-9
            except ValueError:
                same = str(d) == str(got)
            if not same:
                diffs.append(f"{k}={got}")
        if diffs:
            any_stale = True
            print(f"  {r['tag']:<22} held-out {r['held_out']:<7} needs: {'  '.join(diffs)}")
    if not any_stale:
        print("  every recorded run matches today's defaults.")
    else:
        print("\n  These rows were measured under knobs that are no longer the default. Pass the listed")
        print("  overrides to reproduce them; without those, a new run is NOT comparable to the number here.")
    return 0


def cmd_manual(a):
    row = {c: "" for c in COLS}
    row["tag"] = a.tag; row["held_out"] = a.held_out
    row["commit"] = "(no log)"; row["notes"] = f"SOURCE: {a.source}"
    for kv in a.set:
        k, _, v = kv.partition("=")
        if k not in COLS:
            raise SystemExit(f"!! {k} is not a column. Columns: {', '.join(COLS)}")
        row[k] = v
    rows = [r for r in load() if r.get("tag") != row["tag"]]
    rows.append(row); save(rows)
    print(f"added {row['tag']} (manual): held-out {row['held_out']} -- {row['notes']}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add"); p.add_argument("log"); p.add_argument("--tag"); p.add_argument("--notes")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("list"); p.add_argument("--arm"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("stale"); p.set_defaults(fn=cmd_stale)
    # A ROW WHOSE LOG IS GONE. Some baselines survive only as a number written into a source comment; that
    # is the whole reason this file exists. They belong in the record, but NOT indistinguishable from a row
    # parsed out of a real log, so `manual` demands a --source and stamps it into the commit column.
    p = sub.add_parser("manual")
    p.add_argument("--tag", required=True); p.add_argument("--held-out", required=True)
    p.add_argument("--source", required=True, help="where the number comes from, since there is no log")
    p.add_argument("--set", action="append", default=[], metavar="COL=VAL")
    p.set_defaults(fn=cmd_manual)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
