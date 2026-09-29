"""BASELINE FIXTURES: thirteen recorded run.py workloads, so "bit-identical when the new mechanism is
off" is checked against recorded runs rather than asserted against nothing.

WHY THIS FILE EXISTS (Proposal 03 §0 R7, 03b S0b). tests/test_determinism.py measures the machine's noise
floor between two runs of the SAME tree; it holds no record of an earlier tree. Every stage of 03b
(S0b's mid-epoch act first) promises that a default run with the new mechanism disarmed reproduces the
tree it started from. That promise needs a stored trace from the base commit.

THE WORKLOADS (the WORKLOADS table below): since 2026-09-29, six shapes, each held twice -- at the shipped
defaults and under the pins -- and B5 a third time, unpinned against its pre-SR0 record (B5u).
  B1 ... B6r   the six shapes at the SHIPPED DEFAULTS, recorded at the commit after 444ecca -- the one
               that flipped register 04-Q5's, 04-6.2's and 04-6.3's defaults (DATA_SYNTH_HOLDOUT on,
               EVAL_RETENTION_EVERY 1000 with a read at every phase start, DATA_TRUST 'observe';
               DEFAULT BEHAVIOUR CHANGES 1-3). Every synthetic stream changed there, and every default
               run now keeps the source-reliability book; each one whose held-out halves can hold a
               window behind its routing prefix also reads them and generates after its final save.
               B6 and B6r's 20,000-byte stream pins nothing, so their records carry no eval.* key
               (eval.holdout.calls reads 3 in B1, 6 in B3 and 4 in B5, and 5 in B3r's parent and 10 in
               its child, the lineage's total).
               Those records are the flipped tree's own runs, recorded when it was committed: a change
               after it is held to them.
  B1p ... B6rp THE SAME SIX, EACH UNDER PRE_SR0_PINS, AGAINST THE RECORD MADE BEFORE THE FLIP (the files
               *_pre_sr0.json, the six fixtures as they stood, moved unchanged): "the pinned tree is
               the previous tree", 04-Q5's pin rule, made a test. See PINS below.
  B5u          B5 UNPINNED against B5's pre-SR0 record, on its losses and on every counter outside P1's
               exempt set (P1_EXEMPT, its table `exempt`): on the real source nothing a run trains on
               moved at the flip, and what the reading beside training moves is that set.
B1 was the only shape until 2026-09-27. The other five were recorded at ae70638, before any edit of the
register's §8 Stage 3 (docs/proposals/05_DECISIONS.md), because Stage 3 edits the manage pass, the draw,
the epoch roll, both resume paths and the held-out carve, and B1 reaches none of them:
  B1   `run.py --max-windows 80` at DATA_STREAM_BYTES=120000, the shipped defaults otherwise. Recorded
       at d32e2ce, pre-SR0, and unchanged until 2026-09-29's flip. WHAT B1 CANNOT SEE: in 80 windows it
       reaches no FAB manage pass (FAB_MANAGE_EVERY=500), no mid-epoch act (TOK_RETOK_EVERY=3000), no
       resume and no epoch roll; and before the flip, on the synthetic source, there was no held-out
       block to carve (data/api.py::open_areas held nothing out there at DATA_SYNTH_HOLDOUT=0, as B1p
       still does). A change to the cull, the act, the roll or either resume path passes B1 untested.
       NOR DO B3, B3r OR B5 SEE THE ROLL OR A BOUNDARY RESUME: B1, B3, B3r and B5 all run at the
       shipped RUN_EPOCHS=1, where spine/loop.py::run's stage E is unreachable (it tests `finished`
       before `rolled`, and a one-epoch run's only roll is the one that finishes it), and B3r resumes
       mid-epoch. B6 and B6r are the two that do.
  B3   one full epoch -- 312 windows at the shipped defaults, 314 under the pins (B3p) -- at
       tests/test_continuation.py's BASE plus FAB_MANAGE_EVERY=50 FAB_GRACE=2 TOK_GROW_EVERY=30
       TOK_RETOK_EVERY=150: six manage passes past a short grace, a mint burst due every 30 windows,
       mid-epoch acts at windows 151 and 301, and a store that fills, folds and rekeys (manage-, act-
       and MEM-heavy).
  B3r  B3 saved at window 170 -- after the first act, between the manage passes at 151 and 201 -- and
       continued by a second process with CKPT_RESUME: the continuing mid-epoch resume
       (spine/compose.py's seg-log replay, its loop_carried restore and its rebuilt-length check). Two
       legs, each held to its own record. AND ONE DERIVED CHECK, made on any machine: the parent's
       clock stopped mid-epoch, and the parent's losses are B3's first 170 and the child's are B3's
       from window 170 on, exactly -- against this invocation's B3 when it ran, else B3's fixture.
  B5   DATA_SOURCE=real over data/train (eng, py, num, c), a 120000-byte stream, 200 windows: the real
       sources' held-out carve (open_areas) and the step from phase 0 into phase 1 (window 148 is the
       first wholly inside it).
  B6   BASE on a 20000-byte stream for two epochs (RUN_EPOCHS=2 DATA_RESAMPLE=1), 208 windows: the
       epoch roll at window 104, loop.run's stage E -- the epoch-1 draw (rng_for('data.stream.e1')),
       the new seg_log, the re-segmentation, begin_epoch, the shift stamps and MEM's resegment.
  B6r  B6 stopped at its epoch boundary (--max-windows 104: the stop is tested before the roll, so the
       parent's final checkpoint is a boundary checkpoint) and resumed by a second process with
       CKPT_RESUME into epoch 1: the boundary resume (the `stream` row drawing Snapshot.epoch, a fresh
       segmentation and seg_log, no seg-log replay, no loop_carried restore). Two legs, each held to
       its own record, and one derived check: the parent's clock stopped at in_epoch 0 of epoch 1, and
       its losses are B6's first 104, exactly. NOT A CONTINUATION CHECK, because at ae70638 a boundary
       resume is not one (measured 2026-09-27; CPU, operation only). compose restores LOOP.carried only
       on a continuing resume, so the child starts from loop.run's initial carried values (live_domains
       1, no shift stamp), and it repeats none of the roll's deliveries: fab.shift_notifications and
       opt.shift.notifications read 1 in B6 and 0 in the child, FAB's growth blackout covers B6's 104
       windows of epoch 1 and never opens in the child, and store.n_resegment_events is 1 in B6 and
       ABSENT in the child. The child's first loss is 5.2424 where B6's at window 104 is 5.2342 (B6rp's
       record; at the flipped defaults, 6.18328 against 6.18349). Recorded, not repaired; the contract
       already calls a resume from an epoch-boundary checkpoint "not continuing" (Q-OPT-12).

WHAT IS STORED, per leg of a workload, at RUN_DEVICE=cpu and one thread:
  - the per-flush loss curve, as exact float reprs (a trace, compared exactly: same machine, same build);
  - every integer counter line the run prints (the INTEGER channel of test_determinism's vocabulary).
    Each fixture counter must be reproduced exactly; a counter added since is a new instrument and
    is listed, not compared. The count line reads "N integer counters compared, M new": until
    2026-09-27 it printed the run's parsed count as the compared one (247 for B1, of which 241 were
    compared and 6 were new);
  - the leg's environment and arguments. A fixture recorded under other ones FAILS, so a table edited
    after recording is named rather than compared against a different workload's record.
The float curve is compared exactly because the reference is this machine's own earlier run of the
same workload; test_determinism records that this machine reproduces a seeded run bit for bit, and B3,
B3r, B5, B6 and B6r each reproduced their records in fresh processes, twice, before they were committed.
The six records made at the flip were reproduced by a full invocation, and by 444ecca's tree -- the tree
before the flip -- run with the three flipped levers set explicitly, on every loss and every counter.
Each leg's final clock (RUN.RunClock.counters) is read for the resume pairs' derived checks and is
neither recorded nor compared.

PINS. A workload may declare `pins`: levers set on every leg AT RUN TIME, the way --mutants' overrides
are, and kept OUT of the environment its fixture records and its comparison checks. They exist for the
one comparison the environment rule above would otherwise fail on correct code: this tree, under the
values that restore an earlier default, against a record made before those levers existed. Stage 3's
default flips (04-Q5, 04-6.2, 04-6.3) are that case. They hold the pre-flip fixtures to this tree under
04-Q5's pins, DATA_SYNTH_HOLDOUT=0 EVAL_RETENTION_EVERY=0 DATA_TRUST=off (SR0's "DATA_SYNTH_HOLDOUT=0
with the probe off is bit-exact against HEAD"), and no such record can name a lever that did not exist
when it was made. The verdict line prints the pins. A pin may not restate a key its leg's environment
sets. And a pin, like every key a leg is given, must name a lever this tree declares: a run that prints
UNREAD for one FAILS, because the lever assembly's typo net only warns and the key would silently be
the default. A pinned workload is never recorded -- --record refuses it -- so an earlier tree's record
cannot be replaced by this tree's own run; nor is a workload the table marks `kept`, one compared
UNPINNED against such a record (under its own `exempt`, below).

--exempt PATTERNS (comma-separated fnmatch patterns, repeatable) compares every fixture counter EXCEPT
those a pattern names, and prints each exempted counter with both values (and any pattern that
exempted nothing). It is for a change that may move some counters and nothing else -- a read beside
training moves lm.encode.calls, never a loss. SR0's bit-identity (register §8 3.1) reuses it, and so
does the real-source check made when 04-Q5's, 04-6.2's and 04-6.3's defaults flip; the losses are
always compared. compare_counters is the same comparison, importable. A workload may also declare its
own `exempt` patterns in the table, added to the command line's on every invocation: that real-source
check is one, and a table entry that needed the flag would fail the default invocation on correct code,
as a pin written into the environment would.

--mutants runs planted changes that MUST FAIL, the check that the net has teeth where it was widened.
Two are levers: B3 at FAB_GRACE=3 (a cull that waits one more selection) and B5 at
DATA_HOLDOUT_FRAC=0.06 (a held-out block one percentage point of each corpus larger); each passes only
if its comparison fails naming the first differing flush. Two are PLANTED SOURCE CHANGES, for the two
paths no lever reaches: the workload runs against a copy of src/ and run.py with one statement
replaced, from the repository root, so data/ is the repository's. The roll's draw seed + 1
(spine/loop.py's stage-E draw_stream call) must fail B6 first at flush 104, the first window of epoch 1,
with the epoch before it untouched. A resumed child's draw seed + 1 (spine/compose.py's `stream` row,
moved only when a checkpoint was restored) must leave B6r's parent without a finding and fail its child
first at the child's flush 0. A plant's anchor must occur exactly once in the tree, and every
invocation checks that it still does: where the code it was aimed at has moved, re-aim the plant.

Every invocation but --record first runs the comparator's own known answers on planted data: a loss
change named at its flush; an exempt counter's bump passes, printed; a bump no pattern names fails; a
vanished counter fails; a table entry's exempt patterns join the command line's; each resume pair's
derived check passes the shape it was written for and fails a departure from it (B3r a child that
departs from B3 or a parent stopped at a boundary, B6r a parent stopped mid-epoch or departing from
B6); a pin runs but is neither recorded nor compared, and is printed, while a table environment that
departs from its record still fails; a pinned or kept workload and a resume pair whose check did not
pass are not recorded; a plant is made where its anchor occurs once and refused where it does not, and
the two --mutants plants still find theirs; a loss finding is read back with its leg.

A FIXTURE IS A PER-MACHINE RECORD. It carries the machine key (platform, torch version, cpu count,
threads). On another machine the comparison is UNVERIFIABLE and this file says so and exits 0 -- it does
not pass a comparison it could not make, and it does not fail a box it was never recorded on. Record one
there with --record. (A resume pair's derived check is not machine-keyed and still runs there against
its live reference.)

Run from the repository root:
    python3 tests/test_baseline.py                  compare every workload against its fixture
    python3 tests/test_baseline.py B6 B6r           compare the named workloads only
    python3 tests/test_baseline.py --exempt 'eval.*,lm.encode.calls'
    python3 tests/test_baseline.py --record B3      (re)write the named workloads' fixtures (every
                                                    workload's but a pinned or kept one's when none
                                                    is named); commit each with the commit it names
                                                    (HEAD, or "the commit after" HEAD when src/ or
                                                    run.py differ from it: the record's own commit)
    python3 tests/test_baseline.py --mutants        the planted failures above
Exit 0 = matched (or unverifiable on this machine, printed as such); 1 = a difference, named.
"""
import argparse
import collections
import fnmatch
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# EVERY LEG RUNS ON THE CPU AT ONE THREAD; the machine key records the thread count.
COMMON = {"RUN_DEVICE": "cpu", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
# tests/test_continuation.py::BASE, the tenth-size fabric. COPIED, NOT IMPORTED: importing that file
# runs its checks. B3's record is its own either way -- an edit to BASE there moves nothing here.
_BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}
_B3 = dict(COMMON, **_BASE, FAB_MANAGE_EVERY="50", FAB_GRACE="2", TOK_GROW_EVERY="30",
           TOK_RETOK_EVERY="150")
