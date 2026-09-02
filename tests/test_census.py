"""The census, checked against the tree: every knob the old system had, landed somewhere on purpose.

    python3 tests/test_census.py             # PASS/FAIL per check with counts; non-zero exit on any FAIL

WHY THIS FILE EXISTS. .rework/census.json is the one record of what each of the old tree's 328
environment knobs BECAME -- kept, renamed, merged into another, promoted to a wire, or dropped. It was
written once, by reading the old source, and then thirteen packages were implemented from it by
different agents at different times. Nothing checked that the implementation and the census agreed, and
the two ways they can silently disagree are both defects this project has already shipped:

  A KNOB THAT VANISHED.  A census row says keep and no lever exists. The mechanism it controlled is
                         either gone or hardcoded, and nothing says which. The old tree's own history is
                         full of this shape -- a knob read at one site and silently defaulted at
                         another.
  A KNOB THAT SURVIVED A DROP.  A census row says drop, with a reason, and the lever is there anyway.
                         The reason is usually "this arm was never exercised" or "both branches were
                         wrong", so a surviving lever is a mechanism the analysis concluded should not
                         exist, still reachable from the environment.

Neither is visible from either side alone: the census is prose plus JSON and does not know what was
built, and the packages know what they declare and have never seen the census. This file is the join.

THE DEPARTURES TABLE IS A DECLARATION, NOT A DERIVATION. Nine places where the tree deliberately does
something other than what the census row says. Each is already argued at its own declaration in the
package that owns it; what this table adds is that the set is CLOSED. A tenth departure -- someone
renaming a lever, or quietly moving a wire's owner -- fails N1 or N2 with the census row it broke. And
N3 runs it backwards: a departure whose census row now agrees is STALE and must be deleted, so the table
cannot accumulate entries that once meant something.

Writing the reasons here rather than pointing at the package docstrings would duplicate them, and a
reason written twice can disagree with itself -- the SIG_WIN defect at the level of prose. Each entry
carries the file and line where the argument actually lives.

WHAT THIS FILE CANNOT CATCH:
  * whether the census itself is right. It was written by reading self_organize.py, and a knob it
    misread is misread here too. The `reason` prose on each census row is the evidence for that, and it
    is not machine-checkable.
  * whether a lever that exists is READ. A declared lever nothing consumes is armed-but-inert, the
    project's second-largest defect family, and only tests/test_ownership.py's O4 (declared-but-unread)
    and the eventual L2 single-reader sweep speak to it.
  * whether a DROPPED mechanism's code is gone. N4 proves the environment name is gone. Code that still
    runs the dropped branch on a hardcoded constant would pass every check here.
"""
import importlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

CENSUS = os.path.join(ROOT, ".rework", "census.json")
PACKAGES = ("fabric", "memory", "domains", "sig", "tok", "lm", "eval",
            "data", "opt", "world", "capacity", "ckpt", "train")
MAX_SHOWN = 12


def _report(tag, title, ok, detail, findings, vacuous=False):
    """One check's verdict. The size of the examined population is always printed: a green tick over an
    empty set is this project's most repeated defect, and the only honest way to report one is to say
    how big the set was."""
    mark = "PASS" if ok else "FAIL"
    note = "  (VACUOUS: 0 examined)" if vacuous else ""
    print(f"{mark}  {tag}  {title}{note}")
    print(f"      {detail}")
    for f in findings[:MAX_SHOWN]:
        print(f"      - {f}")
    if len(findings) > MAX_SHOWN:
        print(f"      ... and {len(findings) - MAX_SHOWN} more")
    return 0 if ok else 1


# ==================================================================================================
# The declared departures
# ==================================================================================================
#
# Keyed by (family, old_name) -- the census row's own identity, which does not move when the tree
# renames things. `lands` is what the tree actually built: an environment name, a "PKG.d_field" wire, or
# None for "deliberately nothing". `where` is the file and line carrying the argument.

