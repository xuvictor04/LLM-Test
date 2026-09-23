"""TOK PERSISTENCE ACROSS A RESUME -- the four things a checkpoint must carry for a resumed run to be
the SAME run, each driven through the real entry points (build_vocabulary, save_vocabulary,
vocab_state, restore_vocab, on_window, mint_burst) on a synthetic corpus, with no model and no loop.

    python3 tests/test_tok_persist.py        # exit 0 = every check passed

WHY IT EXISTS (Q-TOK-13, docs/04_CONTRACT.md). FOUR DEFECTS were measured on 2026-09-23 -- the three
that ruling covers plus the stale cadence note -- and none of them was visible to any other test,
because nothing here saved and replayed a vocabulary:

  P1  THE WIDTH. The replay arm re-measured bytes_per_token on the REPLAYED vocabulary, which carries
      every token the parent minted online, so derive.signature_width_bytes moved and SIG refused
      the resume ("written at 192 and this run resolves 194") on every default run past its first
      mint burst. The file's recorded value must win, a file without the field must fall back to a
      measurement on the parent's BUILD-TIME vocabulary, and the reconciliation must fire when the
      build sample moved.
  P2  THE RECONCILIATION KEYS. _replay_merges compared min_pair/max_tok/dropout/vmax and
      save_vocabulary wrote none of them, so tok.load_reconciled read 0 ("compared and agreed") on
      every resume. Each lever changed alone must read 1; an unchanged fixed-mode resume must read 0
      (the vmax trap: the fixed arm narrows vocab.ceiling); and a GRANDCHILD's reading must survive
      restore_vocab's counters.update, which used to overwrite it with the parent's.
  P3  THE TALLY. vocab_state saved len(vocab.pair) under "pair_digest" and restore_vocab read
      nothing, so a resumed run's first mint burst ranked on post-resume windows only (0 tokens
      minted against 6). The tally and tally_seen must round-trip EXACTLY, a damaged payload must be
      refused, and a checkpoint that predates the field must leave tok.tally_restored ABSENT.
  P4  THE CADENCE NOTE. vocab_state wrote "TOK.on_window is a P4 stub ... no cadence state to
      carry" beside counters that carried the cadence clocks. `fired` must name the clocks.

WHAT IT CANNOT SEE: whether a resumed LOOP feeds on_window the same windows the uninterrupted run
would have. It does not today -- the first post-resume window's ids differ from the uninterrupted
run's window at the same step -- and that is a stream-position property of the loop and DATA, not of
this package's state; P3 checks that TOK carries what it was given, exactly.
"""
import json
import os
import random
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import assemble, rng                                    # noqa: E402
from spine import derive                                           # noqa: E402
from spine import lever as _lever                                  # noqa: E402
from spine.lever import LeverError                                 # noqa: E402
from tok import api as t                                           # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def corpus(seed, n_words):
    """Deterministic word salad: enough repeated pairs for a build to mint real merges."""
    r = random.Random(seed)
    words = ["the", "vocabulary", "resume", "signature", "width", "tally", "merge", "pair",
             "token", "stream", "window", "burst", "centroid", "fabric", "memory", "cadence",
             "zq", "vx", "kj", "wp", "yf"]
    return " ".join(r.choice(words) for _ in range(n_words)).encode()


HEADS = {"a": corpus(1, 6000)}


def tok_cfg(**env):
    """TOK's frozen Config for one simulated PROCESS. The assembly latch is reopened first because
    each call here stands for a different run (parent, child, grandchild) -- the latch exists to
    stop a second source for a value inside ONE run, and this file needs one run per call."""
    _lever._reopen_assembly()
    cfgs, _w, _warn = assemble.build(environ={k: str(v) for k, v in env.items()})
    return cfgs["TOK"]


def build(tok):
    rng.reset_issued()
    return t.build_vocabulary(tok, area_heads=HEADS, seed=0, soft_cap=None)


def grow(vocab, k):
    """k online mints the way mint_burst makes them: a new id from two existing ids, with a pair."""
    made = 0
    for i in range(256, vocab.size()):
        for j in (101, 32, 115):
            if made >= k:
                return
            seq = bytes(vocab.id2bytes[i]) + bytes(vocab.id2bytes[j])
            if len(seq) <= vocab.max_bytes and seq not in vocab.seq2id:
                if vocab._add(seq, prov=("online", 1), pair=(i, j)) is not None:
                    made += 1


