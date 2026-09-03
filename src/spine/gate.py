"""The DID IT FIRE record: one gated mechanism's three states, with its own arithmetic.

WHY THIS IS IN THE SPINE AND NOT IN EACH PACKAGE. Every package's contract names gates -- DATA's
three exposure gates, LM's compose gate, TOK's build_passes_advice, CAP's block-reason histogram --
and they must all print the same three states in the same shape, because the whole point of G4 is
that a reader can tell FIRED from ARMED-AND-INERT from UNREACHABLE across the entire report. Thirteen
private Gate classes would be thirteen chances for one of them to collapse the last two states, which
is the defect this record exists to prevent: 57 of the survey's 475 records are mechanisms that were
armed and inert while the report said nothing, and 60 more are guards whose condition could not be
satisfied at all. Those are two different bugs and they need two different words.

It belongs beside `units` and `wire` for the same reason those do: it is the shared vocabulary the
packages report in, not a mechanism any one of them owns. It reads no lever, holds no state, and
imports nothing from this package or any other -- so admitting it to O10's allowlist widens the
import surface by a record type with no reach, which is the only kind of thing that allowlist should
ever grow by.

WHAT IT DELIBERATELY DOES NOT DO. It does not decide whether a gate fired -- the owning package
evaluates its own predicate and hands the answer over, because the arithmetic is the mechanism's and
moving it here would put thirteen packages' thresholds in one file. It only fixes how the three
states are SAID.
"""
import dataclasses


@dataclasses.dataclass(frozen=True)
class Gate:
    """One declared gate: whether it fired, against what, and whether it could have.

    THE THIRD STATE IS THE ONE THAT COSTS. `fired=False, reachable=True` means the mechanism ran and
    its condition was not met -- a measurement. `reachable=False` means the condition CANNOT be met
    on this configuration, which is not a measurement at all, and a report that prints them the same
    way says "0" for both. `reason` is required on that arm and says why, not merely that: the
    capacity valve reported "reached the cap but never held it long enough" for a whole round, a true
    sentence about a clock that could not advance.

    `value` and `threshold` are printed so the reader can do the arithmetic themselves. A gate that
    reports a verdict without the numbers behind it is a claim, and this project has paid for those.
    """
    name: str
    fired: bool
    value: object = None
    threshold: object = None
    reachable: bool = True
    reason: str = ""

    def __post_init__(self):
        if not self.reachable and not self.reason:
            raise ValueError(
                f"Gate {self.name!r} is declared unreachable with no reason. UNREACHABLE without a "
                f"reason is indistinguishable from armed-and-inert to every reader of the report, "
                f"which is the exact collapse this record exists to refuse.")
        if not self.reachable and self.fired:
            raise ValueError(
                f"Gate {self.name!r} is declared unreachable AND fired. One of the two is wrong, and "
                f"a report carrying both says nothing.")

    def line(self):
        """The one printed form. Every package uses it, so the report has one shape.

        THE ARITHMETIC SURVIVES THE UNREACHABLE ARM, and the first version dropped it: a gate that
        says only "UNREACHABLE" throws away the two numbers a reader needs to check the claim, which
        is the same "verdict without the arithmetic" this record exists to refuse on the other arms.

        A `reason` IS PRINTED WHENEVER IT IS SET, not only when unreachable. A gate can be reachable,
        computed, and still carry a caveat about what it measured -- DATA's exposure gates under
        DATA_DRAW=uniform are exactly that: they fire correctly against a PREDICTED split while the
        run trains on a draw from it. Rendering the caveat only on the unreachable arm would put that
        sentence nowhere.
        """
        nums = "" if (self.value is None and self.threshold is None) \
            else f" ({self.value} vs {self.threshold})"
        if not self.reachable:
            return f"Gate {self.name}: UNREACHABLE{nums} -- {self.reason}"
        verdict = "FIRED" if self.fired else "armed, did not fire"
        note = f" -- {self.reason}" if self.reason else ""
        return f"Gate {self.name}: {verdict}{nums}{note}"


class NotBuilt(Exception):
    """A mechanism that is DECLARED and deliberately NOT BUILT, refused at the point of use.

    IT IS NOT A NotImplementedError, AND THAT IS THE WHOLE REASON IT EXISTS. In this tree
    `raise NotImplementedError(...)` is not merely an exception, it is a MARKER: it is how P4 leaves
    an entry point unwritten, how tests/test_contract.py::k13_live_counts decides an entry point is a
    stub (a textual test for that name anywhere in the function), how tools/sync_counts.py reports
    progress, and what K2 means by "the composition root raises NOTHING BUT NotImplementedError, and
    it comes FROM A STUB". Two P4 bodies overloaded it for a different statement -- FAB.build
    refusing hop_mode="transition" and LM's composer table -- and the effect was immediate and
    silent: FAB.build has a full body and was counted as a stub, so the documented progress numbers
    said one more entry point was unwritten than actually was, and a reader following the count to
    find work would have opened a finished function.

    THE TWO STATEMENTS ARE GENUINELY DIFFERENT and the project already treats them differently. "P4
    has not written this yet" is a schedule fact that goes away on its own. "This arm is declared,
    the lever stays, and no body for it exists in this tree" is a DESIGN decision the owner ruled on
    -- Q-FAB-1 kept FAB_HOP_MODE with both spellings on the standing rule that a mechanism kept for
    future use is kept with a switch -- and it does not go away when P4 finishes. Collapsing them
    into one exception type is the same shape as collapsing armed-but-inert into unreachable, which
    is what the rest of this module exists to refuse.

    It does NOT subclass NotImplementedError. A subclass would be caught by `except
    NotImplementedError`, and K2 catches exactly that to report "first unimplemented stub: X" -- so a
    run on a declared-but-unbuilt arm would be reported as a missing body, which is the confusion
    this type removes.
    """