DEPARTURES = {
    ("fabric", "FAB_NMAX"): dict(
        census="FAB_NMAX", lands="FAB_SLOTS", where="src/fabric/levers.py:269-281",
        why="The field is `slots`, so the generated environment name is FAB_SLOTS. Not cosmetic and not "
            "reversible by preference: spine/assemble.py reads r['FAB'].slots in five couplings, "
            "spine/derive.py's cull_gate_open and operating_population are both written against that "
            "name, and tests/test_assemble.py's stand-in declares it. Declaring `nmax` instead makes "
            "build() raise 'FABLevers has no lever slots' at startup -- loud, but on every run."),
    ("capacity", "GROW_CAP_EVERY"): dict(
        census="CAP_PIN_STEPS", lands="CAP_PIN_WINDOWS", where="src/capacity/levers.py:60-108",
        why="A UNIT correction, not a rename. The threshold is compared against `step`, and the loop "
            "advances `step` once per WINDOW (`i += WIN; step += 1`, self_organize.py:6796 and :7708). "
            "Calling it _STEPS is the conflation that pinned the population for 43,645 real ticks while "
            "the clock read 2,650. THE SECOND HALF OF THAT NOTE IS NOW DONE AND THIS TEXT SAID "
            "OTHERWISE UNTIL 2026-09-02: it read 'derive.pin_tick still accumulates a Steps clock, so "
            "the port is not finished', which has been false since the 2026-08-30 repair (Q-DERIVE-1) "
            "-- pin_tick accumulates Windows and raises UnitError on a Steps or a Flushes at both "
            "arguments, verified by calling it. N3 checks that a departure still LANDS, not that its "
            "prose is current, so this file was green while asserting an unfinished port, which is the "
            "prose-that-lies-under-a-green-check shape this repository has 60 records of. WHAT REMAINS "
            "TRUE, and is why the departure itself stands: the tree lands CAP_PIN_WINDOWS where the "
            "census says CAP_PIN_STEPS, and applying BOTH legal repairs at once -- re-typing the clock "
            "AND converting the threshold -- would fire the valve 16x too EARLY. That can no longer "
            "happen silently, because Windows >= Flushes raises."),
    ("fabric", "FAB_NORM_ONLY"): dict(
        census="FAB_MODE", lands="FAB_NORM_ONLY", where="src/fabric/levers.py:68-74, :155-163",
        why="The census merges this into a three-valued FAB_MODE, and no row in the census creates the "
            "third value -- the FABRIC row it names produces the two-valued FAB_ON instead. Minting a "
            "three-valued enum with one unreachable value is an armed-but-inert branch by construction, "
            "so the boolean stands until a row exists that needs the third."),
    ("fabric", "ROUTE_LEARN"): dict(
        census="FAB_ROUTE_IDENT_W", lands="FAB_ROUTE_LEARN", where="src/fabric/levers.py:68-74, :325",
        why="The census merges the flag into a WEIGHT, which is the better design and needs the "
            "identity term's scale to be a real number somewhere in the mechanism. It is not, yet: the "
            "term is added or not added. Shipping FAB_ROUTE_IDENT_W now would be a lever whose "
            "intermediate values do nothing -- a knob that reads continuous and behaves boolean, which "
            "is the wrong-measurement family."),
    ("misc", "WRONG_SWEEP"): dict(
        census="MEM_SWEEP", lands="MEM_WRONG_SWEEP", where="src/memory/levers.py:27, :62-63, :412",
        why="The census's MEM_SWEEP is a POLICY knob folding several wrong-entry behaviours together. "
            "The fold's other inputs were dropped (WRONG_MARGIN, WRONG_MIN_N, WRONG_THRESH), so what is "
            "left to merge is one flag, and a policy enum with one input is that flag under a name that "
            "claims more. memory/levers.py:62-63 is the record that the policy knob was intended."),
    ("domains", "MAX_DOMAINS"): dict(
        census="FAB.d_expert_slots", lands="DOM.d_expert_slots", where="spine/assemble.py, DOM row",
        why="The census row's new_owner FIELD says FAB and its own REASON text says the opposite -- 'it "
            "lands on DOM as d_expert_slots and on MEM as d_src_hint' (CENSUS.md:208). The reason is "
            "right and the field is a slip: FAB is the SOURCE (it owns `slots`); a wire whose src and "
            "dst were both FAB would book no edge and constrain nothing. The tree follows the reason, "
            "and lands the second half on MEM as d_source_slots -- named for what memory/levers.py:69 "
            "declares it expects, not the reason's d_src_hint."),
    ("tokenizer", "TOKENIZER_PATH"): dict(
        census="CKPT.d_vocab_path", lands="TOK.d_vocab_save_path + TOK.d_vocab_read_path",
        where="src/ckpt/levers.py:84-97",
        why="TWO fields, not one, and on the RECEIVER rather than the source. The promote exists "
            "because TOKENIZER_PATH had two jobs -- the file a resume reads its parent's vocabulary "
            "from, and the file this run saves its own to -- and conflating them made a run overwrite "
            "its parent's vocabulary. A single d_vocab_path re-conflates exactly what the promote "
            "separates. CKPT is the source of both (dir and resume); TOK is what consumes them."),
    ("encoder", "SIG_WIN"): dict(
        census="SIG.d_signature_width_bytes", lands=None,
        where="spine/assemble.py, 'considered and rejected'",
        why="NOT RESOLVABLE AT ASSEMBLE, so honoured by derive-and-keep instead of by a wire. The width "
            "is max(WIN, int(WIN * bytes_per_token)) and bytes_per_token is MEASURED on a corpus the "
            "tokenizer has not seen when build() returns and freezes every Config. A late wire would "
            "mean a Config writable after startup, which is a Config no report can claim the run used. "
            "derive.signature_width_bytes is the single named function; sig calls it once and keeps the "
            "answer. Recorded rather than dropped because a promote-to-wire that quietly became nothing "
            "is indistinguishable from one nobody noticed."),
    ("misc", "EVAL_GIST"): dict(
        census="SIG.d_eval_gist", lands=None,
        where="spine/assemble.py, 'considered and rejected'",
        why="Same reason as SIG_WIN, one layer up: EVAL_GIST was never a lever, it SELECTED between two "
            "constructions of a value SIG owns, and both branches were wrong -- at the shipped default "
            "_eval_sig built the eval signature from the last max(1, SIG_WIN) = ONE byte while training "
            "encoded >= 256, and set to 0 it returned an all-zero gist that ranks the population "
            "identically for every window. The replacement is one signature whose width is resolved "
            "once, which is the row above, which is not a wire."),
}