B3R_SAVE_AT = 170
# BASE on a third of its stream for two epochs, the second resampled: RUN.startup_refusals refuses
# RUN_EPOCHS > 1 without DATA_RESAMPLE, because the second epoch would replay the first.
_B6 = dict(COMMON, **dict(_BASE, DATA_STREAM_BYTES="20000"), RUN_EPOCHS="2", DATA_RESAMPLE="1")
# EPOCH 0's LENGTH AT _B6, IN WINDOWS: its segmentation holds 13,369 ids at the shipped defaults and
# 13,417 under the pre-SR0 pins (the synthetic held-out block, on since 2026-09-29, takes 5% of each
# generated body, so the stream's bytes and its cuts moved), and LM_CTX is 128, so (13369 - 1) // 128
# and (13417 - 1) // 128 are both 104 (compose.py::_windows_in_epoch). B6r's and B6rp's parents stop
# there, each derived check reads the parent's clock to confirm that the stop is the boundary, and
# --mutants' roll plant must first differ there. Where a later flip moves one of the two, the table
# names two boundaries, and the check says which moved.
B6_EPOCH0 = 104
# 04-Q5's PIN RULE, WRITTEN AS PINS (see PINS above): the three levers whose defaults flipped on
# 2026-09-29 (DEFAULT BEHAVIOUR CHANGES 1-3), at the values that restore the tree before them. The
# register adds DATA_DRAW='planned' to the rule "if that flips"; it has not, so it is not pinned.
PRE_SR0_PINS = {"DATA_SYNTH_HOLDOUT": "0", "EVAL_RETENTION_EVERY": "0", "DATA_TRUST": "off"}
# THE COUNTERS A READING BESIDE TRAINING MOVES, and nothing else may: tests/test_probe.py's EXEMPT, P1's
# exempt set (Q-EVAL-12's exact-accounting amendment), which the probe's reads and its generation move
# by exactly their own book's counts. B5u is compared under it. A copy, because importing test_probe.py
# runs it; its P2 holds the two equal. The observe-mode book moves no counter it did not mint (SR3's
# bit-identity, tests/test_trust.py T1), so data.trust.* is new, not exempt; and CKPT's Retention book
# (P1's exempt row) is printed in no line this file parses.
P1_EXEMPT = ("eval.*", "tok.segment_remap", "lm.embed.*", "lm.encode.calls",
             "lm.encode.key_path_truncated", "lm.decode.calls", "lm.mask.*", "sig.encode_calls",
             "sig.encode_windows", "world.forecast.calls", "world.forecast.inert", "fab.eval_passes")
