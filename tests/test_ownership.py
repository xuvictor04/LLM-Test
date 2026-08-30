"""The STATIC half of the lever rule: L1 (single declaration) and L2 (single reader), by AST over src/.

    python3 tests/test_ownership.py          # PASS/FAIL per check with counts; non-zero exit on any FAIL

WHAT THIS FILE PROVES, AND THE SENTENCE IT MAY NOT SAY. It proves that a module cannot MINT a foreign
lever: it cannot name the environment (O1), cannot hold two lever sets under any spelling (O3), and
cannot call `from_env` outside the wiring file (O8). It does NOT prove that a module cannot READ one. A
Config is an ordinary object; `build()` returns `{PREFIX: Config}`; and `memory_prune(configs["FAB"])`
reads FAB's levers with no error at author time and none at run time -- reproduced by a reviewer against
docstrings in spine/lever.py and spine/assemble.py that called it "an author-time NameError". Those
docstrings now say what is true, this file's O9 refuses the signature that would hold two packages at
once, and `Config.owned_by(PREFIX)` is the assertion at the read site. What is left uncovered is an
unannotated parameter handed a foreign Config: nothing in the source text distinguishes it, so nothing
here can see it, and it is L3's.

That is all it proves. The design review said so in as many words -- "all ten Spine checks are
AST/scope, and are blind to coupling through shared mutable state, RNG draw order or the data" -- and the
finding stands. Two packages that never mention each other still couple if they draw from one RNG in an
order that depends on a lever, or if one of them changes the bytes the other trains on. Nothing below can
see that, and PLAN section 4's L3 (`tests/test_lever_isolation.py`: flip a lever, 200 seeded CPU steps,
diff per-package integer fingerprints against the test_determinism noise floor) is the load-bearing check
for exactly that reason. This file is the cheap half: it runs on every edit, in well under a second, with
no torch and no GPU, and it catches the class of mistake that is easy to make and invisible in review.

So every check below carries a "CANNOT CATCH" block. They are not disclaimers. They are the map of what
L3 has to cover, and a check whose blind spots are not written down is a check that gets over-trusted.

WHY EACH CHECK EXISTS -- the defect, not the rule:

  O1  tokenizer.py read TOK_MINT_PMIN and TOK_MINT_GATE_K straight from os.environ. Both knobs were
      therefore invisible to the registry, to `docs/04_LEVERS.md`, and to every audit built on the
      registry -- including the one that reports which knobs a run actually read. A knob that is read but
      not declared does not appear as "set but never read"; it does not appear at all.
  O2  MAX_DOMAINS = _i("MAX_DOMAINS", _i("FAB_NMAX", 4096)). A computed default reads its input eagerly,
      so FAB_NMAX entered the read audit on every run whether or not it mattered; and the same name was
      read as _i("MAX_DOMAINS", 32) elsewhere, so one knob had two defaults 128x apart.
  O3  the old `_SPEC` table put all 328 knobs in one module, which is what made "who owns this" a comment.
      The check itself then had the defect in miniature: it counted lever sets by their local SPELLING, so
      `from fabric.levers import FabricLevers as _F` followed by `_F.from_env().slots` read FAB_SLOTS and
      passed all seven checks. Reproduced end to end. It now counts by RESOLVED ORIGIN.
  O8  the same bypass, answered from the other end. Resolving aliases is a race against spellings; naming
      the one legal CALL SITE is not, because it constrains where the call may appear rather than what the
      callee is called. `from_env` is the operation that turns a lever set into readable values, so
      whatever `_F` is and however it was spelled, `_F.from_env()` outside the wiring file is a finding.
  O9  `memory_prune(configs["FAB"])` -> 2048. Two docstrings said that was an author-time NameError; it
      is an ordinary call. A function outside the wiring file may not annotate two Config parameters, and
      a Config parameter must name its package through `owned_by("PREFIX")` -- which is what makes the
      wrong hand-off a startup failure instead of a plausible wrong number in a report.
  O4  the review's exact objection: "wires launder couplings -- fab.nmax arrives in domains as
      expert_slots and looks owned." It arrives as `d_expert_slots`, and this check is the audit that
      makes `grep d_` complete in BOTH directions.
  O5  a module global one package mutates and another reads is a coupling with no declaration and no
      name. It is also the only form of coupling in this list that AST can see at all, which is why it is
      here despite being the weakest of the five.
  O6  a coupling with no stated reason is indistinguishable from a coupling nobody noticed.
  O7  pin_tick counted FLUSHES against a threshold declared in STEPS: GROW_CAP_EVERY=20000 silently
      demanded 320,000 real steps at BATCH_W=16, the population sat pinned for 43,645 steps while the
      clock read 2,650, and the report printed "reached the cap but never held it long enough" -- a true
      sentence about a false clock.

VACUITY IS PRINTED. Every check reports the size of the population it examined. On a tree that contains
only the spine there are no LeverSet subclasses, no Lever declarations and no package that reads a `d_`
field, so several of these checks pass by having nothing to look at. A pass line that says
`(vacuous: 0 examined)` is the only honest way to report that, and it is printed rather than hidden
because a green tick over an empty set is this project's most repeated defect -- 60 of the survey's 475
records are guards whose condition cannot be satisfied.

THE ONE SEAM. This file walks the tree with `ast` and does not execute it, with two deliberate exceptions,
both in the checks that would otherwise need a SECOND copy of something src/ already declares:
`spine.wire._NON_REASONS` (O6) and `spine.assemble.COUPLINGS` (O4's cross-check). Re-typing either here
would be a second validator with its own idea of the rule, which is precisely how the old tree ended up
with a report path and an audit path printing different numbers for one quantity.
"""
import ast
import contextlib
import io
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

# The file that is allowed to name the process environment, as a path relative to the repo root. Written
# once, here, because it appears in the check and in its failure message and the two must not drift.
ENV_READER = os.path.join("src", "spine", "lever.py")

# The file allowed to hold more than one LeverSet. See spine/assemble.py's docstring for why exactly one
# file must be: something has to hold every Config at once in order to compute the values that genuinely
# cross boundaries, and keeping that to one file is what makes the coupling graph finite and printable.
WIRING_FILE = os.path.join("src", "spine", "assemble.py")

MAX_SHOWN = 25          # per check; the full count is always printed, only the listing is capped


# ==================================================================================================
# Source loading and the small AST helpers every check shares
# ==================================================================================================

class Module:
    """One parsed source file. Parsed ONCE and shared, so the whole pass is a single walk per file."""

    __slots__ = ("rel", "path", "tree", "lines", "dotted")

    def __init__(self, rel, path, tree, lines, dotted):
        self.rel, self.path, self.tree, self.lines, self.dotted = rel, path, tree, lines, dotted

    def line(self, n):
        """The source text at a line, for the finding message. The SOURCE LINE and not ast.unparse:
        a reviewer reading a failure needs the line as they will find it in the file, including the
        comment on the end of it, not a normalised re-rendering of the expression."""
        if 1 <= n <= len(self.lines):
            t = self.lines[n - 1].strip()
            return t if len(t) <= 96 else t[:93] + "..."
        return "?"

    def __repr__(self):
        return f"<Module {self.rel}>"


def load(src=SRC):
    """Parse every src/**/*.py. A syntax error is a hard failure, not a skipped file.

    Skipping an unparseable file would make this whole pass weaker the more broken the tree is, which is
    backwards: a file that does not parse is the one most likely to contain the thing being looked for.

    PATHS ARE RELATIVE TO THE PARENT OF `src`, NOT TO ROOT. For the real tree those are the same thing --
    SRC is ROOT/src, so `rel` still reads `src/spine/lever.py` and still compares equal to ENV_READER and
    WIRING_FILE. What the change buys is that this whole pass can be pointed at a SYNTHETIC tree in a
    temp directory and the exemptions still land on the right files, which is what the self-test at the
    bottom of this file needs. That is not a convenience: O3 passed the aliased bypass for as long as
    there was no way to hand it a tree containing one, and a check nobody has ever watched FAIL is
    indistinguishable from a check that cannot fail -- 60 of the survey's 475 records are that shape.
    """
    base = os.path.dirname(os.path.abspath(src))
    mods, bad = [], []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, base)
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            try:
                tree = ast.parse(text, filename=rel)
            except SyntaxError as e:
                bad.append(f"{rel}:{e.lineno}  does not parse: {e.msg}")
                continue
            dotted = os.path.relpath(path, src)[:-3].replace(os.sep, ".")
            if dotted.endswith(".__init__"):
                dotted = dotted[:-9]
            mods.append(Module(rel, path, tree, text.splitlines(), dotted))
    return mods, bad


def _at(mod, node, msg):
    return f"{mod.rel}:{getattr(node, 'lineno', 0)}  {msg}"


def _attr_name(node):
    """The dotted text of a Name/Attribute chain, or None. `os.environ` -> "os.environ"."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _toplevel_assigns(tree):
    """Module-level `NAME = value` and `NAME: T = value` pairs. Anything nested in a def or a class is
    not a module global and is not this file's business."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    yield t.id, node.value, node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            yield node.target.id, node.value, node