# ==================================================================================================
# The declared name collisions with the repository root
# ==================================================================================================
#
# Each value says WHY the src/ package still wins, because that is the thing N5 re-measures. "It works"
# is not a reason; a reason names the mechanism that can stop being true.

KNOWN_SHADOWS = {
    "memory": "The old tree's ./memory.py, which self_organize.py still imports by that name, so it "
              "cannot be moved without breaking the only system that has ever produced a result. What "
              "keeps src/memory/ winning is ORDERING and nothing else: every entry point in this tree "
              "does sys.path.insert(0, <root>/src) before importing, putting src ahead of the root. "
              "`PYTHONPATH=src python3` from the root does the OPPOSITE -- PYTHONPATH lands after the "
              "script's own directory -- and returns the legacy module.",
    "data":   "The tracked corpus directory ./data/, which the owner ruled is input and stays. It has "
              "no __init__.py, so it is a NAMESPACE package, and a regular package anywhere on the path "
              "outranks a namespace package found earlier -- src/data/__init__.py wins on package kind "
              "rather than on ordering. Adding an __init__.py to ./data/ reverses that silently.",
}


# ==================================================================================================
# Loading
# ==================================================================================================

def _census():
    with open(CENSUS) as fh:
        return json.load(fh)


def _implemented():
    """Every environment name the thirteen packages generate, and every d_ wire field the table lands."""
    for p in PACKAGES:
        importlib.import_module(f"{p}.levers")
    from spine.registry import all_sets
    from spine.assemble import COUPLINGS
    names = set()
    for cls in all_sets().values():
        names |= set(cls.env_names())
    return names, {c.dst for c in COUPLINGS}


def _expected_env(entry):
    """The environment name a kept/renamed/merged census row implies.

    The census writes `new_name` inconsistently -- sometimes the full environment name
    (FAB_BIRTH_JITTER), sometimes the FIELD (`sustain`) with the owner in `new_owner`. Both mean the
    same thing because spine/lever.py GENERATES the environment name as PREFIX_FIELD; normalising here
    rather than editing the census keeps the census as the artifact it was written as.
    """
    nn, owner = entry.get("new_name"), entry.get("new_owner")
    if not nn or not owner:
        return None
    if nn.startswith("d_") or "." in nn:
        return None                                   # a wire, not an environment name
    return nn if nn.startswith(f"{owner}_") and nn == nn.upper() else f"{owner}_{nn.upper()}"


def _rows():
    """Every census entry as (family, old_name, verdict, entry)."""
    return [(g["family"], e["old_name"], e.get("verdict", "?"), e)
            for g in _census() for e in g["entries"]]


# ==================================================================================================
# The checks
# ==================================================================================================

