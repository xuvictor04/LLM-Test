#!/usr/bin/env python3
"""Does the corpus reach the model as the thing the command asked for?

Two faults, both triggered by the same event -- a corpus that came up short. That is not a hypothetical:
"there is an error of corpus size being too small" is how this session started, and an interrupted fetch, a
gated dataset that wrote nothing, and a --gb the machine could not satisfy all produce it.

  1. DN AND CORP DESYNC. open_corpus returns one entry per name in DOMAINS order, so CORP[i] is DN[i]. The
     5000-byte floor filtered CORP and left DN alone, shifting every name after the gap. DN is what
     report_holdout uses to LABEL each held-out score, and ACROSS THE RUN BOUNDARY looks the previous run's
     score up BY NAME -- so a dropped English corpus makes the next run compare Python against English and
     report the difference as forgetting. That number is the continual-learning claim.

  2. THE RESAMPLING GUARD SUMMED THE CORPORA. build_stream draws PER CORPUS in the proportions PHASE_SCHED
     sets; the guard compared STREAM_LEN against sum(SEG_LEN). 60 MB of English beside 8 MB of Python reads
     as 68 MB against a 4 MB stream and passes, while the Python half repeats 4x every epoch. The added
     corpus is always the small one, and its repetition is what would be mistaken for having learned it.

Runs without torch and without the network: the arithmetic is re-derived here from the same rules.
"""
import random
import re
import sys

FAILED = []