def _imports(mod):
    """Resolve this module's imports to (a) module aliases and (b) from-imported names.

    Returns (alias -> dotted module, local name -> (dotted module, original name)). Relative imports are
    resolved against the module's own package, because `from . import registry` inside `spine/lever.py`
    is how every intra-spine import in this tree is written and a resolver that only understood absolute
    imports would silently see none of them -- an ownership check that resolves nothing passes everything.
    """
    pkg = mod.dotted.rsplit(".", 1)[0] if "." in mod.dotted else ""
    modules, names = {}, {}
    for node in ast.walk(mod.tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                modules[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                # level 1 is the module's own package, level 2 its parent, and so on.
                up = pkg.split(".") if pkg else []
                up = up[:len(up) - (node.level - 1)] if node.level > 1 else up
                base = ".".join([p for p in up if p] + ([base] if base else []))
            for a in node.names:
                local = a.asname or a.name
                # `from . import registry` imports a MODULE under a plain name; `from .registry import x`
                # imports a name out of one. Both are recorded, and the caller decides which it wants.
                modules[local] = f"{base}.{a.name}" if base else a.name
                names[local] = (base, a.name)
    return modules, names


def _report(tag, title, ok, detail, findings, vacuous=False):
    """One check's line, plus its findings. The population size is ALWAYS printed -- see the module
    docstring on vacuity."""
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
# O1 -- os.environ / os.getenv is named in EXACTLY ONE file
# ==================================================================================================
#
# CANNOT CATCH:
#   * `getattr(os, "envi" + "ron")`, `vars(os)["environ"]`, `importlib` by string, or any other way of
#     spelling the name that is not a name. A literal-string getattr IS caught; a computed one is not.
#   * a value COPIED out of the environment in lever.py and handed around -- which is the whole design,
#     so the check is about who READS the mapping, never about where the value goes afterwards.
#   * the environment reaching the process by other means: a subprocess inheriting it, a dotenv file
#     read as text, /proc/self/environ, or a C extension. Nothing here reads the process, only the source.
#   * a lever set from the environment and then IGNORED. That is registry.unread_env's job (G9), and it
#     is a runtime check because a name that matched nothing is only knowable once every set is imported.
# OVER-CATCHES ON PURPOSE: any attribute named `environ`/`getenv`/... on any object, not just on `os`.
# `E = os` then `E.environ` would otherwise walk straight through, and the cost of the over-catch is a
# false positive that a human reads once, against a false negative that hides a knob forever.

ENV_NAMES = ("environ", "environb", "getenv", "getenvb", "putenv", "unsetenv")


def check_o1_one_env_reader(mods):
    findings, per_file = [], {}
    for mod in mods:
        _, from_names = _imports(mod)
        # `from os import environ as E` binds E to the mapping. Track the local name, not the spelling.
        aliased = {local for local, (base, orig) in from_names.items()
                   if base.split(".")[0] == "os" and orig in ENV_NAMES}
        for node in ast.walk(mod.tree):
            hit = None
            if isinstance(node, ast.Attribute) and node.attr in ENV_NAMES:
                hit = _attr_name(node) or f"<expr>.{node.attr}"
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in aliased:
                hit = f"{node.id} (from os import ...)"
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == "getattr" and len(node.args) >= 2
                  and isinstance(node.args[1], ast.Constant) and node.args[1].value in ENV_NAMES):
                hit = f"getattr(..., {node.args[1].value!r})"
            if hit is None:
                continue
            per_file.setdefault(mod.rel, []).append(node.lineno)
            if mod.rel != ENV_READER:
                # The source line is quoted because the knob NAME is the thing a reader needs -- the old
                # tree's instance of this defect was tokenizer.py reading TOK_MINT_PMIN, and a finding
                # that says only "os.getenv at line 2" sends the reader back to the file to learn which
                # lever went missing from the registry.
                findings.append(_at(mod, node, f"names the process environment as {hit}: "
                                               f"{mod.line(node.lineno)} -- only {ENV_READER} may. "
                                               f"Declare a Lever instead."))
    reads_here = len(per_file.get(ENV_READER, []))
    # THE READER MUST EXIST. Without this clause the check passes on a tree where NOTHING names the
    # environment -- including the tree where somebody deletes from_env's one line and every lever
    # silently becomes its default forever. A guard that cannot distinguish "correct" from "absent" is
    # the untrippable-guard shape this project has 60 records of.
    if reads_here == 0:
        findings.append(f"{ENV_READER}  does not name os.environ at all. LeverSet.from_env is the only "
                        f"reader in the tree; if it has stopped reading, every lever is its default.")
    detail = (f"{sum(len(v) for v in per_file.values())} environment reference(s) in {len(per_file)} "
              f"file(s); {reads_here} in {ENV_READER}; {len(mods)} files scanned")
    return _report("O1", "os.environ is named in exactly one file", not findings, detail, findings)


# ==================================================================================================
# O2 -- every Lever default is an ast.Constant
# ==================================================================================================
#
# THIS CHECK AND Lever.__init__ COVER EACH OTHER'S BLIND SPOTS, which is why both exist:
#   Lever.__init__ refuses a non-literal VALUE at runtime, so it catches a default built dynamically or
#   passed in from a loop -- code this file never sees as a `Lever(...)` call with a visible argument.
#   It cannot catch `Lever(N0_DEFAULT, ...)` where N0_DEFAULT is a module constant holding 2048: the
#   value is an int and the isinstance test passes. That one is a second place a default can live, and
#   editing it changes the lever, so it is the exact drift L1 forbids -- and this check catches it.
#
# CANNOT CATCH:
#   * a Lever built through an alias (`L = Lever; L(2048, ...)`) or by a factory function. The runtime
#     isinstance check still applies to those; only the "second home for the number" half is lost.
#   * levers created dynamically -- `for n, d in TABLE: setattr(cls, n, Lever(d, ...))`. There is no
#     `Lever(` call with a constant argument to look at. The registry still sees the resulting levers,
#     so they are declared and owned; what is lost is the guarantee that the number is written once.
#   * a default that is a literal and WRONG. Nothing static can know that 2048 was meant to be 4096.
#     The known-answer tables in tests/test_derive.py are where a wrong number gets caught.

def _is_literal(node):
    """A Constant, or a signed one. `Lever(-1, ...)` parses as UnaryOp(USub, Constant(1)) and refusing
    it would make every negative default illegal for a reason that is purely about the grammar."""
    if isinstance(node, ast.Constant):
        return True
    return (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant))


def _calls_named(mod, name):
    """Every Call in a module whose callee is `name` or `something.name`."""
    for node in ast.walk(mod.tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Name) and f.id == name) or (isinstance(f, ast.Attribute) and f.attr == name):
            yield node


def check_o2_literal_defaults(mods):
    findings, seen = [], 0
    for mod in mods:
        for call in _calls_named(mod, "Lever"):
            seen += 1
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            default = call.args[0] if call.args else kw.get("default")
            if default is None:
                findings.append(_at(mod, call, "Lever(...) with no default. Every lever has exactly one "
                                               "default and it lives on the declaration."))
            elif not _is_literal(default):
                findings.append(_at(mod, default,
                                    f"default is not a literal: {mod.line(default.lineno)} -- a value "
                                    f"derived from another lever is a WIRE. Declare it in "
                                    f"spine.assemble so the coupling is visible in the printed graph."))
    detail = f"{seen} Lever(...) declaration(s) examined, {len(findings)} with a non-literal default"
    return _report("O2", "every Lever default is a literal", not findings, detail, findings, vacuous=not seen)


# ==================================================================================================
# O3 -- no module outside the wiring file references more than one LeverSet subclass
# ==================================================================================================
#
# This is L2 stated as something AST can see. A package function receives its own Config as a parameter,
# and a module that holds two lever sets can mint and hand out either one -- so the count of sets in
# scope is the thing to bound. It bounds MINTING, not reading: see O9 and the module docstring for the
# difference, which two other docstrings in this tree used to get wrong.
#
# COUNTED BY RESOLVED ORIGIN, NOT BY LOCAL SPELLING, because this check had the ownership defect itself.
# It keyed lever sets by class name and matched `ast.Name.id` against those names, so
#     from fabric.levers import FabricLevers as _F
#     _F.from_env().slots
# named zero lever sets as far as it could tell, passed all seven checks, and read FAB_SLOTS at will.
# A reviewer reproduced that end to end; the self-test case named "the reviewer's module" is that file, and
# it now fails here. O8 answers the same bypass from the other end, and answers it better: it constrains
# the CALL SITE, which no spelling can change.
#
# The PREFIX duplicate half is checked here too. spine/registry.py refuses it at import, but only for
# sets that are actually imported -- a package nobody imported yet can sit in the tree for a week with a
# colliding PREFIX and the runtime check will never see it.
#
# CANNOT CATCH:
#   * a module that references ONE foreign lever set AND NONE OF ITS OWN. One set in scope is legal and
#     has to be, since a package's own levers.py declares exactly one, and this check cannot tell whose
#     it is. That hole is real and it is exactly what a bare alias module looks like -- which is why O8
#     exists: the module is legal here and fails there, because it CALLS from_env outside the wiring file.
#     The self-test case "O8 alone" asserts that pair of outcomes -- O3 green, O8 red, on one tree -- so
#     the division of labour between them cannot silently rot.
#   * a lever set fetched by string: `getattr(mod, "FabricLevers")`, an entry in a dict of classes, or
#     one returned by a factory. There is no spelling in the source to resolve.
#   * a foreign value arriving as a plain function argument. `def cull(pop, nmax)` called with FAB.nmax
#     from a module that legitimately holds FAB is invisible to every check in this file. The `d_` rule
#     (O4) is what makes that visible, and only for values that cross via assemble.
#   * a PREFIX that is not a string literal. Reported as a hole rather than skipped, since a computed
#     PREFIX would defeat the duplicate check entirely.

def _leversets(mods):
    """Every LeverSet subclass in src/, to a fixed point, keyed by ORIGIN: (dotted module, class name).

    KEYED BY ORIGIN AND NOT BY CLASS NAME, and the difference was a live hole in both halves of O3:

      * `found[node.name]` skipped any class whose NAME was already taken, so `class Levers` in
        fabric/levers.py and `class Levers` in domains/levers.py collapsed into one row and the second one
        vanished from this function's answer entirely. Reproduced: two packages both declaring
        PREFIX="DUP" printed "3 distinct PREFIX(es)" over four classes and PASSED the duplicate-prefix
        half, which is the one check in this file whose entire job is that collision.
      * a class name is a SPELLING, and O3's other half matched `ast.Name.id` against these keys. A local
        alias therefore defeated it: `from fabric.levers import FabricLevers as _F` put FAB's set in a
        memory module under a name this table had never heard of, and `_F.from_env().slots` read FAB_SLOTS
        through all seven checks. Verified end to end by a reviewer, and by the self-test below.

    TO A FIXED POINT because a package may declare an intermediate base (`class Cadenced(LeverSet)`) whose
    subclasses are lever sets too. A single pass would miss them, and a lever set this function does not
    know about is one no check in this file can count.

    BASES ARE MATCHED BY SIMPLE NAME, deliberately, even though the answer is keyed by origin. Discovery
    and counting want opposite failure modes: a base spelling this pass fails to recognise means a lever
    set that does not exist as far as every check is concerned, so discovery must over-catch, while a
    count inflated by two spellings of one class is a false finding, so counting must resolve. Import
    aliases on the base (`from spine.lever import LeverSet as _LS`) are un-aliased first, for the same
    reason -- a resolver that resolves nothing passes everything.
    """
    unalias = {}                     # mod.rel -> {local name: original name}, for base spellings
    for mod in mods:
        _, from_names = _imports(mod)
        unalias[mod.rel] = {local: orig for local, (base, orig) in from_names.items()}

    found = {}                       # (dotted, class name) -> (mod, node, prefix or None)
    known = {"LeverSet"}             # simple base spellings known to be lever sets
    for _ in range(8):               # depth bound: 8 levels of lever-set inheritance is already absurd
        added = False
        for mod in mods:
            back = unalias[mod.rel]
            for node in ast.walk(mod.tree):
                if not isinstance(node, ast.ClassDef) or (mod.dotted, node.name) in found:
                    continue
                bases = set()
                for b in node.bases:
                    spelled = b.id if isinstance(b, ast.Name) else b.attr if isinstance(b, ast.Attribute) else None
                    if spelled is None:
                        continue
                    bases.add(spelled)
                    bases.add(back.get(spelled, spelled))
                if not (bases & known):
                    continue
                prefix = None
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and any(
                            isinstance(t, ast.Name) and t.id == "PREFIX" for t in stmt.targets):
                        prefix = stmt.value.value if isinstance(stmt.value, ast.Constant) else _UNKNOWN
                found[(mod.dotted, node.name)] = (mod, node, prefix)
                known.add(node.name)
                added = True
        if not added:
            break
    return found