def check_n1_every_kept_knob_landed(rows, env_names, wire_dsts):
    """N1 -- a census row that says keep, rename, merge or AMEND has a lever, or a declared departure.

    `amend` is not one of the census's five original verdicts. It marks a lever minted AFTER the census
    was written, under a FOR THE OWNER ruling, which has no old-tree ancestor and therefore no
    (family, old_name) key a DEPARTURES entry could be written under -- the amendments group in
    census.json exists so N2 can account for such a lever at all. It is checked HERE rather than left to
    N2 alone because N2 only runs one direction: it asks whether every declared lever has a reason
    written down, and an amendment row whose lever was later deleted would sit in the census asserting
    a knob that no longer exists, which is the "knob that vanished" defect this file's docstring opens
    with, arriving through the one door that was not watched. Including `amend` makes the amendment
    load-bearing in both directions; it widens what N1 examines and narrows nothing.
    """
    findings, n = [], 0
    for fam, old, verdict, e in rows:
        if verdict not in ("keep", "rename", "merge", "amend"):
            continue
        n += 1
        dep = DEPARTURES.get((fam, old))
        if dep is not None:
            continue                                  # N3 checks the departure is still real
        want = _expected_env(e)
        if want is None:
            findings.append(f"{fam}/{old}: verdict {verdict!r} but the row names no owner+new_name, so "
                            f"nothing says what should exist. Fix the census row or record a departure.")
        elif want not in env_names:
            findings.append(f"{fam}/{old}: census says {verdict} as {want}, and no package declares it. "
                            f"Either the mechanism is gone, or it is hardcoded, or the lever was named "
                            f"something else and the rename is undeclared.")
    return _report("N1", "every kept, renamed, merged or amended knob has a lever or a declared "
                         "departure",
                   not findings, f"{n} kept/renamed/merged/amended row(s) of {len(rows)}; "
                                 f"{len(DEPARTURES)} declared departure(s)", findings, vacuous=not n)


def check_n2_every_lever_traces_back(rows, env_names, wire_dsts):
    """N2 -- the other direction: a lever nobody's census row asked for.

    An invented lever is not automatically wrong, but it is a knob whose reason for existing was never
    written down, which is how a tree accumulates settings no one can explain. Declaring it as a
    departure is one line and forces the reason to exist.
    """
    accounted = set()
    for fam, old, verdict, e in rows:
        dep = DEPARTURES.get((fam, old))
        if dep is not None and dep["lands"]:
            for piece in dep["lands"].split(" + "):
                accounted.add(piece.strip())
            continue
        want = _expected_env(e)
        if want:
            accounted.add(want)
    orphans = sorted(n for n in env_names if n not in accounted)
    findings = [f"{n}: declared by a package, and no census row and no declared departure produces it. "
                f"Its reason for existing is not written anywhere this check can reach." for n in orphans]
    return _report("N2", "every declared lever traces back to a census row or a declared departure",
                   not findings, f"{len(env_names)} declared lever(s) against {len(accounted)} name(s) "
                                 f"the census and the departures account for", findings,
                   vacuous=not env_names)


def check_n3_departures_are_live(rows, env_names, wire_dsts):
    """N3 -- run the departures table backwards: every entry must still be a departure, and must land.

    Without this the table is write-only. A departure whose census row was later corrected, or whose
    lever was later renamed to match, would sit here forever asserting a difference that no longer
    exists -- and the next reader would take it as current.
    """
    findings = []
    by_key = {(f, o): (v, e) for f, o, v, e in rows}
    for key, dep in sorted(DEPARTURES.items()):
        fam, old = key
        if key not in by_key:
            findings.append(f"{fam}/{old}: no census row with this identity. The row was renamed or "
                            f"removed, and this entry now documents a difference from nothing.")
            continue
        verdict, e = by_key[key]
        want = _expected_env(e)
        lands = dep["lands"]
        if lands is None:
            if want and want in env_names:
                findings.append(f"{fam}/{old}: declared as landing NOTHING, but {want} exists. The "
                                f"lever was built after all; delete the entry.")
            continue
        for piece in [p.strip() for p in lands.split(" + ")]:
            if piece.startswith("d_") or "." in piece:
                if piece not in wire_dsts:
                    findings.append(f"{fam}/{old}: declared as landing the wire {piece}, and no row in "
                                    f"spine/assemble.py's table targets it.")
            elif piece not in env_names:
                findings.append(f"{fam}/{old}: declared as landing {piece}, and no package declares it.")
        if want and lands and want == lands:
            findings.append(f"{fam}/{old}: the census now says {want} and the tree lands {lands} -- "
                            f"they AGREE. This is no longer a departure; delete the entry.")
        if not dep.get("where") or not dep.get("why"):
            findings.append(f"{fam}/{old}: a departure with no `where` or no `why` is an undocumented "
                            f"rename wearing the table's authority.")
    return _report("N3", "every declared departure is still a departure, and still lands",
                   not findings, f"{len(DEPARTURES)} departure(s) re-checked against the census and the "
                                 f"tree", findings, vacuous=not DEPARTURES)


