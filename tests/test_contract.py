"""The CONTRACT: docs/04_CONTRACT.md, the frozen stubs and the composition root describe one system.

    python3 tests/test_contract.py      # PASS/FAIL per check with counts; non-zero exit on any FAIL

WHAT THIS FILE PROVES. Ten implementation agents will fill in ninety-odd bodies independently, and
the ONLY thing keeping their work compatible is that the signatures do not move. This file is the
thing that notices when one does. It also notices the two failures that the survey says are the most
expensive in this repository: a declared knob with no reader (57 armed-but-inert records) and a
declared wire that arrives nowhere (the mirror of the 60 untrippable guards).

    K1  every name docs/04_CONTRACT.md declares exists in the tree WITH THE SIGNATURE IT CLAIMS, and
        every public entry point in the tree is in the document. Both directions, because a document
        that is a subset of the tree is a document that stops mentioning things.
    K2  spine.compose imports and builds against the stubs, raising NOTHING BUT NotImplementedError,
        and the NotImplementedError comes FROM A STUB and not from a typo in the root. Run in a
        subprocess so an import that half-succeeds cannot poison this process.
    K3  no package imports another. This is tests/test_ownership.py's O10 and it already passes;
        it is restated here because the contract is the moment cross-package values become real, and
        a check that lives only in another file is a check this file's author is trusting.
    K4  every one of the declared levers is named `LEVERS READ:` by at least one stub, or appears in
        the document's UNCONSUMED table WITH A REASON. Nothing may be silently dropped.
    K5  every d_ field the coupling ledger declares is read by a stub IN ITS OWN PACKAGE, and no
        stub reads a d_ field no coupling declares.

    K15 a Gate's `reason` is the sentence an operator acts on -- it names a lever, spells its
        value, and says what that value made impossible -- and nothing has ever read one. It must
        name a lever that EXISTS, a value that lever CAN HOLD, a rendered value that is that
        lever's own, and no impossibility on a Gate the source declares reachable. The three
        things it refuses to check, and the twenty-five-commit sweep behind each refusal, are in
        its own block.

WHAT IT DOES NOT PROVE, and the list matters more than the checks. It says nothing about whether a
body, once written, does what its docstring says; nothing about whether the DID IT FIRE counter a
docstring names is ever incremented; and nothing about whether the levers a stub CLAIMS to read are
the ones it will read. `LEVERS READ:` is prose that passes a parser -- exactly the standing
objection to `why=` in spine/wire.py, and the same answer applies: it is checked for PRESENCE and
completeness here, and its truth is L2's single-reader sweep and L3's isolation sweep, neither of
which exists yet. A lever named in a docstring and never read by the body is invisible to this file.

THE SEAM. Two checks import from src/: K4 cross-checks its AST reading of the lever declarations
against spine.assemble.PACKAGES, and K5 cross-checks its AST reading of the coupling table against
spine.assemble.COUPLINGS. Re-typing either here would be a second validator with its own idea of the
rule -- which is how the old tree ended up with a report path and an audit path printing different
numbers for one quantity. On a SYNTHETIC tree (the self-test) the cross-check is skipped and said to
be skipped, because importing a temp directory's spine is not what is under test there.

    K13 every NUMBER THIS TREE'S PROSE WRITES ABOUT A COUNTABLE THING equals the number the tree
        actually holds, and no `### Q-` heading says a thing is ABSENT that the tree declares.
        Counts in prose have gone stale six times here; a prose check over English is a heuristic
        and this one prints both the shapes it searched for and the ones it did not.

VACUITY IS PRINTED. Every check reports the size of the population it examined, and selftest() trips
every one of them against synthetic trees in a temp directory. This repository has SIXTY untrippable
guards on record and one of them was written into tests/test_ownership.py by the patch that was
fixing tests/test_ownership.py. A check nobody has watched fail is indistinguishable from a check
that cannot fail. K13 goes one step further and FAILS when it finds nothing to check, because "no
claims found" and "no claims wrong" print the same way.
"""
import ast
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DOC = os.path.join(ROOT, "docs", "04_CONTRACT.md")

MAX_SHOWN = 25

# PREFIX -> package directory. Written out rather than discovered, for the same reason
# spine.compose.APIS is: a discovered map silently shrinks when a directory is renamed, and this
# table is half of what K1 compares. spine/compose.py holds the same map and K1 checks they agree.
PKG_DIR = {
    "CAP": "capacity", "CKPT": "ckpt", "DATA": "data", "DOM": "domains", "EVAL": "eval",
    "FAB": "fabric", "LM": "lm", "MEM": "memory", "OPT": "opt", "RUN": "train",
    "SIG": "sig", "TOK": "tok", "WORLD": "world",
}

COMPOSE_REL = os.path.join("spine", "compose.py")


def _report(tag, title, ok, detail, findings, vacuous=False):
    """One check's line, plus its findings. The population size is ALWAYS printed."""
    mark = "PASS" if ok else "FAIL"
    tail = "   (VACUOUS: nothing to examine)" if (ok and vacuous) else ""
    print(f"{mark}  {tag}  {title}")
    print(f"          {detail}{tail}")
    for f in findings[:MAX_SHOWN]:
        print(f"          - {f}")
    if len(findings) > MAX_SHOWN:
        print(f"          ... and {len(findings) - MAX_SHOWN} more")
    return 0 if ok else 1


# ==================================================================================================
# Reading the tree and the document
# ==================================================================================================

def api_signatures(src_dir):
    """{"PFX: name(args)"} for every public entry point in every <pkg>/api.py, plus the findings.

    Methods on a public class are included as "PFX: Class.method(args)": RunClock.advance and
    Retention.consider are entry points the loop calls, and a contract that named only module-level
    functions would leave the one site in the tree that increments a counter undeclared.

    A package DIRECTORY that exists with no api.py is a finding, not a skip: that is exactly the
    state "this package's contract was never written", and skipping it would make this whole check
    weaker the more of the contract is absent -- which is backwards. A package directory that does
    not exist at all is not this check's business, so that a partial tree (the self-test's, and any
    future tree assembled from a subset) is judged on what it contains rather than on what a
    hard-coded map says it ought to.
    """
    sigs, findings = {}, []
    for pfx, d in sorted(PKG_DIR.items()):
        pkg_root = os.path.join(src_dir, d)
        if not os.path.isdir(pkg_root):
            continue
        path = os.path.join(pkg_root, "api.py")
        if not os.path.isfile(path):
            findings.append(f"src/{d}/ exists and has no api.py, so {pfx} declares no public "
                            f"surface. A package with levers and no contract is a package ten "
                            f"agents cannot implement compatibly.")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        try:
            tree = ast.parse(text, filename=f"src/{d}/api.py")
        except SyntaxError as e:
            findings.append(f"src/{d}/api.py:{e.lineno} does not parse: {e.msg}")
            continue
        for n in tree.body:
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
                sigs[f"{pfx}: {n.name}({ast.unparse(n.args)})"] = (pfx, n.name, f"src/{d}/api.py")
            elif isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
                for m in n.body:
                    if isinstance(m, ast.FunctionDef) and not m.name.startswith("_"):
                        key = f"{pfx}: {n.name}.{m.name}({ast.unparse(m.args)})"
                        sigs[key] = (pfx, f"{n.name}.{m.name}", f"src/{d}/api.py")
    return sigs, findings


def doc_text(doc_path):
    if not os.path.isfile(doc_path):
        return None
    with open(doc_path, "r", encoding="utf-8") as fh:
        return fh.read()


def doc_signatures(text):
    """The lines of the ```contract fenced block: the document's normative signature list."""
    m = re.search(r"^```contract\s*$(.*?)^```\s*$", text or "", re.M | re.S)
    if not m:
        return None
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]


_UNCONSUMED_SECTION = re.compile(r"^#+\s*[^\n]*UNCONSUMED LEVERS[^\n]*$(.*?)(?=^#+\s|\Z)",
                                 re.M | re.S | re.I)


def doc_unconsumed(text):
    """{"PFX.field": reason} from the rows of the UNCONSUMED LEVERS SECTION only.

    SCOPED TO THE SECTION, not to every table in the document, and that is not tidiness. This
    document also carries a table of the nine wires the contract phase ADDED and a table of the
    candidates it REFUSED, and both have `PFX.d_field` in their first cell with a long reason beside
    it. A parser that read every table would let a wire's reason silently satisfy a LEVER's
    disposition -- a check passing because it found the wrong row.

    A row counts only when its FIRST cell is a backticked PFX.field AND the row carries prose past
    the name. A bare name with an empty reason is the placeholder this project's `why=` check exists
    to refuse, and it must not be able to satisfy K4 -- otherwise "drop a lever quietly" becomes
    "add its name to a table", which is the same silence with a heading over it.
    """
    m = _UNCONSUMED_SECTION.search(text or "")
    body = m.group(1) if m else ""
    out = {}
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        m = re.fullmatch(r"`([A-Z][A-Z0-9_]*)\.([a-z_][a-z0-9_]*)`", cells[0])
        if not m or m.group(2).startswith("d_"):
            continue                       # a d_ field is a WIRE; this table is about LEVERS
        reason = " ".join(cells[1:]).strip()
        if len(reason) < 40 or " " not in reason:
            continue
        out[f"{m.group(1)}.{m.group(2)}"] = reason
    return out


def declared_levers(src_dir):
    """{"PFX": {field, ...}} read out of <pkg>/levers.py by AST, plus findings.

    By AST rather than by import so this runs against a synthetic tree. The real tree is
    cross-checked against spine.assemble.PACKAGES by the caller.
    """
    out, findings = {}, []
    for pfx, d in sorted(PKG_DIR.items()):
        path = os.path.join(src_dir, d, "levers.py")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        try:
            tree = ast.parse(text, filename=f"src/{d}/levers.py")
        except SyntaxError as e:
            findings.append(f"src/{d}/levers.py:{e.lineno} does not parse: {e.msg}")
            continue
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            prefix = None
            for stmt in cls.body:
                if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and stmt.targets[0].id == "PREFIX"
                        and isinstance(stmt.value, ast.Constant)):
                    prefix = stmt.value.value
            if not isinstance(prefix, str):
                continue
            fields = set()
            for stmt in cls.body:
                if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and isinstance(stmt.value, ast.Call)
                        and getattr(stmt.value.func, "id", None) == "Lever"):
                    fields.add(stmt.targets[0].id)
            out.setdefault(prefix, set()).update(fields)
    return out, findings


_BLOCK = re.compile(r"^\s*(LEVERS READ|WIRES READ):\s*(.+?)"
                    r"(?=^\s*(?:LEVERS READ|WIRES READ|DID IT FIRE):)", re.M | re.S)


def _split_items(body):
    """A LEVERS/WIRES READ block, as the comma-separated items it is -- parentheticals kept whole.

    SPLITTING ON A BARE COMMA IS WRONG AND FAILED LOUDLY. Several entries carry a note:

        WIRES READ: d_manage_period (recorded on the report beside manage_every, so the WINDOW
                    cadence and the FLUSH cadence are one line apart)

    A bare split cuts inside that parenthesis, so the first item became "d_manage_period (recorded
    on the report beside manage_every" -- not an identifier, dropped. FAB.d_manage_period and
    FAB.d_cap_lift_period both vanished and K5 reported two wires nobody reads, on a tree where both
    are read at a real site three lines below the docstring. The check was right to fail and the
    oracle was wrong.

    So: depth-aware. Commas inside parentheses do not separate items, and the parenthetical is then
    stripped from the item -- including an UNCLOSED one, since the block can end mid-note.
    """
    items, buf, depth = [], [], 0
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    items.append("".join(buf))
    out = []
    for it in items:
        it = re.sub(r"\(.*", "", it, flags=re.S).strip().strip(".")
        out.append(it)
    return out


def stub_reads(src_dir):
    """{"PFX": ({levers named}, {wires named})} from the machine-readable docstring blocks.

    The blocks are terminated by the NEXT block header rather than by a blank line, so a lever list
    that wraps over several lines is read whole. A `LEVERS READ:` with no following `WIRES READ:` or
    `DID IT FIRE:` is invisible to this parser and therefore does not count -- which is deliberate:
    the three-line block is the declared form, and a partial one must not half-satisfy K4.
    """
    out = {}
    for pfx, d in sorted(PKG_DIR.items()):
        path = os.path.join(src_dir, d, "api.py")
        levers, wires = set(), set()
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                out[pfx] = (levers, wires)
                continue
            for n in ast.walk(tree):
                if not isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef)):
                    continue
                doc = ast.get_docstring(n) or ""
                for kind, body in _BLOCK.findall(doc):
                    # SPLIT ON COMMAS AND REQUIRE EACH ITEM TO BE A BARE IDENTIFIER, rather than
                    # splitting on whitespace and keeping every lowercase word.
                    #
                    # The whitespace version harvested 368 names of which 111 were not levers at
                    # all: "a", "is", "as", "the", "compared", "against", "arrives", "whose" --
                    # ordinary English bleeding in from blocks that wrap into a sentence. That is
                    # not cosmetic. K4 credits a lever when its name appears in the harvest, and
                    # several packages declare levers whose names are ordinary words -- `state`,
                    # `read`, `floor`, `plan`, `path`, `rate`, `only`, `entry`, `on`. Any of those
                    # could be credited by prose in a docstring that never meant to name it, and
                    # K4 would report a reader that does not exist.
                    #
                    # MEASURED BEFORE ADOPTING, because a stricter oracle that quietly drops real
                    # credits is worse than a loose one: strict harvests 266 names with 9
                    # undeclared, and ZERO declared levers lose their credit. So the tightening
                    # removes 102 spurious names and changes no verdict.
                    #
                    # A parenthetical is stripped, not dropped -- "emb_hid (compared against the
                    # sidecar)" is a real item with a note, and the note is the part that used to
                    # contribute "compared" and "against" to the harvest.
                    for item in _split_items(body):
                        if re.fullmatch(r"[a-z_][a-z0-9_]*", item or ""):
                            (levers if kind == "LEVERS READ" else wires).add(item)
        out[pfx] = (levers, wires)
    return out


def coupling_dsts(src_dir):
    """Every Coupling(dst="PFX.d_field") in <src>/spine/assemble.py, by AST."""
    path = os.path.join(src_dir, "spine", "assemble.py")
    dsts = []
    if not os.path.isfile(path):
        return dsts
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return dsts
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Coupling":
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            v = kw.get("dst")
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                dsts.append(v.value)
    return dsts


# ==================================================================================================
# K1 -- the document and the tree declare the same surface, in both directions
# ==================================================================================================
#
# CANNOT CATCH: whether a signature is the RIGHT one. Nothing here knows that `hold_out` belongs on
# forward() rather than on manage(); the reason columns and the five source specs are what stand
# behind that. This is a drift check, and its whole value is that it fails on the SECOND edit -- the
# one where somebody changes a parameter and does not open the document.

def check_k1_signatures(src_dir=SRC, doc_path=DOC):
    text = doc_text(doc_path)
    if text is None:
        return _report("K1", "the document and the tree declare the same public surface", False,
                       f"{os.path.relpath(doc_path, ROOT)} does not exist", [])
    tree_sigs, findings = api_signatures(src_dir)
    declared = doc_signatures(text)
    if declared is None:
        findings.append("the document has no ```contract fenced block, so it declares no signature "
                        "set at all. A contract phase whose contract is prose is a contract ten "
                        "agents will each read differently.")
        return _report("K1", "the document and the tree declare the same public surface", False,
                       f"{len(tree_sigs)} entry point(s) in the tree, 0 declared", findings)
    doc_set, tree_set = set(declared), set(tree_sigs)
    for missing in sorted(doc_set - tree_set):
        pfx = missing.split(":", 1)[0]
        near = sorted(s for s in tree_set if s.startswith(pfx + ":")
                      and s.split("(")[0] == missing.split("(")[0])
        findings.append(f"the document declares {missing!r} and the tree does not have it"
                        + (f" -- the tree has {near[0]!r}" if near else "")
                        + ". A signature that moved without the document moving is exactly what "
                          "makes two implementation agents incompatible.")
    for extra in sorted(tree_set - doc_set):
        findings.append(f"{tree_sigs[extra][2]} defines {extra!r}, which the document does not "
                        f"declare. A public entry point outside the contract is one nobody has "
                        f"agreed to keep.")
    if len(declared) != len(doc_set):
        findings.append(f"the ```contract block has {len(declared)} line(s) and "
                        f"{len(doc_set)} distinct one(s): a duplicate declaration means one of them "
                        f"is unreviewed.")
    detail = (f"{len(tree_set)} entry point(s) across {len(PKG_DIR)} package(s) compared against "
              f"{len(doc_set)} declared in {os.path.relpath(doc_path, ROOT)}")
    return _report("K1", "the document and the tree declare the same public surface",
                   not findings, detail, findings, vacuous=not tree_set and not doc_set)


# ==================================================================================================
# K2 -- the composition root runs, and fails only in the one legal way
# ==================================================================================================
#
# CANNOT CATCH: whether the root passes the RIGHT arguments. `compose()` stops at the first stub, so
# everything after RUN.process_setup is unexercised by this check today and becomes exercised one
# stub at a time as P4 lands. That is the honest reading and it is why ASSEMBLY_ORDER is data: the
# order can be reviewed without being run.
#
# RUN IN A SUBPROCESS on purpose. Importing thirteen packages and a namespace-package spine into the
# test process would make a later check's `import spine.assemble` depend on what this one imported
# first -- and a check that passes or fails depending on import order is the shape this project has
# lost a whole investigation to.

_K2_PROBE = r"""
import sys, traceback
sys.path.insert(0, %r)
try:
    from spine.compose import compose, plan
except Exception as e:
    print("IMPORT_FAILED", type(e).__name__, e); raise SystemExit(0)
a, l = plan()
if not a or not l:
    print("EMPTY_PLAN", len(a), len(l)); raise SystemExit(0)
try:
    compose(environ={})
except NotImplementedError as e:
    print("NOTIMPLEMENTED", str(e).split(":")[0]); raise SystemExit(0)
except Exception as e:
    print("WRONG_ERROR", type(e).__name__, str(e).replace("\n", " ")[:200])
    raise SystemExit(0)
print("NO_ERROR")
"""


def check_k2_compose(src_dir=SRC):
    findings = []
    proc = subprocess.run([sys.executable, "-c", _K2_PROBE % src_dir],
                          capture_output=True, text=True, timeout=180)
    out = (proc.stdout or "").strip().splitlines()
    line = out[-1] if out else ""
    verdict = line.split(" ", 1)[0] if line else "NO_OUTPUT"
    if verdict == "IMPORT_FAILED":
        findings.append(f"spine.compose does not import: {line}. A composition root that cannot be "
                        f"imported is a design document pretending to be code.")
    elif verdict == "EMPTY_PLAN":
        findings.append(f"plan() returned an empty order: {line}. The assembly order is the data "
                        f"docs/04_CONTRACT.md and the loop are both read against.")
    elif verdict == "WRONG_ERROR":
        findings.append(f"compose() raised something other than NotImplementedError: {line}. That is "
                        f"a fault in the ROOT -- a typo, a wrong argument name, a missing attribute "
                        f"-- not a missing body, and it would be indistinguishable from 'P4 has not "
                        f"landed yet' if this check did not separate them.")
    elif verdict == "NO_ERROR":
        findings.append("compose() completed without raising. Every mechanism is a stub, so it "
                        "cannot have: something is swallowing the NotImplementedError, and a "
                        "swallowed failure is the one shape this repository cannot afford.")
    elif verdict != "NOTIMPLEMENTED":
        findings.append(f"the probe produced no verdict (stdout={proc.stdout!r}, "
                        f"stderr={(proc.stderr or '')[-300:]!r})")
    got = line.split(" ", 1)[1] if verdict == "NOTIMPLEMENTED" and " " in line else "-"
    detail = (f"compose(environ={{}}) run in a subprocess; verdict {verdict}, "
              f"first unimplemented stub: {got}")
    return _report("K2", "the composition root imports and fails only at a stub",
                   not findings, detail, findings)


# ==================================================================================================
# K3 -- no package imports another (O10, restated at the contract boundary)
# ==================================================================================================
#
# CANNOT CATCH: everything O10 cannot -- a value handed over as an ordinary argument (which is the
# whole design), a dynamic import spelled without an import statement, or a coupling through shared
# mutable state, RNG draw order or the data. This is the cheap structural half; L3 is the rest.