def _origins_named(mods_sets, mod):
    """{origin: the first spelling of it seen} for every lever set this module has IN SCOPE.

    IN SCOPE, not "mentioned": an import BINDING counts on its own. That is what O3's rule says -- "a
    module with two sets in scope can hand either to anything" -- and the old code did not implement it,
    because it looked only at ast.Name/ast.Attribute uses. `from fabric.levers import FabricLevers as _F`
    binds a foreign lever set with no ast.Name anywhere for the old matcher to find.

    THREE SPELLINGS ARE RESOLVED, and one deliberately is not:
        from fabric.levers import FabricLevers as _F     ->  the binding resolves to the origin
        import fabric.levers as _fl ... _fl.FabricLevers ->  the attribute chain resolves through it
        class FabricLevers(LeverSet)                     ->  a set defined here is named here
    A later `_G = _F` needs no special handling and gets none: the right-hand side is itself one of the
    spellings above and every expression in the module is walked, so the origin is already counted. A
    fixed point over assignments would be code that cannot change any answer, which is the untrippable
    guard this project keeps rediscovering.

    OVER-CATCHES ON PURPOSE, in `snap` below: an attribute whose final component matches a known lever
    set's class name counts even when the base it hangs off resolves to nothing. `src/` is scanned as a
    flat package root and a module reached by another sys.path root spells its own name differently, so
    strict resolution would silently count zero -- and a check that resolves nothing passes everything.
    The cost is a false positive a human reads once.
    """
    sets = mods_sets
    modules, from_names = _imports(mod)
    by_simple = {}
    for (dotted, cname) in sets:
        by_simple.setdefault(cname, set()).add((dotted, cname))

    def snap(dotted_mod, cname):
        """A (module, class) candidate, snapped onto a real lever set, or None."""
        if (dotted_mod, cname) in sets:
            return (dotted_mod, cname)
        hits = by_simple.get(cname)
        if not hits:
            return None
        if len(hits) == 1:
            return next(iter(hits))
        # Two packages declaring one class name is itself a finding in the other half of O3. Counting it
        # under a marker keeps this half honest -- the module really does hold A lever set -- without
        # guessing which one and reporting a package that may not be involved.
        return ("<ambiguous class name>", cname)

    local = {}                                     # local spelling -> origin
    for name, (base, orig) in from_names.items():
        o = snap(base, orig)
        if o is not None:
            local[name] = o

    def attr_origin(node):
        dotted = _attr_name(node)
        if dotted is None or "." not in dotted:
            return None
        head, _, cname = dotted.rpartition(".")
        if head in local:
            # An attribute hanging off a lever set (`_F.from_env`) is not itself a lever set.
            return None
        first, _, rest = head.partition(".")
        base = modules.get(first, first)
        return snap(f"{base}.{rest}" if rest else base, cname)

    out = {}
    for name, o in sorted(local.items()):
        out.setdefault(o, name)
    for node in ast.walk(mod.tree):
        o = spell = None
        if isinstance(node, ast.Name) and node.id in local:
            o, spell = local[node.id], node.id
        elif isinstance(node, ast.Attribute):
            o, spell = attr_origin(node), (_attr_name(node) or node.attr)
        elif isinstance(node, ast.ClassDef) and (mod.dotted, node.name) in sets:
            o, spell = (mod.dotted, node.name), node.name
        if o is not None:
            out.setdefault(o, spell)
    return out


class _Unknown:
    def __repr__(self): return "<not a literal>"


_UNKNOWN = _Unknown()


def check_o3_one_leverset_per_module(mods):
    sets = _leversets(mods)
    findings = []

    # -- half one: a module may have at most one lever set in scope, under any spelling ----------
    for mod in mods:
        named = _origins_named(sets, mod)
        if len(named) > 1 and mod.rel != WIRING_FILE:
            shown = ", ".join(f"{spell} = {d}.{c}" for (d, c), spell in sorted(named.items()))
            findings.append(f"{mod.rel}:1  has {len(named)} lever sets in scope ({shown}). "
                            f"Only {WIRING_FILE} may hold more than one: a module with two sets in scope "
                            f"can hand either to anything, which is the read L2 forbids. The count is by "
                            f"resolved ORIGIN, so renaming one at the import line does not reduce it.")

    # -- half two: one PREFIX, one owner --------------------------------------------------------
    by_prefix = {}
    for (dotted, cname), (mod, node, prefix) in sorted(sets.items()):
        # The class is named with its module, always. Two packages may legally declare a class of the
        # same name, and a finding that says only "Levers" sends the reader to the wrong file -- which is
        # the same confusion that let the by-name keying hide one of them from this half entirely.
        label = f"{cname} ({dotted})"
        if prefix is _UNKNOWN:
            findings.append(_at(mod, node, f"{label}.PREFIX is not a string literal, so the static "
                                           f"duplicate-prefix check cannot see it. Only the import-time "
                                           f"check in spine/registry.py covers this set, and that one "
                                           f"only fires for sets something actually imports."))
            continue
        if prefix is None:
            findings.append(_at(mod, node, f"{label} declares no PREFIX. Ownership IS the namespace: "
                                           f"without a prefix the environment name cannot be generated."))
            continue
        prior = by_prefix.get(prefix)
        if prior is not None:
            findings.append(_at(mod, node, f"PREFIX {prefix!r} is claimed by both {prior[0]} "
                                           f"({prior[1].rel}:{prior[2].lineno}) and {label}. "
                                           f"One prefix, one owner."))
        else:
            by_prefix[prefix] = (label, mod, node)
    detail = (f"{len(sets)} LeverSet subclass(es) across {len(mods)} files, "
              f"{len(by_prefix)} distinct PREFIX(es)")
    return _report("O3", "no module outside the wiring file holds two lever sets",
                   not findings, detail, findings, vacuous=not sets)


# ==================================================================================================
# O4 -- the d_ audit, in BOTH directions
# ==================================================================================================
#
# The review's objection was exact: "wires launder couplings -- fab.nmax arrives in domains as
# expert_slots and looks owned." It arrives as `d_expert_slots` because the WIRE names the field, and the
# claim that buys is that `grep -rn d_ src/` enumerates every coupling with no tooling. That claim is only
# true if both directions hold, so both are checked:
#   forward   every d_ field READ in src/ is a destination declared in the COUPLINGS table.
#             An undeclared d_ read is a coupling the printed graph does not contain, and affects() --
#             the only oracle the L3 sweep has -- would understate that lever's reach and the sweep would
#             go green on a real leak.
#   backward  every declared destination is read somewhere. A wire nobody reads is recorded-never-read
#             (39 of the survey's 475 records): budget spent, an edge in the printed graph, and a value
#             that arrives nowhere.
#
# DEFERRED IS NOT PASSING. A destination whose package has no LeverSet in src/ yet cannot be read by
# anything, so it is counted and listed as DEFERRED rather than failed -- the same distinction
# spine/assemble.py's build() makes in its warnings. On a tree containing only the spine that is ALL ten
# rows, so the backward direction currently proves nothing. The count is printed for that reason.
#
# CANNOT CATCH:
#   * WHICH package a d_ field was read from. The match is on the FIELD NAME alone, because a static pass
#     cannot know that the `cfg` in `cfg.d_cap_lift_period` is TOK's Config and not FAB's -- and the table
#     declares that field for both. A package reading its neighbour's identically-named d_ field passes
#     here; only Config.__getattr__ catches it, at runtime, by raising with the list of what IS available.
#   * a coupling appended to COUPLINGS at runtime. The table is read by AST; the import cross-check below
#     is what makes that visible, and it is a hard failure rather than a note.
#   * a foreign value that never becomes a d_ field at all: passed as a function argument, stashed on a
#     shared object, or recomputed from the same corpus. That is L3's territory, in full.
#   * whether the value in the d_ field is the RIGHT one. `compute` is a lambda and this is a name check.

def _declared_couplings(mods):
    """(dst strings, findings) read out of the `Coupling(...)` calls by AST.

    EVERY module is scanned, not just the wiring file, and a Coupling declared anywhere else is a
    finding. Scanning only the wiring file would have made a second coupling table somewhere in the tree
    invisible to this check while still being a real, running coupling -- the ledger would be short by
    however many rows that other file holds, and affects() understates every lever those rows read.
    """
    dsts, findings = [], []
    for mod in mods:
        for call in _calls_named(mod, "Coupling"):
            if mod.rel != WIRING_FILE:
                findings.append(_at(mod, call, f"declares a Coupling outside {WIRING_FILE}. There is one "
                                               f"coupling table; a second one is a coupling graph that "
                                               f"cannot be printed from one place."))
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            dst = kw.get("dst") or (call.args[1] if len(call.args) > 1 else None)
            if not isinstance(dst, ast.Constant) or not isinstance(dst.value, str):
                findings.append(_at(mod, call, "Coupling(dst=...) is not a string literal. The ledger is "
                                               "read by docs generation and by this test without running "
                                               "anything; a computed destination is invisible to both."))
                continue
            dsts.append(dst.value)
    return dsts, findings


def _d_field_uses(mods):
    """Every `x.d_foo` in src/, split into reads and writes."""
    reads, writes = {}, []
    for mod in mods:
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Attribute) and node.attr.startswith("d_") and len(node.attr) > 2:
                if isinstance(node.ctx, ast.Load):
                    reads.setdefault(node.attr, []).append((mod, node))
                else:
                    # A d_ field assigned anywhere but through the wire is the launder the prefix exists
                    # to stop: the record and the assignment would describe two different systems.
                    writes.append(_at(mod, node, f"assigns {node.attr} directly. Only Wires.add(into=) "
                                                 f"and Config._wire may write a d_ field, so that the "
                                                 f"ledger and the running system cannot disagree."))
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == "getattr" and len(node.args) >= 2
                  and isinstance(node.args[1], ast.Constant)
                  and isinstance(node.args[1].value, str) and node.args[1].value.startswith("d_")):
                reads.setdefault(node.args[1].value, []).append((mod, node))
    return reads, writes


def check_o4_wires_match_reads(mods):
    dsts, findings = _declared_couplings(mods)
    declared_fields = {d.partition(".")[2] for d in dsts}
    reads, writes = _d_field_uses(mods)
    findings.extend(writes)

    # THE LEDGER THIS TEST READS MUST BE THE ONE THE RUN USES. Reading the table by AST is what lets this
    # file run without executing the tree, but an AST oracle that has silently gone out of step with the
    # real table is a smaller oracle, and a smaller oracle passes by having nothing to compare -- the
    # exact failure graft G1 exists to prevent. So the two are compared, and a disagreement is fatal.
    try:
        from spine import assemble
        live = {c.dst for c in assemble.COUPLINGS}
        if live != set(dsts):
            findings.append(f"{WIRING_FILE}:1  the COUPLINGS table read by AST here ({len(dsts)} rows) "
                            f"and the one spine.assemble builds ({len(live)} rows) are not the same "
                            f"ledger. Declared only in the source text: {sorted(set(dsts) - live)}. "
                            f"Present only at runtime: {sorted(live - set(dsts))}. Every check above "
                            f"was made against the source text, so it was made against the wrong table.")
    except Exception as e:                                    # noqa: BLE001 -- reported, never swallowed
        findings.append(f"{WIRING_FILE}:1  could not import spine.assemble to cross-check the ledger: "
                        f"{type(e).__name__}: {e}. The AST reading is therefore unverified.")

    # -- forward: every d_ read is declared ------------------------------------------------------
    for field, sites in sorted(reads.items()):
        if field in declared_fields:
            continue
        for mod, node in sites:
            findings.append(_at(mod, node, f"reads {field}, which no coupling declares. A d_ field is "
                                           f"assigned by the wire that names it; an undeclared one is a "
                                           f"coupling missing from affects(), and affects() is the L3 "
                                           f"sweep's only oracle."))

    # -- backward: every declared destination is read, unless its package has no BODY yet -----------
    # THE CONDITION IS "HAS AN IMPLEMENTATION", NOT "HAS A LeverSet". The first version deferred on
    # whether a package declared levers, which was right while the tree was empty and wrong the moment
    # thirteen levers.py files landed: four packages acquired declarations, none of them acquired the
    # code that would READ a wired value, and O4 failed on five rows that were merely not-yet-written.
    # A package is expected to read its wires once it has a module other than levers.py/__init__.py.
    # This self-clears as each package gets a body, and it cannot be used to hide a real unread wire in
    # a finished package -- which is the failure O4 exists for.
    import os as _os
    _pkg_dir = {}
    for _m in mods:
        # _m.rel, NOT str(_m). Module defines __repr__ as f"<Module {self.rel}>" and no __str__, so
        # str(_m) is "<Module src/memory/levers.py>" and basename() of it is "levers.py>" -- with the
        # angle bracket -- which never equals "levers.py". The first version of this block used str(_m),
        # which left _pkg_dir permanently empty, _has_body() permanently False, and every declared wire
        # permanently "deferred": O4's backward half was green on every commit and printed "their
        # packages are not in src/ yet" about thirteen packages that were all in src/.
        # That is the untrippable-guard shape this file counts 60 of in the survey, introduced BY a patch
        # that was fixing a different O4 problem, in the check whose subject is that class of defect.
        _pth = _m.rel
        if _os.path.basename(_pth) == "levers.py":
            for _mod, _, _pfx in _leversets([_m]).values():
                if isinstance(_pfx, str):
                    _pkg_dir[_pfx] = _os.path.dirname(_pth)
    def _has_body(prefix):
        d = _pkg_dir.get(prefix)
        if not d or not _os.path.isdir(d):
            return False
        return any(f.endswith(".py") and f not in ("levers.py", "__init__.py")
                   for f in _os.listdir(d))
    unread, deferred = [], []
    for dst in dsts:
        prefix, _, field = dst.partition(".")
        if field in reads:
            continue
        (unread if _has_body(prefix) else deferred).append(dst)
    for dst in unread:
        findings.append(f"{WIRING_FILE}:1  {dst} is declared and its package is registered, but nothing "
                        f"in src/ reads it. A wire nobody reads spends budget, prints an edge, and "
                        f"delivers a value that arrives nowhere.")

    detail = (f"{len(dsts)} declared destination(s), {len(reads)} distinct d_ field(s) read at "
              f"{sum(len(v) for v in reads.values())} site(s); {len(unread)} declared-but-unread, "
              f"{len(deferred)} deferred (receiving package has no implementation yet)")
    ok = not findings
    rc = _report("O4", "every d_ read is a declared wire, and every declared wire is read",
                 ok, detail, findings, vacuous=not reads and not dsts)
    if deferred:
        # Printed on a pass as well as a failure. The backward direction is untested for these rows and
        # saying so is the difference between a result and a green tick over an empty set.
        print(f"          note: the backward direction is UNTESTED for {len(deferred)} of {len(dsts)} "
              f"rows -- their receiving packages have no implementation yet:")
        for d in deferred[:MAX_SHOWN]:
            print(f"                {d}")
    return rc