def check_n4_drops_actually_dropped(rows, env_names, wire_dsts):
    """N4 -- a knob the census dropped, with a reason, may not still be reachable from the environment.

    MATCHED EXACTLY, and the loose version is deleted rather than kept with exceptions. The first draft
    also stripped the old name's own first token, so a dropped CULL_MODE matched SIG_MODE and TOK_MODE
    and a dropped EXPERT_CULL_FRAC matched FAB_CULL_FRAC -- four findings, all four spurious, every one
    of them a legitimate lever with its own census row. A check that reports four false positives out of
    four is not a strict check, it is a check nobody will read; the next real resurrection arrives in a
    list already known to be noise. So the rule is the old name itself, or the old name under a package
    prefix.

    WHAT THAT GIVES UP, AND WHY IT COSTS NOTHING. A dropped knob resurrected under a genuinely different
    name is invisible here. It is not invisible to the file: it would have no census row producing it,
    so N2 reports it as a lever whose reason for existing is written nowhere. N4 is the narrow case N2
    cannot see -- a resurrection that ALSO acquired a census row, where provenance looks fine and the
    analysis that removed the mechanism has been quietly reversed.
    """
    findings, n = [], 0
    prefixes = {x.split("_", 1)[0] for x in env_names}
    for fam, old, verdict, e in rows:
        if verdict != "drop":
            continue
        n += 1
        candidates = {old} | {f"{p}_{old}" for p in prefixes}
        hits = sorted(candidates & env_names)
        if hits:
            findings.append(f"{fam}/{old}: census says DROP -- {(e.get('reason') or '')[:110]} -- and "
                            f"the tree declares {hits}.")
    return _report("N4", "every dropped knob is gone from the environment",
                   not findings, f"{n} dropped row(s) matched by exact name against "
                                 f"{len(env_names)} declared lever(s) under {len(prefixes)} prefix(es)",
                   findings, vacuous=not n)


def check_n5_the_shadowed_names_still_resolve_to_src(rows, env_names, wire_dsts):
    """N5 -- every name in src/ that also exists at the repository root still IMPORTS from src/.

    THIS IS A MEASURED FAULT, NOT A PRECAUTION, and it bit inside this session. The old system's files
    are still at the repository root, where two of them share a name with a package in src/. The natural
    way to run anything from the root is `PYTHONPATH=src python3 ...`, which puts the ROOT first on
    sys.path and src after it, so under that invocation `import memory` returns the legacy 654-line
    ./memory.py and not src/memory/ -- silently, with no error and the wrong module's globals.

    It failed loudly only by luck: the old file has no `levers` attribute, so `import memory.levers`
    raised "'memory' is not a package". A plain `import memory`, or an old file that happened to carry
    the attribute, succeeds and returns the wrong system. That is the silent-overwrite family arriving
    through the import system, where none of the ownership checks can see it -- O1 through O10 parse
    src/ and never ask which file a name actually resolves to.

    WHY THIS DOES NOT DEMAND THE FILES BE DELETED, which was the first draft and was wrong twice over.
    The old tree still runs -- it is the only thing that has ever produced a result, and self_organize.py
    imports `memory` by that name -- so moving the file to satisfy a test would break the running system
    to make a check green. And a check that fails for a condition nobody intends to fix teaches its
    reader to skip it, which costs more than it catches.

    SO THE CHECK IS THE MITIGATION, NOT THE COLLISION. The collision is declared below and is allowed to
    exist. What may not happen is the mitigation silently ceasing to work, so this actually IMPORTS each
    colliding name the way the tree's own entry points do -- src first on sys.path, which is what every
    file in tests/ does -- in a SUBPROCESS, because an import here would poison this process's
    sys.modules for the other checks, and asserts the resolved __file__ is under src/. src/data/ wins
    its collision today only because it is a regular package and the root data/ is a namespace package;
    that is a language rule and not a boundary anyone declared, and this check is what notices the day
    an __init__.py appears in the root data/ and reverses it.

    AN UNDECLARED collision still fails outright: a NEW root file shadowing a package is not the old
    tree's residue, it is someone adding one.
    """
    src = os.path.join(ROOT, "src")
    pkgs = sorted(d for d in os.listdir(src) if os.path.isdir(os.path.join(src, d))
                  and not d.startswith("_"))
    collide = [p for p in pkgs
               if os.path.isfile(os.path.join(ROOT, p + ".py")) or os.path.isdir(os.path.join(ROOT, p))]
    findings = []
    for p in collide:
        if p not in KNOWN_SHADOWS:
            what = "./%s.py" % p if os.path.isfile(os.path.join(ROOT, p + ".py")) else "./%s/" % p
            findings.append(f"{what} shadows src/{p}/ and is not in KNOWN_SHADOWS. A root file sharing "
                            f"a package name is not the old tree's residue -- it is a new one. Either "
                            f"rename it or declare it here with what keeps it from resolving first.")
    probe = ("import sys, os, json; sys.path.insert(0, %r); "
             "import importlib; m = importlib.import_module(%s); "
             "print(getattr(m, '__file__', None) or list(m.__path__)[0])")
    for p in sorted(set(collide) & set(KNOWN_SHADOWS)):
        r = subprocess.run([sys.executable, "-c", probe % (src, repr(p))],
                           capture_output=True, text=True, cwd=ROOT)
        got = (r.stdout or "").strip().splitlines()[-1] if r.stdout.strip() else ""
        if r.returncode != 0 or not got:
            findings.append(f"src/{p}/ could not be imported with src first on sys.path, which is how "
                            f"every entry point in this tree imports it: "
                            f"{(r.stderr or '').strip().splitlines()[-1:] or ['no output']}")
        elif not os.path.abspath(got).startswith(src + os.sep):
            findings.append(f"`import {p}` with src FIRST on sys.path resolved to {got}, not to src/. "
                            f"{KNOWN_SHADOWS[p]} -- that no longer holds, and every module importing "
                            f"{p!r} is now reading the other one.")
    return _report("N5", "the names src/ shares with the repository root still import from src/",
                   not findings,
                   f"{len(pkgs)} package(s) in src/; {len(collide)} collide with the root "
                   f"({', '.join(collide) or 'none'}), {len(KNOWN_SHADOWS)} declared; each imported in "
                   f"a subprocess with src first", findings, vacuous=not pkgs)