def check_k3_no_cross_package_imports(src_dir=SRC):
    findings, scanned = [], 0
    pkg_dirs = set(PKG_DIR.values())
    for pfx, d in sorted(PKG_DIR.items()):
        pkg_root = os.path.join(src_dir, d)
        if not os.path.isdir(pkg_root):
            continue
        for dirpath, dirnames, filenames in os.walk(pkg_root):
            dirnames[:] = [x for x in dirnames if x != "__pycache__"]
            for fn in sorted(filenames):
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, src_dir)
                scanned += 1
                with open(path, "r", encoding="utf-8") as fh:
                    src = fh.read()
                try:
                    tree = ast.parse(src, filename=rel)
                except SyntaxError as e:
                    findings.append(f"{rel}:{e.lineno} does not parse: {e.msg}")
                    continue
                for node in ast.walk(tree):
                    names = []
                    if isinstance(node, ast.Import):
                        names = [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        base = node.module or ""
                        names = [base] + [f"{base}.{a.name}" for a in node.names]
                    for n in names:
                        head = n.split(".")[0]
                        tail = n.split(".")
                        if "assemble" in tail or "registry" in tail:
                            findings.append(f"{rel}:{node.lineno} imports {n!r} -- the assembly and "
                                            f"the registry hand out every package's Config.")
                        elif head in pkg_dirs and head != d:
                            findings.append(f"{rel}:{node.lineno} imports {n!r} -- {head!r} is "
                                            f"another package. A cross-package value arrives as an "
                                            f"argument the spine passed in; an import is a coupling "
                                            f"with no wire and nothing in affects().")
    return _report("K3", "no package imports another, the assembly or the registry",
                   not findings, f"{scanned} file(s) across {len(PKG_DIR)} package(s) examined",
                   findings, vacuous=not scanned)


# ==================================================================================================
# K4 -- every declared lever has a reader, or a written reason for having none
# ==================================================================================================
#
# CANNOT CATCH: whether the reader actually reads it. `LEVERS READ:` is a claim in prose that passes
# a parser -- the same standing objection spine/wire.py's `why=` carries, with the same answer: this
# checks PRESENCE and COMPLETENESS, and truth is L2's single-reader sweep and L3's isolation sweep,
# neither of which exists yet. A lever named in a docstring and never read by the body is invisible
# here, and that gap is the reason those two sweeps are on the plan.

def check_k4_levers_have_readers(src_dir=SRC, doc_path=DOC, cross_check=True):
    text = doc_text(doc_path)
    findings = []
    declared, parse_findings = declared_levers(src_dir)
    findings.extend(parse_findings)

    if cross_check:
        # THE LEVER SET THIS TEST READS MUST BE THE ONE THE RUN USES. An AST oracle that has silently
        # gone out of step with the real declarations is a SMALLER oracle, and a smaller oracle
        # passes by having nothing to compare -- the exact failure G1 exists to prevent.
        try:
            sys.path.insert(0, src_dir)
            try:
                from spine.assemble import PACKAGES
                live = {p: set(cls._levers) for p, cls in PACKAGES.items()}
            finally:
                if sys.path and sys.path[0] == src_dir:
                    sys.path.pop(0)
            if live != declared:
                only_ast = {p: sorted(declared.get(p, set()) - live.get(p, set())) for p in
                            set(declared) | set(live)}
                only_run = {p: sorted(live.get(p, set()) - declared.get(p, set())) for p in
                            set(declared) | set(live)}
                findings.append(
                    f"the lever declarations read by AST here and the ones spine.assemble registers "
                    f"are not the same set. Only in the source text: "
                    f"{ {k: v for k, v in only_ast.items() if v} }; only at runtime: "
                    f"{ {k: v for k, v in only_run.items() if v} }. Every check below was made "
                    f"against the source text, so it was made against the wrong set.")
        except Exception as e:                       # noqa: BLE001 -- reported, never swallowed
            findings.append(f"could not import spine.assemble to cross-check the lever set: "
                            f"{type(e).__name__}: {e}. The AST reading is therefore unverified.")

    reads = stub_reads(src_dir)
    unconsumed = doc_unconsumed(text)
    total = sum(len(v) for v in declared.values())
    covered, listed = 0, 0
    for pfx in sorted(declared):
        named = reads.get(pfx, (set(), set()))[0]
        for field in sorted(declared[pfx]):
            if field in named:
                covered += 1
            elif f"{pfx}.{field}" in unconsumed:
                listed += 1
            else:
                findings.append(
                    f"{pfx}_{field.upper()} is declared and no stub names it as read, and "
                    f"docs/04_CONTRACT.md's UNCONSUMED table does not list it with a reason. An "
                    f"operator can set it and nothing changes -- the armed-but-inert family, 57 of "
                    f"the survey's 475 records.")
    for name in sorted(unconsumed):
        pfx, _, field = name.partition(".")
        if field in reads.get(pfx, (set(), set()))[0]:
            findings.append(f"{name} is in the UNCONSUMED table AND is named as read by a stub. One "
                            f"of the two is stale, and a table that disagrees with the code is worse "
                            f"than no table.")
        elif field not in declared.get(pfx, set()):
            findings.append(f"{name} is in the UNCONSUMED table and no package declares it. A "
                            f"disposition for a lever that does not exist is a row nobody will ever "
                            f"revisit.")
    detail = (f"{total} declared lever(s) across {len(declared)} package(s): {covered} named by a "
              f"stub, {listed} listed as unconsumed with a reason, "
              f"{total - covered - listed} unaccounted for")
    return _report("K4", "every declared lever has a reader or a written reason for having none",
                   not findings, detail, findings, vacuous=not total)


# ==================================================================================================
# K5 -- every declared wire is read by its own package, and no stub reads an undeclared one
# ==================================================================================================
#
# CANNOT CATCH: whether the value is USED once read. `_ = cfg.d_foo` satisfies both this check and
# tests/test_ownership.py's O4, and at the stub stage that is exactly what the read is -- a declared
# read site with the body still to come. What it does buy is that the site is in the right package
# and is named in the docstring beside it, so P4 has one place to put the arithmetic.

def check_k5_wires_are_read(src_dir=SRC, cross_check=True):
    findings = []
    dsts = coupling_dsts(src_dir)
    if cross_check:
        try:
            sys.path.insert(0, src_dir)
            try:
                from spine.assemble import COUPLINGS
                live = {c.dst for c in COUPLINGS}
            finally:
                if sys.path and sys.path[0] == src_dir:
                    sys.path.pop(0)
            if live != set(dsts):
                findings.append(f"the coupling table read by AST here ({len(dsts)} rows) and the one "
                                f"spine.assemble builds ({len(live)} rows) are not the same ledger. "
                                f"Only in the source text: {sorted(set(dsts) - live)}; only at "
                                f"runtime: {sorted(live - set(dsts))}.")
        except Exception as e:                       # noqa: BLE001 -- reported, never swallowed
            findings.append(f"could not import spine.assemble to cross-check the ledger: "
                            f"{type(e).__name__}: {e}. The AST reading is therefore unverified.")

    reads = stub_reads(src_dir)
    for dst in sorted(set(dsts)):
        pfx, _, field = dst.partition(".")
        named = reads.get(pfx, (set(), set()))[1]
        if field not in named:
            findings.append(f"{dst} is declared in the coupling table and no stub in src/"
                            f"{PKG_DIR.get(pfx, '?')}/ names it under WIRES READ. A wire nobody "
                            f"reads spends budget, prints an edge, and delivers a value that "
                            f"arrives nowhere.")
    declared_fields = {d.partition('.')[2] for d in dsts}
    for pfx, (_, wires) in sorted(reads.items()):
        for field in sorted(wires):
            if not field.startswith("d_"):
                continue
            if field not in declared_fields:
                findings.append(f"src/{PKG_DIR.get(pfx, '?')}/api.py names {field!r} under WIRES "
                                f"READ and no coupling declares it. An undeclared d_ field is a "
                                f"coupling missing from affects(), and affects() is the L3 sweep's "
                                f"only oracle.")
    n_named = sum(len([w for w in v[1] if w.startswith('d_')]) for v in reads.values())
    detail = (f"{len(set(dsts))} declared destination(s) checked against {n_named} d_ field(s) named "
              f"under WIRES READ across {len(reads)} package(s)")
    return _report("K5", "every declared wire is read by its own package, and no stub reads an "
                         "undeclared one", not findings, detail, findings, vacuous=not dsts)


# ==================================================================================================
# SELF-TEST -- every check is run against a tree that CONTAINS the defect it looks for
# ==================================================================================================
#
# EACH CASE ASSERTS BOTH DIRECTIONS: the broken tree must FAIL, and the control -- the same tree with
# one file different -- must PASS. Only the failing direction is a regression test; only the passing
# direction distinguishes a real check from one that fails on everything, and a check that fails on
# everything gets switched off within a week.

_GOOD_LEVERS = '''\
"""A stand-in package levers module: only what the AST reader parses."""


class Lever:
    def __init__(self, default, help, unit=None, choices=None):
        pass


class LeverSet:
    pass


class DATALevers(LeverSet):
    PREFIX = "DATA"
    source = Lever("synthetic", "which corpus path", None)
    stream_bytes = Lever(4000000, "bytes drawn per epoch", None)
'''

_GOOD_API = '''\
"""A stand-in package api module."""
from spine.lever import Config


def open_areas(dat: Config, *, seed: int):
    """Open every area. Returns Areas(areas, bodies).

    LEVERS READ: source, stream_bytes
    WIRES READ: d_expert_slots
    DID IT FIRE: data.area_open
    """
    dat = dat.owned_by("DATA")
    _ = dat.d_expert_slots
    raise NotImplementedError("DATA.open_areas: P4 fills this in.")


def data_plan(dat: Config, *, areas):
    """The exposure gates.

    LEVERS READ: source
    WIRES READ: none
    DID IT FIRE: data.plan
    """
    dat = dat.owned_by("DATA")
    raise NotImplementedError("DATA.data_plan: P4 fills this in.")
'''

_GOOD_ASSEMBLE = '''\
"""A stand-in wiring file: only the Coupling calls the AST reader looks for."""


class Coupling:
    def __init__(self, src=None, dst=None, compute=None, why=None, unit=None, irreducible=False):
        self.dst = dst


COUPLINGS = [
    Coupling(src="FAB.slots", dst="DATA.d_expert_slots", compute=lambda r: 1,
             why="the stand-in coupling the self-test tree needs"),
]


class _DataLevers:
    """Enough of a LeverSet for K7, which asks the RUNNING registry what each package declares.

    K7 deliberately reads the live declarations rather than an AST copy: an oracle that has drifted
    from the real lever set is a SMALLER oracle, and a smaller oracle passes by having nothing to
    compare. That means the self-test tree has to carry a real one, however small.
    """
    PREFIX = "DATA"
    _levers = {"source": None, "stream_bytes": None, "resample": None}


PACKAGES = {"DATA": _DataLevers}
'''

_GOOD_COMPOSE = '''\
"""A stand-in composition root."""
ASSEMBLY_ORDER = (("corpus", "DATA", "open_areas",
                   "(seed=1234); Cadences.due('data.draw', DATA.draw_period(dat), clock)",
                   "areas -- the corpus handles"),
                  ("plan", "DATA", "data_plan", "(areas)", ""),)
LOOP_ORDER = (("A", "DATA", "draw_stream", "once per epoch"),)


def plan():
    return ASSEMBLY_ORDER, LOOP_ORDER


RNG_SUBSYSTEMS = ("data.synth",)


def _manifest(configs, streams):
    dat = configs["DATA"]
    _ = streams["data.synth"]
    return {"data.stream_bytes": int(dat.stream_bytes)}


def compose(environ=None, *, restored=None):
    raise NotImplementedError("DATA.open_areas: P4 fills this in.")
'''

_GOOD_LEVER_PY = '''\
"""A stand-in spine/lever.py, so the stand-in api module can import Config."""


class Config:
    def owned_by(self, prefix):
        return self
'''

# THE COUNTS AND THE ONE QUESTION HEADING BELOW ARE K13'S POPULATION. Every number in them is TRUE
# of the stand-in tree above -- two entry points, both stubs, two DATA levers, one coupling whose
# source is FAB and whose destination is DATA. The cases then break one number at a time. Without
# them K13 would examine nothing on the control tree and pass VACUOUSLY, which is the state it
# exists to refuse.
_GOOD_DOC = """# contract

## 3. UNCONSUMED LEVERS

| lever | env name | why it has no reader | disposition |
|---|---|---|---|

## 5. THE QUESTIONS

### Q-DATA-1 — `DATA.stream_bytes` has no second reader — **RESOLVED: one is enough**

## 6. THE FROZEN SIGNATURE SET

```contract
DATA: open_areas(dat: Config, *, seed: int)
DATA: data_plan(dat: Config, *, areas)
```

## 7. THE INDEX

### DATA — `src/data/api.py` (2 levers)

2 of the 2 entry points are stubs, against 2 declared levers and 1 coupling.
The ledger stands at 1 of 4.
"""

# --- K15 fixtures. Every case carries a whole <pkg>/api.py, because the check reads Gate calls in
# --- the function that computes them: a fragment would have no enclosing scope and rule 3 traces
# --- through exactly that scope. `_K15_API` is the template and each case replaces one gate.

_K15_LEVERS = '''\
"""A stand-in package levers module, with one lever that declares choices."""


class Lever:
    def __init__(self, default, help, unit=None, choices=None):
        pass


class LeverSet:
    pass


class DATALevers(LeverSet):
    PREFIX = "DATA"
    source = Lever("synthetic", "which corpus path", None, ("synthetic", "corpus"))
    stream_bytes = Lever(4000000, "bytes drawn per epoch", None)
'''

_K15_API = '''\
"""A stand-in api module whose entry point builds gates."""
from spine.gate import Gate
from spine.lever import Config


def open_areas(dat: Config, *, seed: int):
    """Open every area.

    LEVERS READ: source, stream_bytes
    WIRES READ: none
    DID IT FIRE: data.area_open
    """
    dat = dat.owned_by("DATA")
    src, n = str(dat.source), int(dat.stream_bytes)
    return [
        Gate("data.area_open", n > 0, n, "> 0", reachable=False,
             reason="DATA_STREAM_BYTES=0: nothing is drawn, so no area can open at all."),
        Gate("data.source", src == "synthetic", src, "synthetic",
             reason=f"DATA_SOURCE={src}: the corpus path this run drew from."),
        __GATE__,
    ]
'''


def _k15_api(gate):
    """The template with its one variable gate substituted, so each case differs by one Gate."""
    return _K15_API.replace("__GATE__", gate.strip())


# The control gate: a reachable gate whose reason carries ordinary English negation. "cannot be a
# redraw" and "no epoch can precede it" are remarks about the MECHANISM, not about this gate's
# reachability, and rule 4 must admit them -- the broad version of rule 4 reported four sentences of
# exactly this shape at every commit in the tree's history and never once a true instance.
_K15_GATE_OK = '''
        Gate("data.redraw", False, 0, 1,
             reason=f"DATA_STREAM_BYTES={n}: epoch 0 reads armed-and-did-not-fire rather than "
                    f"unreachable, because a FIRST draw cannot be a redraw and no epoch can "
                    f"precede it.")
'''

_K15_GATE_UNDECLARED = '''
        Gate("data.redraw", False, 0, 1,
             reason="DATA_STREAM_BYTE=0: the tokenizer minted nothing.")
'''

_K15_GATE_BAD_LITERAL = '''
        Gate("data.redraw", False, 0, 1,
             reason="DATA_STREAM_BYTES=lots: the epoch drew more than the cap.")
'''

_K15_GATE_BAD_CHOICE = '''
        Gate("data.redraw", False, 0, 1,
             reason="DATA_SOURCE=corpuz: the corpus path this run drew from.")
'''

# RULE 3. The sentence names the byte budget and renders the corpus path. Both locals are real and
# both are read off this package's own Config, which is what makes it the shape that survives every
# other check in this file.
_K15_GATE_WRONG_RENDER = '''
        Gate("data.redraw", False, 0, 1,
             reason=f"DATA_STREAM_BYTES={src}: the epoch drew that many bytes.")
'''

# THE ABSTENTION. `seed` is a parameter: its value was chosen in another file, so the check cannot
# say whether it is the byte budget and does not pretend to.
_K15_GATE_FROM_PARAM = '''
        Gate("data.redraw", False, 0, 1,
             reason=f"DATA_STREAM_BYTES={seed}: the epoch drew that many bytes.")
'''

_K15_GATE_IMPOSSIBLE = '''
        Gate("data.redraw", False, 0, 1,
             reason="DATA_STREAM_BYTES=0: the redraw is structurally unreachable on this run.")
'''

# THE SAME SENTENCE ON THE ARM IT BELONGS TO. Rule 4 is about the CONTRADICTION and not about the
# words, so the identical reason under reachable=False is exactly right and must be admitted.
_K15_GATE_IMPOSSIBLE_OK = '''
        Gate("data.redraw", False, 0, 1, reachable=False,
             reason="DATA_STREAM_BYTES=0: the redraw is structurally unreachable on this run.")
'''


# RULE 4's DYNAMIC HALF. `reachable=` is an expression, so nothing static says whether the gate ran
# -- but the reason branches on that SAME expression, so which arm prints on a reachable run is in
# the source. The pair differs only in which arm carries the sentence, which is the whole claim.
_K15_GATE_DYN_IMPOSSIBLE = '''
        Gate("data.redraw", False, 0, 1, reachable=n > 0,
             reason=("DATA_STREAM_BYTES=0: this gate cannot fire on this run."
                     if n > 0 else ""))
'''

_K15_GATE_DYN_IMPOSSIBLE_OK = '''
        Gate("data.redraw", False, 0, 1, reachable=n > 0,
             reason=("" if n > 0 else
                     "DATA_STREAM_BYTES=0: this gate cannot fire on this run."))
'''

# THE SAME PAIR THROUGH A `bool(...)` WRAPPER, which is how four of src/fabric/api.py's Gates are
# actually written. `bool(X)` and `if X:` are the same truthiness test, so the source settles which
# arm prints here exactly as it does above; a comparison that will not read the wrapper off drops
# the four live Gates and reports nothing in their place.
_K15_GATE_BOOL_IMPOSSIBLE = '''
        Gate("data.redraw", False, 0, 1, reachable=bool(n > 0),
             reason=("DATA_STREAM_BYTES=0: this gate cannot fire on this run."
                     if n > 0 else ""))
'''

_K15_GATE_BOOL_IMPOSSIBLE_OK = '''
        Gate("data.redraw", False, 0, 1, reachable=bool(n > 0),
             reason=("" if n > 0 else
                     "DATA_STREAM_BYTES=0: this gate cannot fire on this run."))
'''

# THE NEGATED FORM, which is the half that breaks if the wrapper is stripped in one place and not
# the other: the arm is selected by comparing the reason's test against `not {reach}`, so `reach`
# must already be normalised when that string is built. The sentence prints when `not (n > 0)` is
# FALSE -- that is, on exactly the runs the gate is reachable -- so this one is a finding.
_K15_GATE_BOOL_NEG_IMPOSSIBLE = '''
        Gate("data.redraw", False, 0, 1, reachable=bool(n > 0),
             reason=("" if not (n > 0) else
                     "DATA_STREAM_BYTES=0: this gate cannot fire on this run."))
'''

# THE NEIGHBOUR THAT MUST STAY OUTSIDE. Same wrapper, but the reason branches on a DIFFERENT
# expression -- `src`, not `n > 0`. Normalising the wrapper may not turn into deciding that two
# different conditions are one; this is src/opt/api.py's `floor_reachable` against
# `not sched_live` in miniature, and it is ABSTAINED on rather than judged.
_K15_GATE_BOOL_SECOND_NAME = '''
        Gate("data.redraw", False, 0, 1, reachable=bool(n > 0),
             reason=("DATA_STREAM_BYTES=0: this gate cannot fire on this run."
                     if src else ""))
'''

# RULE 5. The gate PRINTS `n`, which is DATA_STREAM_BYTES, on the `else` of an ordering test on that
# same lever -- so every value at or below zero reaches this arm while the sentence names one of
# them. This is the shape of ckpt.periodic_armed's "armed, did not fire (-5 vs 1) -- CKPT_EVERY=0".
_K15_API_BRANCHED = """\
\"\"\"A stand-in api module that builds one gate under a branch on a numeric lever.\"\"\"
from spine.gate import Gate
from spine.lever import Config


def open_areas(dat: Config, *, seed: int):
    \"\"\"Open every area.

    LEVERS READ: source, stream_bytes
    WIRES READ: none
    DID IT FIRE: data.area_open
    \"\"\"
    dat = dat.owned_by("DATA")
    n = int(dat.stream_bytes)
    if n > 0:
        gate = Gate("data.area_open", True, n, 1)
    else:
        __GATE__
    return [gate]
"""

# THE THIRD ARM PINS THE VALUE, which is what makes the literal legitimate: `elif n == 0` admits one
# value of the lever and no other, so the sentence and the printed number cannot disagree. Without
# this case the pinning half of _k15_branch_admits_a_range is a guard nothing has ever tripped.
_K15_API_THREE_WAY = """\
\"\"\"A stand-in api module that splits one numeric lever three ways.\"\"\"
from spine.gate import Gate
from spine.lever import Config


def open_areas(dat: Config, *, seed: int):
    \"\"\"Open every area.

    LEVERS READ: source, stream_bytes
    WIRES READ: none
    DID IT FIRE: data.area_open
    \"\"\"
    dat = dat.owned_by("DATA")
    n = int(dat.stream_bytes)
    if n > 0:
        gate = Gate("data.area_open", True, n, 1)
    elif n == 0:
        __GATE__
    else:
        gate = Gate("data.area_open", False, n, 1, reachable=False,
                    reason="a negative budget is refused before this runs.")
    return [gate]
"""

# THE BODY ARM OF AN ORDERING TEST, WHICH IS THE SAME PROGRAM AS THE ELSE ARM ABOVE. `if n <= 0:`
# admits every value at or below zero in its BODY exactly as `if n > 0: ... else:` does in its else,
# and src/opt/api.py writes the first spelling. Until 2026-09-05 rule 5 saw only the second, so this
# tree -- the historical ckpt defect, transliterated and nothing else changed -- PASSED.
_K15_API_BODY_ARM = """\
\"\"\"A stand-in api module that builds one gate on the BODY of an ordering test.\"\"\"
from spine.gate import Gate
from spine.lever import Config


def open_areas(dat: Config, *, seed: int):
    \"\"\"Open every area.

    LEVERS READ: source, stream_bytes
    WIRES READ: none
    DID IT FIRE: data.area_open
    \"\"\"
    dat = dat.owned_by("DATA")
    n = int(dat.stream_bytes)
    if n <= 0:
        __GATE__
    else:
        gate = Gate("data.area_open", True, n, 1)
    return [gate]
"""

# THE ADMIT SIDE OF THE WIDENING, and it is what keeps it from becoming "any literal on any body
# arm". An EQUALITY test pins the lever to one value in its body, so the sentence and the printed
# number cannot disagree -- the same construct, one operator apart, and it must stay green.
_K15_API_BODY_PINNED = """\
\"\"\"A stand-in api module that builds one gate on the BODY of an equality test.\"\"\"
from spine.gate import Gate
from spine.lever import Config


def open_areas(dat: Config, *, seed: int):
    \"\"\"Open every area.

    LEVERS READ: source, stream_bytes
    WIRES READ: none
    DID IT FIRE: data.area_open
    \"\"\"
    dat = dat.owned_by("DATA")
    n = int(dat.stream_bytes)
    if n == 0:
        __GATE__
    else:
        gate = Gate("data.area_open", True, n, 1)
    return [gate]
"""

_K15_BRANCHED_LITERAL = '''
        gate = Gate("data.area_open", False, n, 1,
                    reason="DATA_STREAM_BYTES=0: nothing is drawn, so no area opens.")
'''

_K15_BRANCHED_RENDERED = '''
        gate = Gate("data.area_open", False, n, 1,
                    reason=f"DATA_STREAM_BYTES={n}: nothing is drawn, so no area opens.")
'''


def _k15_branched(template, gate):
    """`template` with its one variable gate substituted, indentation preserved."""
    return template.replace("__GATE__", gate.strip())


_BASE_TREE = {
    "src/spine/lever.py": _GOOD_LEVER_PY,
    "src/spine/assemble.py": _GOOD_ASSEMBLE,
    "src/spine/compose.py": _GOOD_COMPOSE,
    "src/data/__init__.py": "",
    "src/data/levers.py": _GOOD_LEVERS,
    "src/data/api.py": _GOOD_API,
    "docs/04_CONTRACT.md": _GOOD_DOC,
}

# Each case: (name, overlay, {tag: (must_fail, a phrase the finding must contain)}).
_CASES = (
    ("control -- nothing wrong with this tree", {}, {
        "K1": (False, None), "K2": (False, None), "K3": (False, None),
        "K4": (False, None), "K5": (False, None), "K6": (False, None), "K7": (False, None),
        "K8": (False, None), "K9": (False, None), "K10": (False, None), "K11": (False, None),
        "K12": (False, None), "K13": (False, None), "K15": (False, None)}),

    ("K13: the population collapsed below the declared floor",
     {}, {"K13floor": (True, "POPULATION COLLAPSED")}),

    ("K1: a parameter was renamed in the tree and not in the document",
     {"src/data/api.py": _GOOD_API.replace("*, seed: int", "*, run_seed: int")},
     {"K1": (True, "run_seed")}),

    ("K1: the tree grew an entry point the document does not declare",
     {"src/data/api.py": _GOOD_API + '''

def draw_stream(dat: Config, areas):
    """LEVERS READ: stream_bytes
    WIRES READ: none
    DID IT FIRE: data.stream_draw
    """
    raise NotImplementedError("x")
'''},
     {"K1": (True, "draw_stream")}),

    ("K1: the document has no ```contract block at all",
     {"docs/04_CONTRACT.md": "# contract\n\nnothing normative here\n"},
     {"K1": (True, "fenced block")}),

    ("K2: the root raises something other than NotImplementedError",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace(
         'raise NotImplementedError("DATA.open_areas: P4 fills this in.")',
         'raise TypeError("open_areas() got an unexpected keyword argument")')},
     {"K2": (True, "WRONG_ERROR")}),

    ("K2: the root swallows the failure and returns",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace(
         'raise NotImplementedError("DATA.open_areas: P4 fills this in.")', "return None")},
     {"K2": (True, "without raising")}),

    ("K3: a package imports another package",
     {"src/data/api.py": "from fabric import api as fab_api\n" + _GOOD_API},
     {"K3": (True, "another package")}),

    ("K3: a package imports the assembly",
     {"src/data/api.py": "from spine.assemble import build\n" + _GOOD_API},
     {"K3": (True, "the registry")}),

    # ---- K6. The check that found 56 orphans, and then had to be strengthened twice.
    ("K6: an entry point with no row and no deferral",
     {"src/data/api.py": _GOOD_API + '''

def judge_probation(dat: Config):
    """LEVERS READ: resample
    WIRES READ: none
    DID IT FIRE: data.probation
    """
    raise NotImplementedError("x")
'''},
     {"K6": (True, "named by no row")}),

    # THE ATTACK TWO REVIEWERS FOUND INDEPENDENTLY, pinned so it cannot come back. K6 credited an
    # entry point for being MENTIONED anywhere in a row's note, so ONE row listing names it does not
    # call turned 110 rowed / 7 deferred into 117 / 0 and K6 still passed -- the check becoming
    # exactly the shape it exists to catch. A note credits only a written CALL now, and this case is
    # the proof: the same orphan, mentioned by name in a row, must still be reported.
    ("K6: a row that MENTIONS an entry point without calling it credits nothing",
     {"src/data/api.py": _GOOD_API + '''

def judge_probation(dat: Config):
    """LEVERS READ: resample
    WIRES READ: none
    DID IT FIRE: data.probation
    """
    raise NotImplementedError("x")
''',
      "src/spine/compose.py": _GOOD_COMPOSE.replace(
          'LOOP_ORDER = (("A", "DATA", "draw_stream", "once per epoch"),)',
          'LOOP_ORDER = (("A", "DATA", "draw_stream", "once per epoch; this row calls nothing: '
          'DATA.judge_probation"),)')},
     {"K6": (True, "judge_probation")}),

    ("K6: a note that writes the CALL does credit it",
     {"src/data/api.py": _GOOD_API + '''

def judge_probation(dat: Config):
    """LEVERS READ: resample
    WIRES READ: none
    DID IT FIRE: data.probation
    """
    raise NotImplementedError("x")
''',
      "src/spine/compose.py": _GOOD_COMPOSE.replace(
          'LOOP_ORDER = (("A", "DATA", "draw_stream", "once per epoch"),)',
          'LOOP_ORDER = (("A", "DATA", "draw_stream", "once per epoch -> '
          'DATA.judge_probation(window=w)"),)')},
     {"K6": (False, None)}),

    # DEFERRING open_areas, NOT draw_stream, and the difference is the point. The first version of
    # this case deferred DATA.draw_stream -- which the stand-in api.py does not declare -- so K6
    # first PASSED (the stale check lives inside the walk over entry points, and that walk never saw
    # it) and then, once the backwards loop was added, FAILED for the wrong reason. The must_say
    # guard is what reported the difference. open_areas is a real entry point AND is named by an
    # ASSEMBLY_ORDER row, which is the actual stale shape.
    ("K6: a deferral that a row now names is STALE and must be reported",
     {"src/spine/compose.py": _GOOD_COMPOSE + '''
DEFERRED_ENTRY_POINTS = {"DATA.open_areas": "P6 calls this"}
'''},
     {"K6": (True, "stale")}),

    ("K6: a deferral naming something that is not an entry point at all",
     {"src/spine/compose.py": _GOOD_COMPOSE + '''
DEFERRED_ENTRY_POINTS = {"DATA.no_such_function": "P6 calls this"}
'''},
     {"K6": (True, "declares no such entry point")}),

    ("K6: a deferral with an empty reason is an orphan with paperwork",
     {"src/data/api.py": _GOOD_API + '''

def judge_probation(dat: Config):
    """LEVERS READ: resample
    WIRES READ: none
    DID IT FIRE: data.probation
    """
    raise NotImplementedError("x")
''',
      "src/spine/compose.py": _GOOD_COMPOSE + '''
DEFERRED_ENTRY_POINTS = {"DATA.judge_probation": "   "}
'''},
     {"K6": (True, "empty reason")}),

    # ---- K7. The defect that produced it, in the shape it actually had.
    ("K7: the root reads a name off a Config that the package does not declare",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace("dat.stream_bytes", "dat.depth")},
     {"K7": (True, "does not declare")}),

    ("K7: the root reaches for a Config's private _owner, which walks to every package",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace("dat.stream_bytes", "dat._owner")},
     {"K7": (True, "PRIVATE")}),

    # ---- K8. The defect that produced it: WORLD was handed rng=None for the life of every run.
    ("K8: the root takes a stream RNG_SUBSYSTEMS never minted",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace('streams["data.synth"]', 'streams["world"]')},
     {"K8": (True, "does not mint")}),

    ("K8: the root uses .get(), which returns None instead of raising",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace('streams["data.synth"]',
                                                    'streams.get("data.synth")')},
     {"K8": (True, "returns None")}),

    # ---- K9. Three of the five periodic gates in the real tree were this, and the two that were
    # ---- right (EVAL.curve_period, CKPT.save_period) made them look like a style difference.
    ("K9: a cadence gate handed a bare lever read, which Cadences.due refuses",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace("DATA.draw_period(dat)", "DATA.draw_every")},
     {"K9": (True, "bare attribute read")}),

    # ---- K10. The reviewer's demonstrated defeat, pinned. K10's first version let an argument
    # ---- count as produced when the CONSUMING row's own note contained the word, which made the
    # ---- whole produces column optional -- a four-element row reading "(units_by_domain, logits_fn,
    # ---- rng)" passed with no producer anywhere in the tree. The column is the only thing that
    # ---- counts now, plus an explicit binding and the declared helper table.
    ("K10: an argument no earlier row produces",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace('"areas -- the corpus handles"', '""')},
     {"K10": (True, "no earlier row")}),

    ("K10: naming the argument in the CONSUMING row's own note credits nothing",
     {"src/spine/compose.py": _GOOD_COMPOSE
        .replace('"areas -- the corpus handles"', '""')
        .replace('("plan", "DATA", "data_plan", "(areas)", "")',
                 '("plan", "DATA", "data_plan", "areas arrives from the row above", "")')},
     {"K10": (True, "no earlier row")}),

    ("K10: a producer on a LATER row does not count",
     {"src/spine/compose.py": _GOOD_COMPOSE
        .replace('"areas -- the corpus handles"', '""')
        .replace('("plan", "DATA", "data_plan", "(areas)", "")',
                 '("plan", "DATA", "data_plan", "(areas)", "areas -- produced too late")')},
     {"K10": (True, "no earlier row")}),

    ("K10: an explicit lever binding IS a producer",
     {"src/spine/compose.py": _GOOD_COMPOSE
        .replace('"areas -- the corpus handles"', '""')
        .replace('("plan", "DATA", "data_plan", "(areas)", "")',
                 '("plan", "DATA", "data_plan", "(areas=DATA.source)", "")')},
     {"K10": (False, None)}),

    ("K10: a stale ROW_ARGUMENTS_ELSEWHERE entry is reported",
     {"src/spine/compose.py": _GOOD_COMPOSE + '''
ROW_ARGUMENTS_ELSEWHERE = {"DATA.no_such_entry": "produced by _nothing"}
'''},
     {"K10": (True, "stale exemption")}),

    # ---- K11. K10 makes provenance decidable by TRUSTING the produces column, so a column entry
    # ---- naming a value its entry point does not return is a fabrication K10 then certifies. A
    # ---- reviewer found nine, covering fourteen tokens.
    ("K11: a produces entry naming a value the entry point does not return",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace('"areas -- the corpus handles"',
                                                    '"key_fn -- a bound callable"')},
     {"K11": (True, "does not return")}),

    ("K11: a DECLARED RENAME is admitted -- `alias = real` where real is in the docstring",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace('"areas -- the corpus handles"',
                                                    '"handles = areas -- renamed for the consumer"')},
     {"K11": (False, None)}),

    ("K11: a rename that names nothing real is still refused",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace('"areas -- the corpus handles"',
                                                    '"handles = nowhere -- renamed from nothing"')},
     {"K11": (True, "does not return")}),

    # ---- K12. "Two arguments have no producer." Four did.
    ("K12: a deferral reason that omits an argument with no producer",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace('"areas -- the corpus handles"', '""') + '''
DEFERRED_ENTRY_POINTS = {"DATA.data_plan": "P6 fills this in, for unrelated reasons"}
'''},
     {"K12": (True, "does not name")}),

    ("K12: a reason that names the gap is admitted",
     {"src/spine/compose.py": _GOOD_COMPOSE.replace('"areas -- the corpus handles"', '""') + '''
DEFERRED_ENTRY_POINTS = {"DATA.data_plan": "P6. Nothing produces areas."}
'''},
     {"K12": (False, None)}),

    ("K4: a declared lever that no stub names and no table lists",
     {"src/data/levers.py": _GOOD_LEVERS.replace(
         '    stream_bytes = Lever(4000000, "bytes drawn per epoch", None)',
         '    stream_bytes = Lever(4000000, "bytes drawn per epoch", None)\n'
         '    seg_min = Lever(700, "shortest segment", None)')},
     {"K4": (True, "SEG_MIN")}),

    ("K4: the unconsumed table names a lever a stub also reads",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace(
         "|---|---|---|---|\n",
         "|---|---|---|---|\n| `DATA.source` | `DATA_SOURCE` | this is a long enough reason to pass "
         "the placeholder filter and it is still wrong | drop |\n")},
     {"K4": (True, "stale")}),

    ("K4: an unconsumed row with a placeholder instead of a reason does not count",
     {"src/data/levers.py": _GOOD_LEVERS.replace(
         '    stream_bytes = Lever(4000000, "bytes drawn per epoch", None)',
         '    stream_bytes = Lever(4000000, "bytes drawn per epoch", None)\n'
         '    seg_min = Lever(700, "shortest segment", None)'),
      "docs/04_CONTRACT.md": _GOOD_DOC.replace(
          "|---|---|---|---|\n",
          "|---|---|---|---|\n| `DATA.seg_min` | `DATA_SEG_MIN` | TBD | later |\n")},
     {"K4": (True, "SEG_MIN")}),

    # ---- K13. Counts in prose have been wrong five times; a question asserted an absence once.
    # THE ADMIT SIDE IS HALF OF THESE ON PURPOSE. A check that refuses every document passes every
    # regression case above and is worth nothing -- and two of the four admits below are the
    # check's own STATED LIMITS, written as cases so they cannot be quietly widened into refusals
    # or quietly forgotten.
    ("K13: a lever count in the prose that the tree contradicts",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace("against 2 declared levers",
                                               "against 3 declared levers")},
     {"K13": (True, "levers_total")}),

    ("K13: an entry-point total that drifted while the stub count stayed right",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace("2 of the 2 entry points",
                                               "2 of the 9 entry points")},
     {"K13": (True, "entry_points")}),

    ("K13: a per-package lever count in a section heading that drifted",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace("(2 levers)", "(5 levers)")},
     {"K13": (True, "levers:DATA")}),

    ("K13: a coupling count that drifted",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace("and 1 coupling", "and 6 couplings")},
     {"K13": (True, "couplings")}),

    ("K13: a wrong count inside a PAST-TENSE sentence is admitted -- a stated limit, as a case",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace(
         "2 of the 2 entry points are stubs, against 2 declared levers and 1 coupling.",
         "There were 9 declared levers before the split.")},
     {"K13": (False, None)}),

    ("K13: a question heading that says a declared lever is absent",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace(
         "### Q-DATA-1 — `DATA.stream_bytes` has no second reader — **RESOLVED: one is enough**",
         "### Q-DATA-1 — nothing in this system draws a stream of bytes — **OPEN**")},
     {"K13": (True, "stream_bytes")}),

    ("K13: a heading that NAMES the lever it negates a property of is admitted",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace(
         "has no second reader", "cannot reach a second reader")},
     {"K13": (False, None)}),

    ("K13: a document with no counts and no questions FAILS instead of passing empty",
     {"docs/04_CONTRACT.md": _GOOD_DOC.replace(
         "2 of the 2 entry points are stubs, against 2 declared levers and 1 coupling.\n"
         "The ledger stands at 1 of 4.\n", "")
         .replace("### Q-DATA-1 — `DATA.stream_bytes` has no second reader — "
                  "**RESOLVED: one is enough**\n", "")
         .replace(" (2 levers)", "")},
     {"K13": (True, "failure of this check")}),

    # ---- K9, widened. The sixth period has no order-table row, so only the mapping half sees it.
    ("K9: the one period with no row is a module constant with no Clock kind",
     {"src/spine/compose.py": _GOOD_COMPOSE + '''
from data import api as data_api


def _periods(sysm):
    return {"progress": data_api.PROGRESS_WINDOWS}
''',
      "src/data/api.py": _GOOD_API + "\n\nPROGRESS_WINDOWS = 100\n"},
     {"K9": (True, "progress")}),

    ("K9: the same period written units.Windows at its definition is admitted",
     {"src/spine/compose.py": _GOOD_COMPOSE + '''
from data import api as data_api


def _periods(sysm):
    return {"progress": data_api.PROGRESS_WINDOWS}
''',
      "src/data/api.py": _GOOD_API + "\n\nPROGRESS_WINDOWS = U.Windows(100)\n"},
     {"K9": (False, None)}),

    ("K9: a period in the mapping that is a bare Config read",
     {"src/spine/compose.py": _GOOD_COMPOSE + '''

def _periods(sysm):
    return {"curve": sysm.configs["DATA"].stream_bytes}
'''},
     {"K9": (True, "neither a call nor a typed module constant")}),

    ("K5: a declared wire no stub reads",
     {"src/data/api.py": _GOOD_API.replace("    _ = dat.d_expert_slots\n", "")
                                  .replace("    WIRES READ: d_expert_slots\n",
                                           "    WIRES READ: none\n")},
     {"K5": (True, "arrives nowhere")}),

    ("K5: a stub names a d_ field no coupling declares",
     {"src/data/api.py": _GOOD_API.replace("WIRES READ: d_expert_slots",
                                           "WIRES READ: d_expert_slots, d_window")},
     {"K5": (True, "d_window")}),

    # ---- K15. The control tree declares no Gate at all, so K15 passes it VACUOUSLY and says so;
    # ---- these cases give it a population. Each replaces ONE gate in a three-gate entry point, so
    # ---- the two around it stay correct and a case that fails can only be failing on the one.
    ("K15: a correct gate set, negation and all -- the ADMIT side rule 4 needs",
     {"src/data/levers.py": _K15_LEVERS, "src/data/api.py": _k15_api(_K15_GATE_OK)},
     {"K15": (False, None)}),

    ("K15: a reason naming a lever no package declares",
     {"src/data/levers.py": _K15_LEVERS, "src/data/api.py": _k15_api(_K15_GATE_UNDECLARED)},
     {"K15": (True, "DATA_STREAM_BYTE")}),

    ("K15: a reason spelling a value the lever's declared type cannot hold",
     {"src/data/levers.py": _K15_LEVERS, "src/data/api.py": _k15_api(_K15_GATE_BAD_LITERAL)},
     {"K15": (True, "'lots'")}),

    ("K15: a reason spelling a value outside the lever's declared choices",
     {"src/data/levers.py": _K15_LEVERS, "src/data/api.py": _k15_api(_K15_GATE_BAD_CHOICE)},
     {"K15": (True, "declared choices")}),

    ("K15: a reason naming one lever and rendering another quantity",
     {"src/data/levers.py": _K15_LEVERS, "src/data/api.py": _k15_api(_K15_GATE_WRONG_RENDER)},
     {"K15": (True, "never reads 'stream_bytes'")}),

    ("K15: the same shape rendered from a PARAMETER is ABSTAINED on, not guessed at",
     {"src/data/levers.py": _K15_LEVERS, "src/data/api.py": _k15_api(_K15_GATE_FROM_PARAM)},
     {"K15": (False, None)}),

    ("K15: a reason asserting impossibility on a gate built reachable",
     {"src/data/levers.py": _K15_LEVERS, "src/data/api.py": _k15_api(_K15_GATE_IMPOSSIBLE)},
     {"K15": (True, "structurally unreachable")}),

    ("K15: the identical reason on the reachable=False arm is ADMITTED",
     {"src/data/levers.py": _K15_LEVERS, "src/data/api.py": _k15_api(_K15_GATE_IMPOSSIBLE_OK)},
     {"K15": (False, None)}),

    # ---- RULE 4's DYNAMIC HALF. Everything below `reachable=` is a runtime value; what the source
    # ---- still settles is which arm of the reason prints when that value holds. The shipped check
    # ---- before this round passed BOTH of these, which is the gap these two cases close.
    ("K15: an impossibility on the arm that prints when the reachable expression HOLDS",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_api(_K15_GATE_DYN_IMPOSSIBLE)},
     {"K15": (True, "reachable exactly when")}),

    ("K15: the same sentence on the arm that prints when it does NOT hold is ADMITTED",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_api(_K15_GATE_DYN_IMPOSSIBLE_OK)},
     {"K15": (False, None)}),

    # ---- THE `bool(...)` WRAPPER. Four of src/fabric/api.py's Gates are written this way and the
    # ---- version that shipped on 2026-09-04 judged none of them. The first three pin the
    # ---- normalisation in both directions; the fourth pins that it is normalisation and not
    # ---- inference -- a wrapper around one expression may not be matched to a different one.
    ("K15: the impossibility on the printing arm of a bool()-wrapped reachable expression",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_api(_K15_GATE_BOOL_IMPOSSIBLE)},
     {"K15": (True, "reachable exactly when")}),

    ("K15: the same sentence on the other arm of a bool()-wrapped expression is ADMITTED",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_api(_K15_GATE_BOOL_IMPOSSIBLE_OK)},
     {"K15": (False, None)}),

    ("K15: a bool()-wrapped expression whose reason branches on its NEGATION",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_api(_K15_GATE_BOOL_NEG_IMPOSSIBLE)},
     {"K15": (True, "reachable exactly when")}),

    ("K15: a bool()-wrapped expression against a reason branching on a SECOND NAME is ABSTAINED on",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_api(_K15_GATE_BOOL_SECOND_NAME)},
     {"K15": (False, None)}),

    # ---- RULE 5. ckpt.periodic_armed's shape: the gate prints the lever and the reason spells one
    # ---- value of it, on a branch that admits every value at or below zero.
    ("K15: a literal spelled for the lever the gate prints, on a range-admitting branch",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_branched(_K15_API_BRANCHED, _K15_BRANCHED_LITERAL)},
     {"K15": (True, "admits a RANGE")}),

    ("K15: the same gate RENDERING the value it prints is ADMITTED -- that is the repair",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_branched(_K15_API_BRANCHED, _K15_BRANCHED_RENDERED)},
     {"K15": (False, None)}),

    ("K15: the same literal is ADMITTED where the branch PINS the lever to it",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_branched(_K15_API_THREE_WAY, _K15_BRANCHED_LITERAL)},
     {"K15": (False, None)}),

    # ---- THE BODY ARM. `if n <= 0: <gate>` is the same program as `if n > 0: ... else: <gate>`,
    # ---- and rule 5 saw only the second until 2026-09-05 -- so the defect it was written for
    # ---- could be transliterated straight past it, and a live instance of exactly that shape was
    # ---- standing in src/opt/api.py the whole time. The third case is the operator that makes the
    # ---- literal legitimate, so the widening cannot be read as "any literal on any body arm".
    ("K15: the same literal on the BODY arm of an ordering test -- the transliterated defect",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_branched(_K15_API_BODY_ARM, _K15_BRANCHED_LITERAL)},
     {"K15": (True, "admits a RANGE")}),

    ("K15: the body-arm gate RENDERING the value it prints is ADMITTED",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_branched(_K15_API_BODY_ARM, _K15_BRANCHED_RENDERED)},
     {"K15": (False, None)}),

    ("K15: the same literal on the BODY arm of an EQUALITY test is ADMITTED -- it pins the lever",
     {"src/data/levers.py": _K15_LEVERS,
      "src/data/api.py": _k15_branched(_K15_API_BODY_PINNED, _K15_BRANCHED_LITERAL)},
     {"K15": (False, None)}),
)