# ==================================================================================================
# O5 -- no module-level mutable global in one module is assigned by another
# ==================================================================================================
#
# The weakest check here, and it is in the list because it is the ONLY form of undeclared coupling that
# AST can see at all. spine/wire.py already refuses to keep a module-level singleton ledger for exactly
# this reason, and says why: a global would make WIRE_BUDGET a function of how many test modules had been
# imported first, which is a guard that trips on the wrong thing and then gets raised until it never
# trips at all.
#
# CANNOT CATCH -- and this list is why L3 exists:
#   * an ALIAS. `t = registry._SETS` and then `t[k] = v` launders the write in one line. The name that
#     gets mutated is local, and no static pass without a type system follows it.
#   * mutation through a function the owning module exports. `registry.register(cls)` mutates _SETS from
#     lever.py and is correct: that is ownership working, and no check can tell it from a back door
#     except by reading the function.
#   * a mutable DEFAULT ARGUMENT, a class attribute, or state on an instance that two packages both hold.
#     The fabric and the memory store couple through an object passed as a parameter; nothing here sees it.
#   * the couplings that actually matter in this system -- a shared RNG whose draw ORDER depends on a
#     lever, and the data stream itself. Neither is a global and neither is assigned.
# OVER-CATCHES: an attribute store whose base name this file cannot resolve to a module is flagged anyway
# if the attribute matches another module's mutable global. A false positive there is read once by a
# human; a missed cross-module write is a coupling with no name at all.

_MUTABLE_CALLS = frozenset({"list", "dict", "set", "bytearray", "defaultdict", "OrderedDict",
                            "deque", "Counter", "array"})
_MUTATORS = frozenset({"append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse",
                       "add", "discard", "update", "setdefault", "popitem", "__setitem__"})


def _mutable_globals(mods):
    """module dotted name -> {global name: (mod, node)} for module-level mutable containers."""
    out = {}
    for mod in mods:
        for name, value, node in _toplevel_assigns(mod.tree):
            mutable = isinstance(value, (ast.List, ast.Dict, ast.Set, ast.ListComp,
                                         ast.DictComp, ast.SetComp))
            if isinstance(value, ast.Call):
                f = value.func
                mutable = ((isinstance(f, ast.Name) and f.id in _MUTABLE_CALLS)
                           or (isinstance(f, ast.Attribute) and f.attr in _MUTABLE_CALLS))
            if mutable:
                out.setdefault(mod.dotted, {})[name] = (mod, node)
    return out


def check_o5_no_foreign_global_writes(mods):
    owned = _mutable_globals(mods)
    by_name = {}                    # global name -> {owning dotted module}
    for dotted, names in owned.items():
        for n in names:
            by_name.setdefault(n, set()).add(dotted)
    findings, total = [], sum(len(v) for v in owned.values())

    for mod in mods:
        module_aliases, from_names = _imports(mod)
        mine = set(owned.get(mod.dotted, {}))

        def owner_of(base, attr):
            """Which module's global `base.attr` is, or None. `base` is the text before the dot."""
            target = module_aliases.get(base)
            if target and attr in owned.get(target, {}):
                return target
            if target is None and base not in ("self", "cls") and attr in by_name:
                others = by_name[attr] - {mod.dotted}
                if others:
                    return f"{sorted(others)[0]} (unresolved base {base!r})"
            return None

        for node in ast.walk(mod.tree):
            # -- `othermod.TABLE = ...`, `othermod.TABLE += ...`, `othermod.TABLE[k] = ...` --------
            targets = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for t in targets:
                t2 = t.value if isinstance(t, ast.Subscript) else t
                if isinstance(t2, ast.Attribute) and isinstance(t2.value, ast.Name):
                    who = owner_of(t2.value.id, t2.attr)
                    if who and who.split(" ")[0] != mod.dotted:
                        findings.append(_at(mod, t2, f"writes {t2.value.id}.{t2.attr}, a module-level "
                                                     f"mutable owned by {who}. State one module owns and "
                                                     f"another writes is a coupling with no declaration "
                                                     f"and no name in the printed graph."))
                elif isinstance(t2, ast.Name) and t2.id in from_names:
                    base, orig = from_names[t2.id]
                    if orig in owned.get(base, {}) and base != mod.dotted and isinstance(t, ast.Subscript):
                        findings.append(_at(mod, t2, f"writes into {orig}, imported from {base}. "
                                                     f"A from-import does not make the object local."))
            # -- `othermod.TABLE.append(...)` and the from-imported form ---------------------------
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in _MUTATORS:
                recv = node.func.value
                who = None
                if isinstance(recv, ast.Attribute) and isinstance(recv.value, ast.Name):
                    who = owner_of(recv.value.id, recv.attr)
                    shown = f"{recv.value.id}.{recv.attr}"
                elif isinstance(recv, ast.Name) and recv.id in from_names:
                    base, orig = from_names[recv.id]
                    who = base if orig in owned.get(base, {}) else None
                    shown = f"{recv.id} (from {base})"
                if who and who.split(" ")[0] != mod.dotted and (not isinstance(recv, ast.Name)
                                                                or recv.id not in mine):
                    findings.append(_at(mod, node, f"calls .{node.func.attr}() on {shown}, a module-level "
                                                   f"mutable owned by {who}. Mutating another module's "
                                                   f"state is the same coupling as assigning it."))
    detail = (f"{total} module-level mutable global(s) across {len(owned)} module(s); "
              f"{len(findings)} foreign write(s)")
    return _report("O5", "no module-level mutable global is written by another module",
                   not findings, detail, findings, vacuous=not total)


# ==================================================================================================
# O6 -- every wire has a non-empty reason
# ==================================================================================================
#
# `spine.wire._check_why` already refuses an absent reason at construction, and this check does NOT
# re-implement it -- it imports the same placeholder set, because a second copy of that list is a second
# validator with its own idea of the rule. What this adds over the runtime check is that the reason must
# be a LITERAL AT THE DECLARATION SITE. `why=REASONS["expert_slots"]` would satisfy _check_why perfectly
# and leave docs/03_WIRING.md correct while making the table unreadable in the one place a reviewer reads
# it: the table. The reason column exists to be read next to the value it justifies.
#
# CANNOT CATCH -- said plainly, because the design review said it first and it is still true:
#   "a reason is prose that passes an AST check." It is. Nothing here can tell a true explanation from a
#   plausible one, and no rule can. What catches a wrong reason is that render() prints it beside the
#   value in docs/03_WIRING.md, where a reason that does not explain the number sits next to the number.
#   * it also cannot see the `Wires.add(...)` path, whose `why` arrives as a variable by design
#     (assemble.py passes `c.why` from the table row). Wire.__init__ calls _check_why on it at runtime.
#   * an IRREDUCIBLE flag that is wrong -- a chosen coupling declared as physics -- is a claim about the
#     world and is checked by reading, not by a test.

def check_o6_wires_have_reasons(mods):
    try:
        from spine.wire import _NON_REASONS
    except Exception as e:                                    # noqa: BLE001 -- reported, never swallowed
        return _report("O6", "every coupling states a reason", False,
                       f"could not import spine.wire._NON_REASONS: {type(e).__name__}: {e}",
                       ["the placeholder list is not restated here on purpose -- see this check's note"])
    findings, seen = [], 0
    for mod in mods:
        for call in _calls_named(mod, "Coupling"):
            seen += 1
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            why = kw.get("why")
            if why is None:
                findings.append(_at(mod, call, "coupling declares no why=. A coupling with no stated "
                                               "reason is indistinguishable from one nobody noticed."))
                continue
            if not (isinstance(why, ast.Constant) and isinstance(why.value, str)):
                findings.append(_at(mod, why, "why= is not a string literal. The reason has to be legible "
                                              "in the table, which is where it is reviewed."))
                continue
            text = why.value.strip()
            if not text:
                findings.append(_at(mod, why, "why= is empty. Say what breaks in the receiving package "
                                              "if this value is not the owner's value."))
            elif " " not in text or text.lower().rstrip(".!") in _NON_REASONS:
                findings.append(_at(mod, why, f"why={text[:40]!r} is a placeholder, not a reason."))
    detail = f"{seen} coupling declaration(s), {len(findings)} without a legible reason"
    return _report("O6", "every coupling states a reason, as a literal at the declaration",
                   not findings, detail, findings, vacuous=not seen)


# ==================================================================================================
# O7 -- clock kinds are never compared against bare int literals
# ==================================================================================================
#
# `Clock._same` raises UnitError on `Steps(4000) >= 250` at runtime, so why check it statically? Because
# the runtime check only fires when the line RUNS, and this project's characteristic clock bug lives on
# lines that run once every twenty thousand steps. The capacity valve's pin clock compared flushes against
# a threshold in steps; at BATCH_W=16 the branch that would have raised was simply never reached, the
# population sat pinned for 43,645 real steps while the clock read 2,650, and the report printed a true
# sentence about a false clock. A static check fires at author time, on every edit, on every branch.
#
# The clock kinds are read out of spine/units.py rather than listed here, so a kind added there is covered
# without a second list to keep in sync. A hardcoded list would silently stop covering the newest kind,
# which is the shape of every drifted table in the old tree.
#
# CANNOT CATCH:
#   * a threshold that arrives under a name. `n = cfg.manage_every; Flushes(k) >= n` is invisible, and
#     making it visible needs type inference over arbitrary Python -- which the design review rejected as
#     "a type-inference engine with no type system underneath it", defeated by one assignment.
#   * `clock.n >= 250`, which unwraps the clock and compares bare ints. That is sometimes exactly right
#     (spine/derive.py:234 does it deliberately, inside the function that owns the conversion) and
#     sometimes the bug itself. Nothing static separates the two.
#   * `Steps(4000) >= Steps(250)` where the 250 came from a lever denominated in flushes. The types agree
#     and the number is foreign. That is a wrong-measurement defect, and the known-answer tables in
#     tests/test_derive.py are what catch it.
#   * arithmetic rather than comparison -- `Flushes(3) * 16` -- which Clock does not define and which
#     therefore fails loudly at runtime rather than silently.