def main():
    work = tempfile.mkdtemp(prefix="tok_persist_")
    try:
        parent = os.path.join(work, "parent")

        # ---- P1: the width ------------------------------------------------------------------------
        tok_p = tok_cfg(CKPT_DIR=parent)
        v = build(tok_p)
        bpt0, v0 = v.bytes_per_token, v.v0
        grow(v, 12)
        check("P1 setup: the parent minted online after its build", v.size() > v0,
              f"size {v.size()} v0 {v0}")
        t.save_vocabulary(tok_p, v)
        state_p = t.vocab_state(tok_p, v)

        # THE DEFECT'S MECHANISM, SHOWN RATHER THAN ASSUMED: measuring on the grown vocabulary
        # gives a different number, which is what moved SIG's width.
        sample = b"".join(bytes(h)[:int(tok_p.build_bytes)] for h in HEADS.values())
        ids, _ = t._segment(v, sample)
        grown = derive.bytes_per_token(len(sample), len(ids))
        check("P1 control: the grown vocabulary measures a different bytes_per_token", grown != bpt0,
              f"build {bpt0!r} vs grown {grown!r}")

        tok_c = tok_cfg(CKPT_RESUME=parent, CKPT_DIR=os.path.join(work, "child"))
        c = build(tok_c)
        t.restore_vocab(tok_c, state_p, c)
        check("P1 the resume adopts the recorded bytes_per_token", c.bytes_per_token == bpt0,
              f"{c.bytes_per_token!r} vs recorded {bpt0!r}")
        check("P1 the width is the parent's", derive.signature_width_bytes(256, c.bytes_per_token)
              == derive.signature_width_bytes(256, bpt0))
        check("P1 tok.bpt_adopted = 1 and tok.bpt_mismatch = 0 (re-measured on the build-time "
              "vocabulary, agreed to the bit)",
              c.counters.get("tok.bpt_adopted") == 1 and c.counters.get("tok.bpt_mismatch") == 0,
              str({k: c.counters.get(k) for k in ("tok.bpt_adopted", "tok.bpt_mismatch")}))
        check("P1 the replayed vocabulary carries the online mints", c.size() == v.size())

        # A file that predates the field: the fallback measurement on the build-time vocabulary.
        old = os.path.join(work, "old")
        blob = json.load(open(parent + ".dyntok.json"))
        blob.pop("bytes_per_token")
        json.dump(blob, open(old + ".dyntok.json", "w"))
        o = build(tok_cfg(CKPT_RESUME=old, CKPT_DIR=os.path.join(work, "o")))
        check("P1 a file without the field: tok.bpt_adopted = 0 and the build-time value is "
              "re-derived", o.counters.get("tok.bpt_adopted") == 0 and o.bytes_per_token == bpt0
              and "tok.bpt_mismatch" not in o.counters, f"{o.bytes_per_token!r}")

        # The build sample moved across the resume: reported, recorded value still wins. 5000 and
        # not half the sample: this word salad halves into exactly half the tokens, so a half-length
        # sample measures the SAME ratio to the bit and would test nothing (measured 2026-09-23).
        m = build(tok_cfg(CKPT_RESUME=parent, CKPT_DIR=os.path.join(work, "m"),
                          TOK_BUILD_BYTES=5000))
        check("P1 a moved build sample fires tok.bpt_mismatch and keeps the recorded value",
              m.counters.get("tok.bpt_mismatch") == 1 and m.bytes_per_token == bpt0
              and "tok.bpt_mismatch_detail" in m.counters,
              str({k: m.counters.get(k) for k in ("tok.bpt_adopted", "tok.bpt_mismatch")}))

        # Fresh build: the replay rows are unreachable, so absent.
        check("P1 a fresh build carries no tok.bpt_* row",
              not any(k.startswith("tok.bpt_") for k in v.counters))

        # ---- P2: the reconciliation keys ------------------------------------------------------
        blob = json.load(open(parent + ".dyntok.json"))
        check("P2 save_vocabulary writes the four keys the replay compares",
              all(k in blob for k in ("min_pair", "max_tok", "dropout", "vmax")),
              str(sorted(k for k in blob if k != "entries")))
        base = dict(CKPT_RESUME=parent, CKPT_DIR=os.path.join(work, "r"))
        same = build(tok_cfg(**base))
        check("P2 unchanged levers read tok.load_reconciled = 0",
              same.counters.get("tok.load_reconciled") == 0)
        for env, key in ((dict(TOK_MIN_PAIR=7), "min_pair"),
                         (dict(TOK_MAX_BYTES=24), "max_tok"),
                         (dict(TOK_DROPOUT=0.1), "dropout"),
                         (dict(LM_VOCAB_SLOTS=8192), "vmax")):
            r = build(tok_cfg(**base, **env))
            det = r.counters.get("tok.load_reconciled_detail") or ()
            check(f"P2 {list(env)[0]} changed alone reads tok.load_reconciled = 1 naming {key}",
                  r.counters.get("tok.load_reconciled") == 1 and f"recorded {key}=" in det[0],
                  str(r.counters.get("tok.load_reconciled")))

        # An old file (no max_tok) is still checked through max_bytes.
        blob_old = json.load(open(parent + ".dyntok.json"))
        for k in ("min_pair", "max_tok", "dropout", "vmax"):
            blob_old.pop(k, None)
        json.dump(blob_old, open(old + ".dyntok.json", "w"))
        r = build(tok_cfg(CKPT_RESUME=old, CKPT_DIR=os.path.join(work, "o2"), TOK_MAX_BYTES=24))
        check("P2 a file written before the keys is checked for max_tok through max_bytes",
              r.counters.get("tok.load_reconciled") == 1)

        # The vmax trap: fixed mode narrows vocab.ceiling; an unchanged resume must still read 0.
        fixed = os.path.join(work, "fixed")
        tf = tok_cfg(CKPT_DIR=fixed, TOK_MODE="fixed")
        vf = build(tf)
        t.save_vocabulary(tf, vf)
        rf = build(tok_cfg(CKPT_RESUME=fixed, CKPT_DIR=os.path.join(work, "fr"), TOK_MODE="fixed"))
        check("P2 fixed mode, unchanged levers: tok.load_reconciled = 0 (vmax is the wire, not the "
              "narrowed ceiling)", rf.counters.get("tok.load_reconciled") == 0,
              str(rf.counters.get("tok.load_reconciled_detail")))

        # The grandchild: the child's own reading (0) must not overwrite the grandchild's (1).
        tok_c2 = tok_cfg(CKPT_RESUME=parent, CKPT_DIR=os.path.join(work, "child2"))
        c2 = build(tok_c2)
        t.restore_vocab(tok_c2, state_p, c2)
        t.save_vocabulary(tok_c2, c2)
        state_c2 = t.vocab_state(tok_c2, c2)
        check("P2 setup: the child's own state carries tok.load_reconciled = 0",
              state_c2["counters"].get("tok.load_reconciled") == 0)
        tok_g = tok_cfg(CKPT_RESUME=os.path.join(work, "child2"), CKPT_DIR=os.path.join(work, "g"),
                        TOK_MIN_PAIR=7)
        g = build(tok_g)
        t.restore_vocab(tok_g, state_c2, g)
        check("P2 a grandchild's reconciliation survives restore_vocab",
              g.counters.get("tok.load_reconciled") == 1
              and g.counters.get("tok.bpt_adopted") == 1 and g.bytes_per_token == bpt0,
              str(g.counters.get("tok.load_reconciled")))

        # ---- P3: the tally ------------------------------------------------------------------------
        tok_t = tok_cfg(CKPT_DIR=os.path.join(work, "tally"))
        vt = build(tok_t)
        seg = t._segment(vt, corpus(2, 3000))[0]
        for w in range(1, 6):
            t.on_window(tok_t, vt, seg[(w - 1) * 400:w * 400], step=w)
        vt.tally_seen = dict(list(vt.tally.items())[:5])
        check("P3 setup: the tally is filled", len(vt.tally) > 50, str(len(vt.tally)))
        st = t.vocab_state(tok_t, vt)
        t.save_vocabulary(tok_t, vt)
        rt = build(tok_cfg(CKPT_RESUME=os.path.join(work, "tally"), CKPT_DIR=os.path.join(work, "t2")))
        t.restore_vocab(tok_t, st, rt)
        check("P3 the tally round-trips exactly, in order",
              list(rt.tally.items()) == list(vt.tally.items()))
        check("P3 tally_seen round-trips exactly", rt.tally_seen == vt.tally_seen)
        check("P3 tok.tally_restored counts the pairs put back",
              rt.counters.get("tok.tally_restored") == len(vt.tally))
        check("P3 the payload no longer carries pair_digest", "pair_digest" not in st)

        bad = dict(st)
        bad["tally_sum"] = st["tally_sum"] + 1
        rb = build(tok_cfg(CKPT_RESUME=os.path.join(work, "tally"), CKPT_DIR=os.path.join(work, "t3")))
        try:
            t.restore_vocab(tok_t, bad, rb)
            check("P3 a damaged tally payload is refused", False, "no refusal")
        except LeverError:
            check("P3 a damaged tally payload is refused", True)

        pre = {k: v for k, v in st.items() if k not in ("tally", "tally_pairs", "tally_sum",
                                                        "tally_seen")}
        pre["counters"] = {k: v for k, v in st["counters"].items() if k != "tok.tally_restored"}
        ro = build(tok_cfg(CKPT_RESUME=os.path.join(work, "tally"), CKPT_DIR=os.path.join(work, "t4")))
        t.restore_vocab(tok_t, pre, ro)
        check("P3 a checkpoint that predates the field leaves tok.tally_restored ABSENT",
              "tok.tally_restored" not in ro.counters and len(ro.tally) == 0)

        # ---- P4: the cadence note -----------------------------------------------------------------
        check("P4 `fired` names the cadence clocks the counters carry",
              isinstance(st.get("fired"), dict) and "tok.mint_seeded_window" in st["fired"]
              and "fired_unbuilt_reason" not in st, str(st.get("fired")))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"\n{'FAILED' if FAILS else 'OK'}: {len(FAILS)} failing check(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