_BY_TAG = {
    "K1": lambda d: check_k1_signatures(os.path.join(d, "src"),
                                        os.path.join(d, "docs", "04_CONTRACT.md")),
    "K2": lambda d: check_k2_compose(os.path.join(d, "src")),
    "K3": lambda d: check_k3_no_cross_package_imports(os.path.join(d, "src")),
    "K4": lambda d: check_k4_levers_have_readers(os.path.join(d, "src"),
                                                 os.path.join(d, "docs", "04_CONTRACT.md"),
                                                 cross_check=False),
    "K5": lambda d: check_k5_wires_are_read(os.path.join(d, "src"), cross_check=False),
    "K6": lambda d: check_k6_readers_are_reached(os.path.join(d, "src"),
                                                 os.path.join(d, "docs", "04_CONTRACT.md")),
    "K7": lambda d: check_k7_root_reads_declared_names(os.path.join(d, "src")),
    "K8": lambda d: check_k8_streams_are_declared(os.path.join(d, "src")),
    "K9": lambda d: check_k9_cadence_periods_are_typed(os.path.join(d, "src")),
    "K10": lambda d: check_k10_rows_name_their_arguments(os.path.join(d, "src")),
    "K11": lambda d: check_k11_produces_is_not_fabricated(os.path.join(d, "src")),
    "K12": lambda d: check_k12_deferral_reasons_are_complete(os.path.join(d, "src")),
    "K13": lambda d: check_k13_counts_and_absence_claims(
        os.path.join(d, "src"), os.path.join(d, "docs", "04_CONTRACT.md"), floor=1),
    "K13floor": lambda d: check_k13_counts_and_absence_claims(
        os.path.join(d, "src"), os.path.join(d, "docs", "04_CONTRACT.md"), floor=999),
    "K15": lambda d: check_k15_gate_reasons_are_self_consistent(os.path.join(d, "src")),
}


def _tree(overlay):
    files = dict(_BASE_TREE)
    files.update(overlay)
    d = tempfile.mkdtemp(prefix="contract_selftest_")
    for rel, text in files.items():
        p = os.path.join(d, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    return d


def _indent(text):
    return "\n".join("              " + ln for ln in text.strip().splitlines())


def selftest():
    findings, ran = [], 0
    for name, overlay, expect in _CASES:
        d = _tree(overlay)
        try:
            for tag, (want_fail, must_say) in sorted(expect.items()):
                ran += 1
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = _BY_TAG[tag](d)
                out = buf.getvalue()
                got_fail = bool(rc)
                if got_fail != want_fail:
                    verb = ("passed a tree it must fail" if want_fail
                            else "failed a tree it must pass")
                    findings.append(f"[{name}] {tag} {verb}:\n{_indent(out)}")
                elif want_fail and must_say and must_say not in out:
                    # A check that fails for the wrong reason is a green regression test over a live
                    # hole -- the shape this repository has sixty records of.
                    findings.append(f"[{name}] {tag} failed as required, but its finding never "
                                    f"mentions {must_say!r}, so it may be failing for an unrelated "
                                    f"reason:\n{_indent(out)}")
        finally:
            shutil.rmtree(d, ignore_errors=True)
    detail = f"{len(_CASES)} case(s), {ran} check run(s) against synthetic trees in a temp directory"
    return _report("SELF", "the checks fail on trees that contain the defect, and pass on ones that "
                           "do not", not findings, detail, findings)



# ==================================================================================================
# K6 -- a stub that names a lever must be REACHED by the order tables
# ==================================================================================================

def entry_points(src_dir=SRC):
    """{"PFX": {name: lineno}} -- every public function and public method in each <pkg>/api.py."""
    out = {}
    for pfx, d in sorted(PKG_DIR.items()):
        path = os.path.join(src_dir, d, "api.py")
        found = {}
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                out[pfx] = found
                continue
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and not node.name.startswith("_"):
                    found[node.name] = node.lineno
                elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                                and not sub.name.startswith("_"):
                            found[f"{node.name}.{sub.name}"] = sub.lineno
        out[pfx] = found
    return out


def _named_by_orders(src_dir=SRC):
    """Every "PFX.entry" the two order tables name, from compose.py BY AST -- not by import.

    By AST because this check has to run against a synthetic tree in the self-test, where importing
    spine.compose would drag in thirteen real packages. It reads the tables as literals and takes
    BOTH the entry-point column and the prose column: several rows legitimately name a second entry
    point in their note ("-> FAB.grow_check(...)", "the Plan it returns goes to MEM.apply_domain_plan"),
    and a check that ignored those would report live mechanism as orphaned.
    """
    path = os.path.join(src_dir, "spine", "compose.py")
    named, column, prose_calls = set(), set(), set()
    if not os.path.isfile(path):
        return named, column, prose_calls
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return named, column, prose_calls
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") in ("ASSEMBLY_ORDER", "LOOP_ORDER") for t in node.targets)):
            continue
        for row in ast.walk(node.value):
            if not isinstance(row, ast.Tuple) or len(row.elts) < 3:
                continue
            parts = [e.value for e in row.elts if isinstance(e, ast.Constant)
                     and isinstance(e.value, str)]
            if len(parts) < 3:
                continue
            pfx = parts[1]
            for piece in re.split(r"[/\s]+", parts[2]):
                piece = piece.strip("(),.")
                if piece:
                    named.add(f"{pfx}.{piece}")
                    named.add(f"{pfx}.{piece.split('.')[-1]}")
                    column.add(f"{pfx}.{piece}")
                    column.add(f"{pfx}.{piece.split('.')[-1]}")
            prose = " ".join(parts[3:])
            # A PROSE MENTION COUNTS ONLY IF IT IS WRITTEN AS A CALL -- "FAB.grow_check(soft_cap=...)"
            # counts, "goes to MEM.apply_domain_plan" does not.
            #
            # Two reviewers independently found the version without the parenthesis, and their attack
            # is the whole argument for it: a row whose NOTE merely lists entry points credits every
            # one of them, so one row saying "this calls nothing: WORLD.state_dict, LM.counters, ..."
            # turns 110 rowed / 7 deferred into 117 / 0 and K6 still passes. That is this check
            # becoming exactly the shape it exists to catch.
            # The parenthesis is not proof -- a row could write `WORLD.state_dict()` in a note and
            # call nothing -- but the tables ARE data, and no reading of data can prove what the code
            # P4 writes will do. What it buys is that the credit has to be a claim about a CALL, in a
            # row, next to the arguments; and the detail line below reports prose credits separately
            # so a number like "110 rowed" can never again hide eleven of them.
            for a, b in re.findall(r"\b([A-Z]{2,5})\.([A-Za-z_][A-Za-z_0-9]*)\s*\(", prose):
                named.add(f"{a}.{b}")
                named.add(f"{a}.{b.split('.')[-1]}")
                prose_calls.add(f"{a}.{b}")
            # CLASS-QUALIFIED NAMES TOO. An entry point may be a METHOD -- RunClock.advance,
            # Cadences.due, Retention.consider -- and the rows write it that way in both the entry
            # column and the prose. The PREFIX pattern above cannot see "Cadences.due" because
            # "Cadences" is not an all-caps package prefix, so without this the check reported
            # RUN.Cadences.due as orphaned while three separate rows call it by name. A matcher gap
            # that manufactures orphans is as bad as one that hides them: it buries the real list.
            for cls, meth in re.findall(r"\b([A-Z][A-Za-z0-9]+)\.([a-z_][A-Za-z_0-9]*)\s*\(", prose):
                named.add(f"{cls}.{meth}")
                prose_calls.add(f"{cls}.{meth}")
                for _p in PKG_DIR:
                    named.add(f"{_p}.{cls}.{meth}")
    return named, column, prose_calls


def _deferred_entry_points(src_dir=SRC):
    """The DEFERRED_ENTRY_POINTS declaration in compose.py, read by AST as {"PFX.entry": reason}."""
    path = os.path.join(src_dir, "spine", "compose.py")
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "DEFERRED_ENTRY_POINTS" for t in node.targets):
            v = node.value
            if isinstance(v, ast.Call):                      # types.MappingProxyType({...})
                v = v.args[0] if v.args else None
            if isinstance(v, ast.Dict):
                for k, val in zip(v.keys, v.values):
                    if isinstance(k, ast.Constant) and isinstance(val, ast.Constant):
                        out[k.value] = val.value
    return out