def _clock_kinds(mods):
    """Clock subclasses declared in spine/units.py, to a fixed point. Empty is a hard failure: an empty
    set would make this check pass on any tree at all."""
    found, known = set(), {"Clock"}
    for _ in range(4):
        added = False
        for mod in mods:
            for node in ast.walk(mod.tree):
                if not isinstance(node, ast.ClassDef) or node.name in found:
                    continue
                bases = {b.id if isinstance(b, ast.Name) else b.attr
                         for b in node.bases if isinstance(b, (ast.Name, ast.Attribute))}
                if bases & known:
                    found.add(node.name)
                    known.add(node.name)
                    added = True
        if not added:
            break
    return found


def _numeric_literal(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool))


def check_o7_no_clock_vs_int(mods):
    kinds = _clock_kinds(mods)
    findings, compares, constructions = [], 0, 0
    if not kinds:
        findings.append("no Clock subclasses found in src/. This check would pass on any tree, which is "
                        "an untrippable guard, so it fails instead.")
    for mod in mods:
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Call):
                f = node.func
                if ((isinstance(f, ast.Name) and f.id in kinds)
                        or (isinstance(f, ast.Attribute) and f.attr in kinds)):
                    constructions += 1
            if not isinstance(node, ast.Compare):
                continue
            compares += 1
            operands = [node.left] + list(node.comparators)

            def is_clock(x):
                if not isinstance(x, ast.Call):
                    return None
                f = x.func
                if isinstance(f, ast.Name) and f.id in kinds:
                    return f.id
                if isinstance(f, ast.Attribute) and f.attr in kinds:
                    return f.attr
                return None

            clocks = [k for k in map(is_clock, operands) if k]
            if clocks and any(_numeric_literal(o) for o in operands):
                findings.append(_at(mod, node,
                                    f"compares a {clocks[0]} clock against a bare number: "
                                    f"{mod.line(node.lineno)} -- a threshold with no unit is a threshold "
                                    f"from somewhere else. Name the kind on both sides, or convert "
                                    f"explicitly through the function in spine.derive that owns the rate."))
    detail = (f"{len(kinds)} clock kind(s) ({', '.join(sorted(kinds))}); {constructions} construction(s) "
              f"and {compares} comparison(s) examined")
    return _report("O7", "clock kinds are never compared against bare int literals",
                   not findings, detail, findings, vacuous=not constructions)


# ==================================================================================================
# O8 -- LeverSet.from_env is called from EXACTLY ONE file, the wiring file
# ==================================================================================================
#
# THE CHECK THAT DOES NOT CARE HOW THE NAME IS SPELLED. O3 counts lever sets, and counting things by name
# is precisely what an alias defeats: `from fabric.levers import FabricLevers as _F` put FAB's set into a
# memory module under a name O3 had never heard of, and `_F.from_env().slots` read FAB_SLOTS through all
# seven checks. O3 now resolves aliases, but resolution is a race against spellings -- a dict of classes,
# a factory, a getattr with a computed string -- and every round of that race is won by whoever writes
# the next module. This check does not enter the race. It constrains the CALL SITE: whatever `_F` is and
# however it was named, a `.from_env(` outside spine/assemble.py is a finding.
#
# WHY from_env AND NOT SOMETHING ELSE. It is the operation that turns a declaration into values. A module
# can import a lever set, subclass it, print it, and read its defaults off the class without ever
# resolving anything from the environment; the moment it calls from_env it has minted a Config for a
# package that is not its own, and every lever in that package is one attribute away. Between this and
# O1, the environment is READ in one file and the read is TRIGGERED from one file, so the only door to a
# Config is build() and the only caller of build() is the entry point.
#
# THE READER MUST EXIST, same clause as O1 and for the same reason. If nothing in the wiring file calls
# from_env, this check passes over a tree where no lever is ever resolved -- a guard that cannot tell
# "correct" from "absent" is the untrippable shape this project has 60 records of.
#
# CANNOT CATCH:
#   * `getattr(cls, "from_" + "env")()`, or a resolver wrapped in a helper that lever.py itself exports.
#     A literal-string getattr IS caught; a computed one is not.
#   * a Config that arrives some other way -- passed in from the entry point, stashed on a shared object,
#     or handed over as a plain argument. That is O9's half, and past O9 it is L3's.
#   * anything outside src/. A test or a script resolving a synthetic set in isolation is what build()'s
#     `sets=` parameter is for, and scanning tests here would make the check fail on its own self-test.
# OVER-CATCHES ON PURPOSE: any attribute named `from_env` on any object, including one that has nothing
# to do with levers. A false positive is read once by a human; a minted foreign Config is silent forever.

FROM_ENV = "from_env"


def check_o8_from_env_only_in_wiring_file(mods):
    findings, per_file = [], {}
    for mod in mods:
        _, from_names = _imports(mod)
        # `from spine.lever import LeverSet as _LS` does not bind from_env, but
        # `from somewhere import from_env` would. Track the local name, not the spelling.
        aliased = {local for local, (base, orig) in from_names.items() if orig == FROM_ENV}
        for node in ast.walk(mod.tree):
            hit = None
            if isinstance(node, ast.Attribute) and node.attr == FROM_ENV:
                hit = _attr_name(node) or f"<expr>.{FROM_ENV}"
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in aliased:
                hit = f"{node.id} (imported from_env)"
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == "getattr" and len(node.args) >= 2
                  and isinstance(node.args[1], ast.Constant) and node.args[1].value == FROM_ENV):
                hit = f"getattr(..., {FROM_ENV!r})"
            if hit is None:
                continue
            per_file.setdefault(mod.rel, []).append(node.lineno)
            if mod.rel != WIRING_FILE:
                # The source line is quoted for the same reason O1 quotes it: what a reader needs is
                # WHICH set is being resolved, and `_F.from_env()` only says that in the file itself.
                findings.append(_at(mod, node, f"resolves a lever set as {hit}: {mod.line(node.lineno)} "
                                               f"-- only {WIRING_FILE} may call from_env. Minting a "
                                               f"Config here puts every lever of that package one "
                                               f"attribute away, whatever the local name says. Take the "
                                               f"Config your package is given, or declare a wire."))
    calls_here = len(per_file.get(WIRING_FILE, []))
    if calls_here == 0:
        findings.append(f"{WIRING_FILE}  never calls {FROM_ENV}. build() is the only door to a Config; "
                        f"if it has stopped resolving lever sets, this check is passing over a tree "
                        f"where nothing reads the environment at all.")
    detail = (f"{sum(len(v) for v in per_file.values())} from_env reference(s) in {len(per_file)} "
              f"file(s); {calls_here} in {WIRING_FILE}; {len(mods)} files scanned")
    return _report("O8", "from_env is called only from the wiring file", not findings, detail, findings)


# ==================================================================================================
# O9 -- no function outside the wiring file receives two packages' Configs, and one that receives a
#       Config says whose it is
# ==================================================================================================
#
# THE DEFECT, EXACTLY. spine/lever.py and spine/assemble.py both stated that a package receives only its
# own record, so "reading a foreign lever is a NameError at author time, not a policy". It is not. build()
# returns a dict keyed by PREFIX, a Config carries no owner check at the point of use, and
#     def memory_prune(cfg): return cfg.slots        # memory_prune(configs["FAB"]) -> 2048
# runs, returns FAB's slot count, and raises nothing. A reviewer verified it. The wording in both files is
# now what is true; this check and `Config.owned_by` are the part that can be enforced.
#
# TWO HALVES, AND NEITHER IS THE WHOLE THING:
#   signature   a function outside the wiring file may not annotate two parameters as Configs. Holding
#               two packages at once is the thing exactly one file may do, and a signature is the one
#               form of that AST can read without a type system.
#   assertion   a Config-annotated parameter outside src/spine/ must be paired with an
#               `owned_by("PREFIX")` call naming a string literal. Without it the annotation says "some
#               package's levers", which is not a statement about ownership at all -- and the whole point
#               of the helper is that it fires on the wrong hand-off at startup, naming both packages,
#               instead of returning a plausible number.
#
# WHY src/spine/ IS EXEMPT FROM THE SECOND HALF ONLY. The spine implements Config; build(), render() and
# the wiring views necessarily take one that belongs to no package in particular, and demanding they
# declare a prefix would be demanding a wrong answer. They are NOT exempt from the first half: nothing in
# the spine outside the wiring file has any business holding two packages in one signature either. The
# exempt count is printed, because an exemption nobody can see is an exemption nobody re-reads.
#
# IF A FUNCTION OUTSIDE THE SPINE GENUINELY TAKES ANY PACKAGE'S CONFIG -- report rendering is the case
# that will come up -- it is machinery, not a package, and the two fixes are to move it into src/spine/
# or to have it take the `{PREFIX: Config}` map, which is not a Config and is not annotated as one. The
# fix that is NOT available is deleting this half, because the assertion is the only thing between a
# wrong hand-off and a plausible number in a report, and a report is where a wrong number does the most
# damage: it is read as a result.
#
# CANNOT CATCH -- and this is the larger half of the truth:
#   * an UNANNOTATED parameter. `def prune(cfg)` handed configs["FAB"] is the original defect and it is
#     invisible here; there is nothing in the text that distinguishes it from correct code. This check
#     raises the cost of the mistake for annotated code and does nothing at all for the rest, which is
#     why the docstrings may not go back to calling any of this structural.
#   * a Config reached through a container: `cfgs["FAB"].slots` inside a package module, a Config stored
#     on an object, a closure over the build() result. O3 and O8 are what keep the build() result from
#     being reachable in the first place, and neither is a guarantee about where it goes afterwards.
#   * whether `owned_by("MEM")` names the RIGHT package for the function it sits in. A literal that
#     matches no declared PREFIX is caught; a literal that names the wrong existing package is not.
#   * a call to owned_by in a nested def counting for the enclosing one. The walk does not scope, and
#     tightening it would trade a real false negative for a rare one.
# OVER-CATCHES ON PURPOSE: any annotation whose final component is `Config`, resolved or not.

CONFIG_CLASS = "Config"
SPINE_DIR = os.path.join("src", "spine") + os.sep


def _annotates_config(node, unalias):
    """Does this parameter annotation name spine.lever.Config, however it is spelled?

    `Config`, `lever.Config`, `"Config"`, `"spine.lever.Config"` and `Optional[Config]` all count. String
    annotations are included because `from __future__ import annotations` turns every annotation in a file
    into one, and a check that stopped seeing annotations the day someone added that import would be a
    check that silently stopped running.
    """
    if node is None:
        return False
    if isinstance(node, ast.Subscript):
        inner = node.slice
        elts = inner.elts if isinstance(inner, ast.Tuple) else [inner]
        return any(_annotates_config(e, unalias) for e in elts)
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Attribute):
        name = node.attr
    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
        name = node.value.strip().strip("'\"").rpartition(".")[2].strip()
    else:
        return False
    return unalias.get(name, name) == CONFIG_CLASS


def _config_params(mod):
    """(function node, [parameter names annotated as a Config]) for every def in a module."""
    _, from_names = _imports(mod)
    unalias = {local: orig for local, (base, orig) in from_names.items()}
    out = []
    for node in ast.walk(mod.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        a = node.args
        params = list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)
        params += [p for p in (a.vararg, a.kwarg) if p is not None]
        hits = [p.arg for p in params if _annotates_config(p.annotation, unalias)]
        if hits:
            out.append((node, hits))
    return out


def _owned_by_calls(fnode):
    """Every `x.owned_by(...)` inside a function, as (node, the literal prefix or None)."""
    out = []
    for n in ast.walk(fnode):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "owned_by":
            arg = n.args[0] if n.args else None
            lit = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
            out.append((n, lit))
    return out


