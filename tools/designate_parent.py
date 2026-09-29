"""Designate a checkpoint B's long-lived parent -- or refuse, by name, and write nothing.

    python3 tools/designate_parent.py <checkpoint>            # a run directory or a .pt file
    python3 tools/designate_parent.py <checkpoint> --out PATH # where the record goes on admission

WHY THIS EXISTS (2026-09-28, register §8 3.6 and O17; C43, NEW-13; docs/04_CONTRACT.md Q-LM-15).
O17 rules that no checkpoint on either LM arm is designated B's long-lived parent until its position
scheme has a context-widening route that PASSes on GPU, and that "the preset builder refuses the
designation by name (switchable)". The continue preset's builder is not built. This is the one
designation step it will take, standing in for it until it exists, so the refusal O17 rules is a
thing an operator can meet rather than a sentence in a register. The DECISION is not made here: it
is lm/api.py::parent_designation's, the entry point the builder will call, and this file only reads
the checkpoint, asks, and records the answer.

WHAT IT DOES. It reads the checkpoint through CKPT.load -- CKPT_RESUME set to the path through the
lever system, so every spelling CKPT_RESUME accepts works here, and nothing reads the environment --
takes the LM geometry that checkpoint recorded (payload['LM']['geometry'], which LM.state_dict
writes), and asks LM.parent_designation.
  * ADMITTED: it writes ONE JSON record, `<checkpoint file>.designation.json` or --out, holding the
    Designation, the checkpoint's path, step and epoch, and the two switches as they stood -- so a
    designation made with REFUSE_CONTEXT_LOCKED_PARENT off says so wherever the record goes -- and
    exits 0. Written to a temporary name and moved into place, so a record is whole or absent.
  * REFUSED: it prints the refusal, which names the arm, the scheme and O17, WRITES NOTHING, and
    exits 2 -- the code run.py exits with on a startup refusal, for the same reason: a refusal is not
    a crash.
  * UNREADABLE (no checkpoint at the path, or no LM geometry in it): it says so and exits 1.

WHAT IT DOES NOT DO: build a preset, copy a checkpoint, widen a context, or read any lever but
CKPT_RESUME. The switches are lm/api.py's module constants, in D17's shape: turning the refusal off is
a code edit, not a flag here, because a flag on this tool would be a second switch for one ruling.
"""
import argparse
import dataclasses
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from spine import assemble                                            # noqa: E402
from ckpt import api as ckpt_api                                      # noqa: E402
from lm import api as lm_api                                          # noqa: E402

REFUSED, UNREADABLE = 2, 1


def designate(path, out=None):
    """(exit code, the line to print, the record path written or None) for one checkpoint.

    A FUNCTION AS WELL AS A SCRIPT so tests/test_position.py can drive the admission path with a
    switch changed in-process; the script is `main` below and adds nothing but printing."""
    cfgs, _, _ = assemble.build(environ={"CKPT_RESUME": str(path)})
    src = ckpt_api.resume_source(cfgs["CKPT"])
    if src is None or not os.path.isfile(src):
        return UNREADABLE, f"UNREADABLE: no checkpoint at {str(path)!r} (resolved to {src!r}).", None
    snap = ckpt_api.load(cfgs["CKPT"])
    geometry = ((snap.payload or {}).get("LM") or {}).get("geometry") if snap is not None else None
    try:
        d = lm_api.parent_designation(cfgs["LM"], saved_geometry=geometry)
    except lm_api.ContextLockedParent as e:
        # NOTHING IS WRITTEN ON THIS PATH -- not a record, not a marker, not a temporary file.
        return REFUSED, f"REFUSED: {src}: {e}", None
    except lm_api.GeometryError as e:
        return UNREADABLE, f"UNREADABLE: {src}: {e}", None
    target = out or (src + ".designation.json")
    record = {"checkpoint": os.path.abspath(src), "step": int(snap.step), "epoch": int(snap.epoch),
              "designation": dataclasses.asdict(d),
              "refuse_context_locked_parent": bool(lm_api.REFUSE_CONTEXT_LOCKED_PARENT),
              "passed_widening_routes": sorted(list(r) for r in lm_api.PASSED_WIDENING_ROUTES),
              "ruling": "register O17; docs/04_CONTRACT.md Q-LM-15"}
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, target)
    return 0, f"DESIGNATED: {src}: {d.reason} Recorded at {target}.", target


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("checkpoint", help="a run directory or a .pt file, as CKPT_RESUME takes it")
    ap.add_argument("--out", default=None, metavar="PATH",
                    help="where the designation record goes on an admission (default: beside the "
                         "checkpoint, <checkpoint file>.designation.json)")
    args = ap.parse_args(argv)
    code, line, _written = designate(args.checkpoint, args.out)
    print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