# A WORKLOAD IS ONE OR MORE run.py LEGS, run in order, each (name, environment, arguments). `{tmp}` in an
# environment value is the workload's temporary directory, shared by its legs (the parent's checkpoint
# is the child's CKPT_RESUME, and TOK's vocabulary file sits beside the checkpoint directory) and
# deleted with everything in it once the workload has been read. The fixture records the template.
# Optional keys: `resume` makes a parent/child pair a resume of another workload and names its derived
# check (resume_check); `pins` (see PINS above) are set at run time and never recorded or compared;
# `exempt` holds fnmatch patterns of fixture counters this workload is never compared on (--exempt);
# `kept` marks a fixture that is an earlier tree's record, which --record refuses to replace (a pinned
# workload's always is).
WORKLOADS = {
    "B1": {"fixture": "_baseline_fixture.json",
           "what": "run.py --max-windows 80 at the shipped defaults",
           "legs": (("run", dict(COMMON, DATA_STREAM_BYTES="120000"), ("--max-windows", "80")),)},
    "B3": {"fixture": "_baseline_fixture_b3.json",
           "what": "one full epoch with manage passes, acts and a busy store",
           "legs": (("run", _B3, ()),)},
    "B3r": {"fixture": "_baseline_fixture_b3r.json",
            "what": f"B3 saved at window {B3R_SAVE_AT} and continued by CKPT_RESUME",
            "legs": (("parent", dict(_B3, CKPT_DIR="{tmp}/p"), ("--max-windows", str(B3R_SAVE_AT))),
                     ("child", dict(_B3, CKPT_RESUME="{tmp}/p", CKPT_DIR="{tmp}/c"), ())),
            "resume": {"of": "B3", "at": B3R_SAVE_AT, "kind": "continuing"}},
    "B5": {"fixture": "_baseline_fixture_b5.json",
           "what": "DATA_SOURCE=real, 200 windows",
           "legs": (("run", dict(COMMON, DATA_SOURCE="real", DATA_STREAM_BYTES="120000"),
                     ("--max-windows", "200")),)},
    "B6": {"fixture": "_baseline_fixture_b6.json",
           "what": f"two epochs across the roll at window {B6_EPOCH0}",
           "legs": (("run", _B6, ()),)},
    "B6r": {"fixture": "_baseline_fixture_b6r.json",
            "what": f"B6 stopped at its epoch boundary (window {B6_EPOCH0}) and resumed into epoch 1",
            "legs": (("parent", dict(_B6, CKPT_DIR="{tmp}/p"), ("--max-windows", str(B6_EPOCH0))),
                     ("child", dict(_B6, CKPT_RESUME="{tmp}/p", CKPT_DIR="{tmp}/c"), ())),
            "resume": {"of": "B6", "at": B6_EPOCH0, "kind": "boundary"}},
}
# THE PRE-SR0 RECORDS (2026-09-29, the flips of 04-Q5, 04-6.2 and 04-6.3). The six fixtures above were
# recorded before those defaults moved -- B1's at d32e2ce, the rest at ae70638, before any Stage-3 edit
# -- and they moved, unchanged, to *_pre_sr0.json. Each is held to this tree as its workload's legs and
# environment under PRE_SR0_PINS: "the pinned tree is the previous tree" (register 04-Q5's pin rule,
# SR0's "DATA_SYNTH_HOLDOUT=0 with the probe off is bit-exact against HEAD") made a test. B3rp's and
# B6rp's derived checks hold them to B3p and B6p. --record refuses every one of them.
for _name in ("B1", "B3", "B3r", "B5", "B6", "B6r"):
    _w = WORKLOADS[_name]
    WORKLOADS[_name + "p"] = dict(
        _w, fixture=_w["fixture"][:-len(".json")] + "_pre_sr0.json", pins=dict(PRE_SR0_PINS),
        what=_w["what"] + " (pre-SR0)",
        **({"resume": dict(_w["resume"], of=_w["resume"]["of"] + "p")} if "resume" in _w else {}))
