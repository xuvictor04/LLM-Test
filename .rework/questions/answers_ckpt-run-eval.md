## Q-CKPT-1 — the geometry manifest has one producer and eleven packages

**What I read**
- `docs/04_CONTRACT.md:1122-1140` (the question), `:820-855` (§3.9)
- `src/ckpt/api.py:1-24` (module head, RECORD TYPES), `:158-186` (`check_geometry`)
- `src/spine/compose.py:1875-1943` (`_geometry_manifest`), `:1946-1976` (`_sidecar`), `:1296-1310` and `:1346-1350` (`ROW_ARGUMENTS_ELSEWHERE`), `:331-364` (the gate row), `:964-1044` (the C block), `:2132-2157` (`_periods`), `:1760-1783` (`_signature_width`, `_alphabet_size`)
- `src/world/api.py:160-179` (`geometry`), `src/lm/api.py:20-66` (`LMGeometry`, `resolve`), `src/sig/api.py:211-248`, `src/fabric/api.py:363-400`, `src/memory/api.py:25-50`, `src/memory/levers.py:110-131`, `src/fabric/levers.py:258-280`
- Ran all six test files: `test_ownership` 11 checks + 18 self-test cases 0 failing; `test_contract` 12 + 34, 0 failing; `test_census` 5, 0 failing; `test_assemble` 7, 0 failing; `test_couplings` 4, 0 failing; `test_derive` "575 oracle cases, 0 mismatches". (No `pytest` in the container; each file runs as a script.)

**What is true today**
`grep -n "^def geometry" src/*/api.py` returns exactly one hit, `src/world/api.py:160`. The question's factual claim is verified and still live.

I also **ran** `_geometry_manifest` against real frozen Configs (`spine.assemble.build(environ={})`, a stub `sysm` with `geometry=None`). It returns **15 fields with no live object of any kind**:

```
lm.width=128 EXACT   lm.layers=0 EXACT   lm.heads=8 EXACT   lm.ctx=128 EXACT
lm.vocab_slots=4096 MAY_WIDEN   sig.d=64 EXACT   sig.space=bytes EXACT
fab.slots=4096 MAY_WIDEN   fab.rank=8 EXACT   fab.dk=32 EXACT
world.lat=32   world.hid=128   world.route_d=24   world.nmax=6 MAY_WIDEN   world.feedback=True
N FIELDS: 15
```

That result settles the question's premise in a way the question does not state: **the manifest is not a fan-in of package calls and never can be.** Its defining property is that it exists *before the first allocation* (`compose.py:1882-1884`), and a `geometry()` on a package can only be called after that package has built something. WORLD's own `geometry(world, w)` takes a built `w` — which is why it sits on the *save* side at `compose.py:1009-1018`, not beside the gate. Any `geometry()` added to the other eight packages would have to take a Config and no object, at which point it is a lever read the root can already do — with the added cost that the EXACT/MAY_WIDEN **rule** would move into the package, contradicting `ckpt/api.py:166` ("RULES ARE THE OWNER'S").

One thing the run exposed that the question does not mention: with `geometry=None`, `lm.layers` records the **sentinel 0**, not the resolved depth. `LM.resolve` replaces the sentinel with 4/1 (`lm/api.py:33-39`). So a run with `LM_LAYERS=0` and a run with `LM_LAYERS=4` are the same model and would record `0` vs `4` — an EXACT mismatch and a spurious refusal — **unless both sides pass `sysm.geometry`**. That is a hard requirement on whichever side computes the manifest, and it is currently written nowhere.

Second half (the `GeometryField` record): verified. `_geometry_manifest` returns plain 4-tuples in the declared order (`compose.py:1894-1895`, and the run above shows tuples); `ckpt/api.py:19` declares `GeometryField value, rule, env_name, why`. P4 defines the type.

**The options**
- **(a) leave it and print the UNCHECKED set.** Costs nothing, buys nothing new; the docstring at `ckpt/api.py:165` keeps describing a producer that does not and cannot exist, which is exactly the "described owner, no declaration" family this rebuild exists to end.
- **(b) add `geometry()` to eight packages.** Costs eight new frozen signatures P4 must write against, moves the rules out of the owner's hands, and buys nothing: every field those functions could return before allocation is a lever the root already reads. For the fields that *would* need a live object, the call cannot happen at the gate at all.
- **(c) narrow the docstring to what actually produces the manifest.** Costs one docstring edit inside a frozen signature. Buys: the one sentence in `check_geometry` that is false becomes true, and the "eleven packages have no producer" framing disappears rather than being managed.
- **(d) — not in the question — extend the manifest with the remaining Config-pure shape fields** (`sig.mode`, `sig.alphabet_size`, `fab.n0`, `fab.emb_hid`, and the real fabric cap). Cheap, and it is what Q-CKPT-2 needs.

**Recommendation**
**(c), plus (d).** Not (a), and explicitly **not (b) ever** — "when the surface next opens" should be struck, because (b) is not a deferred improvement, it is the wrong shape.

**Why it fits the framework**
The root already owns three named cross-package arithmetics with exactly this justification: `_signature_width` and `_alphabet_size` (`compose.py:1760-1783`, "the assembly's own arithmetic over two packages' frozen Configs, which is exactly what the root is for", `compose.py:1308-1310`), and `_periods` (`compose.py:2132-2149`, "a mapping spanning five packages is exactly the object O10 forbids any one of them to build"). The manifest is the same object and belongs in the same place. Option (b) would put a shape *rule* about FAB's tensors into FAB, so a package would be grading the refusal that protects it — the same reason `aff_min` and `genuine_min` live in EVAL and not in the packages they grade (`eval/api.py:3-7`). Adopting (b) would also add eight entry points to a surface where **116 of 121 are already stubs**, for zero new information.