def check_o9_one_config_per_signature(mods):
    prefixes = {p for _, _, p in _leversets(mods).values() if isinstance(p, str)}
    findings, fns, params, exempt = [], 0, 0, 0
    for mod in mods:
        for fnode, hits in _config_params(mod):
            fns += 1
            params += len(hits)
            if len(hits) > 1 and mod.rel != WIRING_FILE:
                findings.append(_at(mod, fnode,
                                    f"{fnode.name}({', '.join(hits)}) annotates {len(hits)} Config "
                                    f"parameters. One function holding two packages' levers is the thing "
                                    f"only {WIRING_FILE} may do -- it can read across the boundary with "
                                    f"no wire, no ledger row and nothing in affects() to say so."))
            if mod.rel == WIRING_FILE or mod.rel.startswith(SPINE_DIR):
                exempt += 1
                continue
            asserted = _owned_by_calls(fnode)
            if not asserted:
                findings.append(_at(mod, fnode,
                                    f"{fnode.name}({hits[0]}: Config) never says WHOSE Config it is. Add "
                                    f"`{hits[0]} = {hits[0]}.owned_by(\"PREFIX\")`. A Config does not know "
                                    f"who is holding it: memory_prune(configs[\"FAB\"]) returns FAB's "
                                    f"levers and raises nothing, and the assertion is the only thing "
                                    f"that turns that into a startup failure."))
                continue
            for node, lit in asserted:
                if lit is None:
                    findings.append(_at(mod, node,
                                        f"owned_by(...) with a non-literal prefix: "
                                        f"{mod.line(node.lineno)} -- this check reads the source text, so "
                                        f"a computed prefix is an assertion no static pass can verify."))
                elif prefixes and lit not in prefixes:
                    findings.append(_at(mod, node,
                                        f"owned_by({lit!r}) names no declared PREFIX. Declared in src/: "
                                        f"{sorted(prefixes)}. An assertion against a prefix that does not "
                                        f"exist can never fail, and never failing is what it looks like "
                                        f"from the outside when it is working."))
    detail = (f"{fns} function(s) with a Config-annotated parameter, {params} such parameter(s); "
              f"{exempt} exempt from the ownership assertion ({WIRING_FILE} and {SPINE_DIR}*)")
    return _report("O9", "no function outside the wiring file receives two packages' Configs",
                   not findings, detail, findings, vacuous=not fns)


# ==================================================================================================
# SELF-TEST -- every check below is run against a tree that CONTAINS the defect it looks for
# ==================================================================================================
#
# WHY THIS IS NOT OPTIONAL HERE. src/ currently holds only the spine: no lever sets, no packages, no
# Config parameters. O3, O8 and O9 therefore all report VACUOUS on the real tree, and a check that has
# only ever been run over an empty population is not evidence about anything. Worse, that is exactly the
# state O3 was in while it was broken -- it printed PASS on every commit for as long as there was nothing
# for it to look at, and when a reviewer finally handed it the aliased module it printed PASS on that too.
#
# EACH CASE ASSERTS BOTH DIRECTIONS. The bypass tree must FAIL, and the control -- the same tree, one file
# different -- must PASS. Only the failing direction is a regression test; only the passing direction
# distinguishes a real check from one that fails on everything, and a check that fails on everything gets
# switched off within a week and is then worth less than no check at all.
#
# ONLY THE CHECK A CASE IS ABOUT IS RUN, not all nine. O1 would fail on the stand-in lever.py below (it
# names no environment), and O4 imports the real spine.assemble to cross-check the live COUPLINGS table
# against the source text -- correct behaviour for the real tree and meaningless against a synthetic one.
# Running them anyway would make every case fail for reasons that have nothing to do with what it tests.

_BASE_TREE = {
    "src/spine/lever.py": '''\
"""A stand-in for the real spine/lever.py: only what the checks parse."""


class Lever:
    def __init__(self, default, help):
        self.default, self.help = default, help


class LeverSet:
    PREFIX = None

    @classmethod
    def from_env(cls, environ=None):
        return Config(cls)


class Config:
    def owned_by(self, prefix):
        return self
''',
    "src/spine/assemble.py": '''\
from fabric.levers import FabricLevers
from memory.store import MemoryLevers


def build():
    return {c.PREFIX: c.from_env() for c in (FabricLevers, MemoryLevers)}
''',
    "src/fabric/levers.py": '''\
from spine.lever import Lever, LeverSet


class FabricLevers(LeverSet):
    PREFIX = "FAB"
    slots = Lever(2048, "expert slots")
''',
    "src/memory/store.py": '''\
from spine.lever import Config, Lever, LeverSet


class MemoryLevers(LeverSet):
    PREFIX = "MEM"
    quota = Lever(64, "slots per owner")


def prune(mem: Config):
    mem = mem.owned_by("MEM")
    return mem.quota
''',
}

# The reviewer's module, character for character in what matters: a foreign lever set bound to a local
# name, and from_env called on that name. Under the old O3 this named ZERO lever sets.
_ALIAS_IMPORT = '''\
from spine.lever import Config, Lever, LeverSet
from fabric.levers import FabricLevers as _F


class MemoryLevers(LeverSet):
    PREFIX = "MEM"
    quota = Lever(64, "slots per owner")


def capacity():
    return _F.from_env().slots * 64
'''

# The same bypass through a module alias instead of a class alias. The old O3 DID catch this one, because
# it matched ast.Attribute.attr against class names -- so this case exists to prove that resolving by
# origin did not trade one hole for another.
_ALIAS_ATTR = '''\
import fabric.levers as _fl
from spine.lever import Config, Lever, LeverSet


class MemoryLevers(LeverSet):
    PREFIX = "MEM"
    quota = Lever(64, "slots per owner")


def capacity():
    return _fl.FabricLevers.from_env().slots * 64
'''

# One lever set in scope, and it is somebody else's. O3 cannot catch this and says so in its CANNOT CATCH
# block: one set in scope is legal, and nothing in the text says whose it is. O8 catches it on the call.
_FOREIGN_ONLY = '''\
from fabric.levers import FabricLevers as _F


def capacity():
    return _F.from_env().slots * 64
'''

# A lever set that no static resolver can follow -- it is a dict value, reached by subscript. This is the
# case that shows why O8 constrains the CALL SITE instead of the name: O3 cannot see a set here at all,
# and O8 does not need to, because `.from_env(` is still written in the file.
_DICT_OF_SETS = '''\
from fabric.levers import FabricLevers as _F

SETS = {"FAB": _F}


def capacity():
    return SETS["FAB"].from_env().slots * 64
'''

# THE HOLE, PINNED OPEN ON PURPOSE. This is the reviewer's original finding in its purest form: an
# ordinary parameter, no annotation, handed another package's Config by whoever calls it. Nothing in the
# source text distinguishes it from correct code and no check in this file fires. The case asserts that
# all three checks PASS, so that the day someone closes the hole this case FAILS and forces them to say
# so here -- and so that nobody reading the green output above can believe it is already closed. An
# untested claim is what this whole finding was about.
_UNANNOTATED = '''\
def memory_prune(cfg):
    return cfg.slots
'''

_TWO_CONFIGS = '''\
from spine.lever import Config, Lever, LeverSet


class MemoryLevers(LeverSet):
    PREFIX = "MEM"
    quota = Lever(64, "slots per owner")


def prune(mem: Config, fab: Config):
    return mem.quota * fab.slots
'''

_NO_ASSERTION = '''\
from spine.lever import Config, Lever, LeverSet


class MemoryLevers(LeverSet):
    PREFIX = "MEM"
    quota = Lever(64, "slots per owner")


def prune(cfg: Config):
    return cfg.quota
'''

_WRONG_PREFIX = '''\
from spine.lever import Config, Lever, LeverSet


class MemoryLevers(LeverSet):
    PREFIX = "MEM"
    quota = Lever(64, "slots per owner")


def prune(mem: Config):
    mem = mem.owned_by("MEN")
    return mem.quota
'''

_DUP_A = '''\
from spine.lever import Lever, LeverSet


class Levers(LeverSet):
    PREFIX = "DUP"
    x = Lever(1, "x")
'''

_DUP_B = '''\
from spine.lever import Lever, LeverSet


class Levers(LeverSet):
    PREFIX = "DUP"
    y = Lever(2, "y")
'''