# B5u: B5 UNPINNED -- the real source at the shipped defaults, probe, generation and book on -- against
# B5's PRE-SR0 record, on its losses and on every counter outside P1_EXEMPT: the flips promise that no
# number a real-source run trains on moves. The real source carves its held-out block under either
# DATA_SYNTH_HOLDOUT, so nothing it trains on moved; what moved is the reading beside training, and
# P1's exempt set is exactly that. Its record is an earlier tree's, so the table marks it `kept`.
WORKLOADS["B5u"] = dict(WORKLOADS["B5"], fixture=WORKLOADS["B5p"]["fixture"], kept=True,
                        exempt=P1_EXEMPT, what="DATA_SOURCE=real, 200 windows, unpinned, on the pre-SR0 "
                                               "record outside P1's exempt set")
# THE PLANTED SOURCE CHANGES --mutants makes, for the two paths the widening reached that no lever
# reaches: each moves one draw's seed by one. `old` must occur exactly once in `file`.
PLANT_ROLL = {"what": "the roll's draw seed + 1", "file": "src/spine/loop.py",
              "old": "epoch=int(tick.epoch), seed=int(run_cfg.seed))",
              "new": "epoch=int(tick.epoch), seed=int(run_cfg.seed) + 1)"}
PLANT_RESUME = {"what": "a resumed child's draw seed + 1", "file": "src/spine/compose.py",
                "old": ("epoch=0 if restored is None else int(restored.epoch),\n"
                        "        seed=int(run.seed))"),
                "new": ("epoch=0 if restored is None else int(restored.epoch),\n"
                        "        seed=int(run.seed) + (restored is not None))")}
# THE PLANTED CHANGES --mutants must see fail. `first` is (leg, flush): the one loss finding the plant
# must produce, every other leg left without a finding.
MUTANTS = ({"workload": "B3", "env": {"FAB_GRACE": "3"}},
           {"workload": "B5", "env": {"DATA_HOLDOUT_FRAC": "0.06"}},
           {"workload": "B6", "plant": PLANT_ROLL, "first": ("run", B6_EPOCH0)},
           {"workload": "B6r", "plant": PLANT_RESUME, "first": ("child", 0)})
# A counter line: indented, a dotted name, then an integer and nothing else.
COUNTER = re.compile(r"^ {5,}([a-z_][a-z0-9_]*(?:\.[a-z0-9_:]+)+) +(-?\d+)$")
# The typo net's line for a key no lever declares (spine/assemble.py, G9).
UNREAD = re.compile(r"^WARNING: UNREAD ([A-Z][A-Z0-9_]*):", re.M)
# The R stage's clock block, whose names are undotted, so COUNTER never reads them.
CLOCK_HEAD = "    -- RUN.RunClock.counters"
CLOCK_LINE = re.compile(r"^ {7}([a-z_]+) +(-?\d+)$")
# A loss finding as compare_legs writes it: `leg: ` first when the workload has more than one leg.
LOSS_FINDING = re.compile(r"^(?:([a-z]+): )?loss curve differs from flush (\d+) ")


def machine_key():
    import torch
    return {"platform": platform.platform(), "python": platform.python_version(),
            "torch": torch.__version__, "cpu_count": os.cpu_count(), "threads": COMMON["OMP_NUM_THREADS"]}