def check_k6_readers_are_reached(src_dir=SRC, doc_path=DOC):
    """K6 -- an entry point that names levers must be REACHED by ASSEMBLY_ORDER or LOOP_ORDER.

    WHY K4 IS NOT THIS CHECK, and why the gap mattered. K4 asks whether some stub's docstring NAMES
    each declared lever. It passed at 257 named / 2 listed / 0 unaccounted, and docs/04_CONTRACT.md
    reported the unconsumed set as two levers, both FAB's. A reviewer then applied the composition
    root's OWN order tables as the test and found that the naming stub is frequently never called:

      * nothing calls SIG.train_step, SIG.cadence_due or SIG.warm_up, while SIG.mode defaults to
        'learned' and compose() hands SIG's parameters to OPT as a second param group. The run
        therefore allocates an AdamW over the encoder, steps it every flush on zero gradients, and
        routes every window through a RANDOMLY INITIALISED encoder for the whole run -- with
        src/sig/api.py::<module> stating the stakes itself: "the signature is the router's only
        input, so a collapsed encoder routes every window to the same experts".
      * nothing calls MEM.read or MEM.blend. The store is written and maintained and never read, so
        nothing retrieval-side reaches the model's distribution -- and src/memory/api.py::<module>
        prices that path at the difference between -0.097 and +0.085 b/B.
      * nothing calls DOM.rekey, which src/domains/api.py::rekey calls "AN EVENT THE SPINE
        DELIVERS" and which is the only place a radius is measured, while DOM.accept_rule defaults
        to 'radius'.
      * nothing calls DATA.draw_stream. The stream is never drawn.

    That is armed-but-inert -- 57 records, the second-largest family in the survey -- reproduced in
    the new architecture at DESIGN time, where it costs one table edit instead of ten implemented
    bodies for functions nobody calls. K4 could not see it because "reads a lever" and "is reached"
    are different questions and it only ever asked the first.

    THE DEFERRED TABLE IS A DECLARATION, NOT AN ESCAPE. An entry point with no row must appear in
    compose.DEFERRED_ENTRY_POINTS with the phase that will call it and why. It is checked BACKWARDS
    too: an entry that is now named by a row is stale and must be deleted, so the table cannot
    become the place orphans go to be forgotten.

    WHAT IT CANNOT CATCH. That a row exists does not mean the loop, once written, executes it -- the
    tables are data and P4 writes the code. It also cannot see an entry point reached only from
    inside another package's body (LM.load_state through CKPT.load, say); that is why those appear
    in the deferred table with the caller named rather than being silently allowed.
    """
    findings = []
    eps = entry_points(src_dir)
    named, column, prose_calls = _named_by_orders(src_dir)
    deferred = _deferred_entry_points(src_dir)
    reads = stub_reads(src_dir)

    total = sum(len(v) for v in eps.values())
    reached, by_prose, listed = 0, 0, 0
    for pfx, funcs in sorted(eps.items()):
        for fn, line in sorted(funcs.items()):
            key = f"{pfx}.{fn}"
            tail = f"{pfx}.{fn.split('.')[-1]}"
            if key in named or tail in named:
                reached += 1
                if not (key in column or tail in column):
                    by_prose += 1
                if key in deferred:
                    findings.append(
                        f"{key}: listed in DEFERRED_ENTRY_POINTS as {deferred[key]!r}, but a row in "
                        f"ASSEMBLY_ORDER or LOOP_ORDER now names it. The entry is stale -- delete it, "
                        f"or the table becomes the place orphans go to be forgotten.")
                continue
            if key in deferred:
                listed += 1
                if not str(deferred[key]).strip():
                    findings.append(f"{key}: deferred with an empty reason, which is an orphan with "
                                    f"paperwork.")
                continue
            lv = sorted(reads.get(pfx, (set(), set()))[0])
            findings.append(
                f"{PKG_DIR[pfx]}/api.py:{line}  {key} is named by no row in ASSEMBLY_ORDER or "
                f"LOOP_ORDER and is not in DEFERRED_ENTRY_POINTS."
                + (f" It claims to read {len(lv)} lever(s) -- {', '.join(lv[:6])}"
                   f"{' ...' if len(lv) > 6 else ''} -- so those levers have a reader that is never "
                   f"called, which reads as armed-but-0 and is actually never-asked."
                   if lv else " It reads no lever, so the cost is only that the contract declares a"
                              " surface the root does not use."))
    # THE TABLE, READ BACKWARDS -- and this loop exists because the self-test found it missing.
    # The stale check above lives inside the walk over ENTRY POINTS, so it only ever sees a deferral
    # whose function still exists. A deferral naming a function that was deleted, renamed, or never
    # written is invisible to it: the case "a deferral that a row now names is STALE" PASSED on a
    # tree where the deferred name was not an entry point at all. That is the write-only-table shape
    # test_census.py's N3 exists to prevent, reproduced in a table written four hours later.
    all_eps = {f"{p}.{f}" for p, fs in eps.items() for f in fs}
    for key, why in sorted(deferred.items()):
        if key in all_eps:
            continue                                   # handled by the walk above, both directions
        pfx = key.split(".")[0]
        findings.append(
            f"DEFERRED_ENTRY_POINTS names {key!r} ({str(why)[:60]!r}), and "
            + (f"{PKG_DIR[pfx]}/api.py declares no such entry point."
               if pfx in PKG_DIR else f"{pfx!r} is not a package.")
            + " A deferral for something that does not exist is a row nobody can ever retire.")

    return _report("K6", "every entry point is reached by the order tables, or declared deferred",
                   not findings,
                   f"{total} entry point(s): {reached - by_prose} in a row's ENTRY COLUMN, "
                   f"{by_prose} credited by a CALL WRITTEN IN A ROW'S NOTE, {listed} declared "
                   f"deferred; {len(deferred)} deferred entr(y/ies) re-checked against the tables",
                   findings, vacuous=not total)



# ==================================================================================================
# K7 -- every Config attribute the composition root reads must be a declared lever or a declared wire
# ==================================================================================================

def check_k7_root_reads_declared_names(src_dir=SRC):
    """K7 -- src/spine/compose.py may not read a name off a Config that no package declares.

    THE DEFECT THAT PRODUCED THIS CHECK, in the code it now guards. _geometry_manifest read

        "lm.depth": (int(lm.depth), "EXACT", "LM_DEPTH", "the layer stack"),

    where `lm` is sysm.configs["LM"]. LM declares `layers`; there is no `depth`. Config.__getattr__
    RAISES on an undeclared name rather than returning a default, so every compose() would have died
    at the gate stage.

    WHY NOTHING CAUGHT IT, WHICH IS THE WHOLE POINT. RUN.process_setup raises NotImplementedError
    several rows EARLIER, so the crash was unreachable, and K2 -- "the composition root imports and
    fails only at a stub" -- passed on a tree that could not run. K2 checks the FIRST failure and
    stops; every line after it is untested until the stub before it is implemented, which means the
    root's correctness arrives in the order the stubs get bodies rather than all at once. A defect
    hidden behind an earlier stub is this project's oldest shape, and it is the reason a static check
    is worth more here than an execution.

    HOW IT DECIDES. By AST, over compose.py: find every local name bound to `configs[...]` or
    `sysm.configs[...]` with a CONSTANT prefix string, then check every attribute read on that name
    against the declared levers of that package plus its declared d_ wire fields. Both sides come
    from the running registry, so an oracle that drifts from the declarations cannot make this pass
    by having a smaller set to compare against.

    WHAT IT CANNOT CATCH:
      * a Config reached through a name this resolver cannot follow -- stored in a dict, passed to a
        helper, or rebound. It reports the count it examined so a fall in coverage is visible rather
        than silent, and a helper taking a Config parameter is O9's territory.
      * a name that IS declared but wrong -- reading `lm.heads` where `lm.layers` was meant is
        legal here and always will be. The manifest's `why` column is what stands behind that.
      * an attribute on any object that is not a Config: the geometry record, the population, the
        clock. Those are P4's types and do not exist yet.
    """
    path = os.path.join(src_dir, "spine", "compose.py")
    if not os.path.isfile(path):
        return _report("K7", "the root reads only declared names off a Config", False,
                       "src/spine/compose.py is missing", [], vacuous=True)
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return _report("K7", "the root reads only declared names off a Config", False,
                       f"src/spine/compose.py does not parse at line {e.lineno}", [])

    # The declared surface of every package: its levers, plus the d_ fields the wire table lands.
    declared = {}
    try:
        sys.path.insert(0, src_dir)
        try:
            from spine.assemble import PACKAGES, COUPLINGS
            for pfx, cls in PACKAGES.items():
                declared[pfx] = set(cls._levers)
            for c in COUPLINGS:
                pfx, _, field = str(c.dst).partition(".")
                if pfx in declared:
                    declared[pfx].add(field)
        finally:
            if sys.path and sys.path[0] == src_dir:
                sys.path.pop(0)
    except Exception as e:                               # noqa: BLE001 -- reported, never swallowed
        return _report("K7", "the root reads only declared names off a Config", False,
                       f"could not import spine.assemble to learn the declared names: "
                       f"{type(e).__name__}: {e}", [])

    def _prefix_of(node):
        """`configs["LM"]` / `sysm.configs["LM"]` -> "LM"; anything else -> None."""
        if not isinstance(node, ast.Subscript):
            return None
        key = node.slice
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            return None
        base = node.value
        name = (base.attr if isinstance(base, ast.Attribute) else
                base.id if isinstance(base, ast.Name) else "")
        return key.value if name == "configs" else None

    bound, findings = {}, []
    for node in ast.walk(tree):
        # x = configs["LM"]   and   a, b = configs["LM"], configs["SIG"]
        if isinstance(node, ast.Assign):
            tgts, vals = node.targets[0], node.value
            pairs = (zip(tgts.elts, vals.elts)
                     if isinstance(tgts, ast.Tuple) and isinstance(vals, ast.Tuple)
                     else [(tgts, vals)])
            for t, v in pairs:
                p = _prefix_of(v)
                if p and isinstance(t, ast.Name):
                    bound[t.id] = p

    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        base = node.value
        pfx = bound.get(base.id) if isinstance(base, ast.Name) else _prefix_of(base)
        if not pfx or pfx not in declared:
            continue
        checked += 1
        if node.attr.startswith("_"):
            findings.append(f"src/spine/compose.py:{node.lineno}  reads the PRIVATE {pfx}.{node.attr} "
                            f"off a Config. Config.__slots__ exposes _owner, which walks to LeverSet "
                            f"and every other package -- the root has no need of it.")
        elif node.attr not in declared[pfx]:
            near = sorted(n for n in declared[pfx] if n[:3] == node.attr[:3])
            findings.append(
                f"src/spine/compose.py:{node.lineno}  reads {pfx}.{node.attr}, which {pfx} does not "
                f"declare as a lever or receive as a wire. Config.__getattr__ RAISES on an undeclared "
                f"name, so this is a crash at whatever stage reaches it -- and it stays invisible "
                f"while an earlier stub raises first."
                + (f" Closest declared: {', '.join(near)}." if near else ""))
    return _report("K7", "the root reads only declared names off a Config", not findings,
                   f"{checked} Config attribute read(s) across {len(bound)} bound name(s), against "
                   f"{sum(len(v) for v in declared.values())} declared name(s) in "
                   f"{len(declared)} package(s)", findings, vacuous=not checked)



# ==================================================================================================
# K8 -- every RNG stream the root reaches for is one it minted
# ==================================================================================================

def check_k8_streams_are_declared(src_dir=SRC):
    """K8 -- the root may only take streams named in RNG_SUBSYSTEMS, and never with .get().

    THE DEFECT, WHICH WAS LIVE. RNG_SUBSYSTEMS listed nine subsystems and "world" was not among
    them, so compose() reached for WORLD's generator as

        rng=sysm.streams.get("world")

    and handed WORLD None for the life of every run. The four sibling constructors all write
    streams["name"], which RAISES on a missing key; this one line used .get() and returned None
    instead, while src/world/api.py::build takes rng as a REQUIRED keyword.

    WHY THAT IS WORSE THAN AN ORDINARY BUG. compose.py's own comment above RNG_SUBSYSTEMS says
    rng.issued() is the DID-IT-FIRE surface for the whole randomness story: "a subsystem present with
    ZERO DRAWS is armed-but-inert, and a subsystem ABSENT never asked. Those are two different
    statements and G4 requires the report to make both." A package that is absent from the register
    AND was handed None is a third state G4 has no name for -- the report would say WORLD never asked
    for randomness, on a run where WORLD asked and got nothing. The recorded-never-read family (39
    records) meeting the armed-but-inert one (57).

    TWO RULES, and the second is the one that matters. Every key must appear in RNG_SUBSYSTEMS, and
    the lookup must SUBSCRIPT rather than .get(): a missing key has to raise at startup. .get() is
    the silent default, and this project has lost runs to silent defaults -- MAX_DOMAINS read with
    two different defaults 128x apart at two sites is the same shape one layer down.

    WHAT IT CANNOT CATCH: a stream fetched through a name this resolver cannot follow, or a package
    that never asks for the stream it was minted. rng.issued() is the runtime answer to the second
    and it does not exist until the loop runs.
    """
    path = os.path.join(src_dir, "spine", "compose.py")
    if not os.path.isfile(path):
        return _report("K8", "every RNG stream the root takes is one it minted", False,
                       "src/spine/compose.py is missing", [], vacuous=True)
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return _report("K8", "every RNG stream the root takes is one it minted", False,
                       f"src/spine/compose.py does not parse at line {e.lineno}", [])

    declared = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "RNG_SUBSYSTEMS" for t in node.targets):
            for e in ast.walk(node.value):
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    declared.append(e.value)
    declared = set(declared)

    def _is_streams(n):
        return (isinstance(n, ast.Attribute) and n.attr == "streams") or \
               (isinstance(n, ast.Name) and n.id == "streams")

    findings, looked = [], 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _is_streams(node.value):
            looked += 1
            k = node.slice
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value not in declared:
                findings.append(f"src/spine/compose.py:{node.lineno}  takes the stream "
                                f"{k.value!r}, which RNG_SUBSYSTEMS does not mint. It would raise at "
                                f"startup -- which is the right behaviour and the reason to say so "
                                f"here instead.")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and _is_streams(node.func.value):
            looked += 1
            k = node.args[0] if node.args else None
            nm = k.value if isinstance(k, ast.Constant) else "?"
            findings.append(
                f"src/spine/compose.py:{node.lineno}  takes the stream {nm!r} with .get(), which "
                f"returns None for a name RNG_SUBSYSTEMS never minted instead of raising. Every "
                f"sibling constructor subscripts. Use streams[{nm!r}] and add {nm!r} to "
                f"RNG_SUBSYSTEMS."
                + ("" if nm in declared else f" ({nm!r} is not in RNG_SUBSYSTEMS today, so this is "
                                             f"handing None to a required argument right now.)"))
    return _report("K8", "every RNG stream the root takes is one it minted", not findings,
                   f"{looked} stream lookup(s) against {len(declared)} minted subsystem(s)",
                   findings, vacuous=not looked)



# ==================================================================================================
# K9 -- no cadence gate is handed a bare lever read
# ==================================================================================================

_DUE_RE = re.compile(r"Cadences\.due\(\s*'([^']+)'\s*,\s*([^,]+?)\s*,")


def check_k9_cadence_periods_are_typed(src_dir=SRC):
    """K9 -- every Cadences.due period in the order tables is a typed accessor, not a lever read.

    THE DEFECT. RUN.Cadences.due states its own contract: "`period` MUST be units.Windows. An int
    raises; a Flushes raises." Three rows handed it a bare lever read --
    Cadences.due('fab.manage', FAB.manage_every, clock), and the same for DOM.manage_every and
    MEM.rekey_every -- and Config hands back a bare int for all 35 levers that declare a Clock unit
    (ISSUES P1-H51). So three of the five periodic gates in the system would have raised on their first
    evaluation, and the row said they were fine.

    EVAL and CKPT already had typed accessors (curve_period, save_period) and did not raise. That is
    the tell: the same table declared the same thing two ways, and the two that were right made the
    three that were wrong look like a style difference.

    WHAT THE RULE IS. The period must be a CALL -- PKG.something(...) -- not an attribute read. The
    accessor lives in the package that DECLARES the kind, which is the whole argument for it over
    wrapping at the call site: a root writing Windows(fab.manage_every) asserts FAB's kind from
    outside FAB, in as many places as there are gates, each free to be wrong on its own. One
    accessor per period is the rule the wires already follow.

    A CONSTRUCTION IS NOT A CONVERSION, and the distinction matters because this project calls one
    of them a defect. Windows(int) re-attaches a kind the lever already declares. The defect is
    crossing kinds unnamed -- manage_every // batch_w, Windows to Flushes -- which is
    derive.flush_period_windows and is not this.

    THE SIXTH PERIOD HAS NO ROW, AND THIS CHECK NOW READS IT ANYWAY (widened 2026-09-03).
    _periods gained a 'progress' key under Q-RUN-1 whose period is RUN.PROGRESS_WINDOWS, a module
    constant rather than a lever, and which NO ROW NAMES -- rows are entry-point calls and no entry
    point prints the progress line. Reading the order tables alone therefore left one of the six
    gates unexaminable, and _periods' own docstring said so in as many words. The second half below
    reads the mapping ITSELF: every value it returns must be a CALL (the typed accessor) or a
    module-level constant CONSTRUCTED with a Clock kind at its definition. A bare `cfg.something`
    there is the same defect the first half refuses on a row, and a constant written `= 100` is the
    H51 shape one level further out -- Cadences.due would raise on it at the first evaluation.

    WHAT IT CANNOT CATCH: an accessor that returns the wrong kind, or the right kind computed
    wrongly. It reads the ORDER TABLES and the _periods mapping, which are both data; whether P4's
    loop actually calls due() with what the row says is L2's, and does not exist yet. Nor can it see
    a period that reaches Cadences.due without passing through either -- a key invented at a call
    site is what compose.py's own rule forbids in prose, and prose is all that forbids it.
    """
    path = os.path.join(src_dir, "spine", "compose.py")
    if not os.path.isfile(path):
        return _report("K9", "no cadence gate is handed a bare lever read", False,
                       "src/spine/compose.py is missing", [], vacuous=True)
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    # Read the joined row text, so a period split across two source lines is still seen whole.
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return _report("K9", "no cadence gate is handed a bare lever read", False,
                       f"src/spine/compose.py does not parse at line {e.lineno}", [])
    prose = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") in ("ASSEMBLY_ORDER", "LOOP_ORDER") for t in node.targets)):
            continue
        for row in ast.walk(node.value):
            if isinstance(row, ast.Tuple) and len(row.elts) >= 4:
                parts = [e.value for e in row.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if len(parts) >= 4:
                    prose.append((row.lineno, " ".join(parts[3:])))

    findings, gates = [], 0
    for lineno, text_row in prose:
        for key, period in _DUE_RE.findall(text_row):
            period = period.strip()
            if period in ("...", "..."):
                continue                       # an elided illustration, not a declared gate
            gates += 1
            if "(" in period:
                continue                       # a call: the typed accessor
            findings.append(
                f"src/spine/compose.py:{lineno}  the {key!r} gate is handed {period!r}, a bare "
                f"attribute read. Cadences.due states 'period MUST be units.Windows. An int raises', "
                f"and a Config hands back an int for every lever that declares a Clock unit. Give "
                f"the owning package a typed period accessor, as EVAL.curve_period and "
                f"CKPT.save_period already are.")
    # ---- THE MAPPING ITSELF, so the one period with no row is not the one period nothing reads.
    _CLOCK = ("Windows", "Steps", "Flushes", "Backwards", "Epochs", "Selections")
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in PKG_DIR.values():
            for a in node.names:
                if a.name == "api":
                    aliases[a.asname or a.name] = node.module
    periods = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_periods":
            for st in ast.walk(node):
                if isinstance(st, ast.Return) and isinstance(st.value, ast.Dict):
                    for k, v in zip(st.value.keys, st.value.values):
                        if isinstance(k, ast.Constant):
                            periods[k.value] = v
    for key, v in sorted(periods.items()):
        if isinstance(v, ast.Call):
            continue                       # the typed accessor, which the row half also demands
        if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) \
                and v.value.id in aliases:
            mod = os.path.join(src_dir, aliases[v.value.id], "api.py")
            kind, found = None, False
            if os.path.isfile(mod):
                with open(mod, "r", encoding="utf-8") as fh:
                    mtext = fh.read()
                try:
                    mtree = ast.parse(mtext)
                except SyntaxError:
                    mtree = None
                for st in (mtree.body if mtree else ()):
                    if (isinstance(st, ast.Assign)
                            and any(getattr(t, "id", "") == v.attr for t in st.targets)):
                        found = True
                        if isinstance(st.value, ast.Call):
                            kind = getattr(st.value.func, "attr", None) or \
                                getattr(st.value.func, "id", None)
            if kind in _CLOCK:
                continue
            saw = (f"it is constructed with {kind!r}" if kind
                   else "it is assigned a bare value" if found
                   else "no module-level assignment for that name was found")
            findings.append(
                f"src/spine/compose.py  _periods['{key}'] is the module constant "
                f"{v.value.id}.{v.attr}, and src/{aliases[v.value.id]}/api.py does not construct it "
                f"with a Clock kind ({saw}). Cadences.due states 'period MUST be units.Windows. An "
                f"int raises', and this period has NO ORDER-TABLE ROW, so nothing else in the "
                f"suite looks at it.")
            continue
        findings.append(
            f"src/spine/compose.py  _periods['{key}'] is neither a call nor a typed module "
            f"constant. Every period in this mapping is handed straight to Cadences.due, which "
            f"raises on a bare int, and a Config returns a bare int for every Clock-unit lever "
            f"(ISSUES P1-H51).")

    # TWO ARMS, AND `or` MEANT NEITHER OF THEM HAD TO HAVE ANYTHING IN IT. K9 reads the order tables
    # for Cadences.due gates AND compose.py's _periods mapping, and it marked itself VACUOUS only when
    # BOTH were empty. So the arm this check was written for -- the gates, the three rows that handed
    # Cadences.due a bare lever read -- could go to zero and K9 would still print a plain PASS on the
    # strength of the other arm's population. That is a green tick over an empty set wearing a second
    # set's count, which is the same defect the marker exists to refuse. Either arm empty is vacuous,
    # and the detail line says which.
    empty = [n for n, c in (("Cadences.due gates", gates), ("_periods entries", len(periods))) if not c]
    detail = (f"{gates} Cadences.due gate(s) declared across {len(prose)} row note(s); "
              f"{len(periods)} period(s) in _periods, "
              f"{sum(1 for v in periods.values() if not isinstance(v, ast.Call))} of them a "
              f"module constant with no order-table row")
    if empty:
        detail += f" -- EMPTY ARM(S): {', '.join(empty)}"
    return _report("K9", "no cadence gate is handed a bare lever read", not findings,
                   detail, findings, vacuous=bool(empty))



# ==================================================================================================
# K10 -- a row must name every argument its entry point requires
# ==================================================================================================