# (name, files overlaid on _BASE_TREE, {check tag: (expected exit code, text its output must contain)})
# =====================================================================================================
def check_o10_no_backdoor_imports(mods):
    """O10 -- a package may not reach the spine's assembly, the registry, or a foreign levers module.

    WHY THIS EXISTS, and it is the check O1-O9 needed. O8 constrains the CALL SITE of from_env, which
    only works while from_env is the only way to mint a foreign Config. It is not. Three routes were
    demonstrated end to end against the shipped suite, each returning a foreign package's env-overridden
    value with all nine checks passing:

      build()          `from spine.assemble import build` in a memory module, then build()[0]["FAB"] --
                       every package's Config, through the one door that is a legal from_env call site
                       by construction. With FAB_ALPHA=0.9 the memory module returned 900.
      the registry     `registry.all_sets()["FAB"]` hands back the class, and getattr(cls, "from_" +
                       "env") or LeverSet.__dict__["from_env"].__func__ mints from it. O8 matches
                       spellings -- an Attribute named from_env, a from-import of it, getattr with a
                       CONSTANT second argument -- and a computed string, a subscript and an
                       importlib.import_module all walk past. Its own header claimed naming the one
                       legal call site "is not a race against spellings"; it was.
      the declaration  `FABLevers._levers["alpha"].default` reads a foreign lever with no from_env call
                       and no Config at all. Editing FAB's literal then changes MEM's behaviour, and
                       affects() cannot see it -- precisely the coupling G1 exists to detect.

    So the boundary moves from the CALL to the IMPORT, which is a much smaller surface: a module that
    cannot name spine.assemble, spine.registry or a foreign levers module has nothing to call.

    AND IT IS AN ALLOWLIST, BECAUSE THE BLACKLIST WAS DEFEATED BY THE NEXT FILE ADDED TO src/spine/.
    The first version of this check asked `if "assemble" in tail or "registry" in tail`. P3 then wrote
    src/spine/compose.py, whose line 50 was

        from spine.assemble import build, render          # noqa: F401 -- render is re-exported

    which makes `build` an attribute of the module `spine.compose`. For that name the tail is
    ["spine", "compose"] -- no "assemble", no "registry" -- and the head is "spine", which this check
    removes from the package set. So `from spine.compose import build` read as an ordinary permitted
    spine import, and a reviewer demonstrated it: a memory module returned FAB.alpha=0.9 and
    LM.dropout=0.37 from the live environment with all ten checks and all five contract checks green.
    Reproduced here before this was rewritten.

    That is route 1 -- the one this check was WRITTEN to close -- reopened by a differently spelled name
    for the same door, four commits later. It is also the route an implementation agent reaches for by
    accident: they need build(), they know spine.assemble is banned, and spine.compose offers it. A
    blacklist of two tails is a race against spellings, which is the criticism this docstring already
    makes of O8, made of this check by the next thing anyone wrote.

    So: a package may import spine.{lever, units, derive, rng, wire} and nothing else under spine. That
    is PLAN's permitted set, it is closed, and a future spine module holding a re-export is refused
    until someone adds it here on purpose.

    WHAT IT CANNOT CATCH, and the list got longer once a reviewer went looking:
      * a module already inside src/spine/, exempt by construction;
      * a value handed to a package as an ordinary argument -- legal Python, O9's territory;
      * THE WALK THAT NEEDS NO IMPORT. spine.lever is on the permitted list and must be -- Config is the
        annotation on all 117 contract entry points -- so `LeverSet.__subclasses__()` returns all
        thirteen lever sets and `getattr(sib, "from_" + "env")()` mints each from the environment.
        Reproduced: thirteen packages, every env-overridden value, ten checks green. Worse, a package's
        OWN Config reaches the same class through `cfg._owner.__mro__` with nothing imported at all.
        No AST rule can see that, and no rewrite of this check will. What answers it is the runtime
        latch in spine/lever.py -- build() closes the assembly as its last act and from_env raises after
        -- which matches a MOMENT rather than a name. The DECLARATION half
        (`sib._levers["alpha"].default`) survives even that, and only L3 reaches it.
    Do not read a green O10 as "there is no other route". That sentence is the reason a reviewer stops
    looking, and this file has now been corrected for a version of it twice.
    """
    ALLOWED_SPINE = ("lever", "units", "derive", "rng", "wire")
    findings = []
    _PKG_DIRS = {m.rel.split("/")[1] for m in mods
                 if m.rel.startswith("src/") and m.rel.count("/") >= 2} - {"spine"}
    for m in mods:
        if m.rel.startswith("src/spine/"):
            continue                                   # the spine is the assembly; it must import both
        pkg = m.rel.split("/")[1] if m.rel.startswith("src/") and "/" in m.rel[4:] else ""
        for node in ast.walk(m.tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                # THE BASE OF A from-IMPORT IS NOT ITSELF AN IMPORT, and treating it as one made the
                # allowlist refuse `from spine import units as U` in all thirteen levers.py files -- the
                # single most common line in the tree. `from spine import units` binds spine.units, not
                # spine; the dotted forms below are what it actually reaches. A plain `import spine` IS
                # bare and IS refused, on the next branch, because naming the package reaches every
                # submodule already loaded -- and spine.assemble loads all of them.
                names = [f"{base}.{a.name}" if base else a.name for a in node.names]
                if node.level >= 2:
                    findings.append(f"{m.rel}:{node.lineno}  a relative import of level {node.level} "
                                    f"climbs out of its own package. src/ is flat under one sys.path "
                                    f"entry, so this cannot resolve at all -- and if it could, it would "
                                    f"be the coupling O10 refuses.  {m.line(node.lineno)}")
            for n in names:
                tail = n.split(".")
                if tail and tail[0] == "spine":
                    # ALLOWLIST. `import spine` alone is len 1 and reaches every submodule through
                    # attribute access, so it is refused too -- naming the package is naming all of it.
                    sub = tail[1] if len(tail) > 1 else ""
                    if sub not in ALLOWED_SPINE:
                        findings.append(
                            f"{m.rel}:{node.lineno}  imports {n!r} -- a package may import only "
                            f"spine.{{{', '.join(ALLOWED_SPINE)}}}. Everything else under spine is the "
                            f"assembly: spine.assemble and spine.registry hand out every package's "
                            f"Config, and spine.compose re-exported build() under a name a blacklist of "
                            f"tails did not match.  {m.line(node.lineno)}")
                elif True:
                    # NO PACKAGE MAY IMPORT ANOTHER PACKAGE AT ALL. Banning only foreign *levers* left
                    # the natural form of the leak open, and a reviewer demonstrated it: the OWNER
                    # writes its own module global (`SLOTS = None`, then `install(cfg)` sets it) and the
                    # foreign package only READS it (`from fabric import state`; `state.SLOTS // 2`).
                    # Every step is legal on its own, O5 only inspects the WRITE side, and with
                    # FAB_SLOTS=901 the memory function returned 450 with all checks green. There was no
                    # wire, no ledger row, and nothing in affects().
                    # The whole architecture says cross-package values arrive as arguments the spine
                    # assembled -- so a package importing another package IS the coupling, whatever it
                    # then reads. Measured before adopting: 0 cross-package imports across all 13
                    # packages, so the strongest boundary costs nothing today.
                    head = tail[0] if tail and tail[0] else ""
                    if pkg and head in _PKG_DIRS and head != pkg:
                        findings.append(f"{m.rel}:{node.lineno}  imports {n!r} -- {head!r} is another "
                                        f"package. Cross-package values arrive as arguments the spine "
                                        f"assembled; an import is a coupling with no wire and nothing "
                                        f"in affects().  {m.line(node.lineno)}")
            if isinstance(node, ast.Call):
                f = node.func
                nm = (f.attr if isinstance(f, ast.Attribute) else
                      f.id if isinstance(f, ast.Name) else "")
                if nm in ("import_module", "__import__"):
                    findings.append(f"{m.rel}:{node.lineno}  calls {nm}() -- a dynamic import has no "
                                    f"import statement for any of these checks to resolve.  "
                                    f"{m.line(node.lineno)}")
    n_out = sum(1 for m in mods if not m.rel.startswith("src/spine/"))
    return _report("O10", "no package reaches the assembly, the registry, or another package",
                   not findings,
                   f"{n_out} module(s) outside src/spine/ examined", findings, vacuous=not n_out)


# =====================================================================================================
def check_o11_no_unnamed_clock_arithmetic(mods):
    """O11 -- a package body may not do arithmetic on a lever that declares a Clock unit.

    THE DEFECT THAT PRODUCED IT, and the paragraph it was written under. src/opt/api.py said

        units.Steps becomes literally true and no conversion function is needed -- which matters,
        because spine/derive.py has no Windows->Steps function today (verified).

    and four lines below resolved the LR horizon as

        run_steps = max(1, run_windows // d_effective_batch_windows)

    which IS a Windows->Steps conversion, inline, on bare ints, unguarded. The parenthetical was even
    true -- derive had no such function, which is exactly why the division had to be hand-written.
    A reviewer found the assertion and the line together.

    Nothing was numerically wrong at the shipped batch_windows=1, accum=1, where the two counters
    coincide. That is what made it survive. At fetch_big.py's own recommended heavy-run command
    (WIN=256 BATCH_W=16 ACCUM=4) the divisor is 64, and a horizon in the wrong kind puts every
    learning-rate result under a schedule 64 times longer than its label.

    THE RULE IS units.py:86's, APPLIED: "There is no implicit path between kinds ... call the named
    function in spine.derive that already knows the rate, so the conversion exists in one place with
    a name." A division written at its call site is a conversion nobody can audit, and every
    historical instance of this project's most repeated defect is one of those.

    MEASURED BEFORE ADOPTING, as O10 was: after the opt repair there are ZERO such sites across all
    thirteen packages, so the strongest form of the rule costs nothing today. It is added while it is
    green precisely because it cannot then go red silently -- and P4, which writes the bodies, is
    where every one of these would otherwise appear.

    WHAT IT CANNOT CATCH, and the second one is why H51 is still open:
      * arithmetic on a Clock-unit value that arrives as a plain ARGUMENT rather than as a lever
        read. `run_windows // n` inside a function whose parameter is named run_windows is invisible
        here -- which is what the opt defect actually looked like, so this check would have caught it
        only through the `d_effective_batch_windows` operand. Both operands are examined for that
        reason.
      * the reason the whole class is possible: Config hands back a bare int for all 35 levers that
        declare a Clock unit (ISSUES H51), so the kind is metadata at the read site. Enforced between
        packages, advisory within one. This check is the within-one half, done by AST because the
        type system cannot do it.
    """
    _PKG_DIRS = {m.rel.split("/")[1] for m in mods
                 if m.rel.startswith("src/") and m.rel.count("/") >= 2} - {"spine"}
    # The clock-unit levers of each package, from the DECLARATIONS in that package's levers.py --
    # read here rather than imported, so this pass stays "parse, never execute" like the rest.
    clocks, findings = {}, []
    _KINDS = ("Steps", "Flushes", "Windows", "Backwards", "Epochs", "Selections")
    for m in mods:
        if not m.rel.endswith("levers.py"):
            continue
        pkg = m.rel.split("/")[1] if m.rel.startswith("src/") else ""
        for node in ast.walk(m.tree):
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Call)
                    and getattr(node.value.func, "id", "") == "Lever"):
                continue
            for a in node.value.args + [k.value for k in node.value.keywords]:
                nm = (a.attr if isinstance(a, ast.Attribute) else
                      a.id if isinstance(a, ast.Name) else "")
                if nm in _KINDS:
                    clocks.setdefault(pkg, set()).add(node.targets[0].id)
    n_clocks = sum(len(v) for v in clocks.values())

    _OPS = (ast.FloorDiv, ast.Mult, ast.Mod, ast.Div, ast.Pow)
    _TXT = re.compile(r"\b([a-z_][a-z_0-9]*)\s*(//|%|\*(?!\*))\s*")
    examined = 0
    for m in mods:
        if m.rel.startswith("src/spine/"):
            continue                      # derive IS the named conversion; it must do the arithmetic
        pkg = m.rel.split("/")[1] if m.rel.startswith("src/") else ""
        mine = clocks.get(pkg, set())
        if not mine:
            continue

        # (a) REAL CODE. This is the half that matters once P4 writes bodies.
        for node in ast.walk(m.tree):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, _OPS)):
                continue
            examined += 1
            for side in (node.left, node.right):
                nm = side.attr if isinstance(side, ast.Attribute) else ""
                if nm in mine:
                    findings.append(
                        f"{m.rel}:{node.lineno}  {pkg}.{nm} declares a Clock unit and is an operand "
                        f"of {type(node.op).__name__} in CODE. A cross-kind conversion written at "
                        f"its call site is one nobody can audit -- units.py:86 requires it to be a "
                        f"named function in spine.derive.  {m.line(node.lineno)}")

        # (b) THE DOCSTRING SPECIFICATIONS, WHICH AT THIS PHASE ARE THE CODE. Every entry point is a
        # stub that raises NotImplementedError, so the (a) half above examines ZERO expressions and
        # cannot fail -- which is how the first version of this check shipped untrippable. It was
        # caught by putting the original defect back and watching O11 stay green.
        #
        # That matters more than it sounds. The defect this check exists for lived in exactly this
        # place: src/opt/api.py's build() docstring specified the horizon as
        #     run_steps = max(1, run_windows // d_effective_batch_windows)
        # and the repair for it edited that DOCSTRING, because there is no body yet. A rule that
        # only reads bodies would have declared the tree clean while the specification P4 is going
        # to implement still said "divide it inline".
        #
        # Textual, and deliberately narrow: `name // ...`, `name % ...`, `name * ...` where the name
        # is one of THIS package's clock levers. It cannot parse prose and does not try; a formula
        # written some other way slips past. What it buys is that the spec and the code are held to
        # one rule, at the phase where the spec is all there is.
        for i, line in enumerate(m.lines, 1):
            # A FORMULA IN BACKTICKS IS A QUOTATION, NOT A SPECIFICATION, and the distinction had to
            # be drawn because the first live version of this check flagged its own explanation.
            # fabric/api.py and domains/api.py both carry the sentence
            #     `manage_every // batch_w` -- Windows to Flushes, unnamed -- which is
            #     derive.flush_period_windows and is not this.
            # written to explain what the rule forbids. Two of the check's three findings were that
            # prose. A check that reports the documentation of its own rule as a violation of it is
            # noise, and noise is how the real third finding gets skipped.
            # THE HOLE THIS LEAVES, stated rather than discovered later: a genuine specification
            # written inside backticks is skipped. That is a convention this tree already follows --
            # specifications are written as bare indented code under a heading, quotations are
            # inline and quoted -- but it is a convention, not a guarantee.
            bare = re.sub(r"`[^`]*`", "", line)
            for nm, op in _TXT.findall(bare):
                if nm in mine:
                    examined += 1
                    findings.append(
                        f"{m.rel}:{i}  {pkg}.{nm} declares a Clock unit and is divided or scaled by "
                        f"'{op}' in a SPECIFICATION. Every body here is still a stub, so this "
                        f"docstring is what P4 will implement -- name the conversion in "
                        f"spine.derive and write that call instead.  {line.strip()[:70]}")
    return _report("O11", "no package body does arithmetic on a lever that declares a Clock unit",
                   not findings,
                   f"{examined} arithmetic site(s) examined in package code AND in the docstring "
                   f"specifications P4 implements, against {n_clocks} clock-unit lever(s) declared "
                   f"across {len(clocks)} package(s)",
                   findings, vacuous=not n_clocks)