def commit():
    """What a record is OF: HEAD's short sha -- or, where src/ or run.py differ from HEAD, "the commit
    after <sha>". A record made on uncommitted code records the tree its own commit will hold, not
    HEAD's (2026-09-29: the six records of the flip were the first made so, and naming HEAD would have
    labelled the flipped tree's runs with the tree before the flip)."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "src", "run.py"], cwd=ROOT,
                               capture_output=True).returncode != 0
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"the commit after {sha}" if dirty else sha


def clock_of(stdout):
    """The run's final RUN.RunClock.counters (epoch, in_epoch, step, ...) off the R stage's block; {}
    when the block is missing. Integer values only (windows_in_epoch prints None after a roll)."""
    out, inside = {}, False
    for line in stdout.splitlines():
        if line == CLOCK_HEAD:
            inside = True
        elif inside:
            if line.startswith("    -- "):
                break
            m = CLOCK_LINE.match(line)
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


def trace(env, args, tmp, tag="run", script="run.py"):
    """Run run.py (or a planted copy of it) once; return (loss curve as float reprs, {counter: int},
    the final clock)."""
    # A CLEAN environment: a lever exported in the caller's shell would otherwise change the workload.
    clean = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "PYTHONPATH")}
    clean.update({k: v.replace("{tmp}", tmp) for k, v in env.items()})
    curve_path = os.path.join(tmp, f"curve_{tag}.json")
    proc = subprocess.run([sys.executable, script, *args, "--quiet", "--loss-curve", curve_path],
                          cwd=ROOT, env=clean, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"FAIL  run.py exited {proc.returncode} ({tag})\n{proc.stdout[-3000:]}\n"
                         f"{proc.stderr[-3000:]}")
    # A KEY THIS TREE DECLARES NO LEVER FOR IS SILENTLY THE DEFAULT, and the typo net only warns. A table
    # entry, a pin or a mutant naming one would run, and be compared, as another workload.
    unread = sorted(set(UNREAD.findall(proc.stdout + proc.stderr)) & set(env))
    if unread:
        raise SystemExit(f"FAIL  {tag}: this tree declares no lever named {', '.join(unread)} (the run "
                         f"printed UNREAD for each), so each was silently its default and the run is "
                         f"not the workload the table names. Remove the key, or pin a lever only on a "
                         f"tree that declares it.")
    with open(curve_path, encoding="utf-8") as fh:
        curve = [repr(float(v)) for v in json.load(fh)]
    counters = {}
    for line in proc.stdout.splitlines():
        m = COUNTER.match(line)
        if m:
            counters[m.group(1)] = int(m.group(2))
    return curve, counters, clock_of(proc.stdout)


def run_env(env, pins=None, overrides=None):
    """The environment one leg RUNS under: the table's, then the workload's pins, then --mutants'
    overrides. The fixture records, and the comparison checks, the table's alone. A pin may not restate a
    key the table sets, or the recorded environment would name a value the run did not use."""
    pins = dict(pins or {})
    clash = sorted(set(pins) & set(env))
    if clash:
        raise ValueError(f"the pin(s) {clash} restate the leg's own environment; a pin names a lever "
                         f"the record cannot, and the table's value would not be the one the run used")
    return {**env, **pins, **(overrides or {})}


class PlantError(Exception):
    """A planted source change whose anchor does not occur exactly once."""


def apply_plant(text, plant):
    """`text` with the plant's one replacement made. The anchor must occur exactly once: a plant that
    lands nowhere tests nothing, and one that lands twice tests something else."""
    n = text.count(plant["old"])
    if n != 1:
        raise PlantError(f"the plant '{plant['what']}' finds its anchor {n} time(s) in {plant['file']} "
                         f"and must find it once: the statement it was aimed at has moved. Re-aim the "
                         f"plant at the same statement.")
    return text.replace(plant["old"], plant["new"])


def planted_tree(tmp, plant):
    """A copy of src/ and run.py inside `tmp` with the plant made; returns the copy's run.py. run.py puts
    its OWN src/ first on sys.path and DATA_DIR is relative to the working directory, so the copy runs
    from the repository root and reads the repository's data/."""
    root = os.path.join(tmp, "planted")
    shutil.copytree(os.path.join(ROOT, "src"), os.path.join(root, "src"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(os.path.join(ROOT, "run.py"), os.path.join(root, "run.py"))
    path = os.path.join(root, plant["file"])
    with open(path, encoding="utf-8") as fh:
        text = apply_plant(fh.read(), plant)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return os.path.join(root, "run.py")


def run_workload(name, overrides=None, plant=None):
    """Every leg of one workload, in order, in one temporary directory: [{name, env, args, loss_curve,
    counters, clock}]. The table's `pins`, and --mutants' `overrides` and `plant`, change the run only;
    `env` stays the table's, which is what a fixture records and a comparison checks."""
    w = WORKLOADS[name]
    legs = []
    with tempfile.TemporaryDirectory(prefix=f"baseline_{name}_") as tmp:
        script = planted_tree(tmp, plant) if plant else "run.py"
        for leg, env, args in w["legs"]:
            try:
                env_run = run_env(env, w.get("pins"), overrides)
            except ValueError as e:
                raise SystemExit(f"FAIL  {name} ({leg}): {e}")
            curve, counters, clock = trace(env_run, args, tmp, tag=leg, script=script)
            legs.append({"name": leg, "env": dict(env), "args": list(args), "loss_curve": curve,
                         "counters": counters, "clock": clock})
    return legs


def fixture_path(name):
    return os.path.join(ROOT, "tests", WORKLOADS[name]["fixture"])


def fixture_legs(fx):
    """A fixture's legs. B1's record predates legs: one leg named `run`, its windows an argument."""
    if "legs" in fx:
        return fx["legs"]
    return [{"name": "run", "env": fx["env"], "args": ["--max-windows", str(fx["windows"])],
             "loss_curve": fx["loss_curve"], "counters": fx["counters"]}]


def exempt_match(name, patterns):
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def exemptions(entry, cli=()):
    """The patterns a workload is compared under: the command line's, then the table entry's own."""
    cli = list(cli)
    return cli + [p for p in entry.get("exempt", ()) if p not in cli]


Compared = collections.namedtuple("Compared", "findings compared added exempted idle")


def compare_counters(want, got, exempt=()):
    """Every fixture counter in `want` against the run's `got`, except those an `exempt` pattern names.
    Returns Compared(findings: ["name: got (fixture want)"], compared: how many were compared, added:
    the run's counters the fixture never had, exempted: [(name, got, want)], idle: the patterns that
    named no fixture counter)."""
    findings, exempted, n = [], [], 0
    for name in sorted(want):
        if exempt_match(name, exempt):
            exempted.append((name, got.get(name), want[name]))
            continue
        n += 1
        if got.get(name) != want[name]:
            findings.append(f"{name}: {got.get(name)} (fixture {want[name]})")
    # A COUNTER THE FIXTURE NEVER HAD IS A NEW INSTRUMENT, NOT A CHANGED RUN: listed, not failed. A
    # fixture counter that moved or vanished is a difference and fails above.
    added = sorted(set(got) - set(want))
    idle = [p for p in exempt if not any(fnmatch.fnmatchcase(k, p) for k in want)]
    return Compared(findings, n, added, exempted, idle)


def compare_curve(want, got):
    """None when the curves are equal, else the finding naming the first differing flush."""
    if got == want:
        return None
    first = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return f"loss curve differs from flush {first} ({len(got)} vs {len(want)} points)"


def compare_legs(want_legs, legs, exempt=(), name="", kept_record=False):
    """One workload's run legs against its fixture's: (findings, lines). Reads no file and prints
    nothing. `env` on a run leg is the table's, never the pins, so a pinned leg is held to a record
    made without them and a table edited since the record still fails."""
    findings, lines = [], []
    if [w["name"] for w in want_legs] != [g["name"] for g in legs]:
        findings.append(f"the fixture's legs are {[w['name'] for w in want_legs]}, the table's "
                        f"{[g['name'] for g in legs]}")
    many = len(legs) > 1
    for want, got in zip(want_legs, legs):
        pre = f"{got['name']}: " if many else ""
        if want["env"] != got["env"] or list(want["args"]) != list(got["args"]):
            findings.append(f"{pre}the fixture was recorded with env {want['env']} and arguments "
                            f"{want['args']}; the table now says {got['env']} and {got['args']}. "
                            + ("Restore the table: a kept record is an earlier tree's and is not "
                               "re-recorded" if kept_record else
                               f"Restore the table, or re-record with --record {name}"))
        f = compare_curve(want["loss_curve"], got["loss_curve"])
        if f:
            findings.append(pre + f)
        c = compare_counters(want["counters"], got["counters"], exempt)
        findings += [pre + x for x in c.findings]
        lines.append(f"      {pre}{len(got['loss_curve'])} losses, {c.compared} integer counters "
                     f"compared, {len(c.added)} new" + (" (listed)" if c.added else "")
                     + (f", {len(c.exempted)} exempt (listed)" if c.exempted else ""))
        if c.added:
            lines.append(f"      {pre}new counters since the fixture (not compared): {', '.join(c.added)}")
        if c.exempted:
            lines.append(f"      {pre}exempt (not compared): "
                         + ", ".join(f"{n} {g} (fixture {w})" for n, g, w in c.exempted))
        if exempt and c.idle:
            lines.append(f"      {pre}--exempt pattern(s) that named no fixture counter: "
                         f"{', '.join(c.idle)}")
    return findings, lines


def verdict_line(verdict, name, what, recorded_at, pins=None):
    """A workload's verdict, with its pins when it has any: they are in no recorded environment, so this
    line is the one place a reader sees that the run was pinned."""
    pinned = (" under pins " + " ".join(f"{k}={v}" for k, v in pins.items())
              + " (run, not recorded or compared)") if pins else ""
    return f"{verdict}  {name:<4} {what}{pinned} reproduces the fixture recorded at {recorded_at}"


def compare_workload(name, legs, key, exempt=(), quiet=False):
    """One workload's legs against its fixture: (verdict, findings), the verdict PASS, FAIL or
    UNVERIFIABLE. Prints it unless quiet."""
    path = fixture_path(name)
    if not os.path.exists(path):
        if not quiet:
            print(f"FAIL  {name:<4} no fixture at {path}; record one with --record {name} at the base "
                  f"commit")
        return "FAIL", ["no fixture"]
    with open(path, encoding="utf-8") as fh:
        fx = json.load(fh)
    if fx["machine"] != key:
        if not quiet:
            print(f"UNVERIFIABLE  {name}  the fixture was recorded on {fx['machine']}, this machine is "
                  f"{key}. Nothing was compared. Record a fixture for this machine with --record {name}.")
        return "UNVERIFIABLE", []
    pins = WORKLOADS[name].get("pins")
    findings, lines = compare_legs(fixture_legs(fx), legs, exemptions(WORKLOADS[name], exempt), name,
                                   kept_record=kept(WORKLOADS[name]))
    verdict = "FAIL" if findings else "PASS"
    if not quiet:
        print(verdict_line(verdict, name, WORKLOADS[name]["what"], fx["commit"], pins))
        for line in lines:
            print(line)
        for f in findings[:20]:
            print(f"      - {f}")
    return verdict, findings


def resume_check(name, live, key):
    """A resume pair's derived check (the table's `resume`): (verdict, detail), the verdict PASS, FAIL
    or UNVERIFIABLE. The reference is this invocation's run of the workload the pair resumes, else that
    workload's fixture when it was recorded on this machine.
      continuing -- the parent's clock stopped mid-epoch (in_epoch > 0), and the parent's losses are the
                    reference's first `at` and the child's are the reference's from window `at` on,
                    exactly;
      boundary   -- the parent's clock stopped at an epoch boundary (in_epoch 0, epoch 1 or later) and
                    the parent's losses are the reference's first `at`, exactly. The child is held to
                    its own record only: a boundary resume is not a continuation (B6r above)."""
    spec = WORKLOADS[name]["resume"]
    of, at, kind = spec["of"], int(spec["at"]), spec["kind"]
    if of in live:
        ref, src = live[of][0]["loss_curve"], f"this run's {of}"
    else:
        path = fixture_path(of)
        fx = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                fx = json.load(fh)
        if fx is None or fx["machine"] != key:
            return "UNVERIFIABLE", f"no {of} to hold it to: run {of} too, or record its fixture here"
        ref, src = fixture_legs(fx)[0]["loss_curve"], f"{of}'s fixture recorded at {fx['commit']}"
    legs = {leg["name"]: leg for leg in live[name]}
    parent, child = legs.get("parent") or {}, legs.get("child") or {}
    p, c = parent.get("loss_curve", []), child.get("loss_curve", [])
    clock = parent.get("clock") or {}
    bad = []
    if not {"epoch", "in_epoch"} <= set(clock):
        stop = "at an unknown position"
        bad.append("the parent's output carries no RUN.RunClock.counters block, so where it stopped "
                   "is unknown")
    else:
        stop = f"at epoch {clock['epoch']}, in_epoch {clock['in_epoch']}"
        if kind == "continuing" and clock["in_epoch"] <= 0:
            bad.append(f"the parent stopped {stop}, at an epoch boundary, so its child does not "
                       f"continue mid-epoch")
        if kind == "boundary" and (clock["in_epoch"] != 0 or clock["epoch"] < 1):
            bad.append(f"the parent stopped {stop}, not at an epoch boundary: {of}'s epoch 0 no longer "
                       f"ends at window {at}, so move the stop to where it ends")
    fp = compare_curve(ref[:at], p)
    if fp:
        bad.append(f"parent: {fp}")
    if kind == "continuing":
        fc = compare_curve(ref[at:], c)
        if fc:
            bad.append(f"child: {fc}")
        if not c:
            bad.append("the child trained no window")
        detail = (f"the parent's {len(p)} losses (stopped {stop}) against {of}'s first {at} and the "
                  f"child's {len(c)} against {of}'s from window {at} on ({src})")
    else:
        detail = (f"the parent's {len(p)} losses (stopped {stop}) against {of}'s first {at} ({src}); "
                  f"the child's {len(c)} are held to their own record, since a boundary resume is not a "
                  f"continuation of {of}")
    return ("FAIL" if bad else "PASS"), detail + "".join(f"; {b}" for b in bad)


def resume_line(verdict, name, detail):
    spec = WORKLOADS[name]["resume"]
    how = ("continues {of} exactly" if spec["kind"] == "continuing" else
           "resumes {of} at its epoch boundary").format(of=spec["of"])
    return f"{verdict}  {name:<4} {how}: {detail}"


def kept(entry):
    """Is this table entry's fixture an earlier tree's record? Every pinned workload's is."""
    return bool(entry.get("pins") or entry.get("kept"))


def unrecordable(entry, verdict=None):
    """Why --record must not write this table entry, or None. A kept record is an earlier tree's; a
    resume pair is written only once its derived check has passed."""
    if kept(entry):
        return ("its record is an earlier tree's, kept to compare this tree against"
                + (", made before its pinned levers existed" if entry.get("pins") else "")
                + ", and re-recording would replace it with this tree's own run")
    if "resume" in entry and verdict != "PASS":
        return f"its derived check did not PASS ({verdict})"
    return None


def loss_findings(findings):
    """[(leg, flush)] for each loss finding among `findings`; a one-leg workload's leg is `run`."""
    return [(m.group(1) or "run", int(m.group(2))) for m in map(LOSS_FINDING.match, findings) if m]


def comparator_known_answers():
    """The comparison itself, on planted data: [(name, ok, detail)]. No run.py involved."""
    fx = {"a.b": 1, "eval.x": 2, "lm.encode.calls": 5}
    out = []
    f = compare_curve(["1.0", "2.0", "3.0"], ["1.0", "2.0", "3.5"])
    out.append(("a planted loss change is named at its flush", f is not None and "flush 2" in f, f))
    r = compare_counters(fx, dict(fx, **{"eval.x": 3, "new.one": 1}), ["eval.*"])
    out.append(("--exempt passes a planted bump of an exempt counter and prints it",
                not r.findings and r.exempted == [("eval.x", 3, 2)] and r.compared == 2
                and r.added == ["new.one"], str(r)))
    r = compare_counters(fx, dict(fx, **{"a.b": 2, "eval.x": 3}), ["eval.*"])
    out.append(("--exempt still fails a planted bump of a counter no pattern names",
                r.findings == ["a.b: 2 (fixture 1)"], str(r)))
    r = compare_counters(fx, {k: v for k, v in fx.items() if k != "a.b"})
    out.append(("a fixture counter that vanished fails", r.findings == ["a.b: None (fixture 1)"],
                str(r)))
    pats = exemptions({"exempt": ("eval.*", "lm.*")}, ["lm.*"])
    r = compare_counters(fx, dict(fx, **{"eval.x": 3}), pats)
    out.append(("a table entry's own exempt patterns are added to the command line's",
                pats == ["lm.*", "eval.*"] and exemptions({}) == [] and not r.findings, f"{pats}; {r}"))
    # B3r: a continuing pair.
    ref = [repr(float(i)) for i in range(B3R_SAVE_AT + 30)]
    live = {"B3": [{"name": "run", "loss_curve": ref}],
            "B3r": [{"name": "parent", "loss_curve": ref[:B3R_SAVE_AT],
                     "clock": {"epoch": 0, "in_epoch": B3R_SAVE_AT}},
                    {"name": "child", "loss_curve": ref[B3R_SAVE_AT:]}]}
    v_exact = resume_check("B3r", live, None)[0]
    live["B3r"][1]["loss_curve"] = ref[B3R_SAVE_AT:-1] + ["9.5"]
    v_off, d_off = resume_check("B3r", live, None)
    live["B3r"][1]["loss_curve"] = ref[B3R_SAVE_AT:]
    live["B3r"][0]["clock"] = {"epoch": 1, "in_epoch": 0}
    v_edge, d_edge = resume_check("B3r", live, None)
    out.append(("B3r's derived check passes an exact continuation, and fails a child that departs at "
                "its last flush and a parent that stopped at an epoch boundary",
                v_exact == "PASS" and v_off == "FAIL" and "flush 29" in d_off and v_edge == "FAIL"
                and "at an epoch boundary" in d_edge,
                f"{v_exact}; {v_off}: {d_off}; {v_edge}: {d_edge}"))
    # B6r: a boundary pair. The child departs from B6 from its first flush and still passes.
    ref = [repr(float(i)) for i in range(2 * B6_EPOCH0)]
    live = {"B6": [{"name": "run", "loss_curve": ref}],
            "B6r": [{"name": "parent", "loss_curve": ref[:B6_EPOCH0],
                     "clock": {"epoch": 1, "in_epoch": 0}},
                    {"name": "child", "loss_curve": ["9.5"] * B6_EPOCH0}]}
    v_edge = resume_check("B6r", live, None)[0]
    live["B6r"][0]["clock"] = {"epoch": 0, "in_epoch": B6_EPOCH0}
    v_mid, d_mid = resume_check("B6r", live, None)
    live["B6r"][0].update(clock={"epoch": 1, "in_epoch": 0}, loss_curve=ref[:B6_EPOCH0 - 1] + ["9.5"])
    v_dep, d_dep = resume_check("B6r", live, None)
    out.append(("B6r's derived check passes a parent stopped at the boundary on B6's epoch 0 whatever "
                "its child reads, and fails a parent stopped mid-epoch, naming its clock, and one that "
                "departs from B6", v_edge == "PASS" and v_mid == "FAIL"
                and f"in_epoch {B6_EPOCH0}, not at an epoch boundary" in d_mid and v_dep == "FAIL"
                and f"parent: loss curve differs from flush {B6_EPOCH0 - 1}" in d_dep,
                f"{v_edge}; {v_mid}: {d_mid}; {v_dep}: {d_dep}"))
    # PINS: run, never recorded or compared, and printed; the environment rule still holds.
    table, pins = {"DATA_STREAM_BYTES": "120000"}, {"DATA_SYNTH_HOLDOUT": "0", "DATA_TRUST": "off"}
    env_run = run_env(table, pins, {"FAB_GRACE": "3"})
    try:
        run_env(table, {"DATA_STREAM_BYTES": "20000"})
        restated = "accepted"
    except ValueError as e:
        restated = str(e)
    rec = [{"name": "run", "env": dict(table), "args": [], "loss_curve": ["1.0"],
            "counters": {"a.b": 1}}]
    f_pin, _ = compare_legs(rec, [dict(rec[0], env=dict(table))], name="B1p", kept_record=True)
    f_env, _ = compare_legs(rec, [dict(rec[0], env=dict(table, DATA_HOLDOUT_FRAC="0.05"))], name="B1p",
                            kept_record=True)
    line = verdict_line("PASS", "B1p", "w", "ae70638", pins)
    out.append(("a pin runs but is neither recorded nor compared, and the verdict line prints it; a "
                "table environment that departs from its record still fails; a pin restating the table "
                "is refused", env_run == dict(table, FAB_GRACE="3", **pins) and not f_pin
                and len(f_env) == 1 and "DATA_HOLDOUT_FRAC" in f_env[0] and "not re-recorded" in f_env[0]
                and "under pins DATA_SYNTH_HOLDOUT=0 DATA_TRUST=off" in line
                and "DATA_STREAM_BYTES" in restated, f"{env_run}; {f_pin}; {f_env}; {line}; {restated}"))
    refusals = (unrecordable({"pins": pins}), unrecordable({"kept": True, "exempt": ("eval.*",)}),
                unrecordable({"resume": {}}, "FAIL"), unrecordable({"resume": {}}, "PASS"),
                unrecordable({"exempt": ("eval.*",)}))
    out.append(("--record refuses a pinned workload, a kept one and a resume pair whose check did not "
                "pass, and writes the rest", bool(refusals[0]) and "pinned levers" in refusals[0]
                and bool(refusals[1]) and "earlier tree" in refusals[1] and bool(refusals[2])
                and refusals[3:] == (None, None), str(refusals)))
    # PLANTS: made where the anchor occurs once, refused where it does not, and still aimed in this tree.
    plant = {"what": "p", "file": "f.py", "old": "a = 1", "new": "a = 2"}
    made = apply_plant("x\na = 1\n", plant) == "x\na = 2\n"
    refused = []
    for text in ("x\n", "a = 1\na = 1\n"):
        try:
            apply_plant(text, plant)
        except PlantError as e:
            refused.append("f.py" in str(e))
    aimed = {}
    for label, p in (("PLANT_ROLL", PLANT_ROLL), ("PLANT_RESUME", PLANT_RESUME)):
        with open(os.path.join(ROOT, p["file"]), encoding="utf-8") as fh:
            aimed[label] = (fh.read().count(p["old"]), p["file"])
    out.append(("a plant is made where its anchor occurs once and refused, naming its file, where it "
                "occurs 0 or 2 times; each --mutants plant finds its anchor once in this tree",
                made and refused == [True, True] and all(n == 1 for n, _ in aimed.values()),
                f"made {made}, refused {refused}; anchors found: "
                + ", ".join(f"{k} {n} time(s) in {f}" for k, (n, f) in aimed.items())
                + " -- re-aim a plant whose statement has moved"))
    lf = loss_findings(["child: loss curve differs from flush 0 (104 vs 104 points)",
                        "child: a.b: 2 (fixture 1)",
                        "loss curve differs from flush 104 (208 vs 208 points)"])
    out.append(("a loss finding is read back with its leg: a two-leg workload's by its prefix, a "
                "one-leg workload's as `run`", lf == [("child", 0), ("run", 104)], str(lf)))
    return out


def mutants(key):
    """--mutants: each planted change must FAIL its workload's comparison, naming the first differing
    flush, and a mutant with `first` must produce exactly that loss finding and leave every other leg
    without a finding. Returns 0 when every one did."""
    ok = True
    for m in MUTANTS:
        name, env, plant, first = m["workload"], m.get("env") or {}, m.get("plant"), m.get("first")
        what = ("at " + " ".join(f"{k}={v}" for k, v in env.items()) if env else
                f"with {plant['what']} planted in {plant['file']}")
        try:
            legs = run_workload(name, env, plant)
        except PlantError as e:
            ok = False
            print(f"FAIL  mutant {name} {what}: {e}")
            continue
        verdict, findings = compare_workload(name, legs, key, quiet=True)
        if verdict == "UNVERIFIABLE":
            print(f"UNVERIFIABLE  mutant {name} {what}: the fixture is from another machine, so "
                  f"nothing was compared")
            continue
        named = [f for f in findings if LOSS_FINDING.match(f)]
        where = loss_findings(findings)
        good = verdict == "FAIL" and bool(named)
        aim = ""
        if first is not None:
            others = [f for f in findings for leg in legs
                      if leg["name"] != first[0] and f.startswith(f"{leg['name']}: ")]
            hit = where == [tuple(first)] and not others
            good = good and hit
            aim = (f"; planted to first differ at flush {first[1]} of `{first[0]}`"
                   + (" and nowhere else, as it did" if hit else
                      f", and it did not: loss findings {where}, {len(others)} finding(s) on other "
                      f"legs"))
        ok = ok and good
        print(f"{'PASS' if good else 'FAIL'}  mutant {name} {what} fails its fixture and names the "
              f"first differing flush: {named[0] if named else 'no loss finding'}{aim} "
              f"({len(findings) - len(named)} other finding(s) beside it)")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workloads", nargs="*", metavar="NAME",
                    help=f"the workloads to run (default: all of {', '.join(WORKLOADS)})")
    ap.add_argument("--record", action="store_true",
                    help="(re)write the named workloads' fixtures instead of comparing")
    ap.add_argument("--exempt", action="append", default=[], metavar="PATTERNS",
                    help="comma-separated fnmatch patterns of fixture counters not to compare")
    ap.add_argument("--mutants", action="store_true",
                    help="run the planted changes that must fail their comparison")
    args = ap.parse_args(argv)
    bad = [n for n in args.workloads if n not in WORKLOADS]
    if bad:
        ap.error(f"unknown workload(s) {bad}; the table has {list(WORKLOADS)}")
    names = [n for n in WORKLOADS if n in args.workloads] or list(WORKLOADS)
    exempt = [p.strip() for a in args.exempt for p in a.split(",") if p.strip()]
    key = machine_key()
    ok = True
    if not args.record:
        for n, good, detail in comparator_known_answers():
            print(f"{'PASS' if good else 'FAIL'}  comparator: {n}" + ("" if good else f" -- {detail}"))
            ok = ok and good
    if args.mutants:
        return mutants(key) if ok else 1
    if args.record:
        # A KEPT RECORD'S WORKLOAD IS NOT EVEN RUN BY --record: it could only be refused afterwards.
        for name in [n for n in names if kept(WORKLOADS[n])]:
            print(f"NOT RECORDED  {name}: {unrecordable(WORKLOADS[name])}")
            ok = ok and name not in args.workloads
        names = [n for n in names if not kept(WORKLOADS[n])]
    live = {}
    for name in names:
        live[name] = run_workload(name)
        if not args.record:
            ok = compare_workload(name, live[name], key, exempt)[0] != "FAIL" and ok
    verdicts = {}
    for name in live:
        if "resume" in WORKLOADS[name]:
            verdicts[name], detail = resume_check(name, live, key)
            print(resume_line(verdicts[name], name, detail))
            ok = ok and verdicts[name] != "FAIL"
    if args.record:
        for name in names:
            why = unrecordable(WORKLOADS[name], verdicts.get(name))
            if why:
                print(f"NOT RECORDED  {name}: {why}")
                ok = False
                continue
            # THE CLOCK IS READ, NEVER RECORDED: the resume checks take it from the live parent.
            legs = [{k: v for k, v in leg.items() if k != "clock"} for leg in live[name]]
            with open(fixture_path(name), "w", encoding="utf-8") as fh:
                json.dump({"commit": commit(), "workload": name, "machine": key, "legs": legs}, fh,
                          indent=1, sort_keys=True)
                fh.write("\n")
            print(f"RECORDED  {fixture_path(name)}: "
                  + "; ".join(f"{leg['name']} {len(leg['loss_curve'])} losses, "
                              f"{len(leg['counters'])} integer counters" for leg in legs)
                  + f" at {commit()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