# ==================================================================================================
# The meta-test
# ==================================================================================================

def selftest():
    """SELF -- each check must FAIL on a tree that has the defect it names, and PASS on one that does not.

    Five checks came up green the first time they ran end to end. That is the moment this repository's
    history says to distrust: the survey counts sixty guards whose condition could not be satisfied, one
    of them introduced into tests/test_ownership.py's O4 by the patch that was fixing O4. A check nobody
    has seen fail is a check nobody has tested.

    N1-N4 take their whole world as arguments, so tripping them is a matter of handing them a perturbed
    world -- no temp tree, no imports, no state to leak. N5 reads the filesystem and is tripped in a
    temp directory. Output is captured because a self-test that prints five FAIL blocks in the middle of
    a passing run is indistinguishable from a run that failed.
    """
    import contextlib
    import io
    import shutil
    import tempfile

    rows = _rows()
    env, dsts = _implemented()
    cases, bad = [], []

    def run(check, *a):
        with contextlib.redirect_stdout(io.StringIO()):
            return check(*a)

    def case(name, expect_fail, check, *a):
        rc = run(check, *a)
        cases.append(name)
        if bool(rc) != expect_fail:
            bad.append(f"{name}: expected {'FAIL' if expect_fail else 'PASS'}, got "
                       f"{'FAIL' if rc else 'PASS'}")

    # --- the baseline. Without this the four below prove only that the checks can say FAIL. ---
    for tag, ck in (("N1", check_n1_every_kept_knob_landed),
                    ("N2", check_n2_every_lever_traces_back),
                    ("N3", check_n3_departures_are_live),
                    ("N4", check_n4_drops_actually_dropped)):
        case(f"{tag} passes on the real tree", False, ck, rows, env, dsts)

    # --- N1: a kept knob whose lever was deleted. FAB_ALPHA stands for any of the 281. ---
    victim = sorted(n for n in env if n.startswith("FAB_"))[0]
    case("N1 catches a kept knob with no lever", True,
         check_n1_every_kept_knob_landed, rows, env - {victim}, dsts)

    # --- N2: a lever nobody's census row asked for. ---
    case("N2 catches a lever with no census row", True,
         check_n2_every_lever_traces_back, rows, env | {"FAB_INVENTED"}, dsts)

    # --- N3, both directions. A departure pointing at a census row that is gone, and one whose census
    #     row has come to AGREE with the tree -- the stale entry that would otherwise sit here forever.
    saved = dict(DEPARTURES)
    try:
        DEPARTURES[("nosuchfamily", "NOSUCHKNOB")] = dict(
            census="X", lands="FAB_SLOTS", where="nowhere", why="a departure from nothing")
        case("N3 catches a departure whose census row does not exist", True,
             check_n3_departures_are_live, rows, env, dsts)
        DEPARTURES.clear(); DEPARTURES.update(saved)
        # FAB_NMAX's row says FAB_NMAX and the tree lands FAB_SLOTS. Rewrite the entry to claim it lands
        # FAB_NMAX -- now census and tree agree and the entry is describing a difference that is not
        # there. It must be reported as stale rather than silently satisfied.
        DEPARTURES[("fabric", "FAB_NMAX")] = dict(saved[("fabric", "FAB_NMAX")], lands="FAB_NMAX")
        case("N3 catches a departure that no longer departs", True,
             check_n3_departures_are_live, rows, env | {"FAB_NMAX"}, dsts)
        DEPARTURES.clear(); DEPARTURES.update(saved)
        # A departure with no argument behind it.
        DEPARTURES[("fabric", "FAB_NMAX")] = dict(saved[("fabric", "FAB_NMAX")], why="")
        case("N3 catches a departure with no recorded reason", True,
             check_n3_departures_are_live, rows, env, dsts)
    finally:
        DEPARTURES.clear(); DEPARTURES.update(saved)

    # --- N4: a dropped knob back in the environment, both spellings the check matches. ---
    case("N4 catches a dropped knob resurrected bare", True,
         check_n4_drops_actually_dropped, rows, env | {"CHAIN_BAN"}, dsts)
    case("N4 catches a dropped knob resurrected under a prefix", True,
         check_n4_drops_actually_dropped, rows, env | {"FAB_CHAIN_BAN"}, dsts)
    # And the case the loose first draft got wrong: a legitimate lever that merely ENDS like a dropped
    # one must not be reported. SIG_MODE against the dropped CULL_MODE was one of four false positives.
    case("N4 does not fire on a lever that merely ends like a dropped one", False,
         check_n4_drops_actually_dropped, rows, env, dsts)

    # --- N6: two rows under one identity. It happened with the two census amendments, and N3's
    # --- lookup silently kept the last, so this case is a regression test for a live defect.
    _dup = rows + [("amendments", "(amendment: OPT_GRAD_CLIP)", "amend",
                    {"new_name": "OPT_SOMETHING_ELSE", "new_owner": "OPT"})]
    case("N6 catches two rows sharing one identity", True,
         check_n6_row_identity_is_unique, _dup, env, dsts)
    case("N6 passes on the real census", False, check_n6_row_identity_is_unique, rows, env, dsts)

    # --- N5: the mitigation actually failing, in a temp tree, in both of its two forms. ---
    tmp = tempfile.mkdtemp(prefix="n5probe-")
    try:
        global ROOT
        real_root = ROOT
        os.makedirs(os.path.join(tmp, "src", "memory"))
        os.makedirs(os.path.join(tmp, "src", "data"))
        for pkg in ("memory", "data"):
            open(os.path.join(tmp, "src", pkg, "__init__.py"), "w").close()
        try:
            ROOT = tmp
            case("N5 passes when src/ wins both collisions", False,
                 check_n5_the_shadowed_names_still_resolve_to_src, rows, env, dsts)
            # form one: a root .py that wins because it is found first. Written to shadow `memory` the
            # way ./memory.py does, and the subprocess puts src first, so this must still PASS -- the
            # ordering mitigation is doing its job. The FAILING form is the one below.
            with open(os.path.join(tmp, "memory.py"), "w") as fh:
                fh.write("LEGACY = True\n")
            case("N5 passes with the root file present but src first", False,
                 check_n5_the_shadowed_names_still_resolve_to_src, rows, env, dsts)
            # form two: the mitigation defeated WITH THE PACKAGE STILL THERE, which is the whole point
            # and is not obvious. Deleting src/memory/ was the first version of this case and it PASSED,
            # correctly: with no package in src/ there is no collision to lose. The real failure is
            # subtler -- drop src/memory/__init__.py and it becomes a NAMESPACE package, and a regular
            # module found LATER on the path outranks a namespace package found earlier, so `import
            # memory` returns the root file even though src is first. Measured, not assumed:
            #   src/memory/ without __init__.py, root memory.py  ->  /tmp/.../memory.py
            #   src/memory/ with    __init__.py, root memory.py  ->  /tmp/.../src/memory/__init__.py
            # It is the same mechanism KNOWN_SHADOWS["data"] names, running the other way, and it is
            # what N5 exists to notice: one deleted file and every `import memory` in the tree silently
            # reads the old system.
            os.remove(os.path.join(tmp, "src", "memory", "__init__.py"))
            case("N5 catches src losing the collision while the package is still there", True,
                 check_n5_the_shadowed_names_still_resolve_to_src, rows, env, dsts)
            open(os.path.join(tmp, "src", "memory", "__init__.py"), "w").close()
            # form three: a NEW root name shadowing a package, which is not the old tree's residue and
            # is not in KNOWN_SHADOWS.
            os.makedirs(os.path.join(tmp, "src", "fabric"))
            open(os.path.join(tmp, "src", "fabric", "__init__.py"), "w").close()
            open(os.path.join(tmp, "fabric.py"), "w").close()
            case("N5 catches an undeclared new root file shadowing a package", True,
                 check_n5_the_shadowed_names_still_resolve_to_src, rows, env, dsts)
        finally:
            ROOT = real_root
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return _report("SELF", "each check fails on a tree with its defect, and passes on one without",
                   not bad, f"{len(cases)} case(s) against perturbed inputs and a temp tree",
                   bad, vacuous=not cases)



