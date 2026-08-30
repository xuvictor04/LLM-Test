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

VACUITY IS PRINTED. Every check reports the size of the population it examined, and selftest() trips
all five against synthetic trees in a temp directory. This repository has SIXTY untrippable guards on
record and one of them was written into tests/test_ownership.py by the patch that was fixing
tests/test_ownership.py. A check nobody has watched fail is indistinguishable from a check that
cannot fail.
"""
import ast
import contextlib
import io
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

_GOOD_DOC = """# contract

## 3. UNCONSUMED LEVERS

| lever | env name | why it has no reader | disposition |
|---|---|---|---|

## 6. THE FROZEN SIGNATURE SET

```contract
DATA: open_areas(dat: Config, *, seed: int)
DATA: data_plan(dat: Config, *, areas)
```
"""

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
        "K8": (False, None), "K9": (False, None), "K10": (False, None), "K11": (False, None), "K12": (False, None)}),

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

    ("K5: a declared wire no stub reads",
     {"src/data/api.py": _GOOD_API.replace("    _ = dat.d_expert_slots\n", "")
                                  .replace("    WIRES READ: d_expert_slots\n",
                                           "    WIRES READ: none\n")},
     {"K5": (True, "arrives nowhere")}),

    ("K5: a stub names a d_ field no coupling declares",
     {"src/data/api.py": _GOOD_API.replace("WIRES READ: d_expert_slots",
                                           "WIRES READ: d_expert_slots, d_window")},
     {"K5": (True, "d_window")}),
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
        sig/api.py:8 stating the stakes itself: "the signature is the router's only input, so a
        collapsed encoder routes every window to the same experts".
      * nothing calls MEM.read or MEM.blend. The store is written and maintained and never read, so
        nothing retrieval-side reaches the model's distribution -- and memory/api.py:8 prices that
        path at the difference between -0.097 and +0.085 b/B.
      * nothing calls DOM.rekey, which domains/api.py:116 calls "AN EVENT THE SPINE DELIVERS" and
        which is the only place a radius is measured, while DOM.accept_rule defaults to 'radius'.
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
    instead, while world/api.py:35 takes rng as a REQUIRED keyword.

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
    (ISSUES H51). So three of the five periodic gates in the system would have raised on their first
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

    WHAT IT CANNOT CATCH: an accessor that returns the wrong kind, or the right kind computed
    wrongly. It reads the ORDER TABLES, which are data; whether P4's loop actually calls due() with
    what the row says is L2's, and does not exist yet.
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
    return _report("K9", "no cadence gate is handed a bare lever read", not findings,
                   f"{gates} Cadences.due gate(s) declared across {len(prose)} row note(s)",
                   findings, vacuous=not gates)



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
    memory/api.py:265 itself names as the inert state. K10 cannot see that; only reading the
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
            for arg in pos_req:
                if arg.arg == "self":
                    continue
                if getattr(arg.annotation, "id", None) == "Config":
                    continue                      # the package's own Config, never named in a row
                after_config.append(arg.arg)
            # DROP THE FIRST: it is the package's own live object, built by its own constructor row.
            req.extend(after_config[1:])
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
    memory/api.py:265 itself names as the inert state. K10 cannot see that; only reading the
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
