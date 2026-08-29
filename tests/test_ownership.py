"""The STATIC half of the lever rule: L1 (single declaration) and L2 (single reader), by AST over src/.

    python3 tests/test_ownership.py          # PASS/FAIL per check with counts; non-zero exit on any FAIL

WHAT THIS FILE PROVES, AND THE SENTENCE IT MAY NOT SAY. It proves that a module cannot NAME a foreign
lever. That is all it proves. The design review said so in as many words -- "all ten Spine checks are
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
import os
import sys

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
    """
    mods, bad = [], []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT)
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
# so a foreign lever has no name in scope and reading one is a NameError at author time rather than a
# policy. That guarantee only holds while no module imports two lever sets at once, because a module
# holding both can hand either to anything.
#
# The PREFIX duplicate half is checked here too. spine/registry.py refuses it at import, but only for
# sets that are actually imported -- a package nobody imported yet can sit in the tree for a week with a
# colliding PREFIX and the runtime check will never see it.
#
# CANNOT CATCH:
#   * a module that references ONE foreign lever set. One is legal here and has to be: the package's own
#     levers.py defines and references exactly one. This check counts NAMES IN SCOPE, so a module that
#     imports somebody else's set and none of its own reads as compliant. What stops that is that a
#     function is only ever handed its own Config -- a structural fact, not something checked here.
#   * a foreign value arriving as a plain function argument. `def cull(pop, nmax)` called with FAB.nmax
#     from a module that legitimately holds FAB is invisible to every check in this file. The `d_` rule
#     (O4) is what makes that visible, and only for values that cross via assemble.
#   * a PREFIX that is not a string literal. Reported as a hole rather than skipped, since a computed
#     PREFIX would defeat the duplicate check entirely.

def _leversets(mods):
    """Every LeverSet subclass in src/, to a fixed point, with its declared PREFIX literal.

    To a fixed point because a package may reasonably declare an intermediate base (`class Cadenced
    (LeverSet)`) and its subclasses are lever sets too. A single pass would miss them, and a lever set
    this function does not know about is one the ownership checks cannot count.
    """
    found = {}                       # class name -> (mod, node, prefix or None)
    known = {"LeverSet"}
    for _ in range(8):               # depth bound: 8 levels of lever-set inheritance is already absurd
        added = False
        for mod in mods:
            for node in ast.walk(mod.tree):
                if not isinstance(node, ast.ClassDef) or node.name in found:
                    continue
                bases = {b.id if isinstance(b, ast.Name) else b.attr
                         for b in node.bases if isinstance(b, (ast.Name, ast.Attribute))}
                if not (bases & known):
                    continue
                prefix = None
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and any(
                            isinstance(t, ast.Name) and t.id == "PREFIX" for t in stmt.targets):
                        prefix = stmt.value.value if isinstance(stmt.value, ast.Constant) else _UNKNOWN
                found[node.name] = (mod, node, prefix)
                known.add(node.name)
                added = True
        if not added:
            break
    return found


class _Unknown:
    def __repr__(self): return "<not a literal>"


_UNKNOWN = _Unknown()


def check_o3_one_leverset_per_module(mods):
    sets = _leversets(mods)
    findings = []

    # -- half one: a module may name at most one lever set --------------------------------------
    for mod in mods:
        named = set()
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Name) and node.id in sets:
                named.add(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in sets:
                named.add(node.attr)
            elif isinstance(node, ast.ClassDef) and node.name in sets:
                named.add(node.name)
        if len(named) > 1 and mod.rel != WIRING_FILE:
            findings.append(f"{mod.rel}:1  names {len(named)} lever sets ({', '.join(sorted(named))}). "
                            f"Only {WIRING_FILE} may hold more than one: a module with two sets in scope "
                            f"can hand either to anything, which is the read L2 forbids.")

    # -- half two: one PREFIX, one owner --------------------------------------------------------
    by_prefix = {}
    for name, (mod, node, prefix) in sorted(sets.items()):
        if prefix is _UNKNOWN:
            findings.append(_at(mod, node, f"{name}.PREFIX is not a string literal, so the static "
                                           f"duplicate-prefix check cannot see it. Only the import-time "
                                           f"check in spine/registry.py covers this set, and that one "
                                           f"only fires for sets something actually imports."))
            continue
        if prefix is None:
            findings.append(_at(mod, node, f"{name} declares no PREFIX. Ownership IS the namespace: "
                                           f"without a prefix the environment name cannot be generated."))
            continue
        prior = by_prefix.get(prefix)
        if prior is not None:
            findings.append(_at(mod, node, f"PREFIX {prefix!r} is claimed by both {prior[0]} "
                                           f"({prior[1].rel}:{prior[2].lineno}) and {name}. "
                                           f"One prefix, one owner."))
        else:
            by_prefix[prefix] = (name, mod, node)
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

    # -- backward: every declared destination is read, unless its package does not exist yet ------
    prefixes = {p for _, _, p in _leversets(mods).values() if isinstance(p, str)}
    unread, deferred = [], []
    for dst in dsts:
        prefix, _, field = dst.partition(".")
        if field in reads:
            continue
        (unread if prefix in prefixes else deferred).append(dst)
    for dst in unread:
        findings.append(f"{WIRING_FILE}:1  {dst} is declared and its package is registered, but nothing "
                        f"in src/ reads it. A wire nobody reads spends budget, prints an edge, and "
                        f"delivers a value that arrives nowhere.")

    detail = (f"{len(dsts)} declared destination(s), {len(reads)} distinct d_ field(s) read at "
              f"{sum(len(v) for v in reads.values())} site(s); {len(unread)} declared-but-unread, "
              f"{len(deferred)} deferred (package not in src/ yet)")
    ok = not findings
    rc = _report("O4", "every d_ read is a declared wire, and every declared wire is read",
                 ok, detail, findings, vacuous=not reads and not dsts)
    if deferred:
        # Printed on a pass as well as a failure. The backward direction is untested for these rows and
        # saying so is the difference between a result and a green tick over an empty set.
        print(f"          note: the backward direction is UNTESTED for {len(deferred)} of {len(dsts)} "
              f"rows -- their packages are not in src/ yet:")
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
    print(f"=== {len(CHECKS)} checks, {failed} failing ===")
    print("These checks prove that a module cannot NAME a foreign lever. They cannot see a coupling")
    print("through shared mutable state, RNG draw order or the data -- PLAN section 4's L3")
    print("(tests/test_lever_isolation.py, behavioural, against the test_determinism noise floor) is the")
    print("load-bearing check for that, and this file is not evidence about it either way.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