def _required_params(src_dir=SRC):
    """{"PFX.entry": [required parameter names]} -- from the frozen signatures, by AST.

    REQUIRED means: keyword-only without a default, plus any positional-or-keyword without a default
    BEYOND THE FIRST. Excluding: the leading Config, `self`, and the FIRST positional after the
    Config.

    THAT FIRST POSITIONAL IS THE PACKAGE'S OWN LIVE OBJECT -- store, pop, part, valve, model,
    snapshot -- produced by the package's own constructor row, which ASSEMBLY_ORDER always contains
    and K6 already guarantees is reached. Demanding every row restate it produced 25 findings of
    which the majority were that noise: "the MEM.census row does not name 'store'", on a row whose
    package built the store nine rows earlier. A check that reports mostly noise is a check nobody
    reads, and the real findings drown -- the same argument that narrowed K4's oracle and N4's
    matching.

    What survives the narrowing is exactly what the reviewers found by hand: EVAL.curve_probe naming
    none of units_by_domain / logits_fn / rng, MEM.read naming no queries, DOM.manage naming none of
    now / memory_counts / mem_floor_entries, CKPT.check_geometry naming no geometry.

    A parameter WITH a default is the author saying the call works without it, so this check does not
    ask about it. That is a real limit and it is where MEM.judge sat:
    judge(mem, store, *, scorer=None, reconstructor=None) with MEM.verify defaulting to "selfcon",
    which needs a scorer -- so a row calling judge(mem, store) yields n_checked=0 forever, which
    src/memory/api.py::judge itself names as the inert state. K10 cannot see that; only reading the
    docstring can, and that is why the row was fixed by hand and this docstring says so.
    """
    out = {}
    for pfx, d in sorted(PKG_DIR.items()):
        path = os.path.join(src_dir, d, "api.py")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        def _collect(node, name):
            a = node.args
            req = []
            allargs = a.posonlyargs + a.args
            n_def = len(a.defaults)
            pos_req = allargs[:len(allargs) - n_def] if n_def else allargs
            after_config = []
            took_config = False
            for arg in pos_req:
                if arg.arg == "self":
                    continue
                if getattr(arg.annotation, "id", None) == "Config":
                    took_config = True
                    continue                      # the package's own Config, never named in a row
                after_config.append(arg.arg)
            # DROP THE LIVE OBJECT BY NAME, NOT BY POSITION. The first version dropped "the first
            # positional after the Config", and a reviewer showed it drops the wrong argument twice:
            #   Retention.consider(self, curve_bpb, step) is a METHOD -- no Config, `self` already
            #     skipped -- so the rule discarded `curve_bpb`, which is the held-out curve value
            #     the EVAL.curve_probe deferral says "can never arrive". K10 certified that row
            #     while asking only about `step`.
            #   TOK.restore_vocab(tok, state, vocab) puts the snapshot blob FIRST and the live
            #     object second, so the rule dropped `state` and demanded `vocab` -- backwards.
            # A method's live object is `self` and is already gone; only a module-level function
            # carries one as a parameter, and it is identifiable by NAME. The set is small, closed
            # and written down rather than inferred from position, because position was the
            # assumption that failed.
            LIVE = {"store", "pop", "part", "valve", "model", "vocab", "areas", "st", "w",
                    "plan", "clock", "cadences", "sysm", "system"}
            if took_config and after_config and after_config[0] in LIVE:
                after_config = after_config[1:]
            req.extend(after_config)
            for kw, dflt in zip(a.kwonlyargs, a.kw_defaults):
                if dflt is None:
                    req.append(kw.arg)
            out[name] = req

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and not node.name.startswith("_"):
                _collect(node, f"{pfx}.{node.name}")
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            and not sub.name.startswith("_"):
                        _collect(sub, f"{pfx}.{node.name}.{sub.name}")
    return out


def _rows_with_prose(src_dir=SRC):
    """[(lineno, "PFX.entry", "the whole receives column")] for every row in either order table."""
    path = os.path.join(src_dir, "spine", "compose.py")
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return rows
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") in ("ASSEMBLY_ORDER", "LOOP_ORDER") for t in node.targets)):
            continue
        for row in ast.walk(node.value):
            if not isinstance(row, ast.Tuple) or len(row.elts) < 3:
                continue
            parts = [e.value for e in row.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(parts) < 3:
                continue
            # parts[3] is `receives`; parts[4:] is `produces`, when the row carries one. A row with
            # only four elements produces nothing FOR THIS CHECK -- which is a real statement, not a
            # default: a row that yields a value later rows need has to say so, and the ones that
            # yield nothing (a refusal, a save, a counter read) legitimately have none.
            recv = parts[3] if len(parts) > 3 else ""
            # THE PRODUCES COLUMN IS A LIST OF NAMES, EACH WITH AN EXPLANATION AFTER `--`, THE
            # ENTRIES SEPARATED BY `;`. Harvesting every identifier from it instead gave the
            # producer side the SAME hole the consumer side had: a column reading
            #     "geometry -- CKPT.save's argument, the RECORDED side of the comparison"
            # produced the tokens `geometry`, `CKPT`, `save`, `argument`, `side`, `comparison` and
            # `RECORDED`, so any later row wanting an argument called `side` or `comparison` was
            # satisfied by prose about something else entirely. Measured: 24 tokens harvested this
            # way across nine rows were ordinary English, including `THE`, `WHICH` and `WRITES`.
            # Parsing the declared form means a produced name has to be WRITTEN as one.
            prod = {}
            for entry in " ".join(parts[4:]).split(";"):
                head, _, why = entry.partition("--")
                head = head.strip().strip(",.")
                # `alias = real` -- the head carries the rename, so split it off and keep it where
                # K11 can read it. K10 only ever wants the alias: that is the name the CONSUMING
                # signature uses, and matching consumers to producers is its whole job.
                alias, eq, real = head.partition("=")
                if eq:
                    head, why = alias.strip(), "= " + real.strip() + " -- " + why.strip()
                if re.fullmatch(r"[a-z_][A-Za-z_0-9]*", head or ""):
                    prod[head] = why.strip()
            for piece in re.split(r"[/\s]+", parts[2]):
                piece = piece.strip("(),.")
                if piece:
                    rows.append((row.lineno, f"{parts[1]}.{piece}", recv, prod))
    return rows


def check_k10_rows_name_their_arguments(src_dir=SRC):
    """K10 -- every required argument of a rowed entry point is produced by an earlier row.

    THE STANDARD THE ORDER TABLES ALREADY CLAIM, applied. compose.py's own header says a row is
    "(stage, PREFIX, entry point, what it receives that is not its own Config)", and the deferral
    reason written for EVAL.holdout_probe states the rule outright: "the root has no join that
    produces that pair; writing a row now would name a call whose arguments nothing supplies."

    A reviewer then found the standard broken by the row the standard's own argument rests on.
    EVAL.curve_probe and EVAL.holdout_probe have BYTE-IDENTICAL signatures --
    (ev: Config, *, units_by_domain, logits_fn, rng) -- and curve_probe's entire row prose is
    "Cadences.due('curve', EVAL.curve_period(ev), clock)", which names neither argument and no row or
    helper produces either. So the same gap was grounds for deferral in one case and a row in the
    other, and the compose header cited the rowed one as PROOF that the standard is about arguments
    rather than phase. Two more of the repair's own rows had the shape: R MEM.read (nothing produces
    `queries`) and R MEM.blend (whose prose CONCEDES the join is missing and writes the row anyway).

    A standard stated in a header and broken by the first row under it is worse than no standard --
    it reads as an argument that the gap is acceptable.

    REQUIRED, NOT ALL. A parameter with a default is the author saying the call works without it, so
    this check does not ask about it. That is a real limit and it is where MEM.judge sat:
    judge(mem, store, *, scorer=None, reconstructor=None) with MEM.verify defaulting to "selfcon",
    which needs a scorer -- so a row calling judge(mem, store) yields n_checked=0 forever, which
    src/memory/api.py::judge itself names as the inert state. K10 cannot see that; only reading the
    docstring can, and that is why the row was fixed by hand and this docstring says so.

    THE EXEMPTION TABLE IS A DECLARATION. compose.ROW_ARGUMENTS_ELSEWHERE names rows whose arguments
    are supplied by a helper in compose.py rather than written into the note, with the helper named.
    It is checked backwards: an entry whose row now names its arguments is stale.

    WHAT IT CANNOT CATCH: whether the named producer actually produces it, whether it produces the
    right thing, or whether an argument named in a note is passed at the call P4 writes. The tables
    are data.
    """
    req = _required_params(src_dir)
    rows = _rows_with_prose(src_dir)
    exempt = {}
    path = os.path.join(src_dir, "spine", "compose.py")
    whole = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            whole = fh.read()
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            try:
                tree = ast.parse(fh.read())
            except SyntaxError:
                tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(
                        getattr(t, "id", "") == "ROW_ARGUMENTS_ELSEWHERE" for t in node.targets):
                    v = node.value
                    if isinstance(v, ast.Call):
                        v = v.args[0] if v.args else None
                    if isinstance(v, ast.Dict):
                        for k, val in zip(v.keys, v.values):
                            if isinstance(k, ast.Constant) and isinstance(val, ast.Constant):
                                exempt[k.value] = val.value

    # Rows are in source order, so "earlier" is every row before this one in the same table. The
    # ASSEMBLY table runs once before the loop and the LOOP table runs many times, so a LOOP row may
    # also consume anything the ASSEMBLY table produced -- both are folded in, in order.
    produced_before = {}
    running = []
    for lineno, key, prose, prod in rows:
        produced_before[(lineno, key)] = list(running)
        running.append((lineno, key, prose, prod))

    # The declared surface of every package -- levers plus the d_ fields the wire table lands. From
    # the RUNNING registry, for the reason K4 gives: an oracle that has drifted from the real
    # declarations is a SMALLER oracle, and a smaller oracle passes by having nothing to compare.
    declared = {}
    try:
        sys.path.insert(0, src_dir)
        try:
            from spine.assemble import PACKAGES as _PKGS, COUPLINGS as _CPL
            for _p, _cls in _PKGS.items():
                declared[_p] = set(_cls._levers)
            for _c in _CPL:
                _p, _, _f = str(_c.dst).partition(".")
                if _p in declared:
                    declared[_p].add(_f)
        finally:
            if sys.path and sys.path[0] == src_dir:
                sys.path.pop(0)
    except Exception:                                # noqa: BLE001 -- a synthetic tree may have none
        declared = {}

    findings, checked, seen = [], 0, set()
    for lineno, key, prose, prod in rows:
        want = req.get(key)
        if not want:
            continue
        checked += 1
        seen.add(key)
        if key in exempt:
            continue
        # PROVENANCE, AGAINST THE `produces` COLUMN -- not against whether the row restates the name.
        #
        # TWO HEURISTICS WERE TRIED AND BOTH FAILED, and the failures are why this column exists.
        # "The row must restate every required argument" gave 30 findings, mostly rows declining to
        # repeat `h`, `step`, `now` or `x`; restating every argument in every note turns the tables
        # into a second copy of the signatures, and a second copy is what this whole design exists to
        # prevent. "The name must appear somewhere else in compose.py" gave 25, and flagged
        # LM.lm_loss's `y` and FAB.forward's `h` -- produced by the row immediately above -- while
        # still catching the real four. Neither heuristic can separate "produced by an earlier row"
        # from "mentioned in passing", because THE TABLES DID NOT RECORD WHAT A ROW PRODUCES.
        #
        # So they do now: a row is (stage, PREFIX, entry, receives, produces), and `produces` names
        # the values that row yields for later rows to consume. That is the same discipline the wire
        # ledger already follows one level down -- src and dst, both named -- and it is the only
        # thing that makes "nothing supplies this argument" a decidable question rather than a
        # judgement call.
        earlier = set()
        for _ln, _k, _pr, _pd in produced_before.get((lineno, key), []):
            earlier |= set(_pd)
        # NO PROSE ESCAPE. The first version read
        #     if a not in earlier and not re.search(r"\b" + a + r"\b", prose)
        # -- an argument counted as produced when the CONSUMING ROW'S OWN NOTE contained the word.
        # That made the entire `produces` column optional, and a reviewer demonstrated it end to end:
        # deleting EVAL.curve_probe from DEFERRED_ENTRY_POINTS and adding a four-element row reading
        #     ("R", "EVAL", "curve_probe", "(units_by_domain, logits_fn, rng)")
        # -- no produces column at all, no producer anywhere in the tree -- passed K6 and K10 with
        # the suite green. Spelling the two words was the entire fix K10 demanded. Of 137 checked
        # pairs, the column was the sole justification for 8; the other 129 rode the note.
        # It also reopened the ordering the column exists to close: with a producer token moved to a
        # row AFTER its consumer, K10 correctly failed -- and one sentence of prose in the consuming
        # row's note made it pass again.
        # This is the same hole K6 had, in the check written to close K6's class, four hours later.
        # An argument is produced by an EARLIER row's column, or by a declared helper in
        # ROW_ARGUMENTS_ELSEWHERE, or it is not produced.
        # A LEVER BINDING IS A PRODUCER; A BARE MENTION IS NOT. The distinction is the whole point.
        # Removing the prose escape left 30 rows failing, and most were arguments the root reads off
        # a Config -- DATA.data_plan's `epochs=RUN.epochs`, FAB.build's `d_model=LM.width`,
        # RUN.new_clock's `batch_windows=OPT.batch_windows`. Those ARE produced: by the assembly,
        # which is the thing this whole spine exists to do, and K7 already checks that every such
        # read names a declared lever or wire. Refusing them would push the root toward writing rows
        # for values that have no row to come from.
        # But the binding must be WRITTEN AS ONE -- `arg=PKG.field` -- not merely mentioned. That is
        # what separates it from the escape a reviewer defeated: "(units_by_domain, logits_fn, rng)"
        # names three words and no origin; "epochs=RUN.epochs" names an owner and a field, and is
        # wrong in a way a reader can see.
        bound = set()
        for arg, pfx, field in re.findall(
                r"\b([a-z_][a-z_0-9]*)\s*=\s*([A-Z]{2,5})\.([a-z_][a-z_0-9]*)", prose):
            if field in declared.get(pfx, set()):
                bound.add(arg)
        # A LITERAL IS A PRODUCER TOO. `epoch=0` on the epoch-0 draw is the root supplying a constant,
        # which is as complete an answer to "where does this come from" as a lever read is -- and
        # more auditable than either, since the value is on the page. Numbers, quoted strings and the
        # three singletons only; a bare name is NOT a literal and stays unproduced.
        for arg in re.findall(
                r"\b([a-z_][a-z_0-9]*)\s*=\s*(?:-?\d+(?:\.\d+)?|'[^']*'|\"[^\"]*\"|True|False|None)\b",
                prose):
            bound.add(arg)
        # A MODULE CONSTANT IS A PRODUCER. `subsystems=RNG_SUBSYSTEMS` names a declaration at the
        # top of compose.py -- as complete an answer as a lever read, and one K8 separately checks
        # every member of. ALL-CAPS only, so a bare name still counts for nothing.
        for arg in re.findall(r"\b([a-z_][a-z_0-9]*)\s*=\s*([A-Z][A-Z_0-9]{2,})\b", prose):
            bound.add(arg[0])
        unproduced = [a for a in want if a not in earlier and a not in bound]
        if unproduced:
            findings.append(
                f"src/spine/compose.py:{lineno}  the {key} row calls for "
                f"{', '.join(repr(m) for m in unproduced)}, and no earlier row's `produces` column "
                f"yields {'them' if len(unproduced) > 1 else 'it'}. Either add the value to the "
                f"producing row's `produces` column, name the "
                f"producer in this row's note, or move the entry point to DEFERRED_ENTRY_POINTS with "
                f"that gap as the reason -- which is what the identical gap earned "
                f"EVAL.holdout_probe.")
    for key, why in sorted(exempt.items()):
        if key not in seen:
            findings.append(f"ROW_ARGUMENTS_ELSEWHERE names {key!r} ({str(why)[:50]!r}) and no row "
                            f"requires arguments for it. A stale exemption is a row nobody can retire.")
    return _report("K10", "every required argument is produced by an earlier row", not findings,
                   f"{checked} row(s) whose entry point takes required arguments, against "
                   f"{sum(len(v) for v in req.values())} required parameter(s) across "
                   f"{len(req)} signature(s); {len(exempt)} exemption(s). An argument is produced "
                   f"ONLY by an EARLIER row's `produces` column or a declared helper -- a mention in "
                   f"the consuming row's own note counts for nothing", findings,
                   vacuous=not checked)



# ==================================================================================================
# K11 -- a produces entry must name something its entry point actually returns
# ==================================================================================================

def check_k11_produces_is_not_fabricated(src_dir=SRC):
    """K11 -- every name in a row's `produces` column appears in that entry point's own docstring.

    THE DEFECT, AND IT IS THE ONE K10 CREATED. K10 makes provenance decidable by trusting the
    `produces` column -- so a column entry naming a value its entry point does not return is a
    fabricated provenance that K10 then CERTIFIES. A reviewer found nine, covering fourteen tokens:
    LM.build_model producing `key_fn` and `head` (it returns a model; both are compose's partial
    applications), SIG.build producing `encode` (it returns SigState), TOK.tokenize producing
    `windows_in_epoch`, `run_windows` and `bytes_per_window` (it returns a Segmentation; all three
    are compose helpers), CKPT.Retention.consider producing `reason` and `suffix` (it returns a
    BestAction), FAB.forward producing `owners` (a join with no named helper), TOK.mint_burst
    producing a RetokEvent the same table says is "DECLARED BY NO ENTRY POINT'S DOCSTRING".

    Five of the nine SAY SO in their own prose, which is honest writing and does not help: K10 reads
    the token, not the sentence. compose.py's own header already names the legal move for a
    helper-supplied argument -- ROW_ARGUMENTS_ELSEWHERE with the helper named -- and a `produces`
    entry on another package's row is not it.

    HOW IT DECIDES, and this is a weak test on purpose. The name must appear somewhere in the entry
    point's docstring or its module's -- which is where every package declares its RECORD TYPES
    RETURNED. It cannot tell a returned field from a mention, and it does not try: what it makes
    impossible is inventing a name out of nothing, which is what all nine were.

    WHAT IT CANNOT CATCH: a docstring that names a field the code will not return (nothing here
    executes), and a return whose fields the docstring does not enumerate -- which is itself worth
    reporting, so the count of entry points with no discoverable return text is printed.
    """
    rows = _rows_with_prose(src_dir)
    docs, undocumented = {}, []
    for pfx, d in sorted(PKG_DIR.items()):
        path = os.path.join(src_dir, d, "api.py")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        mod_doc = ast.get_docstring(tree) or ""
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and not node.name.startswith("_"):
                docs[f"{pfx}.{node.name}"] = (ast.get_docstring(node) or "") + "\n" + mod_doc
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            and not sub.name.startswith("_"):
                        docs[f"{pfx}.{node.name}.{sub.name}"] = \
                            (ast.get_docstring(sub) or "") + "\n" + mod_doc

    findings, checked, seen = [], 0, set()
    for lineno, key, _prose, prod in rows:
        if (lineno, key) in seen:
            continue
        seen.add((lineno, key))
        # A COMBINED ROW'S produces COLUMN IS THE UNION OF ITS CALLS. One row reads
        #     ("B", "LM", "encode/decode/lm_loss", ...)
        # and _rows_with_prose splits it into three keys, each handed the whole column -- so
        # per_window_loss, which lm_loss returns, was reported as fabricated on encode and on decode.
        # The row names three calls on one line; its column describes what the three produce
        # between them, and attributing each token to one of them is a precision this table does not
        # have. Any entry point the row names may account for a token.
        siblings = [k for _l, k, _p, _d in rows if _l == lineno]
        doc = "\n".join(docs.get(k, "") for k in siblings)
        if not doc.strip():
            continue
        for tok in sorted(prod):
            checked += 1
            # A DECLARED RENAME IS HONEST. The root's job includes handing one returned value to
            # several packages under the names their signatures use: CKPT.load returns a Snapshot and
            # the same Snapshot.payload reaches five packages as `state`, `saved`, `sd`, `restored`
            # and `resume`. The column writes those as "state -- Snapshot.payload, under the spelling
            # DATA.restore_stream_state uses", so the EXPLANATION names the real field even though
            # the token does not. Refusing that would push the root toward one spelling and thirteen
            # signatures changed to match, which is the opposite of the frozen contract.
            # So: the token, OR a `Something.field` in its explanation whose field the docstring
            # names. A rename must SAY what it renames.
            # TWO DECLARED FORMS FOR A RENAME, and both must NAME the real thing:
            #   `alias -- Type.field ...`     the returned record's field, spelled out
            #   `alias = real -- ...`         for a return with no record type to qualify against,
            #                                 which lm_loss has: it returns a bare
            #                                 "(per_window: (B,), mean: scalar)" and four rows take
            #                                 per_window under four names.
            # Prose alone is not a rename. "saved -- the same field" named nothing and passed
            # nothing; "saved -- Snapshot.payload again" names the field and is checkable.
            renamed = any(re.search(r"\b" + re.escape(f) + r"\b", doc)
                          for _t, f in re.findall(r"\b([A-Z][A-Za-z0-9]*)\.([a-z_][a-z_0-9]*)",
                                                  prod[tok]))
            alias = re.match(r"\s*=\s*([A-Za-z_][A-Za-z_0-9]*)", prod[tok])
            if alias and re.search(r"\b" + re.escape(alias.group(1)) + r"\b", doc):
                renamed = True
            if not re.search(r"\b" + re.escape(tok) + r"\b", doc) and not renamed:
                findings.append(
                    f"src/spine/compose.py:{lineno}  the {key} row claims to produce {tok!r}, and "
                    f"nothing in that entry point's docstring or its module's RECORD TYPES RETURNED "
                    f"block mentions it. K10 reads this column as provenance, so a name invented "
                    f"here is a fabricated producer that K10 then certifies. If a helper in "
                    f"compose.py supplies it, that is ROW_ARGUMENTS_ELSEWHERE on the CONSUMING row, "
                    f"with the helper named.")
    return _report("K11", "no produces entry names a value its entry point does not return",
                   not findings,
                   f"{checked} produces entr(y/ies) across {len(seen)} row(s), against "
                   f"{len(docs)} documented entry point(s)", findings, vacuous=not checked)



# ==================================================================================================
# K12 -- a deferral reason must name every argument that has no producer
# ==================================================================================================

def check_k12_deferral_reasons_are_complete(src_dir=SRC):
    """K12 -- a deferred entry point's reason names every required argument nothing produces.

    A DEFERRAL REASON IS AN ARGUMENT, and an argument that is wrong is worse than none: it is the
    thing the next reader trusts instead of checking. A reviewer found two false ones and one
    incomplete, and the incomplete one is the shape this check generalises --

        FAB.contribution: "Two arguments have no producer."  Four do.
        CAP.observe:      the reason omits a sixth required argument entirely.

    WHICH OMISSIONS COUNT, because most do not. A deferred entry point typically requires arguments
    that ARE produced -- FAB.contribution's h, signature, head and targets all come off earlier
    rows, and `rng` comes off RUN.streams. Those are not why it is deferred and a reason listing
    them would be noise. What the reason must account for is exactly the arguments with NO producer:
    those are the deferral, and a reason that names two of four is a claim the reader will act on.

    HOW `produced` IS COMPUTED HERE: the union of every row's `produces` column, plus the declared
    helper exemptions, plus explicit bindings in any row's note. Not "earlier rows" -- a deferred
    entry point has no row, so it has no position, and the honest question is whether the value
    exists anywhere in the assembly at all.

    WHAT IT CANNOT CATCH: a reason that names the right arguments and says something false ABOUT
    them. EVAL.null_excess's reason claimed real/permute "are produced by the verdict machinery,
    which is P6's" -- and the dependency runs the other way, since EVAL.verdicts takes neither and
    null_excess's own docstring calls itself "the permutation null every 2-sigma verdict is judged
    against". Naming the consumer as the producer passes this check. Only reading does.
    """
    rows = _rows_with_prose(src_dir)
    req = _required_params(src_dir)
    deferred = _deferred_entry_points(src_dir)
    exempt = {}
    path = os.path.join(src_dir, "spine", "compose.py")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            try:
                tree = ast.parse(fh.read())
            except SyntaxError:
                tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(
                        getattr(t, "id", "") == "ROW_ARGUMENTS_ELSEWHERE" for t in node.targets):
                    v = node.value
                    if isinstance(v, ast.Call):
                        v = v.args[0] if v.args else None
                    if isinstance(v, ast.Dict):
                        for k, val in zip(v.keys, v.values):
                            if isinstance(k, ast.Constant) and isinstance(val, ast.Constant):
                                exempt[k.value] = val.value

    produced = set()
    for _ln, _k, prose, prod in rows:
        produced |= set(prod)
        for arg, _p, _f in re.findall(
                r"\b([a-z_][a-z_0-9]*)\s*=\s*([A-Z]{2,5})\.([a-z_][a-z_0-9]*)", prose):
            produced.add(arg)
    for why in exempt.values():
        for arg in re.findall(r"\b([a-z_][a-z_0-9]*) is ", str(why)):
            produced.add(arg)

    findings, checked = [], 0
    for key, why in sorted(deferred.items()):
        want = req.get(key)
        if not want:
            continue
        checked += 1
        gaps = [a for a in want if a not in produced]
        unnamed = [a for a in gaps if not re.search(r"\b" + re.escape(a) + r"\b", str(why))]
        if unnamed:
            findings.append(
                f"{key} is deferred, and {len(gaps)} of its {len(want)} required argument(s) have "
                f"no producer -- but the reason does not name "
                f"{', '.join(repr(u) for u in unnamed)}. A reason that accounts for some of the gap "
                f"is what the next reader acts on instead of checking, and a reason listing two of "
                f"four is how FAB.contribution's already read.")
    return _report("K12", "every deferral reason names the arguments that have no producer",
                   not findings,
                   f"{checked} deferred entr(y/ies) with required arguments, against "
                   f"{len(produced)} value(s) the assembly produces", findings, vacuous=not checked)


# ==================================================================================================
# K13 -- a number written in prose must equal the number in the tree, and a question may not
#        assert that something is absent while the tree declares it
# ==================================================================================================
#
# WHY THIS CHECK EXISTS, IN THE RECORD THAT PRODUCED IT. Counts written in this contract's prose have
# been wrong five separate times, every one found by a human reading and every one a `grep` away:
#   * the geometry manifest's field count, written 15 and 16 against 20 in three live statements;
#   * `WORLD.geometry` called five fields against six;
#   * `CKPT.check_geometry` called "two arguments" against four;
#   * "121 entry points" against 123, in four present-tense places at once;
#   * "6 rejected candidates in NOT_WIRES" against 7.
# And once in the other direction: Q-OPT-3's heading said "nothing in this system clips gradients"
# while `OPT.grad_clip` was declared four hundred lines below it. A count in prose is a copy of a
# fact, and this repository's own name for a copy that drifts is C12.

_K13_PAST = re.compile(r"\b(?:was|were|had|used\s+to|stood\s+at|historically|no\s+longer)\b"
                       r"|\buntil\s+20\d\d", re.I)
_K13_TRANSITION = re.compile(r"(?:→|->)\s*\**\d*\s*$")

# WHERE A SENTENCE STOPS BEING ONE CLAIM. The tense skip used to switch off for a WHOLE SENTENCE, so
# one "was" anywhere in it silenced every number in it: "Everything above is prose about these 123
# entry points" sat inside a sentence that also recounted what the count HAD been, and went unchecked.
# Measured: seven live claims were switched off that way, six of which the tree could confirm on the
# spot. The window is now the clause holding the number, and a clause that is itself historical is
# still skipped -- so a history keeps its numbers and a live claim beside one stops hiding behind it.
_K13_CLAUSE = re.compile(r"(?:[;:|]|\s—\s|\s--\s|,\s+(?:and|but|while|which|so|because|until)\s+)")

# THE FLOOR IS THE ONLY THING THAT MAKES A REWORD LOUD. K13's patterns are literal English shapes, so
# rewording a claim out of a shape removes it from the population and nothing says so: the checked
# count drops and the check still prints PASS. That is the same green-tick-over-a-shrinking-set the
# VACUOUS marker exists to refuse, one step short of empty -- and 60 of the survey's 475 records are
# guards whose condition cannot be satisfied. Zero is not the only dishonest population.
#
# So the size is DECLARED here and compared. Deleting prose legitimately lowers it; lowering this
# number is then a deliberate line in a diff with a reason beside it, which is the whole difference
# between a population that shrank and a population that was allowed to shrink.
_K13_FLOOR = 50


def _k13_clause(sentence, offset):
    """The clause of `sentence` containing the character at `offset`, for the tense test."""
    parts, last = [], 0
    for c in _K13_CLAUSE.finditer(sentence):
        parts.append((last, c.start()))
        last = c.end()
    parts.append((last, len(sentence)))
    for a, b in parts:
        if a <= offset < b:
            return sentence[a:b]
    return sentence

# (label printed in the detail line, regex, quantity per capture group, words the sentence must
# contain for the match to count). The labels ARE the report: a reader has to be able to see the
# shape of what was searched for, and therefore the shape of what was not.
_K13_PATTERNS = (
    ("<n> of <m> entry points",
     r"\b(\d+)\s+of\s+(?:the\s+)?(\d+)\s+(?:frozen\s+)?entry[- ]points\b",
     ("stubs", "entry_points"), ()),
    ("<n> of <m>, in a sentence that says 'entry point'",
     r"\b(\d+)\s+of\s+(\d+)\b", ("stubs", "entry_points"), ("entry point",)),
    ("<n> entry points",
     r"\b(\d+)\s+(?:frozen\s+|documented\s+)?entry[- ]points\b", ("entry_points",), ()),
    ("<n> declared deferred / <n> deferred entries",
     r"\b(\d+)\**\s+(?:declared\s+deferred|deferred\s+entr)", ("deferred",), ()),
    ("<n> declared levers",
     r"\b(\d+)\**\s+(?:of\s+the\s+)?declared\s+levers\b", ("levers_total",), ()),
    ("<n> declared, in a sentence that says 'entry point'",
     r"\b(\d+)\**\s+declared\b", ("entry_points",), ("entry point",)),
    ("### <PFX> ... (<n> levers)",
     r"^###\s+([A-Z][A-Z]{1,4})\s+—\s+`src/\w+/api\.py`\s*\((\d+)\s+levers\b",
     ("PFX", "levers"), ()),
    ("<n> couplings / <n> coupling rows",
     r"\b(\d+)\s+(?:declared\s+)?coupling\s*(?:rows?|s)?\b", ("couplings",), ()),
    ("<n> of <m>, in a sentence that says 'budget' or 'ledger'",
     r"\b(\d+)\s+of\s+(?:a\s+)?(\d+)\b", ("wires", "wire_budget"), ("budget", "ledger")),
    ("<n> cross-package wires",
     r"\b(\d+)\s+cross-package\s+wires\b", ("wires",), ()),
    ("<n> intra-package",
     r"\b(\d+)\s+intra-package\b", ("intra_couplings",), ()),
    ("<n> rejected candidates",
     r"\b(\d+)\s+rejected\s+candidates?\b", ("not_wires",), ()),
    ("<n> fields, in a sentence that says 'manifest' or 'geometry'",
     r"\b(\d+)\s+fields\b", ("manifest_fields",), ("manifest", "geometry")),
    ("<n> RNG subsystems",
     r"\b(\d+)\s+(?:declared\s+)?RNG\s+subsystems?\b", ("rng_subsystems",), ()),
    ("<n> rows in ASSEMBLY_ORDER / LOOP_ORDER",
     r"\b(\d+)\s+rows?\s+in\s+`?(ASSEMBLY_ORDER|LOOP_ORDER)`?", ("ORDER", "order_rows"), ()),
    ("<n> entries in ROW_ARGUMENTS_ELSEWHERE",
     r"\b(\d+)\s+entr(?:y|ies)\s+in\s+`?ROW_ARGUMENTS_ELSEWHERE`?",
     ("row_arguments_elsewhere",), ()),
    ("a mapping spanning <n> packages",
     r"spanning\s+(\d+)\s+packages\b", ("packages",), ()),
    ("the census's <n>",
     r"census['’]s\s+(\d+)\b", ("census_old_rows",), ()),
    ("<n> census rows",
     r"\b(\d+)\s+census\s+rows?\b", ("census_rows",), ()),
    ("The <n> is unchanged, in a sentence that says 'census'",
     r"\bThe\s+(\d+)\s+is\s+unchanged\b", ("census_old_rows",), ("census",)),
)

# A heading asserts an ABSENCE when one of these stands in the question half of it. `no` and `not`
# are in the list on purpose -- narrowing to `nothing` alone would have missed nothing yet, but the
# suppression rule below, not this list, is what keeps the arm quiet.
_K13_NEG = re.compile(r"\b(?:nothing|nobody|never|neither|none|nowhere|no|not|cannot|"
                      r"can't|doesn't)\b", re.I)

# Words that carry no identity. A name whose only matching part is one of these has not been
# described by the heading, it has been described by English.
_K13_STOP = frozenset("""the and for with that this its are was were has have from into any all one
two but who how what when which than then only does did not can cannot system tree contract
resolved measurable open nothing never neither none nowhere also own new old still would there
here about over under both each same other""".split())


def _k13_parse(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _k13_seq_len(tree, name):
    """len() of the literal sequence/dict assigned to `name` at module level, or None."""
    if tree is None:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == name for t in node.targets):
            v = node.value
            if isinstance(v, ast.Call) and v.args:        # types.MappingProxyType({...})
                v = v.args[0]
            if isinstance(v, (ast.Tuple, ast.List, ast.Set)):
                return len(v.elts)
            if isinstance(v, ast.Dict):
                return len(v.keys)
    return None


def _k13_dict_in_function(tree, func, var):
    """len() of the dict literal bound to `var` inside `func` (or returned by it), or None."""
    if tree is None:
        return None
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == func):
            continue
        for st in ast.walk(node):
            if (isinstance(st, ast.Assign) and len(st.targets) == 1
                    and getattr(st.targets[0], "id", "") == var
                    and isinstance(st.value, ast.Dict)):
                return len(st.value.keys)
            if var == "return" and isinstance(st, ast.Return) and isinstance(st.value, ast.Dict):
                return len(st.value.keys)
    return None