def check(ok, msg):
    print(f"  {'ok  ' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILED.append(msg)


SRC = open("self_organize.py").read()


def load_phases():
    """Import _phases from the real source rather than restating it -- a test that restates the rule it is
    checking passes forever after the rule changes."""
    m = re.search(r"def _phases\(n, p=None, w=None\):.*?\n    return out\n", SRC, re.S)
    if not m:
        sys.exit("corpus_test: could not find _phases in self_organize.py -- the test is stale, not the code.")
    ns = {"_i": lambda k, d: d}
    exec(m.group(0), ns)
    return ns["_phases"]


_phases = load_phases()

# --- 1. THE FILTER MUST TAKE THE NAMES WITH IT ------------------------------------------------------------
print("A DROPPED CORPUS TAKES ITS NAME WITH IT")


def filter_aligned(names, sizes, floor=5000):
    """The fixed logic, stated once. Mirrors self_organize.py's _keep/_drop block."""
    keep = [i for i, s in enumerate(sizes) if s > floor]
    dropped = [(names[i], sizes[i]) for i in range(len(sizes)) if i not in set(keep)]
    return [names[i] for i in keep], [sizes[i] for i in keep], dropped


def filter_old(names, sizes, floor=5000):
    """What it used to do: CORP filtered, DN untouched."""
    return names, [s for s in sizes if s > floor], []


# The exact reproduction from the session: DOMAINS="eng,py", eng under the floor after a partial fetch.
CASES = [
    (["eng", "py"], [1880, 84000], ["py"]),
    (["eng", "py"], [84000, 1880], ["eng"]),
    (["eng", "py", "num", "c"], [90000, 40, 70000, 30], ["eng", "num"]),
    (["eng", "py"], [90000, 84000], ["eng", "py"]),          # nothing dropped: must be a no-op
    (["a", "b", "c"], [10, 20, 30], []),                     # everything dropped
]
for names, sizes, want in CASES:
    got_names, got_sizes, dropped = filter_aligned(names, sizes)
    check(got_names == want, f"{names} sizes {sizes} -> surviving names {got_names} (want {want})")
    check(len(got_names) == len(got_sizes),
          f"...and one name per surviving corpus ({len(got_names)} names, {len(got_sizes)} corpora)")
    # THE PROPERTY THAT ACTUALLY MATTERS: every surviving name still points at its own corpus.
    orig = dict(zip(names, sizes))
    check(all(orig[n] == s for n, s in zip(got_names, got_sizes)),
          f"...and every surviving name still points at ITS OWN corpus: "
          f"{list(zip(got_names, got_sizes))}")

print("\n  ...and the old behaviour is the mislabelling, reproduced so it cannot come back silently")
old_names, old_sizes, _ = filter_old(["eng", "py"], [1880, 84000])
mislabelled = old_names[0] if old_sizes else None
check(mislabelled == "eng" and old_sizes == [84000],
      f"pre-fix: the 84000-byte PYTHON corpus was reported as {mislabelled!r} -- the bug this test pins")
new_names, new_sizes, dropped = filter_aligned(["eng", "py"], [1880, 84000])
check(new_names == ["py"] and new_sizes == [84000],
      f"post-fix: it is reported as {new_names[0]!r}, and {dropped} is named in the log")

# --- 2. THE PHASE SCHEDULE IS THE CONTINUAL-LEARNING SHAPE ------------------------------------------------
# Not an incidental detail: PHASE_SCHED decides whether "add an area" is a task boundary or a rehearsal.
print("\nTHE GENERATED PHASE SCHEDULE, AND WHAT IT MEANS FOR ADDING AN AREA")
sched2 = _phases(2)
check(sched2 == [[0], [0], [1], [1]],
      f"NP=2 -> {sched2}: corpus 0 for the first half of the stream, corpus 1 for the second")
check(all(len(p) == 1 for p in sched2),
      "...the two corpora are never active together, so within one epoch this IS a task boundary")
# And the thing to know before reading any result from it:
check(sched2[0] != sched2[-1],
      "...the last phase excludes the first corpus, so `faded` is non-empty and the unlearn test is not vacuous")
sched1 = _phases(1)
check(all(p == [0] for p in sched1), f"NP=1 -> {sched1}: one corpus cannot fade; PHASED degenerates, as documented")

# --- 3. THE PER-CORPUS DRAW, PREDICTED vs SIMULATED --------------------------------------------------------
# The guard predicts each corpus's share from PHASE_SCHED. If that prediction does not match what
# build_stream actually draws, the guard is a mechanism that runs and reports the wrong number -- which is
# worse than not having it, because it reads as an all-clear.
print("\nTHE PREDICTED PER-CORPUS SHARE MATCHES WHAT build_stream ACTUALLY DRAWS")


def predict(stream_len, sched, NP, phased=True):
    """The guard's arithmetic, as written in self_organize.py."""
    draw = [0.0] * NP
    if phased and sched:
        per = stream_len / len(sched)
        for act in sched:
            a = [x for x in act if x < NP] or list(range(NP))
            for p in a:
                draw[p] += per / len(a)
    else:
        for p in range(NP):
            draw[p] = stream_len / NP
    return draw


def simulate(stream_len, sched, NP, seg_min, seg_max, phased=True, seed=0):
    """build_stream's draw loop, byte-for-byte on the accounting: per-phase budget, uniform choice of an
    active corpus, segment lengths in [SEG_MIN, SEG_MAX], truncated to STREAM_LEN at the end."""
    rs = random.Random(seed)
    got = [0] * NP
    pos = 0
    if phased:
        per = stream_len // len(sched)
        for pi, act in enumerate(sched):
            a = [x for x in act if x < NP] or list(range(NP))
            while pos < min((pi + 1) * per, stream_len) and pos < stream_len:
                p = rs.choice(a)
                L = rs.randint(seg_min, seg_max)
                take = min(L, stream_len - pos)          # buf[:STREAM_LEN] truncates the tail
                got[p] += take
                pos += L
    else:
        while pos < stream_len:
            p = rs.randrange(NP)
            L = rs.randint(seg_min, seg_max)
            got[p] += min(L, stream_len - pos)
            pos += L
    return got


# pilot-add's real settings: STREAM_LEN=4000000, SEG_MIN=8000, SEG_MAX=20000, DOMAINS="eng,py".
for NP, phased, sl, smin, smax in ((2, True, 4_000_000, 8000, 20000),
                                   (2, False, 4_000_000, 8000, 20000),
                                   (3, True, 4_000_000, 8000, 20000),
                                   (4, True, 4_000_000, 700, 1800),
                                   (2, True, 120_000, 700, 1800)):
    sched = _phases(NP)
    pred = predict(sl, sched, NP, phased)
    # Average several seeds: one draw of ~300 segments has real variance, and a test that fails one seed in
    # ten is a test nobody trusts. The claim is about the EXPECTED share, so measure the expectation.
    sims = [simulate(sl, sched, NP, smin, smax, phased, seed=s) for s in range(12)]
    mean = [sum(s[p] for s in sims) / len(sims) for p in range(NP)]
    worst = max(abs(mean[p] - pred[p]) / max(1.0, pred[p]) for p in range(NP))
    tag = f"NP={NP} {'PHASED' if phased else 'flat'} STREAM_LEN={sl} seg[{smin},{smax}]"
    check(worst < 0.02,
          f"{tag}: predicted {[round(x/1e3) for x in pred]} kB vs drawn "
          f"{[round(x/1e3) for x in mean]} kB -- worst error {worst*100:.1f}%")

# --- 4. THE GUARD FIRES ON THE CASE THAT MOTIVATED IT ------------------------------------------------------
# EXPOSURE IS A WHOLE-RUN QUANTITY. The first version of this guard compared the PER-EPOCH draw against the
# corpus and stayed quiet on 60 MB eng + 8 MB py: 2.00 MB/epoch is under 7.6 MB, so nothing fired. Over
# EPOCHS=8 that is 16 MB drawn from 7.6 MB -- the added area seen 2.1x over while English is 28% sampled.
# Writing an exposure check in epoch units is the same units fault the check itself exists to catch, so this
# case is pinned here: it is the one that found it.
print("\nEXPOSURE OVER THE WHOLE RUN, NOT PER EPOCH")
VAL_FRAC, EPOCHS = 0.05, 8
EXPOSURE_MAX, EXPOSURE_SKEW = 2.0, 3.0


def guard(eng_mb, py_mb, stream_len=4_000_000, epochs=EPOCHS):
    """The three tests self_organize.py applies, stated once."""
    seg_len = [int(eng_mb * 1e6 * (1 - VAL_FRAC)), int(py_mb * 1e6 * (1 - VAL_FRAC))]
    draw = predict(stream_len, _phases(2), 2)
    exp = [draw[i] * epochs / seg_len[i] for i in range(2)]
    return dict(
        seg_len=seg_len, draw=draw, exp=exp,
        summed_ok=stream_len <= sum(seg_len),                          # the OLD guard: sums the corpora
        tight=[i for i in range(2) if draw[i] > seg_len[i]],           # within one epoch
        repeated=[i for i in range(2) if exp[i] > EXPOSURE_MAX],       # across the run
        skew=max(exp) / min(exp) if min(exp) > 0 else float("inf"),
    )


#                eng   py   within-epoch   over-run repetition   imbalance
for eng_mb, py_mb, want_tight, want_rep, want_skew in (
        (60, 60, False, False, False),      # matched: nothing to say
        (60, 30, False, False, False),      # the recommended pull: quiet
        (60,  8, False, True,  True),       # THE CASE THE PER-EPOCH GUARD MISSED
        (60,  3, False, True,  True),       # worse, still under the per-epoch cap
        (60,  1, True,  True,  True),       # bad enough to repeat inside one epoch too
):
    g = guard(eng_mb, py_mb)
    check(bool(g["tight"]) == want_tight,
          f"eng {eng_mb} + py {py_mb} MB: within-epoch guard "
          f"{'FIRES' if g['tight'] else 'quiet'} (py draws {g['draw'][1]/1e6:.2f} MB/epoch "
          f"from {g['seg_len'][1]/1e6:.2f} MB)")
    check(bool(g["repeated"]) == want_rep,
          f"   ...whole-run repetition {'FIRES' if g['repeated'] else 'quiet'}: "
          f"eng {g['exp'][0]:.2f}x, py {g['exp'][1]:.2f}x over {EPOCHS} epochs "
          f"(EXPOSURE_MAX={EXPOSURE_MAX:g})")
    check((g["skew"] > EXPOSURE_SKEW) == want_skew,
          f"   ...imbalance {'FIRES' if g['skew'] > EXPOSURE_SKEW else 'quiet'}: "
          f"{g['skew']:.1f}x between the two areas (EXPOSURE_SKEW={EXPOSURE_SKEW:g})")
    if want_rep or want_skew:
        check(g["summed_ok"],
              f"   ...and the SUMMED check says nothing: 4 MB stream vs "
              f"{sum(g['seg_len'])/1e6:.0f} MB total. That is the gap these guards close.")

# --- 5. THE REAL SOURCE LINES EXECUTE ----------------------------------------------------------------------
# Everything above tests the ARITHMETIC, restated here. That is not the same as the code running. torch is not
# installed on every box this test runs on, so self_organize.py cannot be imported -- and a NameError, a bad
# format spec or a wrong variable name in a block that only executes at startup would survive every check
# above and only surface on the GPU, minutes into a run. So: pull the actual source text of both new blocks
# out of the file, dedent it, and exec it against a stub namespace. Restating a rule and testing the
# restatement is how a test passes forever after the code stops matching it.
print("\nTHE ACTUAL SOURCE BLOCKS EXECUTE, NOT A RESTATEMENT OF THEM")
import textwrap


def block(start, end):
    a = SRC.index(start)
    a = SRC.rfind("\n", 0, a) + 1        # back up to the START OF THE LINE, or dedent sees the first line as
    b = SRC.index(end, a)                #   unindented and every line after it as an unexpected indent
    return textwrap.dedent(SRC[a:b])


def run_block(code, ns):
    out = []
    ns.setdefault("print", lambda *a, **k: out.append(" ".join(str(x) for x in a)))
    exec(compile(code, "<self_organize block>", "exec"), ns)
    return out


# -- the DN / CORP re-alignment, run on the reproduction case
dn_src = block("_keep = [_i0 for _i0", "# SAY SO HERE.")
ns = dict(CORP=[b"x" * 1880, b"y" * 84000], DN=["eng", "py"])
printed = run_block(dn_src, ns)
check(ns["DN"] == ["py"] and ns["NP"] == 1 and len(ns["CORP"]) == 1,
      f"DN block executes: DN={ns['DN']} NP={ns['NP']} -- the surviving corpus keeps its own name")
check(any("DROPPED" in l and "eng" in l for l in printed),
      f"...and it names the dropped domain in the log: {printed[0][:78] if printed else '(nothing printed)'}")
ns2 = dict(CORP=[b"x" * 90000, b"y" * 84000], DN=["eng", "py"])
p2 = run_block(dn_src, ns2)
check(ns2["DN"] == ["eng", "py"] and ns2["NP"] == 2 and not p2,
      "...and it is a silent no-op when nothing is under the floor")

# -- the exposure guard, run on the case that motivated it
# END THE BLOCK AT THE NEXT BANNER, AND LET IT BREAK LOUDLY WHEN ONE IS INSERTED. This ended at
# "# TWO WRITE PATHS" until a capacity-gate warning was added between the two, at which point this test
# started exec'ing code it was never written for and died on a NameError from it. That is the right
# failure: a brittle anchor that reports on the WRONG text is far worse than one that stops. Both this
# test and resume_test.py have now caught an anchor drift this way, which is the argument for anchoring
# on distinctive banner comments rather than on ordinary lines.
exp_src = block('if DATA_MODE == "real" and NP > 1:',
                "    # WIDENING THE FABRIC MOVES THE CAPACITY GATE")
for eng_mb, py_mb, want_warns in ((60, 60, 0), (60, 30, 0), (60, 8, 2), (60, 1, 3)):
    ns = dict(
        DATA_MODE="real", NP=2, DN=["eng", "py"], PHASED=True, PHASE_SCHED=[[0], [0], [1], [1]],
        STREAM_LEN=4_000_000, EPOCHS=8, _warn=[],
        SEG_LEN=[int(eng_mb * 1e6 * 0.95), int(py_mb * 1e6 * 0.95)],
        _f=lambda k, d: d,
    )
    printed = run_block(exp_src, ns)
    check(len(ns["_warn"]) == want_warns,
          f"exposure block on eng {eng_mb} + py {py_mb} MB: {len(ns['_warn'])} warning(s), want {want_warns}")
    check(len(printed) == 1 + 2,
          f"...and it prints the exposure table for every run: {len(printed)} lines (1 header + 2 corpora)")
    if want_warns:
        check(all(isinstance(w, str) and w for w in ns["_warn"]),
              f"...and every warning is a formatted string: {ns['_warn'][0][:70]}...")

# The stationary and single-corpus paths must not trip over the new code either.
ns = dict(DATA_MODE="real", NP=2, DN=["eng", "py"], PHASED=False, PHASE_SCHED=[[0], [1]],
          STREAM_LEN=4_000_000, EPOCHS=8, _warn=[], SEG_LEN=[57_000_000, 57_000_000], _f=lambda k, d: d)
run_block(exp_src, ns)
check(ns["_warn"] == [], "PHASED=0 with matched corpora: the block runs and says nothing")
ns = dict(DATA_MODE="real", NP=1, DN=["eng"], PHASED=True, PHASE_SCHED=[[0]] * 4,
          STREAM_LEN=4_000_000, EPOCHS=8, _warn=[], SEG_LEN=[57_000_000], _f=lambda k, d: d)
out = run_block(exp_src, ns)
check(ns["_warn"] == [] and out == [], "NP=1: the block is skipped entirely, as its guard says")

# -- IS THE HELD-OUT TAIL A SAMPLE OR A BLOCK? Run on the actual source, because this warning decides whether
# every held-out number in the report is about the corpus or about its last few documents, and it reads a file
# on disk -- which means it has three outcomes (shuffled / arrival-order / no manifest) and a run only ever
# exercises one of them.
print("\nTHE HELD-OUT TAIL SAYS WHETHER IT IS A SAMPLE")
import json as _json, os as _os, tempfile

tail_src = block("    _unshuf = []", "    if USE_TOK:")


def _corpus(tmp, name, manifest):
    d = _os.path.join(tmp, "train", name)
    _os.makedirs(d, exist_ok=True)
    if manifest is not None:
        with open(_os.path.join(d, "_fetch_manifest.json"), "w") as fh:
            _json.dump(manifest, fh)


def _tail(cases):
    tmp = tempfile.mkdtemp()
    for nm, man in cases:
        _corpus(tmp, nm, man)
    ns = dict(DN=[nm for nm, _ in cases], VAL_FRAC=0.05, os=_os, json=_json,
              _env=lambda k, d: tmp if k == "DATA_DIR" else d)
    return run_block(tail_src, ns), ns


_M = lambda buf, src: {"bytes": 1, "shard": 0, "docs": 1, "source": src, "shuffle_buffer": buf, "seed": 0}

out, ns = _tail([("eng", _M(10000, "HuggingFaceFW/fineweb-edu")), ("py", _M(10000, "bigcode/the-stack-dedup"))])
check(ns["_unshuf"] == [] and not out, "two shuffled corpora: nothing is said, because there is nothing to say")

out, ns = _tail([("eng", _M(10000, "HuggingFaceFW/fineweb-edu")), ("py", _M(0, "bigcode/the-stack-dedup"))])
check([n for n, _ in ns["_unshuf"]] == ["py"],
      f"one arrival-order corpus is named and the shuffled one is not: {[n for n, _ in ns['_unshuf']]}")
check(any("HELD-OUT TAIL IS A BLOCK" in l and "py" in l and "the-stack" in l for l in out),
      "...and the warning names the corpus AND the dataset it came from, which is what decides whether "
      "arrival order matters")
check(not any("eng" in l.split("for:")[-1] for l in out if "HELD-OUT TAIL" in l),
      "...and does not accuse the corpus that was shuffled")

# THE RUN THAT MOTIVATED THIS is the case where the manifest predates the field entirely.
out, ns = _tail([("py", {"bytes": 1, "shard": 0, "docs": 1, "source": "bigcode/the-stack-dedup"})])
check([n for n, _ in ns["_unshuf"]] == ["py"],
      "a manifest written before --shuffle-buffer existed counts as arrival order, which is what it was")

out, ns = _tail([("eng", None), ("py", None)])
check(ns["_unshuf"] == [] and not out,
      "no manifest at all says NOTHING -- an absent record is not evidence either way, and a corpus the "
      "harness built by hand must not be accused")

print()
if FAILED:
    print(f"corpus_test: {len(FAILED)} CHECK(S) FAILED")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
print("corpus_test: all checks passed")