def check_n6_row_identity_is_unique(rows, env_names, wire_dsts):
    """N6 -- (family, old_name) identifies exactly one census row.

    THE WHOLE FILE KEYS ON THIS PAIR AND NOTHING CHECKED IT. `DEPARTURES` is keyed by it, N3 builds
    `by_key = {(f, o): (v, e) for ...}` from it, and a dict silently keeps the last write. So two rows
    sharing an identity means one of them is invisible to N3 -- not reported, not skipped, GONE.

    IT HAPPENED. The two census amendments (OPT_GRAD_CLIP, minted 2026-09-02, and MEM_JUDGE_FRAC) were
    both written with `old_name` = "(none -- amendment, not an old-tree knob)", which is a true
    sentence and a duplicate key. N3's lookup kept MEM_JUDGE_FRAC and dropped OPT_GRAD_CLIP entirely:
    a departure declared against OPT_GRAD_CLIP would have been reported as "no census row with this
    identity" while the row sat in census.json, and a stale one would never have been reported at all.
    Each amendment now carries "(amendment: <NAME>)".

    That is the shape this file's own N3 exists to prevent one level up -- a table that silently stops
    describing what it indexes -- reproduced in the index itself. An amendment has no ancestor knob, so
    the honest `old_name` is a sentence rather than a name, and the moment there were two of them the
    sentence stopped being an identity. The general rule is the check: whatever an amendment's
    old_name says, it has to be UNIQUE, because the rest of the file treats it as a key.

    WHAT IT CANNOT CATCH: two rows that are genuinely the same knob written twice under different
    names. This asks whether the index is injective, not whether the census is right.
    """
    import collections as _c
    seen = _c.Counter((f, o) for f, o, _v, _e in rows)
    findings = []
    for (fam, old), n in sorted(seen.items()):
        if n > 1:
            names = [e.get("new_name") for f, o, _v, e in rows if (f, o) == (fam, old)]
            findings.append(
                f"{fam}/{old!r} identifies {n} rows ({', '.join(repr(x) for x in names)}). DEPARTURES "
                f"is keyed by this pair and N3 builds a dict from it, so a dict keeps the last and the "
                f"rest are invisible -- not reported, GONE. Give each row its own old_name.")
    return _report("N6", "(family, old_name) identifies exactly one census row", not findings,
                   f"{len(rows)} row(s) against {len(seen)} distinct identit(y/ies)", findings,
                   vacuous=not rows)