def _k13_entry_points(src_dir):
    """[(PFX, name, is_stub)] -- the same surface api_signatures() counts, plus the stub flag."""
    out = []
    for pfx, d in sorted(PKG_DIR.items()):
        tree = _k13_parse(os.path.join(src_dir, d, "api.py"))
        if tree is None:
            continue

        def _is_stub(fn):
            return any(isinstance(n, ast.Raise) and "NotImplementedError" in ast.dump(n)
                       for n in ast.walk(fn))

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                    not node.name.startswith("_"):
                out.append((pfx, node.name, _is_stub(node)))
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                            not m.name.startswith("_"):
                        out.append((pfx, f"{node.name}.{m.name}", _is_stub(m)))
    return out


def k13_live_counts(src_dir=SRC):
    """{quantity: (value, where it was counted)} -- every countable thing the prose talks about.

    Read by AST, like every other reader in this file, so it runs against the self-test's synthetic
    tree. A quantity whose source is missing is simply ABSENT from the map, and a claim about an
    absent quantity is not checked -- reported, so the reader can see the check shrank.
    """
    eps = _k13_entry_points(src_dir)
    lev, _ = declared_levers(src_dir)
    cps = []
    atree = _k13_parse(os.path.join(src_dir, "spine", "assemble.py"))
    for node in ast.walk(atree) if atree else ():
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Coupling":
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            dst, src = kw.get("dst"), kw.get("src")
            srcs = []
            if isinstance(src, ast.Constant) and isinstance(src.value, str):
                srcs = [src.value]
            elif isinstance(src, (ast.Tuple, ast.List)):
                srcs = [e.value for e in src.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if isinstance(dst, ast.Constant) and isinstance(dst.value, str):
                cps.append((srcs, dst.value))
    # A WIRE IS A COUPLING WITH A FOREIGN SOURCE. assemble.py's own header states the rule -- an
    # edge from a package to itself books nothing and spends no budget -- so the 23 rows are 19
    # wires and 4 local couplings, and the prose says "19 of 25" for the first number.
    wires = [r for r in cps if any(s.split(".")[0] != r[1].split(".")[0] for s in r[0])]
    ctree = _k13_parse(os.path.join(src_dir, "spine", "compose.py"))
    wtree = _k13_parse(os.path.join(src_dir, "spine", "wire.py"))
    budget = None
    for node in ast.walk(wtree) if wtree else ():
        if (isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "WIRE_BUDGET"
                                                 for t in node.targets)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, int)):
            budget = node.value.value

    out = {}

    def put(key, value, how):
        if value is not None:
            out[key] = (value, how)

    put("entry_points", len(eps) or None,
        "public functions and public methods in src/*/api.py")
    put("stubs", sum(1 for e in eps if e[2]) or None,
        "entry points whose body raises NotImplementedError")
    put("implemented", (len(eps) - sum(1 for e in eps if e[2])) or None,
        "entry points that do not raise NotImplementedError")
    put("levers_total", sum(len(v) for v in lev.values()) or None,
        "Lever(...) assignments in src/*/levers.py")
    for pfx, fields in lev.items():
        put("levers:" + pfx, len(fields),
            f"Lever(...) assignments in src/{PKG_DIR.get(pfx, '?')}/levers.py")
    put("packages", len(lev) or None, "packages with a levers.py declaring a PREFIX")
    put("couplings", len(cps) or None, "Coupling(...) calls in spine/assemble.py")
    put("wires", len(wires) or None, "couplings with a source outside the destination's package")
    put("intra_couplings", (len(cps) - len(wires)) or None, "couplings - wires")
    put("wire_budget", budget, "spine/wire.py WIRE_BUDGET")
    put("not_wires", _k13_seq_len(atree, "NOT_WIRES"), "spine/assemble.py NOT_WIRES")
    put("assembly_rows", _k13_seq_len(ctree, "ASSEMBLY_ORDER"), "compose.py ASSEMBLY_ORDER")
    put("loop_rows", _k13_seq_len(ctree, "LOOP_ORDER"), "compose.py LOOP_ORDER")
    put("deferred", _k13_seq_len(ctree, "DEFERRED_ENTRY_POINTS"),
        "compose.py DEFERRED_ENTRY_POINTS")
    put("row_arguments_elsewhere", _k13_seq_len(ctree, "ROW_ARGUMENTS_ELSEWHERE"),
        "compose.py ROW_ARGUMENTS_ELSEWHERE")
    put("rng_subsystems", _k13_seq_len(ctree, "RNG_SUBSYSTEMS"), "compose.py RNG_SUBSYSTEMS")
    put("manifest_fields", _k13_dict_in_function(ctree, "_geometry_manifest", "man"),
        "the keys of `man` in compose.py's _geometry_manifest")
    put("periods", _k13_dict_in_function(ctree, "_periods", "return"),
        "the keys compose.py's _periods returns")
    # THE CENSUS IS THE OWNER'S LEDGER AND LIVES OUTSIDE src/. Absent on a synthetic tree, which is
    # why every use of these two keys is guarded by presence rather than assumed.
    census = os.path.join(os.path.dirname(os.path.abspath(src_dir)), ".rework", "census.json")
    if os.path.isfile(census):
        try:
            with open(census, "r", encoding="utf-8") as fh:
                groups = json.load(fh)
            put("census_rows", sum(len(g.get("entries", ())) for g in groups),
                ".rework/census.json entries")
            put("census_old_rows",
                sum(len(g.get("entries", ())) for g in groups
                    if g.get("family") != "amendments"),
                ".rework/census.json entries outside the `amendments` group")
        except (ValueError, TypeError, AttributeError):
            pass
    return out


def _k13_sentences(text):
    """[(start, end)] -- sentence spans. A boundary is .!? followed by whitespace, or a blank line.

    `compose.py:1117` and `0.75 GB` survive this because the character after the dot is not
    whitespace. `e.g. ` does not, and splitting there costs nothing.
    """
    spans, start = [], 0
    for m in re.finditer(r"(?<=[.!?])[ \n]|\n\n", text):
        spans.append((start, m.end()))
        start = m.end()
    spans.append((start, len(text)))
    return spans


def _k13_scan(paths, counts, root):
    """Every numeric claim the patterns can see, checked against `counts`."""
    findings, examined, skipped, unchecked = [], [], [], []
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        spans = _k13_sentences(text)
        taken = []
        for label, rx, keys, ctx in _K13_PATTERNS:
            for m in re.finditer(rx, text, re.I | re.M):
                if any(a <= m.start() and m.end() <= b for a, b in taken):
                    continue          # already claimed by a more specific pattern
                span = next(((a, b) for a, b in spans if a <= m.start() < b), None)
                if span is None:
                    s_start = max(0, m.start() - 200)
                    sentence = text[s_start:m.end() + 200]
                else:
                    s_start, _s_end = span
                    sentence = text[s_start:_s_end]
                if ctx and not any(c in sentence.lower() for c in ctx):
                    continue
                taken.append((m.start(), m.end()))
                rel = os.path.relpath(path, root)
                ln = text.count("\n", 0, m.start()) + 1
                where = f"{rel}:{ln}"
                if _K13_TRANSITION.search(text[max(0, m.start() - 40):m.start()]):
                    skipped.append(f"{where} {m.group(0)!r} -- reads as a transition (N -> M)")
                    continue
                # THE CLAUSE, NOT THE SENTENCE. See _K13_CLAUSE above: the sentence-wide test
                # switched off seven live claims because something else in the same sentence was
                # written in the past. A clause that is itself historical is still skipped.
                clause = _k13_clause(sentence, m.start() - s_start)
                if _K13_PAST.search(clause):
                    skipped.append(f"{where} {m.group(0)!r} -- clause is past-tense")
                    continue
                if keys[0] == "PFX":
                    pairs = [("levers:" + m.group(1).upper(), m.group(2))]
                elif keys[0] == "ORDER":
                    pairs = [({"ASSEMBLY_ORDER": "assembly_rows",
                               "LOOP_ORDER": "loop_rows"}[m.group(2).upper()], m.group(1))]
                else:
                    pairs = list(zip(keys, m.groups()))
                for key, got in pairs:
                    if key not in counts:
                        unchecked.append(f"{where} {m.group(0)!r} -- no live source for {key!r}")
                        continue
                    want, how = counts[key]
                    examined.append((where, key))
                    if int(got) != want:
                        findings.append(
                            f"{where} says {key} = {got}; the tree has {want} ({how}). "
                            f"Matched {m.group(0)!r} by the pattern [{label}]. A count in prose is "
                            f"a copy of a fact; delete it or correct it, do not add a second copy.")
    return findings, examined, skipped, unchecked


def _k13_absence_claims(doc_text, src_dir, root_rel):
    """Arm (b): a `### Q-` heading that says a thing is ABSENT while a matching name resolves."""
    lev, _ = declared_levers(src_dir)
    eps = {}
    for pfx, name, _stub in _k13_entry_points(src_dir):
        eps.setdefault(pfx, set()).add(name.split(".")[-1])
    findings, headings, negatives = [], 0, 0
    for m in re.finditer(r"^###\s+Q-([A-Z]+)-\d+\b(.*)$", doc_text, re.M):
        headings += 1
        pfx, rest = m.group(1), m.group(2)
        # The QUESTION half only. Everything from the verdict em-dash on is the ANSWER, and an
        # answer naming the mechanism it created is not an assertion that the mechanism is absent.
        question = re.split(r"—\s*\*\*", rest, 1)[0]
        if not _K13_NEG.search(question):
            continue
        negatives += 1
        words = {w for w in re.findall(r"[a-z][a-z0-9]{2,}", question.lower())
                 if w not in _K13_STOP}
        pool = []
        pkgs = [pfx] if (pfx in lev or pfx in eps) else sorted(set(lev) | set(eps))
        for p in pkgs:
            pool += [("lever", p, n) for n in sorted(lev.get(p, ()))]
            pool += [("entry point", p, n) for n in sorted(eps.get(p, ()))]
        low = question.lower()
        for kind, p, name in pool:
            parts = [q for q in name.split("_") if len(q) >= 3]
            if not parts:
                continue
            # A PART MATCHES A WORD when the word begins with the part ("gradients" carries
            # "grad"). The reverse -- the part beginning with the word -- is allowed only for a
            # word of five characters or more, because "tok" otherwise matches `tokenize` and every
            # heading in the TOK section resolves against every entry point in it.
            if not all(any(w.startswith(q) or (len(w) >= 5 and q.startswith(w)) for w in words)
                       for q in parts):
                continue
            # IF THE HEADING NAMES IT, THE HEADING IS NOT SAYING IT IS ABSENT. `Q-SIG-1 --
            # prototype_frac has no supplier` negates a PROPERTY of a lever it spells out;
            # `Q-OPT-3 -- nothing in this system clips gradients` negates the EXISTENCE of one it
            # never learned the name of. Only the second is the stale shape.
            if name.lower() in low or name.lower().replace("_", "") in low.replace("_", ""):
                continue
            ln = doc_text.count("\n", 0, m.start()) + 1
            findings.append(
                f"{root_rel}:{ln} Q-{pfx}-{m.group(0).split('-')[2].split()[0]} asserts an absence "
                f"-- {question.strip()[:90]!r} -- while {kind} {p}.{name} is declared in the tree "
                f"and every part of its name is a word in that assertion. Either the assertion is "
                f"stale, or it must name {p}.{name} and say what is still absent about it.")
    return findings, headings, negatives