_CLOCK_ARITH_CODE = """\
from spine.lever import Config


def flush_gate(fab: Config, batch_w):
    \"\"\"the shape units.py forbids: a cross-kind conversion at its call site\"\"\"
    return fab.manage_every // max(1, batch_w)
"""

_CLOCK_ARITH_SPEC = """\
from spine.lever import Config


def flush_gate(fab: Config, batch_w):
    \"\"\"P4 fills this in. The gate is
        period = manage_every // batch_w
    which is what the loop compared against _nbwd.
    \"\"\"
    raise NotImplementedError("x")
"""

_CLOCK_ARITH_QUOTED = """\
from spine.lever import Config


def flush_gate(fab: Config, batch_w):
    \"\"\"P4 fills this in. It must NOT write `manage_every // batch_w` inline -- that is the
    conversion derive.flush_period_windows exists to name.
    \"\"\"
    raise NotImplementedError("x")
"""

_CLOCK_LEVERS = """\
from spine.lever import Lever, LeverSet
from spine import units as U


class FabricLevers(LeverSet):
    PREFIX = "FAB"
    manage_every = Lever(500, "the management cadence", U.Windows)
    alpha = Lever(0.5, "not a clock", U.FLAG)
"""

# --- O10 fixtures. The check had no self-test cases until the route it was written to close was
# --- reopened by src/spine/compose.py and a reviewer walked through it with every check green.

_SPINE_COMPOSE_REEXPORT = """\
from spine.compose import build
from spine.lever import Config


def prune_budget(mem: Config):
    return build(environ=None)[0]["FAB"].alpha
"""

_BARE_SPINE = """\
import spine


def peek():
    return spine.assemble.build(environ=None)[0]["MEM"].quota
"""

_PERMITTED_SPINE = """\
from spine import units as U
from spine.lever import Config
from spine.derive import cull_gate_open


def manage(fab: Config):
    fab = fab.owned_by("FAB")
    return cull_gate_open(fab.n0, fab.slots, fab.pressure), U.Windows(1)
"""

_CROSS_PACKAGE = """\
from fabric import state
from spine.lever import Config


def blocks(mem: Config):
    return state.SLOTS // 2
"""

_DYNAMIC_IMPORT = """\
import importlib
from spine.lever import Config


def blocks(mem: Config):
    return importlib.import_module("fabric.levers").FABLevers._levers["slots"].default
"""

_CASES = (
    ("control: no bypass anywhere in the tree", {},
     {"O3": (0, None), "O8": (0, None), "O9": (0, None)}),

    ("O3/O8: a foreign lever set imported under a local alias -- the reviewer's module",
     {"src/memory/store.py": _ALIAS_IMPORT},
     {"O3": (1, "fabric.levers.FabricLevers"), "O8": (1, "_F.from_env")}),

    ("O3/O8: the same bypass spelled through a module alias",
     {"src/memory/store.py": _ALIAS_ATTR},
     {"O3": (1, "fabric.levers.FabricLevers"), "O8": (1, "_fl.FabricLevers.from_env")}),

    ("O8 alone: a module holding ONLY the foreign set, which O3 is documented not to catch",
     {"src/memory/store.py": _FOREIGN_ONLY},
     {"O3": (0, None), "O8": (1, "only " + WIRING_FILE + " may call from_env")}),

    ("O8 alone: a lever set reached through a dict, which no resolver can follow",
     {"src/memory/store.py": _DICT_OF_SETS},
     {"O3": (0, None), "O8": (1, 'SETS["FAB"].from_env')}),

    ("the residual hole, pinned open: an unannotated parameter is caught by NOTHING",
     {"src/memory/store.py": _UNANNOTATED},
     {"O3": (0, None), "O8": (0, None), "O9": (0, None)}),

    ("O3: one class name in two packages must not hide a duplicate PREFIX",
     {"src/a/levers.py": _DUP_A, "src/b/levers.py": _DUP_B},
     {"O3": (1, "claimed by both")}),

    ("O9: two Config parameters in one signature outside the wiring file",
     {"src/memory/store.py": _TWO_CONFIGS},
     {"O9": (1, "annotates 2 Config parameters")}),

    ("O9: a Config parameter that never declares whose package it is",
     {"src/memory/store.py": _NO_ASSERTION},
     {"O9": (1, "never says WHOSE Config it is")}),

    ("O9: an ownership assertion against a PREFIX no package declares",
     {"src/memory/store.py": _WRONG_PREFIX},
     {"O9": (1, "names no declared PREFIX")}),

    # ---- O11. The first version scanned CODE only, and every body in this tree is a stub, so it
    # ---- examined zero expressions and was untrippable -- caught by putting the original defect
    # ---- back and watching it stay green. It reads the docstring SPECIFICATIONS too, because at
    # ---- this phase those are what P4 implements.
    ("O11: a cross-kind conversion in real code",
     {"src/fabric/levers.py": _CLOCK_LEVERS, "src/fabric/gate.py": _CLOCK_ARITH_CODE},
     {"O11": (1, "in CODE")}),

    ("O11: the same conversion in the docstring P4 will implement",
     {"src/fabric/levers.py": _CLOCK_LEVERS, "src/fabric/gate.py": _CLOCK_ARITH_SPEC},
     {"O11": (1, "in a SPECIFICATION")}),

    # THE ADMIT SIDE, without which the two above prove only that O11 can say FAIL. Prose QUOTING the
    # forbidden formula to explain the rule is not a violation of it -- and the first live version
    # reported exactly that, flagging two of its own explanatory sentences and burying the one real
    # finding underneath them.
    ("O11: prose quoting the forbidden formula in backticks is ADMITTED",
     {"src/fabric/levers.py": _CLOCK_LEVERS, "src/fabric/gate.py": _CLOCK_ARITH_QUOTED},
     {"O11": (0, None)}),

    # ---- O10. THE FIRST OF THESE IS A REGRESSION TEST FOR A LIVE DEFEAT, not a hypothetical. O10
    # ---- shipped asking `if "assemble" in tail or "registry" in tail`; P3 wrote src/spine/compose.py
    # ---- with `from spine.assemble import build, render  # noqa: F401 -- render is re-exported`, and
    # ---- `from spine.compose import build` then read as an ordinary permitted spine import. A memory
    # ---- module returned FAB.alpha=0.9 and LM.dropout=0.37 from the live environment with all ten
    # ---- ownership checks and all five contract checks green. Reproduced before the rule was changed.
    ("O10: the assembly reached through a differently spelled spine module -- the defeat that happened",
     {"src/memory/store.py": _SPINE_COMPOSE_REEXPORT},
     {"O10": (1, "spine.compose")}),

    ("O10: bare `import spine`, which reaches every submodule already loaded",
     {"src/memory/store.py": _BARE_SPINE},
     {"O10": (1, "may import only")}),

    # THE OTHER DIRECTION, and the case without which the three above prove only that O10 can say FAIL.
    # An allowlist that refuses everything passes every bypass test and is useless; this is the line
    # every levers.py in the tree actually writes, and the first draft of the allowlist REFUSED it in
    # all thirteen of them because it treated the base of a from-import as an import of the base.
    ("O10: the permitted spine imports are ADMITTED -- units, lever and derive together",
     {"src/memory/store.py": _PERMITTED_SPINE},
     {"O10": (0, None)}),

    ("O10: one package importing another, the shared-global route O5 cannot see",
     {"src/memory/store.py": _CROSS_PACKAGE},
     {"O10": (1, "another package")}),

    ("O10: a dynamic import, which leaves no import statement to resolve",
     {"src/memory/store.py": _DYNAMIC_IMPORT},
     {"O10": (1, "dynamic import")}),
)

_BY_TAG = {
    "O3": check_o3_one_leverset_per_module,
    "O8": check_o8_from_env_only_in_wiring_file,
    "O9": check_o9_one_config_per_signature,
    "O10": check_o10_no_backdoor_imports,
    "O11": check_o11_no_unnamed_clock_arithmetic,
}


def _tree(overlay):
    """Write _BASE_TREE plus `overlay` to a fresh temp directory and return its path.

    The tree is rooted so that `load(<dir>/src)` produces paths reading `src/spine/assemble.py` -- see
    load()'s docstring. Without that, WIRING_FILE and ENV_READER would match nothing in a synthetic tree
    and every exemption in every check would land on the wrong file, which would make these cases pass
    for the wrong reason.
    """
    files = dict(_BASE_TREE)
    files.update(overlay)
    d = tempfile.mkdtemp(prefix="ownership_selftest_")
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
            mods, bad = load(os.path.join(d, "src"))
            if bad:
                findings.append(f"[{name}] the case tree does not parse, so it tests nothing: {bad}")
                continue
            for tag, (want, must_say) in sorted(expect.items()):
                ran += 1
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    got = _BY_TAG[tag](mods)
                out = buf.getvalue()
                if got != want:
                    verb = "passed a tree it must fail" if want else "failed a tree it must pass"
                    findings.append(f"[{name}] {tag} {verb}:\n{_indent(out)}")
                elif want and must_say and must_say not in out:
                    # A check that fails for the wrong reason is a green regression test over a live hole.
                    findings.append(f"[{name}] {tag} failed as required, but its finding never mentions "
                                    f"{must_say!r} -- so it may be failing for an unrelated reason:\n"
                                    f"{_indent(out)}")
        finally:
            shutil.rmtree(d, ignore_errors=True)
    detail = f"{len(_CASES)} case(s), {ran} check run(s) against synthetic trees in a temp directory"
    return _report("SELF", "the checks fail on trees that contain the bypass, and pass on ones that do not",
                   not findings, detail, findings)


# ==================================================================================================
# The runner
# ==================================================================================================


CHECKS = (
    check_o1_one_env_reader,
    check_o2_literal_defaults,
    check_o3_one_leverset_per_module,
    check_o4_wires_match_reads,
    check_o5_no_foreign_global_writes,
    check_o6_wires_have_reasons,
    check_o7_no_clock_vs_int,
    check_o8_from_env_only_in_wiring_file,
    check_o9_one_config_per_signature,
    check_o10_no_backdoor_imports,
    check_o11_no_unnamed_clock_arithmetic,
)


def main():
    mods, bad = load()
    print(f"=== ownership: L1 and L2 by AST over {os.path.relpath(SRC, ROOT)} ===")
    print(f"{len(mods)} file(s) parsed" + (f", {len(bad)} UNPARSEABLE" if bad else ""))
    print()
    failed = 0
    for b in bad:
        # A file that does not parse is not skipped: see load(). It is reported and it fails the run,
        # because the file most likely to contain what these checks look for is the broken one.
        print(f"FAIL  --  {b}")
        failed += 1
    for check in CHECKS:
        failed += check(mods)
        print()
    # LAST, AND COUNTED. Run after the checks so its output sits next to theirs, and counted into the
    # exit code because a broken check is a worse failure than anything a check reports: O3 spent its
    # whole life green while an aliased module read FAB_SLOTS through it.
    failed += selftest()
    print()
    print(f"=== {len(CHECKS)} checks + {len(_CASES)} self-test cases, {failed} failing ===")
    print("These checks prove that a module cannot MINT a foreign lever: it cannot name the environment,")
    print("cannot hold two lever sets under any spelling, and cannot call from_env outside the wiring")
    print("file. They do NOT prove it cannot READ one. A Config handed to the wrong package as an")
    print("ordinary argument is legal Python and returns the wrong package's numbers; O9 and")
    print("Config.owned_by narrow that to unannotated parameters, and nothing here narrows it further.")
    print("Nor can any of this see a coupling through shared mutable state, RNG draw order or the data --")
    print("PLAN section 4's L3 (tests/test_lever_isolation.py, behavioural, against the test_determinism")
    print("noise floor) is the load-bearing check for that, and this file is not evidence either way.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