CHECKS = (
    check_n1_every_kept_knob_landed,
    check_n2_every_lever_traces_back,
    check_n3_departures_are_live,
    check_n4_drops_actually_dropped,
    check_n5_the_shadowed_names_still_resolve_to_src,
    check_n6_row_identity_is_unique,
)


def main():
    rows = _rows()
    env_names, wire_dsts = _implemented()
    verdicts = {}
    for _, _, v, _e in rows:
        verdicts[v] = verdicts.get(v, 0) + 1
    print("=== the census against the tree ===")
    print(f"{len(rows)} census row(s) in {len(_census())} family group(s): "
          + ", ".join(f"{k} {n}" for k, n in sorted(verdicts.items())))
    print(f"{len(env_names)} declared lever(s), {len(wire_dsts)} wire target(s), "
          f"{len(DEPARTURES)} declared departure(s); Python {sys.version.split()[0]}")
    print()
    failed = 0
    for check in CHECKS:
        failed += check(rows, env_names, wire_dsts)
        print()
    failed += selftest()
    print()
    print(f"=== {len(CHECKS)} checks + the self-test, {failed} failing ===")
    print("These checks prove the tree and the census AGREE about what exists. They are not evidence")
    print("that the census is right -- it was written by reading self_organize.py, and a knob it misread")
    print("is misread here too -- nor that a lever which exists is ever READ. A declared lever nothing")
    print("consumes is armed-but-inert, the second-largest defect family in the survey, and only")
    print("test_ownership.py's O4 and the eventual L2 single-reader sweep speak to that.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