def check_k13_counts_and_absence_claims(src_dir=SRC, doc_path=DOC, floor=None):
    """K13 -- every number the prose writes about a countable thing equals the tree's number, and
    no question heading says a thing is absent that the tree declares.

    (a) THE COUNTS. Every pattern in _K13_PATTERNS is searched for in docs/04_CONTRACT.md and in
    every .py under src/, and each captured number is compared against the live tree, which is
    counted by AST here and printed with its provenance. The patterns are LISTED IN THE DETAIL LINE
    so a reader can see the size of what was examined and, more importantly, the shape of what was
    not.

    (b) THE ABSENCE CLAIMS. Every `### Q-` heading that negates something is matched, word by word,
    against the levers and entry points its own package declares. Q-OPT-3's heading said "nothing
    in this system clips gradients" while `OPT.grad_clip` was declared: both parts of the name are
    words in the assertion, and the assertion never spells the name. A heading that DOES spell the
    name is not making an existence claim -- `Q-SIG-1 -- prototype_frac has no supplier` negates a
    property of a lever it names -- and is admitted.

    WHAT IT CANNOT CATCH, AND THE LIST IS LONGER THAN THE CHECK.
      * A NUMBER WRITTEN IN WORDS. "The four accessors exist" against five, and "DEFERRED_ENTRY_
        POINTS -- fourteen" against fifteen, were both live in this document while this check was
        being written, and it saw neither. Both were found by reading.
      * TENSE. A stale count survives by sitting in a CLAUSE containing "was", "were", "had",
        "used to", "stood at", "historically", "no longer" or "until <year>" -- those are SKIPPED,
        and the skipped list is printed with its size, because a history is allowed to record the
        number it recorded. The window was the whole SENTENCE until 2026-09-02, which silenced
        seven live claims sitting beside a historical one -- six of which the tree confirmed on the
        spot once the window narrowed, and the population went 44 to 50. A live claim in a clause
        that is itself past-tense is still invisible. The
        same applies to a number written as the target of an arrow (`19 -> 17 of 25`), which is a
        transition and not a claim about today.
      * A CLAIM PHRASED DIFFERENTLY. The patterns are literal English shapes, so a claim written
        outside them -- "the manifest holds a score of fields" -- is not read. What IS now caught is
        the reword: taking an existing claim out of a matched shape drops the population, and
        `_K13_FLOOR` fails on that rather than printing a green tick over a smaller set. The floor
        does not say WHICH claim left, only that one did; the remedy is still to add the shape.
      * WHETHER THE NUMBER IS WORTH WRITING. `ROW_ARGUMENTS_ELSEWHERE["CKPT.save"]` says the count
        is deliberately absent because it "stood at 15, 16 and 20 in three live statements at
        once". This check makes a copy cheap to verify; it does not make a copy a good idea.
      * ARM (b) READS HEADINGS AND NOTHING ELSE. The same stale assertion inside a body paragraph
        is invisible to it, and its word matching is a prefix comparison, so a lever whose name
        shares no stem with the English of the assertion is invisible too.

    IT MUST NOT PASS VACUOUSLY. A tree in which the patterns match nothing, or a document with no
    `### Q-` headings, FAILS -- because "no claims found" and "no claims wrong" are the same output
    from a check that has quietly stopped reading, and this repository has sixty records of that.
    """
    root = os.path.dirname(os.path.abspath(src_dir))
    counts = k13_live_counts(src_dir)
    paths = []
    if os.path.isfile(doc_path):
        paths.append(doc_path)
    for dirpath, dirnames, filenames in os.walk(src_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        paths += [os.path.join(dirpath, f) for f in sorted(filenames) if f.endswith(".py")]
    findings, examined, skipped, unchecked = _k13_scan(paths, counts, root)

    doc = doc_text(doc_path) if os.path.isfile(doc_path) else ""
    b_findings, headings, negatives = _k13_absence_claims(
        doc, src_dir, os.path.relpath(doc_path, root))
    findings = findings + b_findings

    if not examined:
        findings.append(
            "NO NUMERIC CLAIM MATCHED ANY PATTERN in any of the "
            f"{len(paths)} file(s) read. That is a failure of this check, not a clean tree: "
            "either the prose stopped writing counts, or the shapes below stopped matching it.")
    if not headings:
        findings.append(
            f"NO `### Q-` HEADING was found in {os.path.relpath(doc_path, root)}, so arm (b) "
            "examined nothing. A check with an empty population is a check that cannot fail.")
    want_floor = _K13_FLOOR if floor is None else floor
    if len(examined) < want_floor:
        findings.append(
            f"POPULATION COLLAPSED: {len(examined)} numeric claim(s) matched, against a declared "
            f"floor of {want_floor}. The patterns are literal English shapes, so rewording a claim "
            f"out of a shape removes it from this check silently and leaves a green tick over a "
            f"smaller set. If prose was legitimately deleted, lower _K13_FLOOR in this file and say "
            f"why in the commit; if a claim was reworded, either restore the shape or add the new "
            f"one to _K13_PATTERNS. Do not leave the floor above what the tree can meet.")

    quantities = ", ".join(f"{k}={v[0]}" for k, v in sorted(counts.items()))
    shapes = "; ".join(label for label, _, _, _ in _K13_PATTERNS)
    detail = (f"{len(examined)} numeric claim(s) checked across {len(paths)} file(s), "
              f"{len(skipped)} skipped as past-tense or as a transition, "
              f"{len(unchecked)} matched with no live source; "
              f"{negatives} of {headings} `### Q-` heading(s) assert an absence"
              f"\n          LIVE COUNTS: {quantities}"
              f"\n          PATTERNS SEARCHED FOR: {shapes}"
              f"\n          NOT SEARCHED FOR: a number written in words; a claim in a past-tense "
              f"clause; any shape not listed above")
    if skipped:
        detail += "\n          SKIPPED: " + "; ".join(skipped[:8])
        if len(skipped) > 8:
            detail += f"; ... and {len(skipped) - 8} more"
    if unchecked:
        detail += "\n          NO LIVE SOURCE: " + "; ".join(unchecked[:5])
    return _report("K13", "a count in prose equals the count in the tree, and no question asserts "
                          "an absence the tree contradicts", not findings, detail, findings)


# ==================================================================================================
# K14 -- an order-table row may not supply a spelling the consuming docstring explicitly refuses
# ==================================================================================================

# A docstring that says "NOT <name>" about an argument is making a NEGATIVE claim, and negative claims
# are the ones prose loses. This finds them: `and NOT live_size`, `NOT Judgement.live_size`,
# `rather than live_size`, `never an estimate`.
# THE TRAILING SET MUST INCLUDE `:`, and leaving it out made the check report the very sentence that
# states the refusal correctly. `... and NOT live_size: decode uses this number as ...` did not match,
# so the negation was not stripped, so the token read as a supplied spelling. A check whose parser
# cannot read its own subject matter's punctuation reports the fix as the defect.
_K14_REFUSAL = re.compile(
    r"\b(?:and\s+)?(?:NOT|not)\s+(?:`)?([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)(?:`|\(\))?"
    r"(?=\s|,|\.|;|:|\)|--|$)")


def check_k14_rows_honour_stated_refusals(src_dir=SRC):
    """K14 -- no order-table row supplies an argument under a spelling that argument's own consumer
    explicitly refuses.

    THE CRITICAL THIS EXISTS FOR, and it is worth the whole check. LM.decode's frozen docstring says
    its `live_vocab` argument must be `Vocabulary.size()` -- the positional boundary where
    never-minted rows begin -- and says in as many words that it is NOT `live_size()`, because ids
    are positional (retire() pops from the match table and leaves id2bytes intact) so live_size is
    that boundary minus the retired count and passing it masks exactly that many LIVE rows to -inf.

    TWO INDEPENDENTLY WORDED ROWS in compose.py both named live_size anyway -- the `vocab` row in
    ASSEMBLY_ORDER and the `judge_probation` row in LOOP_ORDER -- so the defect an earlier audit had
    already filed against LM.decode's BODY was sitting in the wiring table, ready to be reintroduced
    the moment the loop driver was written. Neither K10 (does every argument have a producer) nor
    K11 (does a produces entry name a real return value) can see it: the argument HAS a producer and
    the field it names DOES exist. What was wrong was the CHOICE between two real fields, and the
    consumer had already written down which one is wrong.

    IT ALSO CAUGHT A HALF-FIX. Correcting the rows to name `Judgement.size` failed K11, because the
    record declared only `live_size` -- the row and the record were wrong together, and the record
    now carries `id_count` beside `live_size` with the distinction written out. A check that only
    read the rows would have certified the first repair.

    WHAT IT CANNOT CATCH, stated because the limit is the point. It reads a NEGATIVE claim that
    somebody wrote down. A consumer that requires one of two plausible fields and never says which
    is invisible here, and so is a row that supplies the wrong thing under a spelling nobody
    forbade. The remedy when a quantity has two plausible spellings is to write the refusal into the
    consumer's docstring -- which is a thing an author does, not a thing a check can do for them.
    """
    docs = doc_signatures(DOC)
    rows = _rows_with_prose(src_dir)
    entry_docs = _entry_docstrings(src_dir)

    findings, checked, refusals = [], 0, 0
    for target, text in sorted(entry_docs.items()):
        # The refusals a consumer states about its OWN arguments.
        banned = set()
        for m in _K14_REFUSAL.finditer(text):
            tok = m.group(1)
            # ONLY A CODE SPELLING COUNTS, and the first version did not check that: this file's
            # house style shouts in CAPITALS, so "NOT LIVE" and "NOT SAVING" were read as field
            # names and the check reported 788 pairs of nonsense. A refused spelling must look like
            # something a row could actually name -- dotted (`Judgement.live_size`) or snake_case
            # (`live_size`) -- and must appear in BACKTICKS somewhere in the same docstring, which
            # is how this codebase marks a value as opposed to a word.
            if tok.lower() in _K14_ENGLISH or tok.isupper():
                continue
            if "." not in tok and not re.fullmatch(r"[a-z][a-z0-9_]*", tok):
                continue
            if f"`{tok}`" not in text and f"`{tok}()`" not in text:
                continue
            banned.add(tok)
        if not banned:
            continue
        refusals += len(banned)
        # PAIRED BY ARGUMENT NAME, which is how this table actually references things. Pairing by
        # CONSUMER name was the second version and it was still untrippable on the case the check
        # exists for: the `vocab` row says "under LM.decode's spelling" and names the consumer, but
        # the `judge_probation` row says "under the same consumer's spelling" and does not -- so the
        # row carrying the defect was the one the pairing could not see. A refusal is ABOUT an
        # argument, the row SUPPLIES that argument by name, and that is the join.
        short = target.split(".")[-1]
        args = _K14_ARGS.get(target, set())
        for lineno, entry, recv, produces in rows:
            # BOTH COLUMNS. The third version read only `receives`, and the defect this check exists
            # for lives in `produces`: the `vocab` row and the `judge_probation` row DECLARE
            # live_vocab as something they hand to later rows, they do not receive it. A check that
            # reads half the table is a check that cannot see half the table's claims -- and the
            # half it could not see is the half that carried the critical.
            # THE `--` IS PUT BACK. _rows_with_prose splits the produces column into {name:
            # explanation}, and the clause regex below keys on `<name> -- <value>` because that is
            # how the table is WRITTEN. Reconstructing it as "name value" left no separator, the
            # clause never matched, and K14 passed on a tree carrying the defect it was built for --
            # untrippable, which is the one outcome worse than a false positive and the class this
            # repository has sixty records of.
            joined = " ; ".join(f"{k} -- {v}" for k, v in (produces or {}).items()) \
                if isinstance(produces, dict) else str(produces or "")
            prose = recv + " ; " + joined
            about = [a for a in args if re.search(r"\b" + re.escape(a) + r"\b", prose)]
            if entry != target and short not in prose and target not in prose and not about:
                continue
            checked += 1
            for tok in sorted(banned):
                # ONLY THE VALUE CLAUSE, which is the text between `<arg> --` and the first negation
                # or the next `;` separator. Stripping negations token-by-token was not enough and
                # the failure was instructive: the `vocab` row's CORRECT prose reads
                # `live_vocab -- Vocabulary.size() ... and NOT live_size: decode uses this number
                # as the INDEX ...`, and everything after the negation is explanation that names
                # the refused spelling repeatedly BECAUSE it is refusing it. A check that reads the
                # explanation as a supply reports the fix as the defect -- and a check that cries
                # wolf gets switched off, which is the state this file's own A8 docstring warns
                # about. So the search is confined to what the row says it SUPPLIES, which is the
                # clause before the first "not".
                clause = None
                for a in about:
                    m = re.search(re.escape(a) + r"\s*--\s*(.*?)(?=;|$)", prose, re.S)
                    if m:
                        clause = _K14_REFUSAL.split(m.group(1))[0]
                        break
                if clause is None:
                    continue
                if re.search(r"\b" + re.escape(tok) + r"\b", clause):
                    findings.append(
                        f"src/spine/compose.py:{lineno}  the {entry} row supplies "
                        f"{tok!r}, which {target}'s own docstring explicitly refuses. The consumer "
                        f"wrote the refusal down because the two spellings are both real and only "
                        f"one is right; a row naming the refused one is that defect, in the wiring "
                        f"table, waiting for the driver to be written.")

    detail = (f"{refusals} stated refusal(s) across {len(entry_docs)} entry point docstring(s), "
              f"checked against {len(rows)} order-table row(s); {checked} row/consumer pair(s) "
              f"examined")
    return _report("K14", "no row supplies a spelling its consumer explicitly refuses",
                   not findings, detail, findings, vacuous=(refusals == 0 or not rows))


# Ordinary English after "not", which is never a value a row supplies. Without this the check reports
# every "not a lever", "not the tail", "not merely" in 130 docstrings.
_K14_ENGLISH = frozenset("""
a an the this that these those it its by to of in on at from for with as and or but if then so
merely only just simply always never both either neither all any some one two three yet still
because since while when where which what who whom whose how why do does did done be been being
is are was were am has have had can could may might must shall should will would
enough true false none null empty zero more less same other another new old
""".split())


# INVERTED FROM PKG_DIR, not declared again: a second directory->prefix map is one quantity with
# two answers, which is the shape this file's own checks exist to refuse.
_DIR_TO_PREFIX = {v: k for k, v in PKG_DIR.items()}


def _k14_args(src_dir=SRC):
    """{"PFX.entry": {parameter names}} — what each entry point actually takes.

    Read from the SIGNATURE by AST rather than from the contract document, because the join this
    powers has to be about the code the row will call, and a document can be stale where a signature
    cannot.
    """
    out = {}
    for d in sorted(os.listdir(src_dir)):
        path = os.path.join(src_dir, d, "api.py")
        if not os.path.isfile(path):
            continue
        pfx = _DIR_TO_PREFIX.get(d, d.upper())
        tree = _k13_parse(path)
        if tree is None:
            continue

        def names(fn):
            a = fn.args
            return {x.arg for x in list(a.args) + list(a.kwonlyargs) if x.arg not in ("self",)}

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                out[f"{pfx}.{node.name}"] = names(node)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_"):
                        out[f"{pfx}.{node.name}.{m.name}"] = names(m)
    return out


_K14_ARGS = _k14_args()


def _entry_docstrings(src_dir=SRC):
    """{"PFX.entry": docstring} for every entry point in src/*/api.py, methods included."""
    out = {}
    for d in sorted(os.listdir(src_dir)):
        path = os.path.join(src_dir, d, "api.py")
        if not os.path.isfile(path):
            continue
        pfx = _DIR_TO_PREFIX.get(d, d.upper())
        tree = _k13_parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                out[f"{pfx}.{node.name}"] = ast.get_docstring(node) or ""
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_"):
                        out[f"{pfx}.{node.name}.{m.name}"] = ast.get_docstring(m) or ""
    return out


# ==================================================================================================
# K15 -- a Gate's printed reason does not contradict the Gate it is printed on
# ==================================================================================================
#
# THE CLASS, AND WHY A CHECK RATHER THAN ANOTHER SWEEP. A Gate's `reason` is the sentence an operator
# acts on: it names a lever, spells its value, and says what that value made impossible. Four review
# rounds have now found reasons whose arithmetic does not describe the comparison made -- including
# reasons written by the round that was repairing the previous round's false equations. The invariant
# Gate whose stated job is proving ISSUES P3-H29 dead printed "FIRED (16 backward // 4 vs 10)" on
# every resumed run, and 16 // 4 is 4. Fixing those one at a time while new ones are written at the
# same rate is not convergence; this check takes the part of the class that a static reader can be
# RIGHT about, and says exactly which part that is.
#
# WHAT IT CHECKS -- four rules, each of which is a statement the source text alone settles:
#   1. every `PREFIX_NAME=` a reason spells is a DECLARED lever. An operator sent to a knob that does
#      not exist has been sent nowhere, and the name is generated (spine/lever.py::Lever.env_name_for
#      is `f"{prefix}_{self.name.upper()}"`) so there is exactly one right spelling.
#   2. a LITERAL value spelled beside that name is one the lever can hold: among its `choices` where
#      it declares them, and otherwise of its declared default's type. `SIG_MODE=off` on a lever
#      whose choices are learned/bigram describes a run that cannot be configured.
#   3. a RENDERED value -- `PREFIX_NAME={expr}` in an f-string -- is the named lever's own value.
#      This is shape (c) of the observed defect, "an equation whose two sides are rendered from
#      different quantities than the comparison performed", in the one form a static reader can
#      settle: the expression is traced back through the enclosing function's assignments, and it
#      must reach a read of that lever's field (or, on a receiving package, its `d_` wire spelling).
#   4. a reason may not assert IMPOSSIBILITY on a Gate the source declares REACHABLE. `Gate.line`
#      prints "armed, did not fire" -- the measurement words -- for `fired=False, reachable=True`,
#      so a reason saying the condition cannot be met is one line making both statements. Where
#      `reachable=` is an EXPRESSION the rule still applies to the part of the reason that prints
#      when that expression holds, whenever the source settles which part that is -- see
#      _k15_live_reason, and the sweep below for what it does and does not catch.
#   5. a reason may not SPELL a lever's value as a literal when the Gate PRINTS that same lever's
#      live value and the branch it sits on admits a range of that lever rather than one value.
#      `Gate.line` renders `(value vs threshold)` immediately before the reason, so the two are read
#      as one sentence: "armed, did not fire (-5 vs 1) -- CKPT_EVERY=0 with CKPT_DIR set" names two
#      different numbers for one lever. Render the value instead of spelling it.
#
# WHAT IT DOES NOT CHECK, AND THE MEASUREMENT BEHIND EACH REFUSAL. These are not modesty; each one
# was tried against the tree and against the commits of its history -- twenty-five for the rules
# adopted on 2026-09-03, thirty-seven for the two added on 2026-09-04 -- and dropped on evidence:
#
#   RULE 4 IS NARROW ON PURPOSE, AND THE BROAD VERSION IS REFUTED. The obvious rule -- scan a
#   reachable Gate's reason for "cannot", "never", "no ... can", "unreachable" -- was run over
#   twenty-five commits. It reported the SAME FOUR SITES at every one of them, all four correct
#   prose: a reason explaining why epoch 0 is "armed-and-did-not-fire rather than unreachable", one
#   saying a counter is "rendered here, never computed here", one arguing the state is "an UNMET
#   CONDITION and not an unreachable one", and one saying "no lift can have happened yet" about
#   lifts rather than about its own gate. It caught ZERO true instances, because the true ones were
#   `reachable=<expression>` and no static reader can evaluate those. What rule 4 uses instead is a
#   closed list of phrases that can only be about the gate carrying them, and that list was
#   calibrated the only honest way: across the same twenty-five commits it fires on THREE of them,
#   e4c5e4b through 694f156, on `Gate("opt.lr.sched", ..., reachable=True, reason="OPT_LR_SCHED=none:
#   warmup, wavelength, floor, restarts, damping, envelope and re-warm are ALL structurally
#   unreachable ...")` -- the exact instance spine/opt/api.py's own repair comment describes as "one
#   line making both statements" -- and on nothing else, ever.
#
#   A `reachable=` EXPRESSION IS SEEN ONLY WHERE THE SOURCE SETTLES WHICH ARM PRINTS. Some of this
#   tree's Gates compute reachability from the configuration; the count, and how many of them rule 4
#   reaches, are both on this check's report line. What makes the rest decidable is that
#   `Gate.line` prints the reason on BOTH arms, so a reason that branches on the SAME expression
#   `reachable=` was given has one arm that prints on a reachable run, and rule 4 applies to that
#   arm alone (_k15_live_reason). ONE NORMALISATION IS PERFORMED AND IT IS NOT INFERENCE: a
#   `reachable=bool(EXPR)` is read as `reachable=EXPR`, because `bool(X)` and `if X:` are the same
#   truthiness test. Four of this tree's computed-reachability Gates are written that way
#   (src/fabric/api.py's fab.expert_choice, fab.discover, fab.distinctness and fab.independence,
#   each `reachable=bool(EXPR)` against `reason=(A if EXPR else B)` with EXPR textually identical),
#   and the version of this file that shipped on 2026-09-04 dropped all four while its own prose
#   said the whole residue was "a second name for the same condition" -- true of two of the six and
#   false of four. What is left outside after the normalisation is a reason branching on a genuinely
#   DIFFERENT expression: a second name (`floor_reachable` against `not sched_live`), or a WEAKER
#   one (`not sched_live` against `reachable=sched_live and warmup_n > 1`). Those are left alone:
#   deciding two different expressions are one condition is inference, and this file has a
#   measurement for what inference costs.
#
#   RULE 4's DYNAMIC HALF HAS NO HISTORICAL TRUE POSITIVE AND IS SHIPPED ANYWAY, WHICH NEEDS SAYING.
#   Run over 37 trees -- every commit from 1348da6 to HEAD plus the working tree -- the arm-selecting
#   rule fires ZERO times, on correct code and on defective code alike. It is here because the ONE
#   instance rule 4 ever caught was REPAIRED INTO ITS POPULATION: `opt.lr.sched` carried
#   "structurally unreachable" under `reachable=True` at e4c5e4b, 7e902ba and 694f156, where the
#   static half catches it; the repair at 6d8eb0e made it `reachable=sched_live` with the sentence
#   on the `else` arm, which is correct and which also moved the site out of every rule in this
#   file. Measured, not argued: put that same sentence on the OTHER arm of 6d8eb0e's IfExp -- the
#   arm that prints when sched_live holds -- and the shipped check before this round PASSES while
#   the dynamic half reports it. So the guard on the tree's only recorded instance of this defect
#   survives the repair that fixed it, at a measured cost of zero false alarms.
#
#   IT CANNOT CHECK THE ARITHMETIC IN A REASON. "16 backward // 4 vs 10" is four runtime quantities;
#   nothing in the source says what they were. Rule 3 reaches the neighbouring case -- a rendered
#   value that is not the lever the same sentence names -- and stops there. Extending it to `value=`
#   and `threshold=` was tried and abandoned: those two are routinely rendered from a DERIVED
#   quantity on purpose (`f"balance={balance_w} x warm={round(bal_scale, 4)}"`), so the rule would
#   have fired on correct gates, and this repository has sixty untrippable guards on record and must
#   not gain a check that gets weakened the first time it is wrong.
#
#   IT ABSTAINS WHEN A TRACE LEAVES THE FUNCTION. Rule 3 follows local assignments only. When the
#   rendered value comes from a parameter -- `LM_ARCH={str(lm_kind)}` in memory/api.py, where the
#   composition root passes MEM's wire in -- the provenance is in another file and the rule says so
#   by not firing. How many rendered values are in that state is on this check's report line and is
#   deliberately not repeated here: this sentence said "Two of this tree's forty-eight" while the
#   check printed 49 on the same run, because four packages were edited after the prose was written.
#   Nothing can catch that -- K13's population is docs/04_CONTRACT.md plus src/**/*.py, so tests/ is
#   never scanned, and its own output line says "NOT SEARCHED FOR: a number written in words".
#
#   RULE 5 IS CALIBRATED THE SAME WAY RULE 4 WAS, AND THE BROAD VERSION IS REFUTED BY MEASUREMENT
#   -- BUT NOT BY THE MEASUREMENT THIS BLOCK USED TO QUOTE. The obvious rule is: any literal
#   spelled for the lever the Gate prints. This block said it "reports up to 15 sites at once,
#   every one of them correct prose". Both halves are wrong, and re-measuring is what found the
#   defect below. Built from the shipped code by dropping the `ranged` requirement, the numeric
#   filter and the `pinned` skip, and run over 2e8a63e, e4c5e4b, 7e902ba, 694f156, a2ffc08,
#   dd6a396, f11ae02, 40d2446 and the working tree, the broad rule reports at most SIX sites (six
#   at 2e8a63e, e4c5e4b, 7e902ba, 694f156 and a2ffc08; four at dd6a396, f11ae02, 40d2446 and the
#   working tree) -- and on the working tree three of the four are correct prose (cap.valve on
#   `if targets == "off"` beside "CAP_TARGETS=off", cap.vocab_arm_honest twice on `elif mask_dead:`
#   where `mask_dead = bool(cap.d_mask_dead_rows)` pins it) while THE FOURTH IS A REAL DEFECT. So
#   the broad rule's noise was never the only thing the narrowing removed.
#
#   What ships fires only where the branch admits a RANGE of that lever's values -- the Gate sits
#   on EITHER arm of an ordering test on the same lever, so more than one value reaches it -- and
#   only for a NUMERIC literal the branch does not pin. The `else`-only version of that was itself
#   a narrowing, and it cost a live instance: over the nine trees above the widened rule reports
#   src/ckpt/api.py's `ckpt.periodic_armed` at 2e8a63e, e4c5e4b, 7e902ba, 694f156 and a2ffc08 (the
#   false equation repaired by hand at dd6a396, and one every check in this file was green on) and
#   src/opt/api.py's `opt.lr.shift_warm` at EVERY ONE of the nine, and NO OTHER SITE at any of
#   them. cap.vocab_arm_honest -- the nearest correct-prose neighbour, and the one the broad rule
#   reports twice -- stays out because `elif mask_dead:` carries no Compare at all.

_K15_ENV = re.compile(r"\b([A-Z][A-Z0-9]*)_([A-Z0-9_]+)\s*=")
# The value token immediately after `PREFIX_NAME=`: a number, a quoted string, or a bare word. Kept
# deliberately short -- a reason writes "at FAB_N0=8/SLOTS=16", and the claim being checked is about
# the 8 and not about the rest of the sentence.
_K15_VALUE = re.compile(r"([-+]?\d[\w.]*|'[^']*'|\"[^\"]*\"|[A-Za-z][\w.\-]*)")
# Rule 4's closed list. Every phrase here is a statement about the mechanism the reason belongs to;
# none of them can be read as a remark about a neighbouring gate, which is what the four false
# positives of the broad version all were. Adding to this list means re-running the history sweep.
_K15_IMPOSSIBLE = re.compile(
    r"\b(structurally unreachable|cannot be reached|cannot fire|can never fire|could never fire|"
    r"never fires|cannot be met|can never be met|cannot be satisfied|no configuration can|"
    r"this gate cannot)\b", re.I)

_K15_GATE_FIELDS = ("name", "fired", "value", "threshold", "reachable", "reason")


def _k15_lever_specs(src_dir=SRC):
    """{"PFX_FIELD": (prefix, field, default, choices)} for every declared lever, plus findings.

    A SECOND READER OF THE SAME FILES, AND CROSS-CHECKED AGAINST THE FIRST. declared_levers() above
    answers "which fields does this package declare", which is all K4 needs; this needs the DEFAULT
    and the CHOICES as well, because rule 2 is a statement about what a lever can hold. Two readers
    of one declaration is exactly the shape this file's own header calls out, so the two are
    compared and a disagreement is reported as a finding rather than resolved silently.
    """
    out, findings = {}, []
    for pfx, d in sorted(PKG_DIR.items()):
        path = os.path.join(src_dir, d, "levers.py")
        if not os.path.isfile(path):
            continue
        tree = _k13_parse(path)
        if tree is None:
            continue
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            prefix = None
            for stmt in cls.body:
                if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                        and getattr(stmt.targets[0], "id", None) == "PREFIX"
                        and isinstance(stmt.value, ast.Constant)):
                    prefix = stmt.value.value
            if not isinstance(prefix, str):
                continue
            for stmt in cls.body:
                if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and isinstance(stmt.value, ast.Call)
                        and getattr(stmt.value.func, "id", None) == "Lever"):
                    continue
                field = stmt.targets[0].id
                call = stmt.value
                default = call.args[0].value if (call.args and isinstance(call.args[0], ast.Constant)) \
                    else None
                # Lever(default, help, unit=U.COUNT, choices=None) -- positional or keyword.
                ch = None
                for kw in call.keywords:
                    if kw.arg == "choices":
                        ch = kw.value
                if ch is None and len(call.args) >= 4:
                    ch = call.args[3]
                choices = None
                if isinstance(ch, (ast.Tuple, ast.List)):
                    choices = [c.value for c in ch.elts if isinstance(c, ast.Constant)]
                out[f"{prefix}_{field.upper()}"] = (prefix, field, default, choices)
    # The cross-check. Same files, different reader, one answer required.
    other, _ = declared_levers(src_dir)
    mine = {}
    for env, (prefix, field, _d, _c) in out.items():
        mine.setdefault(prefix, set()).add(field)
    for prefix in sorted(set(mine) | set(other)):
        diff = mine.get(prefix, set()) ^ other.get(prefix, set())
        if diff:
            findings.append(
                f"src/{PKG_DIR.get(prefix, prefix.lower())}/levers.py  the two readers of this file "
                f"disagree about which fields are levers: {sorted(diff)}. One declaration with two "
                f"answers is what both of them exist to refuse -- fix the readers, not the report.")
    return out, findings


def _k15_fragments(node):
    """A reason expression as INDEPENDENT token sequences of ("s", text) and ("h", expr).

    Independent, because a `"" if x else f"..."` has two arms and a name spelled at the end of one
    must never be paired with a hole opening the other. Same for the arguments of a helper call --
    opt/api.py wraps several reasons in `_stale_note(st, "counter", f"...")` and each argument is
    its own sentence.
    """
    if isinstance(node, ast.Constant):
        return [[("s", node.value)]] if isinstance(node.value, str) else []
    if isinstance(node, ast.JoinedStr):
        seq = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                seq.append(("s", v.value))
            elif isinstance(v, ast.FormattedValue):
                seq.append(("h", v.value))
        return [seq] if seq else []
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _k15_fragments(node.left), _k15_fragments(node.right)
        if not left:
            return right
        if not right:
            return left
        return left[:-1] + [left[-1] + right[0]] + right[1:]
    if isinstance(node, ast.IfExp):
        return _k15_fragments(node.body) + _k15_fragments(node.orelse)
    if isinstance(node, ast.Call):
        out = []
        for a in list(node.args) + [k.value for k in node.keywords]:
            out += _k15_fragments(a)
        return out
    return []