The one thing (c) must *not* do is drop `WORLD.geometry`. It is correctly placed: it is the only field set that needs a built object (the grown `n`), and it is on the save side where the object exists.

**What changes**
- `src/ckpt/api.py:165` — replace *"assembled by the composition root from each package's own `geometry()` call"* with: assembled by the composition root from the frozen Configs and `LM.resolve`'s `LMGeometry`, before any allocation; a package's own `geometry()` (WORLD's, the only one, and correctly so) records the **grown** counts on the SAVE side and is reported UNCHECKED here. **No signature moves.**
- `src/world/api.py:171-174` — `DID IT FIRE` says "the manifest `CKPT.check_geometry` consumes". It is not consumed by the gate; it is *recorded* by the save. One-line correction.
- `src/spine/compose.py:1892-1895` — the "TWO THINGS HERE ARE THE OWNER'S" paragraph resolves to one (the `GeometryField` constructor).
- `src/spine/compose.py:1900-1943` — add the four Config-pure fields Q-CKPT-2 needs, and **record the fabric's real extent**: `fabric/levers.py:269` says *"cap = max(n0, slots)"*, so `fab.slots` alone is not the tensor extent. Either add `fab.n0` (needed anyway) or record `fab.cap = max(n0, slots)`.
- Add an assertion or a comment that the manifest **must** be built with `sysm.geometry` present, because with `geometry=None` `lm.layers` is the sentinel — I hit this by running it.
- `docs/04_CONTRACT.md:1122-1140` — recommendation changes from "(a) now, (b) when the surface next opens" to (c).

**Confidence**
**High** on the facts (one `geometry()`; manifest is Config-pure; ran it). **High** on (c) over (b). Medium on the exact wording of the replacement docstring — that is P4's to phrase.

**Literature**
NOT APPLICABLE to the choice. This is a question about which object in *this* tree can exist before allocation; no paper speaks to it. One weak external datum is noted under Q-CKPT-2.

---

## Q-CKPT-2 — what does the SAVE side write for the geometry gate, and who emits FAB's sidecar?

**What I read**
- `docs/04_CONTRACT.md:1284-1298` (the question), `:820-855` (§3.9)
- `src/ckpt/api.py:158-186` (`check_geometry`, and the refusal rule at `:174-179`)
- `src/spine/compose.py:331-364` (the gate row), `:964-984` (the C-block prose), `:995-1018` (the SIG / FAB / WORLD C rows), `:1296-1305` and `:1311-1321` and **`:1346-1350`**, `:1875-1976`
- `src/sig/api.py:211-248`, `src/fabric/api.py:363-400`, `src/world/api.py:160-179`
- `src/fabric/levers.py:261-280, 447-462`; `src/sig/levers.py:183-225`; `src/world/levers.py:211-304`
- Executed `_geometry_manifest` (output quoted under Q-CKPT-1)

**What is true today — and the tree contains two answers, not one**

The question, §3.9 and the C-block prose (`compose.py:970-984`) all say the same thing: *the save side records `WORLD.geometry` alone, five fields, so ten of fifteen are in the manifest and absent from the recording, and `ckpt/api.py:174` makes that a REFUSAL, so every resume raises the day P4 lands.*

**That is not what `ROW_ARGUMENTS_ELSEWHERE` says, and `ROW_ARGUMENTS_ELSEWHERE` is the table K10 actually reads.** `compose.py:1346-1350`:

> `"CKPT.save":` *"geometry is `_geometry_manifest(sysm)`, the LIVE manifest — the same object `CKPT.check_geometry` compares a restored Snapshot against, written here so the two sides of that comparison are one function's output rather than two. Ten of its fields have no writer on the save side today (Q-CKPT-2), which the C-block prose states."*

Read literally, that entry **already implements the third option the task asked me to look for**: `CKPT.save`'s `geometry` argument is the 15/16-field manifest, so the recorded key set equals the live key set and **no resume raises at all**. Its own last sentence ("ten of its fields have no writer") then contradicts its own first sentence; the residue means "no *package* produces them", which is true and irrelevant to the gate.

So the state of the tree is worse than the question says in one respect and better in another: the "every resume raises" outcome is real **only under the §3.9 reading**, and P4 has two written instructions that produce different code from the same rows. That is the definition of blocking.

**Is the third option actually true for all 15 fields? Yes — verified by running it.** All 15 resolve off frozen Configs with `sysm` carrying no built object. The 16th, `pos_max`, comes from `LMGeometry`, itself resolved once per process from the frozen LM Config (`lm/api.py:56-63`: levers plus `d_pos_max`/`d_max_token_bytes`, both wires, both frozen). Configs freeze when `build()` returns and the assembly latches, so **`_geometry_manifest(sysm)` at save time and at the child's gate are the same function over the same class of input.** The save side does not need to collect anything from packages.

**Which fields genuinely need a live object** — I worked this through field by field:

| field | live-object dependency | who can produce it |
|---|---|---|
| all 15 manifest fields + `pos_max` | none | `_geometry_manifest(sysm)` |
| `world.n` (grown population) | yes — grows in-run | `WORLD.geometry(world, w)`, save side, already rowed |
| `fab` n_live | none that matters — slots are **preallocated**, growth only advances `n_live` (`fabric/levers.py:278-280`), so tensor extents never move | n/a |
| SIG `width_units` | **yes** — `derive.signature_width_bytes(LM.ctx, Vocabulary.bytes_per_token)` and `bytes_per_token` is MEASURED over the build sample (`tok/api.py:61`); `compose.py:1763-1766` says outright it cannot be a Coupling for that reason | `SIG.state_dict`, which `sig/api.py:211-214` **already says it emits** |
| SIG `alphabet_size`, `space`, `d`, `mode` | none — `_alphabet_size` is `256` or `LM.vocab_slots` (`compose.py:1776-1783`); the rest are levers | `_geometry_manifest` |
| FAB `slots`, `n0`, `rank`, `dk`, `emb_hid` — the five `FAB.load_state_dict` compares (`fabric/api.py:393`) | **none. All five are levers.** | `_geometry_manifest` |

**That answers the second half of the question outright: nobody needs to emit FAB's sidecar.** Every field FAB's refusal reads is Config-pure, so the `fab.*` slice of a manifest the root already computes *is* the sidecar. FAB.state_dict does not have to claim anything it does not do.

**The options**
- **(a) the C block records the manifest keyed by prefix, plus `'SIG'`/`'FAB'` sidecars.** Buys an armed gate. Costs: FAB must declare a sidecar it does not emit (a docstring change inside a frozen signature, and a claim about behaviour nobody can check), and `Snapshot.geometry` becomes two-level — flat fields plus reserved prefix keys — which `check_geometry`'s key-set rule would then report as two junk UNCHECKED "fields" unless a reserved-key exemption is written into `ckpt/api.py`. Two new rules to buy one.
- **(b) `geometry()` on eleven packages.** See Q-CKPT-1: eleven entry points that can only be called after the thing the gate precedes. Not available.
- **(c) narrow the gate's key set to what is recorded.** The smallest edit and the one that checks nothing: it makes `check_geometry` an untrippable guard over five fields while its docstring names fifteen, and it *inverts the rule at `ckpt/api.py:174-179`* — the paragraph exists specifically because the fabric's three branches were each guarded on `_ck_cap and ...` so a checkpoint with no `cap` slid through all three (`self_organize.py:4432-4441`). Narrowing the key set to the recording is that bug, promoted to policy. **It should not be adopted, and it is the option to argue against, not for.**
- **(d) — the third option, and the one to take. The save side computes the same manifest.** `CKPT.save(geometry=_geometry_manifest(sysm))` — which `compose.py:1346-1350` already says — overlaid with `WORLD.geometry`'s live values under the same `world.*` keys, contributing `world.n` as a recorded-only field. `_sidecar` then **slices the recorded flat manifest by prefix** instead of looking for a key nobody writes. `SIG`'s one measured field, `width_units`, stays where `sig/api.py:213` already puts it: inside SIG's own blob, which SIG reads back from `sd` in `load_state_dict`.

**Recommendation**
**(d).** Concretely:

1. `CKPT.save`'s `geometry` = `dict(_geometry_manifest(sysm))`, then overlay `WORLD.geometry(world, w)`'s fields under `world.*` (the live values win — they describe the actual tensors) and add `world.n`, which the live manifest deliberately lacks and the gate therefore reports **UNCHECKED**, re-refused by `WORLD.load_into` (M43).
2. Add to `_geometry_manifest`: `sig.mode`, `sig.alphabet_size`, `fab.n0`, `fab.emb_hid`, and the fabric's real extent (`max(n0, slots)`). All Config-pure. `sig.alphabet_size` is not a tidy-up: under `space="tokens"` it is `LM.vocab_slots`, so it sizes the encoder embedding, and today **nothing refuses a resume that changes it** before allocation.
3. `_sidecar(sysm, restored, PFX)` returns `{name: value for "pfx.name" in the RECORDED flat manifest}` — no new key, no reserved namespace, no `'SIG'`/`'FAB'` entries in `Snapshot.geometry`, and therefore nothing spurious in the UNCHECKED list.
4. `SIG.load_state_dict` compares `width_units` against the copy in its own `sd`; the `sidecar` argument carries the four Config-pure fields. `FAB.load_state_dict` gets all five of its fields from the slice.

**Argument against (c), since the task asked for it properly:** (c) is smaller by line count and larger by consequence. `ckpt/api.py:174-179` does not merely *permit* the key-set rule, it explains that truthiness-driven comparison is precisely what let a `cap`-less checkpoint reach `load_state_dict` as a five-shape torch dump. Narrowing the key set to the recording makes the gate's coverage a function of what the save side happened to write — so the day someone drops a field from the recording, the gate silently stops checking it and every check stays green. Under (d), dropping a recorded field makes a resume **refuse and name the field**. That asymmetry is the whole reason the rule is written the way it is.

**Why it fits the framework**
- **The wire rule is what makes (d) correct rather than merely convenient.** "A coupling's compute sees ONLY frozen Configs — so anything MEASURED at runtime can never be a wire." The manifest obeys exactly that predicate. It is the same class of object as `_signature_width` and `_alphabet_size`, and it is the reason `width_units` — measured — is the single field that must travel in a package's blob. The framework's own line between "computable from Configs" and "measured" cuts this problem cleanly, and (d) is what falls out of it.
- **The ownership spine permits it and (a) strains it.** (d) needs no package to claim anything it does not do; (a) needs FAB to declare an emission, in a docstring, that no check can verify — a written claim about behaviour is exactly the evidence class this project treats as unreliable.
- **DID IT FIRE.** Under (d) both sidecar refusals are armed on every resume from a checkpoint written by this code, and `_sidecar`'s `System.warnings` line (`compose.py:1970-1975`) becomes what it should be: a report about **old** checkpoints, not a permanent statement about the current one.
- **Frozen signatures: nothing moves.** `save(ckpt, *, payload, geometry, step, epoch, reason, suffix="")` unchanged; `check_geometry(ckpt, snapshot, geometry)` unchanged; both `load_state_dict(..., *, sidecar)` unchanged. Every edit is inside `compose.py` plus three docstrings. If the tree instead adopts (a), FAB's signature is unchanged but its *contract* gains an unverifiable clause, and `ckpt/api.py` gains a reserved-key exemption to the one rule it states most emphatically.
- **What breaks if the other way is adopted:** under (c), `check_geometry` becomes the untrippable guard it was written to replace — a 60-record family in the survey — and `GeometryReport` prints "PASS" over five fields while `LM_WIDTH`, `SIG_D`, `FAB_RANK` and `FAB_DK` go unexamined until torch raises. Under the §3.9 reading left as-is, every resume raises `GeometryRefusal`, and a resume is what `ckpt/api.py:3-6` calls **the experiment** for goal B.

**One residual I want on the record.** A recorded manifest computed from the parent's Configs describes the parent's *intent*, not its tensors. It is faithful because every tensor in `payload` was allocated from those same frozen Configs and nothing reallocates (FAB preallocates; LM's vocab rows sit at the slot ceiling; WORLD grows only within `nmax`). The two places that could drift are exactly the two (d) covers with live producers: `world.n`, and SIG's measured `width_units`. I checked MEM as well — its extents are `quota`/`owners` (Config-pure, via `d_capacity`), and `MEM.open_store` already carries its own named refusal for a lowered `owners` (`memory/api.py:42-45`, M50), so MEM does not need to join the manifest for a resume to fail by name.

**What changes**
- `src/spine/compose.py:1900-1943` — four new Config-pure fields plus the fabric cap; a note that `sysm.geometry` must be present (with `geometry=None` `lm.layers` records the sentinel `0`, which I hit by running it, and which would make an `LM_LAYERS=0` parent and an `LM_LAYERS=4` child refuse each other spuriously).
- `src/spine/compose.py:1946-1976` — `_sidecar` slices the recorded flat manifest by prefix; the `System.warnings` line narrows to "this snapshot predates the prefix-sliceable manifest".
- `src/spine/compose.py:1346-1350` — delete the contradicting last sentence; state the WORLD overlay.
- `src/spine/compose.py:970-984` and `:341-364` — the C-block prose and the gate row are rewritten to the (d) answer. **They currently instruct P4 to write code that raises on every resume.**
- `src/spine/compose.py:1009-1018` — the `WORLD.geometry` C row becomes "the live overlay plus `world.n`", not "the recorded side of the comparison".
- `src/ckpt/api.py:180-186` — the `DID IT FIRE` block gains: recorded-and-absent-from-the-manifest is UNCHECKED and `world.n` is the expected member of that set.
- `src/sig/api.py:232-243` — say that `width_units` is compared against the copy in `sd` (the only measured field), the other four against the sidecar.
- `src/fabric/api.py:385-395` — say the sidecar's five fields are the `fab.*` slice of the recorded manifest, **and that FAB emits no sidecar of its own and does not need to.** This is the sentence that closes the second half of the question.
- `docs/04_CONTRACT.md:820-855, 1284-1298`.
- **No frozen signature moves.** If the owner prefers (a) instead, that is still true, but `ckpt/api.py`'s key-set rule needs a written reserved-key exemption and FAB's docstring gains an unverifiable claim — say so out loud now rather than discovering it in P4.

**Confidence**
**High** that all 15 fields are Config-pure and the save side can compute them — I ran the function with no live object and it returned all 15. **High** that FAB needs no sidecar producer — all five fields it compares are declared levers (`fabric/levers.py:261, 269, 447, 455, 462`). **High** that `width_units` is the one genuinely-live field (`compose.py:1763-1766` says so itself). **High** that the tree currently contains two contradicting instructions. **Medium** on the exact placement of `width_units` — I am confident SIG can read it from `sd`, but `SIG.state_dict`'s blob keys are undeclared prose (`sig/api.py:212-214`), so a P4 author could put it elsewhere; declaring those keys would raise this to high. What else would raise confidence: a P4 draft of `check_geometry` run against a synthetic parent/child pair with one lever changed, asserting the refusal names the knob.

**Literature**
**Bore, weakly, and I want to be precise about how little.** The practice of recording the model's *configuration* next to the weights and comparing configs on resume is standard (HF-style `config.json` beside the state dict), which is the shape of option (d). NVIDIA's NeMo distributed-checkpoint guide is the closest published analogue to the field-level rule set here: it has an explicit `allow_shape_mismatch` for tensors where padding is legitimate (this tree's `MAY_WIDEN`) and a mismatch policy that is deliberately `raise_all` first and only then `log_all` (this tree's REFUSAL vs UNCHECKED). It supports the direction of (d) and the argument against (c) — refuse by default, downgrade to a logged skip only where the widening is understood. It does **not** and cannot answer who in *this* tree emits FAB's sidecar, which is where the actual decision was. Sources: [NeMo Distributed Checkpoint User Guide](https://docs.nvidia.com/nemo-framework/user-guide/25.07/nemotoolkit/checkpoints/dist_ckpt.html), [nemo_automodel.checkpoint.checkpointing](https://docs.nvidia.com/nemo/automodel/latest/apidocs/nemo_automodel/nemo_automodel.checkpoint.checkpointing.html).

---

## Q-RUN-1 — the progress/ETA log cadence has a described owner and no declaration

**What I read**
- `docs/04_CONTRACT.md:1071-1079`
- `src/eval/levers.py:319-340` (the `curve_every` declaration and its comment), `src/eval/api.py:40-58` (`curve_period`)
- `src/train/levers.py:1-12, 88-100, 238-500` (every `Lever(` in the file), `src/train/api.py:69-90, 254-272`
- `src/spine/compose.py:2132-2157` (`_periods`), `:617-621`, `:1363-1370`
- `src/capacity/levers.py:341` (the `PLATEAU_WARM` precedent), `src/spine/units.py:100-152`
- `.rework/CENSUS.md:365`

**What is true today**
Verified and still live, with the contradiction now **three-to-one inside the tree**:
- `src/eval/levers.py:329-331` — *"the progress/ETA line and profiler dump take a separate **RUN-owned log cadence**"*
- `.rework/CENSUS.md:365` — the same sentence, verbatim
- `src/eval/api.py:53-54` — *"the progress line takes **RUN's own fixed constant**"*

A cadence and a constant are different objects with different obligations (census row, environment name, `Cadences.ledger` key, `cadence_audit` coverage), so this is a live fork. `grep "= Lever("` over `src/train/levers.py` returns seven levers — `epochs, seed, device, tf32, amp, bench, profile` — and no cadence, confirming `train/levers.py:5` ("nothing here is a cadence, a threshold or a weight"). `grep -i progress` over `src/` returns **nothing**: neither a lever nor a constant exists. `_periods` (`compose.py:2151-2157`) has exactly five keys and no `progress`. There is no `PROGRESS_WINDOWS` and no module-level constant of any kind in `src/*/api.py`.

Two things the question does not say. First, the same sentence covers the **profiler dump** as well as the progress line, so whatever is decided serves two consumers. Second, `spine/units.py:136-150` has `U.SECONDS` as a unit string but **not** as a `Clock` kind (`CLOCK_KINDS = (Steps, Flushes, Windows, Backwards, Epochs, Selections)`), so a wall-clock log cadence could never pass through `Cadences.due`, which requires `units.Windows`.

**The options**
- **(a) a RUN lever `progress_every`.** Buys tunability and automatic `cadence_audit` coverage. Costs the invariant: `compose.py:2138-2139` and `train/api.py`'s `new_cadences` both state *"RUN evaluates gates; RUN owns no threshold"*, and `train/levers.py:5-12` makes "nothing here is a cadence" the module's stated identity. It also costs a census row for a knob whose only effect is how often a human sees a line — and `curve_every`'s own history is the argument against: a log knob that can be turned up is a log knob that silently disables things.
- **(b) a fixed module constant `PROGRESS_WINDOWS` in `src/train/`, documented as a property.** Costs nothing declarative. Buys the split the census promised. **Its one real cost is DID IT FIRE**: a constant outside `_periods` is invisible to `RUN.cadence_audit`, the single statement that makes ISSUES P1-C11 visible (ten cadence defaults longer than a 937-window run), so a progress line that never prints in a short run would say nothing about why.
- **(c) wall-clock (every N seconds).** Genuinely the most honest denomination for an ETA meter and immune to C11. But `U.SECONDS` is not a `Clock`, so it cannot go through `Cadences.due`, and RUN would evaluate a sixth gate by a mechanism nothing else in the tree uses. It fights the unit types rather than fitting them.

**Recommendation**
**(b), with one amendment the framework forces: route the constant through `_periods` as a sixth key.**

```
"progress": U.Windows(train_api.PROGRESS_WINDOWS)
```

so the gate goes through `Cadences.due` like the other five, appears in `Cadences.ledger()["progress"]`, and is covered by `RUN.cadence_audit`. `PROGRESS_WINDOWS` stays a module constant in `src/train/api.py` — no lever, no census row, no environment name.

**Why it fits the framework**
- **The unit types force the `U.Windows` wrap.** `Cadences.due` refuses a bare int (`compose.py:2141-2145`, ISSUES P1-H51 — three of five gates were handed bare ints until 2026-08-30), and `step` counts Windows. A raw `int` constant compared against `clock.step` at a call site is precisely the `pin_tick` defect the unit system exists to prevent.
- **The ownership spine permits (b) and refuses (a).** The rule is *"a cadence belongs to the thing it fires"* (`train/levers.py:9`). The progress line is fired by RUN's loop, so RUN is the right home — but *"RUN owns no threshold"* is about the **lever registry**, and a module constant is not a lever. (b) satisfies both sentences at once; (a) satisfies the first by breaking the second.
- **DID IT FIRE is what makes the amendment non-optional.** A guard whose condition cannot be satisfied is a defect even where the code is correct. A `PROGRESS_WINDOWS` larger than a smoke run is exactly ISSUES P1-C11, and putting it in `_periods` is the only thing in the tree that would say so. `_periods`' docstring says each period arrives "through that package's typed accessor"; if the owner wants that literal, `RUN.progress_period()` is a new entry point and therefore a signature addition — **cheap today, expensive after P4**. My reading is that the constant does not need an accessor: the accessors exist because `Config` hands back bare ints for Clock-unit *levers*, and a module constant can be written `U.Windows(...)` at its definition.
- **What breaks the other way:** under (a) the census gains a row for a log knob, and the next person quietening a smoke run sets it high — the exact `RATE_EVERY=100000` failure (`eval/levers.py:325-329`) that suppressed the curve table for a round, reintroduced under a new name.

**What changes**
- `src/train/api.py` — module-level `PROGRESS_WINDOWS = U.Windows(<n>)` with a comment justifying it as a property (the `PLATEAU_WARM = 1000` form at `capacity/levers.py:341`), and stating that it also drives the profiler dump.
- `src/spine/compose.py:2151-2157` — a sixth key; `:2133` "the five periods" becomes six.
- `src/eval/levers.py:329-331` and `.rework/CENSUS.md:365` — "a separate RUN-owned log cadence" becomes "RUN's own fixed constant", matching `eval/api.py:53-54`. **Three statements now disagree; this is the edit that makes them one.**
- No frozen signature moves — unless the owner insists on the typed-accessor form, in which case `RUN.progress_period(run)` is one addition and must land now.

**Confidence**
**High** that the question is live and that no declaration exists (grepped). **High** on (b) over (a). **Medium** on the `_periods` amendment — it is my inference from the DID IT FIRE discipline rather than something the tree states; someone may prefer the constant to stay out of the cadence ledger on the grounds that a log line is not a gate.

**Literature**
NOT APPLICABLE. Nothing in the two goals turns on how often a terminal line prints, and no paper bears on which of this tree's declaration mechanisms owns it.

---

## Q-RUN-7 — `RUN.bench`'s second job

**What I read**
- `docs/04_CONTRACT.md:1080-1088`
- `src/train/levers.py:418-448` (`bench`), `:449-462` (`profile`)
- `src/train/api.py:69-90` (`mode`), `:254-272` (`bench_summary`)
- `src/spine/compose.py:1495-1520` (`compose()`), `:1092-1105` (the R row), `:1351-1355`
- `src/eval/levers.py:290-315`, `src/eval/api.py:147-160`
- `.rework/CENSUS.md:352`
- `ls bin src/bin` — **neither exists**

**What is true today**
The question is **substantially already answered inside the tree**, and the remaining live part is smaller than the question implies.

`src/train/api.py:77-81` already states the recommendation as the tree's position: *"prompt.py's `os.environ["BENCH"]="1"` import trick (prompt.py:41) does not port — from_env is called once, in build()… 'Do not run the report' is the ENTRY POINT choosing which half to run, not a lever; see FOR THE OWNER Q-RUN-7."* `train/levers.py:434-440` says the same. `RunMode(bench, profile, timing)` carries only the throughput meaning; the R row (`compose.py:1092-1105`) branches on `RunMode.bench` to print `bench_summary` **instead of** the battery. `eval/api.py:152-155` and `eval/levers.py:300` already say `prompt.py` will receive the frozen EVAL Config rather than re-reading `GEN_LEN`/`GEN_TEMP`. So the whole recommendation is written down; nothing in `src/` conflates the two jobs.

What is **not** true is the mechanism the recommendation names. `bin/sample` does not exist, and `compose(environ=None, *, restored=None)` (`compose.py:1495`) has **no** parameter for disabling the battery. So "calls the composition root with the battery disabled" is not a thing that can be done today.

The good news is that it does not need to be. `compose()` **builds**; it does not run the loop or the battery — `LOOP_ORDER` is data, and the R stage is executed by whoever drives the loop. A sampler therefore calls `compose()`, takes the `System`, and calls the generation path directly. There is nothing to disable, no flag, and no `compose()` parameter.

**The options**
- **(a) a second lever (`report`/`no_report`).** Reintroduces the shared switch by another name; a second flag can disagree with the first.
- **(b) a `compose(..., run_battery=False)` parameter.** Makes the composition root know what a battery is, which it explicitly does not (`train/api.py:74-75`: "nothing in this package knows what a battery is"), and adds a boolean to the one signature every phase writes against.
- **(c) the entry point chooses — and it already can.** The sampler calls `compose()` and never enters the R stage. `RUN_BENCH` keeps only throughput. Zero changes to `src/`.

**Recommendation**
**(c).** It is the contract's own recommendation, and the verification result is that it needs **no code change at all** — only that `bin/sample` be written that way when it is written, and that the docs stop implying a "battery disabled" flag exists.

**Why it fits the framework**
`compose()` returns a `System`; the loop and the report are stages a driver executes. That separation is what lets an entry point pick a half without a knob. A `bench`-shaped flag for "no report" would be a lever whose consumer is an `if` in a script, and `train/levers.py:8` restricts this package to "which half of the program executes" as a *run mode* — the sampler is not a run mode, it is a different program. The DID IT FIRE discipline also argues for (c): with one flag doing two jobs, `RunMode.bench` cannot distinguish "timing arm" from "sampler suppressing a report", and that ambiguity is how the throughput arm and the sampler ended up sharing a switch in the first place.

**What changes**
- `src/spine/compose.py:331` region and the R rows — **nothing.** No signature moves.
- `docs/04_CONTRACT.md:1080-1088` — replace *"`bin/sample` calls the composition root with the battery disabled"* with the accurate mechanism: `bin/sample` calls `compose()` and does not enter the R stage; there is nothing to disable. As written the sentence will send a P8 author looking for a parameter that does not exist.
- When `bin/sample` lands (P8/P9), it takes `configs["EVAL"]` from the `System` and never reads the environment — already required by `eval/api.py:152-155`.
- `prompt.py` at the repository root is the old system; it is rewritten or retired, not ported.

**Confidence**
**High.** The position is already in `src/train/api.py:77-81`; `compose()`'s signature is verified; `bin/` verified absent.

**Literature**
NOT APPLICABLE. Purely internal — which entry point runs which half of this program.

---

## Q-EVAL-10 — `EVAL.coherence` takes a `sample` and its docstring says it draws its own

**What I read**
- `docs/04_CONTRACT.md:1300-1315`, `:722`
- `src/eval/api.py:1-38` (module head, G7, ONE LOGITS PATH, RECORD TYPES), `:147-164` (`generate`), **`:167-183` (`coherence`)**
- `src/eval/levers.py:14-24, 226-249` (`coh_seeds`, `coh_len`)
- `src/spine/compose.py:1184-1192` (the `EVAL.coherence` deferral)

**What is true today**
The contradiction is live and verified verbatim. `eval/api.py:167`: `def coherence(ev: Config, *, logits_fn, sample, rng):`. `eval/api.py:168`: *"The coherence Reading over its OWN seeded sample, not over the printed generations."* `:173-174`: *"coh_seeds and coh_len size a sample this instrument draws for itself."* The levers agree with the docstring, not the signature: `eval/levers.py:227` — *"**Seed passages the coherence instrument draws** — the sample size behind its standard error."*

The contract's line references are stale by a few lines (it cites `eval/api.py:162-168` and `:142-143`; the real lines are `:167-179` and `:147-150`) — the files have moved; the facts hold. `EVAL.generate` does return a `Sample` (`:148`), confirming the correction already recorded at `compose.py:1184-1187`.

**Two things I found that the question's option set does not account for, and they change the answer.**

1. **`rng` is the tell.** A function that only *scores* a handed-in sample needs no RNG — the draws already happened. `coherence` takes one, and `eval/api.py:21-23` (G7) says *"Every probe runs under `spine.rng.frozen_rng` and draws from its own named stream."* The frozen signature already asserts that this instrument draws.

2. **Option (a) as written — "drop the parameter" — is not implementable.** With `sample` gone, `coherence(ev, *, logits_fn, rng)` has a model and a random stream and **no material**. `coh_seeds` counts *seed passages*, which come from the corpus; EVAL cannot import DATA or TOK, and no entry point in the tree produces a `coh_seeds × coh_len` sample (`EVAL.generate` is sized by `gen_samples × gen_domains × gen_len`). So the parameter is needed. What is wrong with it is its **meaning and its name**: typed as a `Sample`, it is the printed generations, which is exactly the object the docstring forbids and exactly what the old code handed it.

A related gap, stated once because signature changes are cheap now: `eval/levers.py:234-236` says *"in the self-referential case HOME is measured per seed by encoding it and taking the nearest centroid"*. Encoding is SIG's and centroids are DOM's, and `coherence` has neither and cannot import either. That is a second missing callable of the same class as `logits_fn`.

**The options**
- **(a) drop the parameter.** Matches the docstring's argument, but leaves the instrument with nothing to draw from. Not writable as stated.
- **(b) keep it, delete the sentence, caller draws.** Then `coh_seeds`/`coh_len` are read by nobody — but `coherence` is the **only** stub that names them (K4 requires a `LEVERS READ:` reader), so the declaration becomes prose that passes a parser while the sizing happens in the root. The root would be reading EVAL's levers to size a measurement: the C4 shape.
- **(c) keep both, document `sample` as an A/B override.** Leaves the default path undefined and leaves the door the old code walked through wide open.
- **(d) — the corrected form of (a). Keep a parameter, change what it *is*, and rename it.** `coherence(ev, *, logits_fn, seed_units, rng)`: `seed_units` is the raw material (the unit stream the seeds are cut from), the instrument draws `coh_seeds` seeds from it under `rng` and generates `coh_len` tokens each through `logits_fn`. The sentence at `:168` stands and becomes true; the levers become real reads; a `Sample` can no longer be passed by reflex because the parameter is not named or typed for one.

**Recommendation**
**(d)** — which is the contract's (a) with the gap filled. The instrument owns its draw; what is handed in is material, not a measurement.

**Why it fits the framework**
- **The frozen signature's own `rng` argument settles the direction**, together with G7's "every probe… draws from its own named stream". A scoring-only reading makes `rng` dead weight in a frozen signature.
- **K4 and the armed-but-inert family force it.** `coh_seeds` and `coh_len` are declared with `coherence` as their only reader. Under (b) or (c) that reader becomes nominal — the 57-record armed-but-inert family, created deliberately.
- **The callable-passing idiom already exists** for exactly this boundary: `logits_fn` is passed in and never constructed (`eval/api.py:26-29`), as `DOM.rekey` gets `encode` and `MEM.write` gets `key_fn`. Passing the seed material in is the same move; it does not need a cross-package import and it does not need a wire.
- **The measured-vs-wired rule** puts the seed material firmly on the argument side: it is drawn from the live stream at report time and could never be a `d_` field.
- **What breaks the other way:** (b) or (c) re-creates the exact defect on the record — coherence scored on the four printed generations, every number landing on 0.25/0.50/0.75/1.00, "memory HELPS (0.50 → 0.75)" being one sample flipping and reported as a finding twice in opposite directions. The parameter *as a `Sample`* is the mechanism by which that happened.

**What changes**
- `src/eval/api.py:167` — **A FROZEN SIGNATURE MOVES. SAY IT LOUDLY.** `coherence(ev, *, logits_fn, sample, rng)` → `coherence(ev, *, logits_fn, seed_units, rng)`. It is a parameter rename plus a change of meaning, it is checked by K1, and it is one token in the file plus one row in `docs/04_CONTRACT.md`. **116 of 121 entry points are stubs and P6 writes against this one; renaming it now is free and renaming it after P6 is not.**
- `src/eval/api.py:168-178` — say what `seed_units` is (the unit stream seeds are cut from), that the draw is `coh_seeds` seeds × `coh_len` tokens under the package's own frozen stream, and that a `Sample` is **not** an acceptable argument.
- `src/spine/compose.py:1184-1192` — the deferral records that the contradiction is resolved; the remaining reason stays `logits_fn`.
- `docs/04_CONTRACT.md:1300-1315` and the K1 declaration row.
- **Settle the second gap in the same edit** or record it as a new question: whether `coherence` also needs a `home_fn` (encode → nearest centroid) for the self-referential case at `eval/levers.py:234-236`. If it does, that argument must land while the surface is cheap. I have **not** verified that P6's coherence definition requires it — `eval/levers.py:234` describes it as the self-referential case, which may be one arm of two.

**Confidence**
**High** that the contradiction is live and that literal option (a) is not writable (the function would have no material). **High** that the docstring and the levers should win over the signature. **Medium** on the parameter name `seed_units` and on whether one argument suffices or a `home_fn` is also required — reading P6's intended coherence definition, or the old `self_organize.py` coherence block, would raise that to high.

**Literature**
NOT APPLICABLE to the decision. The empirical half — that a four-sample mean with SE 0.25 cannot support the difference that was reported — is already settled arithmetic inside the tree (`eval/levers.py:241-248`), and no paper is needed to confirm it. Searching for one would not tell me which of a signature and its own docstring this project intends to be authoritative.

---

## Q-MEM-8 — which management cadence does `MEM.judge` run on?

*(Flagged "if not covered" — this is most likely the MEM slice's. Answering briefly because I verified one fact that contradicts the question's own premise.)*

**What I read**
`docs/04_CONTRACT.md:1170-1180`; `src/memory/api.py:243-265`; `src/spine/compose.py:660-690` (the `dom.manage` pass), `:1223-1232` (the `MEM.judge` deferral); `grep -n '"MEM", *"judge"' src/spine/compose.py` → **no match**.

**What is true today**
The question says *"`LOOP_ORDER` places `judge` as an **event on the `dom.manage` pass**… (a) the `dom.manage` pass (**what is written**)."* **That is stale.** `MEM.judge` has **no row in `LOOP_ORDER`**. It is in `DEFERRED_ENTRY_POINTS` at `compose.py:1223-1232`, and that entry ends: *"Q-MEM-8 still owns WHICH management pass it rides when it returns."* The deferral reason is `scorer` — required by the default `verify="selfcon"` arm, must be the same forward path training used (M47), and that callable does not exist, the same gap as `EVAL.curve_probe`.

So option (a) is not "what is written"; nothing is written. `memory/api.py:254-255` still says *"the management cadence the spine already imposes; no new lever (see FOR THE OWNER Q-MEM-8)"*, and the spine imposes two: `dom.manage` (100 Windows) and `fab.manage` (500 Windows).

**The options / Recommendation**
Unchanged in substance: (a) `dom.manage`, (b) `fab.manage` — 5× cheaper, (c) a new `MEM.judge_every`, which `memory/api.py:255` forbids. **Recommendation: (a)**, for the reason the question gives — `judge` re-reads provenance the fold-and-delete pass has just rewritten, so riding that pass means it invents no key and reads no foreign period at the call site. With the cost noted: `judge` is a forward pass over checked entries at the shorter of the two cadences.

**Why it fits the framework**
The `dom.manage` gate is asked **once** and the rows inside it run on that single answer (`compose.py:660-665`) — asking `Cadences.due` a second time under the same key *consumes* the event, which is the defect that made minting never fire. So `judge` must be an event on an existing pass, never its own `due()` call. That is also why (c) is refused: a `MEM.judge_every` would add a sixth `_periods` key and a lever the package's own docstring rules out.

**What changes**
When the `scorer` join lands, one `("A", "MEM", "judge", …)` row inside the `dom.manage` pass, and `memory/api.py:254` names `dom.manage` explicitly. Until then, `docs/04_CONTRACT.md:1170-1180` should stop saying `LOOP_ORDER` places it — **it does not**, and a P4 author reading that will look for a row that is not there.

**Confidence** High on the stale-premise finding (grepped both tables). Medium on (a) over (b) — the cost argument is real and I did not measure it.
**Literature** NOT APPLICABLE — which of two internal cadences a package's own probe rides.

---

## Q-TOK-12 — which window's `Due` does the flush act on?

*(Flagged "if not covered" — almost certainly the TOK slice's. Brief, and I defer to them.)*

**What I read**
`docs/04_CONTRACT.md:1327-1338`, `:856-870` (§3.10); `src/spine/compose.py:773-786` (the `TOK.on_window` A row), `:787-795` (`RunClock.advance`), `:927-939` (`mint_burst`), `:940-953` (`judge_probation`), `:1448-1467` (`System.__slots__` and the `due` comment).

**What is true today**
Live and unchanged. The carrier is named — `System.due`, `compose.py:1467` — and the choice is deliberately left open: `compose.py:779-786` states both failure modes and defers to Q-TOK-12. `batch_windows` Dues reach one flush; `mint_burst` and `judge_probation` act per flush.

**Recommendation**
**(b), the OR over the batch, with the count of merged fires as a counter** — the contract's recommendation, and I did not find anything that undermines it.

**Why it fits the framework**
DID IT FIRE is decisive and it is not close. The measured failure this cadence design exists to prevent is a fire that silently does not happen — minting fired 999 times at `batch_w=1` and **zero** times at every `batch_w` in {2, 8, 15, 16, 32}. Option (a) drops up to `batch_windows − 1` fires *by construction* and reports nothing: an untrippable-guard-shaped loss. (b) loses no fire, and its cost — a flush acting on a cadence that fired mid-batch — is a *phase* error of at most one flush, which a merged-fire counter makes visible. A defect you can count beats a defect that is silent. (c) is refused by the loop's own shape: hoisting the three B acts to A puts a mint inside the accumulator and invalidates the batch the model is mid-flush on.

**What changes**
`compose.py:779-786` and `:1458-1461` state the resolution; the merged-fire counter joins TOK's DID IT FIRE surface. No signature moves.

**Confidence** Medium-high — internally consistent and I verified the rows, but the TOK slice will have read `TOK.on_window`'s and `mint_burst`'s bodies-to-be more closely than I did. If they conclude otherwise, take theirs.
**Literature** NOT APPLICABLE — no paper can say which window's event this tree's flush acts on.
