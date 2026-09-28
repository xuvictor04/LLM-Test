# Questions for the owner

Only decisions you can make. Each states what changes depending on the answer. Engineering questions —
the survey has 174 of them — are not here; they get resolved against the source during implementation.

Ordered by how much work hangs on the answer.

---

## Q1. Does the Fabric stay? **[blocks P3 — the largest single decision]**

The expert population is the architecture, and the evidence for it is weaker than the project has been
treating it:

- On pure language quality (goal A), the `nofabric` arm ties `pop1024` within noise.
- SUFFICIENCY reports 479 experts buying −0.002 b/B over the best single rank-slot.
- The fabric makes the base model **0.285 b/B worse** as a standalone ablation.
- It earns its keep only on goal B — and goal B has been measured **once**, at n=1.

Against that: **every routing and specialization number that would settle this is confirmed void** — the
one-byte eval signature and `compose_test`'s missing fabric mean we have never actually measured whether
the fabric specializes. So "the fabric does nothing" and "we have never been able to see it" are currently
indistinguishable.

- **A. Keep it, and measure it properly first.** P5–P6 give trustworthy routing instruments; decide after.
  *Recommended* — the cost of keeping it one more cycle is bounded; the cost of deleting a working
  mechanism on broken evidence is not.
- **B. Cut it now.** Bedrock's path. Much smaller system, faster to build, and goal B loses its
  modularity story.
- **C. Keep it, deprioritised.** Build it but do not spend GPU time on it until goal A is stronger.

## Q2. Is `PURE_ADD=1` the default continual-learning protocol?

The default `PHASE_SCHED` for two corpora is `[[0],[0],[1],[1]]` — it **rehearses** the old corpus every
epoch, eight times over a run. `PURE_ADD=1` streams the new area only. On a CPU toy the two arms disagreed
**10×** (`+0.046 HELD` rehearsed vs `+0.444 WORSE` pure).

Rehearsal is a legitimate CL technique, but with it on, "English held" partly means "English was retrained."
Only the pure arm asks the question goal B is about.

- **A. `PURE_ADD` is the default; rehearsed is the comparison arm.** *Recommended.*
- **B. Keep rehearsed as default; report both every time.**
- **C. Both are first-class; no default.**

## Q3. The per-source memory quota — a live collision between your instruction and the literature

On 2026-07-21 you rejected a strict per-domain memory quota, on the grounds that a wall fights growability
and pressure should be a *signal* (grow/retrain/split the domain) rather than a limit. That reasoning is
recorded and the code implements it.

The literature review this project later commissioned returned **class-balanced reservoir sampling** and
**iCaRL per-class exemplars** as the standard fix for exactly the dilution failure this system exhibits —
one source ending up owning 88% of a 200k store.

I am not resolving this either way. It is your call, and it is the one place where the record's own
instruction and the external evidence point in opposite directions.

- **A. Your rule stands** — pressure is a signal, not a wall. The floor guards eviction only.
- **B. Adopt a reservoir quota** and treat the 2026-07-21 decision as superseded.
- **C. Both, selectable, measured against each other** on the add-area benchmark. *Recommended* — it is
  cheap under the new harness and it is the kind of question two arms answer definitively.

## Q4. Does the world model stay?

413 recorded measurements, **zero readings above baseline**, latent std never above 0.15, and a resume
replay that is an unbounded `while` loop. Separately: reconstruction-based Verification is dead at the
base-rate wall and its report line appears in **zero** logs.

Both are candidates for the "unnecessary material" you want filtered. Both are also gestures at goal A's
*"room for additional inclusions"*.

- **A. Cut both; keep ByteComposer as the modality story.** *Recommended* — the composer is byte-grounded
  and is the actual mechanism for attaching a new symbol space.
- **B. Keep the world model, cut Verification.**
- **C. Keep both.**

## Q5. Branch policy

Your standing constraint has been *"commit and push to `rm-predict` only."* `rm-predict-DC` now supersedes
it, and I have been pushing there. Confirm — and say what happens to `rm-predict`:

- **A. `rm-predict` is frozen** as the historical baseline; all work continues on `-DC`. *Recommended.*
- **B. `rm-predict` stays live** for fixes to the old tree while `-DC` is built.
- **C. `-DC` merges back into `rm-predict` when it is ready.**

## Q6. The two-day hole in the record

You said everything from all our messages must be documented. There is a gap I cannot close: the session
of **2026-08-15 → 2026-08-17** survives only as a compaction summary at line 2 of the current transcript.
That is the session that produced the entire `notes/` corpus. The raw exchange is gone.

- **A. Mark it unrecoverable in the timeline and reconstruct what it produced from its artifacts.**
  *Recommended* — honest, and the artifacts are substantial.
- **B. Treat the compaction summary as the record for that window.**
- **C. You have the exchange saved elsewhere and can supply it.**

Related and mechanical: the transcript **grows every turn** (8,072 entries when surveyed, 8,224 an hour
later). I propose a documented cutoff entry number plus an append protocol, so "fully documented" has a
checkable meaning rather than a moving one. Say if you would rather it be re-swept at the end instead.

## Q7. The direction call you were asked for and never gave

At the end of the last cycle I asked which way to take the domain-collapse fix and did not get an answer,
because the initiative arrived instead. It is still open, and it is now entangled with Q1:

`SPECIALIZATION` has read **INTERCHANGEABLE** in every arm ever measured, up to 4,103 experts. That is
either the finding of the project or an artifact of the one-byte signature. Under Q1-A it resolves itself
at P6. Under Q1-B it never gets asked. Flagging it so the choice is deliberate.

---

## Environment — still outstanding

These go verbatim into `docs/02_OPERATIONS.md`. I have been calling your box a GH200 for weeks on no
evidence; `preflight.sh`'s entire advice section is written for aarch64 and is wrong if it isn't one.

```
uname -a && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
free -g | head -2 && df -h ~ | tail -1
python3 -c "import sys,torch;print(sys.executable, torch.__version__, torch.version.cuda)"
```

- Which python environment do you run in — system, venv, conda?
- Can a run be left going unattended for hours or days, or does the box get reclaimed?
- Confirm the working arrangement: I hand you commands, you run them and paste results back. Say if you
  want me to take more or less of that.