def _k15_reason_text(node):
    """Every static character of a reason, holes elided. Rule 4 reads this and nothing else."""
    return " ".join(t for seq in _k15_fragments(node) for kind, t in seq if kind == "s")


def _k15_assignments(fn):
    """({name: [value exprs]}, {names whose provenance leaves this function}) for one function.

    TUPLE UNPACKING IS THE COMMON CASE HERE AND THE FIRST VERSION DROPPED IT. fabric/api.py binds
    `balance_w, bal_floor, bal_warm_n = float(fab.balance), float(fab.bal_floor), int(fab.bal_warm)`
    on one line; a reader that only understood `name = value` reported FAB_BALANCE={balance_w} as a
    value rendered from something other than FAB_BALANCE, which is a false finding about the one
    gate in that file that is right.
    """
    assigns, opaque = {}, set()
    if fn is None:
        return assigns, opaque
    a = fn.args
    for arg in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
        opaque.add(arg.arg)                      # a parameter's value was chosen by a caller
    if a.vararg:
        opaque.add(a.vararg.arg)
    if a.kwarg:
        opaque.add(a.kwarg.arg)
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    assigns.setdefault(t.id, []).append(n.value)
                elif isinstance(t, (ast.Tuple, ast.List)):
                    elts = list(t.elts)
                    vals = list(n.value.elts) if isinstance(n.value, (ast.Tuple, ast.List)) \
                        and len(n.value.elts) == len(elts) else None
                    for i, e in enumerate(elts):
                        if isinstance(e, ast.Name):
                            assigns.setdefault(e.id, []).append(vals[i] if vals else n.value)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
            assigns.setdefault(n.target.id, []).append(n.value)
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            for t in ast.walk(n.target):
                if isinstance(t, ast.Name):
                    opaque.add(t.id)             # a loop variable is not traceable to a declaration
    return assigns, opaque


def _k15_trace(expr, assigns, opaque):
    """(names reachable from `expr`, whether the trace left this function).

    Follows every Name back through the function's own assignments and collects the attribute names
    it passes through, so `int(cap.d_mask_dead_rows)` yields `d_mask_dead_rows`. Returns `leaked`
    when it reaches a parameter or a name it cannot account for, which is the signal to ABSTAIN --
    the rule fires only when the whole provenance is visible in one function.
    """
    def _names(node):
        out = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                out.add(n.id)
            elif isinstance(n, ast.Attribute):
                out.add(n.attr)
        return out

    seen, stack, found, leaked = set(), list(_names(expr)), set(), False
    while stack:
        nm = stack.pop()
        if nm in seen:
            continue
        seen.add(nm)
        found.add(nm)
        if nm in assigns:
            for v in assigns[nm]:
                stack.extend(_names(v))
        elif nm in opaque:
            leaked = True
    return found, leaked


_K15_ORDER_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _k15_live_reason(reason, reach):
    """The part of a reason that PRINTS WHEN THE GATE IS REACHABLE, or None if that is not decidable.

    A GATE WHOSE REACHABILITY IS COMPUTED STILL SETTLES ONE THING STATICALLY. `reachable=<expr>` is
    a runtime value, so rule 4 cannot ask whether the gate ran -- but spine/gate.py::Gate.line
    prints the reason on BOTH arms ("A `reason` IS PRINTED WHENEVER IT IS SET, not only when
    unreachable"), and when the reason branches on the SAME expression `reachable=` was given, which
    arm prints on a reachable run is written in the source. Two shapes are decidable and no others:

      * `X if COND else Y` where COND is textually the reachable expression -> X, and where it is
        its negation -> Y. Nearly every computed-reachability gate in this tree writes that shape;
        how many of them key the branch on the reachable expression itself is on the report line,
        beside how many are computed at all, and neither number is spelled here for the reason the
        block above check_k15 gives.
      * a reason with no conditional in it at all -> the whole reason, which prints on both arms and
        therefore on the reachable one.

    A `bool(...)` WRAPPER AROUND THE REACHABLE EXPRESSION IS READ OFF FIRST, and that is the one
    normalisation this function performs. Four of this tree's Gates -- src/fabric/api.py's
    fab.expert_choice, fab.discover, fab.distinctness and fab.independence -- write
    `reachable=bool(EXPR)` against `reason=(A if EXPR else B)` with EXPR textually identical, and
    a comparison that refuses to see through the wrapper drops all four. Measured: coverage on this
    tree goes from 9 of 15 computed-reachability Gates to 13, rule 4's dynamic half still reports
    ZERO findings at every commit swept, and the count is on the check's report line either way.

    Anything else -- a branch keyed on a second name for the same condition, a nested conditional --
    returns None and the gate stays outside rule 4, counted and printed as such. The comparison is
    deliberately textual and deliberately not clever: `floor_reachable` and `not sched_live` may
    well be the same condition, and a rule that decides they are is a rule that has started
    inferring. See the sweep recorded in the block above check_k15 for what that costs.
    """
    if reason is None or reach is None:
        return None
    if isinstance(reason, ast.IfExp):
        # `bool(X)` AND `if X:` ARE THE SAME TRUTHINESS TEST, so a Gate written
        # `reachable=bool(EXPR)` against `reason=(A if EXPR else B)` has told the source text which
        # arm prints on a reachable run just as plainly as one written `reachable=EXPR`. Reading
        # the wrapper off is normalisation and not inference -- the two expressions are compared
        # textually afterwards exactly as before, so nothing else is decided here. THE UNWRAPPING
        # IS DELIBERATELY THE NARROWEST ONE THAT IS TRUE BY LANGUAGE RULE: only a call of the bare
        # name `bool` with exactly one positional argument and no keywords, because that is the
        # only call whose result IS the truthiness of its argument. It is not applied to a
        # sub-expression of a larger reachable expression either, since `bool(X) and Y` is not X.
        # NOT SELF-TESTED, and said here rather than left to be discovered: the cases below pin
        # the normalisation and the abstention on a second name, but no case pins the `bool`-only
        # restriction, because every fixture for it would have to branch a reason on a
        # non-boolean expression and would be modelling code this tree does not write.
        if (isinstance(reach, ast.Call) and getattr(reach.func, "id", "") == "bool"
                and len(reach.args) == 1 and not reach.keywords):
            reach = reach.args[0]
        r, t = ast.unparse(reach), ast.unparse(reason.test)
        arm = (reason.body if t == r else
               reason.orelse if t in (f"not {r}", f"not ({r})") else None)
        if arm is None or any(isinstance(n, ast.IfExp) for n in ast.walk(arm)):
            return None
        return arm
    if any(isinstance(n, ast.IfExp) for n in ast.walk(reason)):
        return None
    return reason


def _k15_value_field(value, assigns, opaque, by_field):
    """The ONE lever field a Gate's `value=` traces to, or None.

    None when the trace leaves the function, when it reaches no declared field, or when it reaches
    more than one -- `f"{a} of {b}"` is a rendered summary of two levers and the sentence beside it
    is not making a claim this rule can settle.
    """
    if value is None:
        return None
    names, leaked = _k15_trace(value, assigns, opaque)
    if leaked or not names:
        return None
    fields = {f for f in names if f in by_field}
    fields |= {f[2:] for f in names if f.startswith("d_") and f[2:] in by_field}
    return next(iter(fields)) if len(fields) == 1 else None


def _k15_branch_admits_a_range(fn, node, field, assigns, opaque):
    """(the branch admits a RANGE of that lever's values, the literals it pins by equality).

    THE QUESTION RULE 5 TURNS ON. A reason may spell `CKPT_EVERY=0` beside a printed value that IS
    CKPT_EVERY only if the branch the Gate sits in forces that lever to be 0. `if targets == "off":`
    forces it and the sentence is safe. `elif every > 0: ... else:` does NOT -- the else arm admits
    every value at or below zero -- and that is the shape the false equation had.

    BOTH ARMS OF AN ORDERING TEST ADMIT A RANGE, AND THE FIRST VERSION OF THIS HELPER ONLY LOOKED AT
    THE ELSE. That narrowing had two costs, both measured rather than argued. It missed a LIVE
    instance of the class: src/opt/api.py builds Gate("opt.lr.shift_warm", ..., value=shift_warm,
    reachable=False, reason="OPT_LR_SHIFT_WARM=0, ...") on the body of `elif shift_warm <= 0:`,
    where `shift_warm = int(opt.lr_shift_warm)` carries no clamp and no refusal, so at
    OPT_LR_SHIFT_WARM=-3 the rendered line reads "UNREACHABLE (-3 vs > 0) -- OPT_LR_SHIFT_WARM=0"
    -- two numbers for one lever in one sentence, which is exactly ckpt.periodic_armed's defect.
    And it made the repaired defect REWRITABLE past the rule: `elif every > 0: ... else: <gate>`
    and `elif every <= 0: <gate> ... else:` are the same program, and only the first was seen.

    Only the enclosing `if` statements that TEST THE SAME LEVER count, resolved through the
    function's own assignments by _k15_trace, so `every > 0` counts for the field `every` and
    `not saving_on(ckpt)` does not.
    """
    ranged, pinned = False, set()
    if fn is None:
        return ranged, pinned
    for iff in [n for n in ast.walk(fn) if isinstance(n, ast.If)]:
        in_body = any(node is sub for st in iff.body for sub in ast.walk(st))
        in_else = any(node is sub for st in iff.orelse for sub in ast.walk(st))
        if not (in_body or in_else):
            continue
        tn, _leaked = _k15_trace(iff.test, assigns, opaque)
        if field not in tn and f"d_{field}" not in tn:
            continue
        for cmp_node in [c for c in ast.walk(iff.test) if isinstance(c, ast.Compare)]:
            for op, comparand in zip(cmp_node.ops, cmp_node.comparators):
                if isinstance(op, _K15_ORDER_OPS):
                    # EITHER ARM OF AN ORDERING TEST ADMITS A RANGE, and requiring the `else` was
                    # a narrowing that let a live instance of this exact class through. `elif
                    # shift_warm <= 0:` with the Gate in the BODY is the same program as `elif
                    # shift_warm > 0: ... else:` with it in the else -- every value at or below
                    # zero reaches it either way -- and src/opt/api.py writes the first spelling.
                    # `if not (in_body or in_else): continue` above already guarantees the Gate is
                    # inside one of the two arms, so no third case is being admitted here.
                    ranged = True
                if isinstance(op, ast.Eq) and in_body and isinstance(comparand, ast.Constant):
                    pinned.add(str(comparand.value))
    return ranged, pinned


def check_k15_gate_reasons_are_self_consistent(src_dir=SRC):
    """K15 -- a Gate's reason names a lever that exists, a value that lever can hold, a rendered
    value that is that lever's, no impossibility on a Gate the source declares reachable, and no
    literal spelled for the lever the Gate prints on a branch that admits a range of it.

    THE DEFECT. `spine/gate.py::Gate` exists because 57 of the survey's 475 records are mechanisms
    that were armed and inert while the report said nothing, and 60 more are guards whose condition
    could not be satisfied at all -- two different bugs needing two different words. The `reason`
    string is where those words are chosen, and it is prose: nothing has ever read it. Every review
    round has found reasons whose printed arithmetic does not describe the comparison actually made,
    including reasons written by the round that was fixing the previous round's false equations.

    WHAT THIS PROVES AND WHAT IT DOES NOT is written out at length in the block above this function,
    including the measurements behind each thing it refuses to check. The short version: it settles
    the four claims a reason makes that the SOURCE TEXT alone can settle, and it counts and prints
    the reasons it could not reach, so the size of what is left is on the report instead of in a
    docstring.

    IT IS NOT A REPLACEMENT FOR READING THE REPORT. The Gates whose reachability is computed and
    whose reason does not branch on that same expression are outside every rule here -- the count is
    on this check's report line, split into the part rule 4 now judges and the part it does not, and
    it is not spelled in this docstring because the version that was went stale inside one round.
    The arithmetic inside a reason is runtime and is outside all of them too. This check makes the
    CHEAP contradictions impossible to ship, which is the half that was being re-found by hand every
    round.
    """
    specs, findings = _k15_lever_specs(src_dir)
    prefixes = set(PKG_DIR)
    by_field = {}
    for env, (_p, _f, _d, _c) in specs.items():
        by_field.setdefault(_f, set()).add(env)
    gates = examined_names = literals = holes = 0
    abstained_holes = dynamic_reachable = dynamic_judged = range_guarded = 0

    for d in sorted(os.listdir(src_dir)):
        pkg_dir = os.path.join(src_dir, d)
        if not os.path.isdir(pkg_dir):
            continue
        for fn_name in sorted(os.listdir(pkg_dir)):
            if not fn_name.endswith(".py"):
                continue
            path = os.path.join(pkg_dir, fn_name)
            rel = os.path.relpath(path, os.path.dirname(src_dir))
            if rel.replace(os.sep, "/").endswith("src/spine/gate.py"):
                continue                          # the record's own declaration and its examples
            tree = _k13_parse(path)
            if tree is None:
                continue
            enclosing = {}
            for f in [n for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for n in ast.walk(f):
                    enclosing.setdefault(n, f)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and (getattr(node.func, "id", None) == "Gate"
                             or getattr(node.func, "attr", None) == "Gate")):
                    continue
                gates += 1
                args = dict(zip(_K15_GATE_FIELDS, node.args))
                args.update({k.arg: k.value for k in node.keywords if k.arg})
                reason = args.get("reason")
                gate_name = args["name"].value if isinstance(args.get("name"), ast.Constant) \
                    else "<computed>"
                where = f"{rel}:{node.lineno}  Gate {gate_name!r}"
                reach = args.get("reachable")
                static_reachable = reach is None or (isinstance(reach, ast.Constant)
                                                     and reach.value is True)
                is_dynamic = reach is not None and not isinstance(reach, ast.Constant)
                if is_dynamic:
                    dynamic_reachable += 1
                if reason is None:
                    continue
                fn = enclosing.get(node)
                assigns, opaque = _k15_assignments(fn)

                # ---- rule 4: impossibility asserted on a gate the source says RAN ----------------
                if static_reachable:
                    m = _K15_IMPOSSIBLE.search(_k15_reason_text(reason))
                    if m:
                        findings.append(
                            f"{where} is built reachable and its reason says {m.group(0)!r}. "
                            f"spine/gate.py::Gate.line prints 'FIRED' or 'armed, did not fire' for "
                            f"a reachable gate -- the words reserved for a mechanism that RAN -- so "
                            f"this one line says the condition was tested and says it cannot be "
                            f"met. If the mechanism really cannot fire here, pass reachable=False; "
                            f"if it ran and was not satisfied, the reason must not say otherwise.")
                elif is_dynamic:
                    # THE COMPUTED-REACHABILITY HALF, and it is where this class actually lives: the
                    # one instance the tree ever had was repaired INTO this population and out of
                    # the branch above. _k15_live_reason picks the arm that prints on a reachable
                    # run, and the same closed phrase list is applied to that arm alone.
                    live = _k15_live_reason(reason, reach)
                    if live is not None:
                        dynamic_judged += 1
                        m = _K15_IMPOSSIBLE.search(_k15_reason_text(live))
                        if m:
                            findings.append(
                                f"{where} is reachable exactly when "
                                f"`{ast.unparse(reach)}` holds, and the part of its reason that "
                                f"prints in that case says {m.group(0)!r}. A gate that RAN may not "
                                f"describe itself as one that cannot -- spine/gate.py::Gate.line "
                                f"puts 'FIRED' or 'armed, did not fire' in front of this sentence "
                                f"on exactly those runs. Put the impossibility on the arm that "
                                f"prints when the expression is false, where the line reads "
                                f"UNREACHABLE.")

                # ---- rule 5: a literal value spelled for the lever the gate PRINTS ---------------
                # THE FALSE EQUATION REPAIRED BY HAND AT dd6a396, made impossible to ship again.
                # ckpt/api.py built Gate("ckpt.periodic_armed", False, every, 1, reason="CKPT_EVERY=0
                # with CKPT_DIR set: ...") on the `else` of `elif every > 0`, so at CKPT_EVERY=-5 the
                # line read "armed, did not fire (-5 vs 1) -- CKPT_EVERY=0 with CKPT_DIR set": the
                # printed value and the named value contradicting each other in one sentence. The
                # rule fires only where the printed value IS that lever and the branch admits a
                # RANGE of its values, which is what makes the spelled literal a guess.
                # AND THE SAME SHAPE ON THE BODY ARM IS THE SAME DEFECT: `elif shift_warm <= 0:`
                # with the Gate inside it admits every value at or below zero exactly as the else
                # of `elif shift_warm > 0:` would. See _k15_branch_admits_a_range.
                field = _k15_value_field(args.get("value"), assigns, opaque, by_field)
                if field is not None and not any(isinstance(n, ast.IfExp)
                                                 for n in ast.walk(reason)):
                    ranged, pinned = _k15_branch_admits_a_range(fn, node, field, assigns, opaque)
                    if ranged:
                        range_guarded += 1
                        for seq in _k15_fragments(reason):
                            for i, (kind, text) in enumerate(seq):
                                if kind != "s":
                                    continue
                                for m in _K15_ENV.finditer(text):
                                    env = f"{m.group(1)}_{m.group(2)}"
                                    if env not in by_field[field]:
                                        continue
                                    rest = text[m.end():]
                                    if not rest.strip() and i + 1 < len(seq) \
                                            and seq[i + 1][0] == "h":
                                        continue          # rendered: that is rule 3's question
                                    v = _K15_VALUE.match(rest.lstrip())
                                    if not v:
                                        continue
                                    tok = v.group(1).rstrip(".,;:").strip("'\"")
                                    try:
                                        float(tok)
                                    except ValueError:
                                        continue          # a numeric lever's value, or nothing
                                    if tok in pinned:
                                        continue
                                    findings.append(
                                        f"{where} prints {field!r} as its value and its reason "
                                        f"spells {env}={tok} as a literal, on a branch that admits "
                                        f"a RANGE of that lever's values rather than that one. "
                                        f"Gate.line renders the live value beside the reason, so "
                                        f"every other value reaching this arm produces one "
                                        f"sentence naming two different numbers for one lever. "
                                        f"Render it -- "
                                        f"f\"{env}={{{ast.unparse(args['value'])}}}\" -- instead "
                                        f"of spelling it.")

                # ---- rules 1-3: the lever names, values and rendered quantities ------------------
                for seq in _k15_fragments(reason):
                    for i, (kind, text) in enumerate(seq):
                        if kind != "s":
                            continue
                        for m in _K15_ENV.finditer(text):
                            prefix, tail = m.group(1), m.group(2)
                            if prefix not in prefixes:
                                continue          # not a name claiming to be this tree's lever
                            env = f"{prefix}_{tail}"
                            examined_names += 1
                            spec = specs.get(env)
                            if spec is None:
                                findings.append(
                                    f"{where} names {env} and no package declares it. An operator "
                                    f"reading this line is sent to a knob that does not exist; "
                                    f"env names are GENERATED as PREFIX_FIELD, so there is exactly "
                                    f"one right spelling and this is not it.")
                                continue
                            _pfx, field, default, choices = spec
                            rest = text[m.end():]
                            # `.strip()` and not `not rest`: an f-string may be written
                            # `f"{env}= {value}"`, and reading the space as "no rendered value here"
                            # would drop the site silently rather than check it.
                            if not rest.strip() and i + 1 < len(seq) and seq[i + 1][0] == "h":
                                holes += 1
                                names, leaked = _k15_trace(seq[i + 1][1], assigns, opaque)
                                if field in names or f"d_{field}" in names:
                                    continue
                                if leaked or not names:
                                    abstained_holes += 1
                                    continue
                                findings.append(
                                    f"{where} prints '{env}=' beside "
                                    f"{ast.unparse(seq[i + 1][1])!r}, which is computed here and "
                                    f"never reads {field!r}. The sentence names one lever and "
                                    f"renders another quantity, which is the shape of every false "
                                    f"equation this check exists for -- render the lever the "
                                    f"sentence names, or name the quantity it renders.")
                                continue
                            v = _K15_VALUE.match(rest.lstrip())
                            if not v:
                                continue
                            tok = v.group(1).rstrip(".,;:").strip("'\"")
                            value, err = _k15_coerce(tok, default)
                            if err is None and choices is None and isinstance(default, (bool, str)):
                                continue          # nothing textual to check -- see _k15_coerce
                            literals += 1
                            if err is not None:
                                findings.append(
                                    f"{where} says {env}={tok!r}, and {err}. The configuration this "
                                    f"line describes cannot be set, so whatever it reports beside "
                                    f"it was measured under some other one.")
                            elif choices is not None and value not in choices:
                                findings.append(
                                    f"{where} says {env}={tok!r} and that lever's declared choices "
                                    f"are {choices!r}. The line describes a run nobody can "
                                    f"configure, so whatever it reports beside it was measured "
                                    f"under some other setting.")

    detail = (f"{gates} Gate construction(s) read across src/; {examined_names} lever name(s) "
              f"spelled in a reason, of which {literals} carry a literal value and {holes} a "
              f"rendered one; {abstained_holes} rendered value(s) ABSTAINED on because the trace "
              f"left the function; {dynamic_reachable} Gate(s) whose reachability is computed, "
              f"{dynamic_judged} of them judged by rule 4 through the arm that prints on a "
              f"reachable run and {dynamic_reachable - dynamic_judged} outside it; "
              f"{range_guarded} Gate(s) print one lever's value on a branch that admits a range "
              f"of it, examined by rule 5")
    return _report("K15", "a Gate's reason names a lever that exists, a value it can hold, no "
                          "impossibility on a reachable gate and no literal for the lever it "
                          "prints", not findings, detail, findings,
                   vacuous=not gates)


def _k15_coerce(tok, default):
    """(value, error) for a token spelled in a reason, by the SAME rule the runtime uses.

    A MIRROR OF spine/lever.py::Lever.coerce AND NOT A SECOND OPINION ABOUT WHAT A LEVER ACCEPTS.
    The first version hand-rolled the type test and reported OPT_LR_RESTARTS='off' as a value that
    lever cannot hold -- three times, in three correct gates. It can: coerce's bool branch is
    `str(raw).strip().lower() not in ("0", "", "off", "no", "none", "false")`, so 'off' is how a
    FLAG is spelled off and the reasons were right. That is what a second idea of one rule costs.

    Because coerce's bool branch cannot raise, a bool lever constrains NOTHING textually and the
    caller skips it; a str lever with no choices is the same. What is left is a number that is not
    a number, and a value outside a declared choices tuple -- checked by the caller against the
    coerced value, exactly as coerce checks it.
    """
    try:
        if isinstance(default, bool):
            return str(tok).strip().lower() not in ("0", "", "off", "no", "none", "false"), None
        if isinstance(default, int):
            return int(float(tok)), None
        if isinstance(default, float):
            return float(tok), None
        return str(tok), None
    except (TypeError, ValueError):
        return None, (f"spine/lever.py::Lever.coerce would refuse that at startup -- the declared "
                      f"default is {default!r}, so the value is read as a {type(default).__name__}")


CHECKS = (
    check_k1_signatures,
    check_k2_compose,
    check_k3_no_cross_package_imports,
    check_k4_levers_have_readers,
    check_k5_wires_are_read,
    check_k6_readers_are_reached,
    check_k7_root_reads_declared_names,
    check_k8_streams_are_declared,
    check_k9_cadence_periods_are_typed,
    check_k10_rows_name_their_arguments,
    check_k11_produces_is_not_fabricated,
    check_k12_deferral_reasons_are_complete,
    check_k13_counts_and_absence_claims,
    check_k14_rows_honour_stated_refusals,
    check_k15_gate_reasons_are_self_consistent,
)


def main():
    print("=== contract: the document, the stubs and the composition root are one system ===")
    print(f"{len(PKG_DIR)} package(s); document {os.path.relpath(DOC, ROOT)}; Python "
          f"{sys.version.split()[0]}")
    print()
    failed = 0
    for check in CHECKS:
        failed += check()
        print()
    # LAST, AND COUNTED. A broken check is a worse failure than anything a check reports.
    failed += selftest()
    print()
    print(f"=== {len(CHECKS)} checks + {len(_CASES)} self-test cases, {failed} failing ===")
    print("These checks prove that the document, the stubs and the composition root DECLARE the same")
    print("system. They do not prove that a body, once written, does what its docstring says, that a")
    print("DID IT FIRE counter is ever incremented, or that the levers a stub CLAIMS to read are the")
    print("ones it reads -- `LEVERS READ:` is prose that passes a parser. Those are L2's single-reader")
    print("sweep and L3's isolation sweep, and neither exists yet.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
