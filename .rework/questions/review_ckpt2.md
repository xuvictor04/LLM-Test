**Scope note, before the findings.** The prompt's agent array is truncated mid-way through the second agent (it cuts off inside Q-OPT-5), so **no Q-CKPT-2 recommendation text reached me**. I therefore verified the chain from the tree and judged the option the tree itself recommends — `docs/04_CONTRACT.md:1284-1298`, **option (a)** — plus (b) and (c). If the agent recommended something else, findings 1-5 stand regardless, because they are about the tree, not about the answer. All six suites were run first and are green (`test_ownership` 11+18, `test_contract` 12+34, `test_census` 5, `test_assemble` 7, `test_couplings` 4, `test_derive` 575 oracle cases, 0 mismatches).

---

### [CRITICAL] ISSUES C12's premise is contradicted by the tree's own K10-checked declaration: under the declaration that a machine check actually reads, **no resume raises at all**

**Which question(s)** Q-CKPT-2, and directly ISSUES C12 — the reviewer prompt asked "Would every resume really raise? … if it would NOT, that is a critical finding against ISSUES C12 and I want it."

**Why it is real**
`Snapshot.geometry` is written by exactly one thing: `CKPT.save`'s `geometry` argument (`src/ckpt/api.py:16` declares `Snapshot payload, geometry, step, epoch, best_state`; `:83` is `def save(ckpt, *, payload, geometry, step, epoch, reason, suffix="")`). So the question "what does the save side record" reduces to "what produces `CKPT.save`'s `geometry`".

The tree answers that in **data**, at `src/spine/compose.py:1346-1350`:

```
    "CKPT.save":
        "geometry is _geometry_manifest(sysm), the LIVE manifest -- the same object CKPT.check_geometry "
        "compares a restored Snapshot against, written here so the two sides of that comparison are "
        "one function's output rather than two. Ten of its fields have no writer on the save side "
        "today (Q-CKPT-2), which the C-block prose states.",
```

That entry is not prose — it is a member of `ROW_ARGUMENTS_ELSEWHERE`, which `tests/test_contract.py` K10 reads in **both** directions (`tests/test_contract.py:1940-1943`: *"ROW_ARGUMENTS_ELSEWHERE names {key!r} … and no row requires arguments for it. A stale exemption is a row nobody can retire."*). K10 passes, so this entry is live and is the normative producer declaration for `geometry`. The same claim is repeated inside the C row itself at `compose.py:1016`: *"CKPT.save gets its manifest from `_geometry_manifest` via ROW_ARGUMENTS_ELSEWHERE."*

If the save side writes `_geometry_manifest(sysm)`, the recorded key set is **byte-identical** to the live key set the child builds at `compose.py:1582`. `check_geometry`'s comparison is *"driven off the manifest's KEY SET"* (`ckpt/api.py:177-179`), so the missing-field set is **empty** and the refusal at `ckpt/api.py:175` never fires.

Meanwhile `compose.py:970-976`, `:1014`, `:343-348`, `docs/04_CONTRACT.md:823-832`, `:1284-1290` and `.rework/ISSUES.md:88-96` all say the opposite: *"the save side records **WORLD.geometry alone — five fields**"* and therefore *"EVERY RESUME RAISES GeometryRefusal THE DAY P4 LANDS"*. `git show 35b02ee` (the C12 commit, 2026-08-30) touched `compose.py` in three places and **did not touch** `ROW_ARGUMENTS_ELSEWHERE["CKPT.save"]`, which had already been added in the earlier commit `04e67bf`. So C12 was written against a claim the same file had already contradicted.

This is not a wording dispute. It is the difference between *"Q-CKPT-2 is BLOCKING because the gate refuses everything"* and *"Q-CKPT-2 is a narrower question about two sidecars and one live field"*. The owner is being asked to act on the first.

**Demonstrated**
```
$ python3 - <<'EOF'   (sys.path.insert(0, .../src); LMGeometry stubbed per lm/api.py:20-22)
live manifest fields: 16
['fab.dk', 'fab.rank', 'fab.slots', 'lm.ctx', 'lm.heads', 'lm.layers', 'lm.pos_max',
 'lm.vocab_slots', 'lm.width', 'sig.d', 'sig.space', 'world.feedback', 'world.hid',
 'world.lat', 'world.nmax', 'world.route_d']

READING A (save records _geometry_manifest): in manifest & absent from recording = []
READING B (save records WORLD.geometry alone): in manifest & absent from recording = 16 [...]
```
```
$ python3 tests/test_contract.py | grep K10
PASS  K10  every required argument is produced by an earlier row
```
```
$ git show 35b02ee --stat
 .rework/ISSUES.md    | 13 +++++++++++--
 docs/04_CONTRACT.md  | 14 +++++++++++---
 src/spine/compose.py | 23 ++++++++++++++++++++---
```
(the diff, quoted in full above in my working, touches `ASSEMBLY_ORDER`'s gate row, the C-block comment and `_sidecar`'s docstring — not `ROW_ARGUMENTS_ELSEWHERE`.)

**What the answer should be instead**
State plainly that the tree currently holds **two mutually exclusive answers to Q-CKPT-2's first half**, and that the one a check reads (`ROW_ARGUMENTS_ELSEWHERE["CKPT.save"]`) already implements option (a)'s field half. The owner's ruling must **delete one of them in the same commit** — either `ROW_ARGUMENTS_ELSEWHERE["CKPT.save"]` loses the words *"the same object … one function's output rather than two"*, or the six C12 statements lose *"every resume raises"*. Until then, "would every resume raise?" has no determinate answer, and **C12's severity as filed is not supported by the tree**. The residual live defects — which are real — are the two sidecars, the grown population count, and the missing shape fields below; those are worth a HIGH, not a CRITICAL "the gate refuses everything".

Note also the internal contradiction *inside* the single `ROW_ARGUMENTS_ELSEWHERE` entry: it says `geometry is _geometry_manifest(sysm)` and then says *"Ten of its fields have no writer on the save side today"*. If `geometry` **is** `_geometry_manifest(sysm)`, that one call is the writer of all sixteen. The second sentence is the C-block's claim leaking into the entry that refutes it.

---

### [CRITICAL] The gate omits every field that decides *which tensors exist* — `lm.arch`, `lm.compose`, `sig.mode`, `fab.emb_hid` — and all four are pure frozen-Config reads. This is the option nobody proposed.

**Which question(s)** Q-CKPT-2 ("is there an option nobody proposed?"), Q-CKPT-1.

**Why it is real**
The gate exists because *"a checkpoint built at one width cannot load into a model built at another"* (`compose.py:1577-1580`, citing `self_organize.py:4413-4468`). Yet `_geometry_manifest` (`compose.py:1875-1946`) copies only six names off `LMGeometry` — `("width", "layers", "heads", "ctx", "pos_max", "vocab_slots")` at `:1937` — and never reads these:

- **`lm.arch`** (`src/lm/levers.py:221`, `Lever("gru", …)`, gru vs transformer). Two entirely different modules. `LM_ARCH=gru LM_LAYERS=1` and a transformer at the same numbers produce an identical manifest.
- **`lm.compose`** (`src/lm/levers.py:455`, default `False`). `lm/api.py:76-79`: *"When compose is FALSE, emb and head are constructed; when TRUE they are **NOT constructed at all**"*. Flipping it across a resume changes the parameter **set**, not a dimension — and the gate passes it.
- **`sig.mode`** (`src/sig/levers.py:183-185`, `choices=("learned","bigram")`) — a trained encoder versus a frozen hashed-bigram modulus.
- **`fab.emb_hid`** (`src/fabric/levers.py:462`, `Lever(128, "Hidden width of the shared identity embedder eemb and its inverse edec.")`) — a real tensor dimension, named in `FAB.load_state_dict`'s `LEVERS READ` (`src/fabric/api.py:393`) and compared *only* against the sidecar, which is `None` on every resume.

`fabric/api.py:389-391` states the exact failure this leaves open: *"three widths, one error message (:4678-4684)"* — *"no way to tell whether **FAB_EMB_HID**, SIG_D or D_MODEL was to blame"*. `SIG_D` and `D_MODEL` (`lm.width`) are in the manifest; `FAB_EMB_HID` is not.

Every one of the four is readable off a frozen Config with no live object, so this costs **no new entry point, no wire, no signature, no lever** — four lines in `_geometry_manifest`.

**Demonstrated**
```
$ python3 -c "...; print([f for f in ('arch','width','layers','heads','ctx','pos_max',
   'vocab_slots','compose','dropout','max_token_bytes','param_estimate') if 'lm.'+f not in live])"
LMGeometry fields NOT in the manifest: ['arch', 'compose', 'dropout', 'max_token_bytes', 'param_estimate']
```
```
$ grep -n "    arch = Lever\|    compose = Lever" src/lm/levers.py
221:    arch = Lever("gru", "Which base language model is constructed: the GRU (MiniLM) or the transformer "
455:    compose = Lever(False, "Build each token's vector from its bytes plus a learned residual, instead of "
$ grep -n "emb_hid" src/fabric/levers.py
462:    emb_hid = Lever(128, "Hidden width of the shared identity embedder eemb and its inverse edec.",
$ sed -n 183,185p src/sig/levers.py
    mode = Lever("learned", "Which signature function the run uses: the online contrastive encoder, "
                            "or the frozen hashed-bigram control.", U.NAME,
                 choices=("learned", "bigram"))
```

**What the answer should be instead**
**The option nobody proposed — call it (e) — and it dominates (a) on every axis the owner's decision rule names:**

1. Add to `_geometry_manifest`: `lm.arch` (EXACT), `lm.compose` (EXACT), `sig.mode` (EXACT), `fab.emb_hid` (EXACT), plus the two SIG values the root **already computes before the gate**: `sig.width_units` = `_signature_width(lm, sysm.vocab)` and `sig.alphabet_size` = `_alphabet_size(sig, lm)`. Both are available: `sysm.vocab` is built at `compose.py:1567-1568`, the gate runs at `:1581-1584`, and `SIG.build` consumes exactly these two helpers at `:1613-1614`. So SIG's **entire** five-field sidecar — `width_units, alphabet_size, space, d, mode` (`sig/api.py:235`) — is computable before the first allocation.
2. Re-point `_sidecar` (`compose.py:1949-1976`) from `Snapshot.geometry[PFX]` to the **prefix slice of the recorded manifest** (`{k.split(".",1)[1]: v for k in recorded if k.startswith("sig.")}`).

That arms **both** disarmed refusals, closes the four missing shape fields, needs **no** `FAB.state_dict` sidecar declaration (which is the one thing option (a) says it cannot do without the owner), touches **no frozen signature**, adds **no** entry point, and leaves `_geometry_manifest` a pure function of frozen Configs so the save side can still rebuild it verbatim. `_sidecar` is a private helper in the composition root; changing what it reads is not a surface change.

---

### [HIGH] `WORLD.geometry` returns **six** fields, not five — and its return has no declared consumer, so the one field in the whole system that genuinely needs a live object is computed and dropped

**Which question(s)** Q-CKPT-2 ("Does WORLD.geometry's five-field return actually cover the fields the C-stage row claims?"), Q-CKPT-1.

**Why it is real**
`src/world/api.py:160-175`: *"Every field a resume must match, with its rule: lat/hid/route_d EXACT, nmax MAY_WIDEN, **n (the grown population) MAY_WIDEN AND MAY_NARROW**, feedback EXACT"*, `LEVERS READ: lat, hid, route_d, nmax, n0, feedback`. That is **six** returned fields.

Three statements call it five: `.rework/ISSUES.md:90` (*"WORLD.geometry alone — five fields"*), `docs/04_CONTRACT.md:828` (*"five fields"*) and `compose.py:1014` (*"five fields recorded against fifteen compared"*) — while `compose.py:1016`, in the **same row**, says *"WORLD.geometry returns WORLD's own **six** fields"*. Five of the six (`lat, hid, route_d, nmax, feedback`) are already in the live manifest as `world.*`, so they add nothing to the recording. The **sixth, `n`, is the only field in this entire question that cannot be computed from frozen Configs** — and it is the one the file drops.

Dropped, because the C row's `produces` column literally begins *"NOT geometry: …"* (`compose.py:1016`) and names no consumable value, while `ROW_ARGUMENTS_ELSEWHERE` hands `CKPT.save`'s `geometry` to `_geometry_manifest`. No row, note or table declares a merge. So `WORLD.geometry(w)` is called at stage C and its return goes nowhere.

The claim in the same row that *"What this row does supply is the RECORDED side of the gate's comparison"* is therefore false on both halves: it supplies at most 6 of 16 fields, and nothing consumes it.

**Demonstrated**
```
$ grep -n "def geometry" -A 15 src/world/api.py
160:def geometry(world: Config, w):
161:    """Every field a resume must match, with its rule: lat/hid/route_d EXACT, nmax MAY_WIDEN, n
162:    (the grown population) MAY_WIDEN AND MAY_NARROW, feedback EXACT.
171:    LEVERS READ: lat, hid, route_d, nmax, n0, feedback
```
```
$ grep -n "five fields\|six fields" src/spine/compose.py docs/04_CONTRACT.md .rework/ISSUES.md
src/spine/compose.py:1014:  "and the block above: five fields recorded against fifteen "
src/spine/compose.py:1016:  "NOT geometry: WORLD.geometry returns WORLD's own six fields, ..."
docs/04_CONTRACT.md:828:   WORLD's** (Q-CKPT-1) — five fields.
.rework/ISSUES.md:90:      records **`WORLD.geometry` alone — five fields**
```

**What the answer should be instead**
Correct "five" to "six" in the three places, and give the ruling the one thing the enumeration actually demands: **`world.n` is the single field that needs a live object, and `WORLD.geometry` is its only possible emitter.** It must be merged into the recorded map with a declared key (`world.n`) and a declared rule (MAY_WIDEN **and** MAY_NARROW), reported UNCHECKED by the child's gate — which is the direction `check_geometry`'s DID IT FIRE (`ckpt/api.py:183-186`) actually covers — and re-refused by `WORLD.load_into` (`world/api.py:201-210`), which reads it off `payload['WORLD']` and so already works. Everything else `WORLD.geometry` returns is redundant with the manifest and should be documented as such rather than presented as "the recorded side".

---

### [HIGH] The enumeration the prompt asked for: **all 16 manifest fields are pure functions of frozen Configs; zero need a live object.** The manifest is 16 fields, not 15.

**Which question(s)** Q-CKPT-2, the crux question.

**Why it is real**
`_geometry_manifest(sysm)` (`compose.py:1875-1946`) reads exactly two things off `sysm`: `sysm.configs["LM"|"SIG"|"FAB"|"WORLD"]` (frozen — configs freeze when `build()` returns) and `sysm.geometry`. `sysm.geometry` is set at `compose.py:1554` as `lm_api.resolve(lm)`, and `lm/api.py:29` is `def resolve(lm: Config)` — **one frozen Config in, an immutable `LMGeometry` out**. No tensor, no model, no corpus.

Enumeration, name by name, with the answer for each:

| field | source | pure over frozen Configs? |
|---|---|---|
| `lm.width` | `LM.width`, then `LMGeometry.width` | yes |
| `lm.layers` | `LM.layers`, then `LMGeometry.layers` (resolved) | yes |
| `lm.heads` | `LM.heads` / `LMGeometry.heads` | yes |
| `lm.ctx` | `LM.ctx` / `LMGeometry.ctx` | yes |
| `lm.pos_max` | `LMGeometry.pos_max` only | yes |
| `lm.vocab_slots` | `LM.vocab_slots` / `LMGeometry.vocab_slots` | yes |
| `sig.d` | `SIG.d` | yes |
| `sig.space` | `SIG.space` | yes |
| `fab.slots` | `FAB.slots` | yes |
| `fab.rank` | `FAB.rank` | yes |
| `fab.dk` | `FAB.dk` | yes |
| `world.lat` | `WORLD.lat` | yes |
| `world.hid` | `WORLD.hid` | yes |
| `world.route_d` | `WORLD.route_d` | yes |
| `world.nmax` | `WORLD.nmax` | yes |
| `world.feedback` | `WORLD.feedback` | yes |

**Sixteen, not fifteen.** `LMGeometry` declares `pos_max` (`src/lm/api.py:20-22`), so the `:1937` loop always adds `lm.pos_max`. "15 fields — 16 with pos_max" (`compose.py:970`, `:1298`, `docs/04_CONTRACT.md:825`) is phrased as a contingency; it is not one. 15 is only reachable when `LM.resolve` is a stub and `sysm.geometry` is absent — and in that state the manifest silently records **the `layers` sentinel `0`** instead of the resolved depth (`lm.layers = 0` in my run below), because `:1938-1940` does `getattr(geom, name, None)` / `if value is None: continue`. That is a latent wrong-measurement in the manifest itself if a caller ever builds it before `resolve()`.

**Demonstrated**
```
$ python3 -c "... s.configs=cfgs; s.geometry=None; m=C._geometry_manifest(s); ..."
15 fields
  lm.width = 128 EXACT LM_WIDTH
  lm.layers = 0 EXACT LM_LAYERS          <-- the SENTINEL, not the resolved depth
  ... world.feedback = True EXACT WORLD_FEEDBACK
```
The call succeeded against an object carrying **only** `.configs` and `.geometry` — no model, no vocab, no stream. That is the purity proof. With a real `LMGeometry`: 16 fields (output quoted in finding 1).

**What the answer should be instead**
Say the crux out loud, because it changes the shape of the whole question: **there is no collection problem for the manifest.** Every field the gate compares is rebuildable on the save side by calling the same function, and `compose.py` already stores it (`sysm.manifest = _geometry_manifest(sysm)`, `:1582`) so `CKPT.save` at stage C can hand back the identical object. The collection problem is confined to exactly two things: the grown counts (`world.n`, and FAB's `n_live`, which no one has proposed recording at all) and the two sidecars. An answer that describes Q-CKPT-2 as "ten/eleven packages have no producer" is describing Q-CKPT-1's framing, not this one.

---

### [HIGH] The "ten fields" arithmetic is wrong under every reading, because **the recorded map's key spelling is nowhere declared**

**Which question(s)** Q-CKPT-2.

**Why it is real**
`_geometry_manifest` keys are **prefixed**: `world.lat`, `world.nmax`. `WORLD.geometry`'s docstring (`world/api.py:161-171`) names its fields **unprefixed**: `lat`, `hid`, `route_d`, `nmax`, `n`, `feedback`. And `_sidecar` (`compose.py:1969-1970`) reads the recorded object as **nested by package**: `recorded.get(prefix)` with `prefix` in `{"SIG","FAB"}`.

So three different shapes for one object are in play and none is declared:
- flat prefixed (`world.lat`) — what the live manifest is;
- flat bare (`lat`) — what `WORLD.geometry` returns;
- nested (`{"WORLD": {...}}`) — what `_sidecar` and §3.9's option (a) assume.

Under C12's own reading, the missing set is therefore **16, not 10**: `world.lat` is in the manifest and `lat` is not the same key. Under a nested recording it is 16 as well. "Ten" is only reachable if you silently assume a re-keying that no statement in the tree performs.

This is the same defect family the C rows already flag one column over — `compose.py:983-989` on `payload['DATA']`: *"its KEY SPELLINGS ARE NOWHERE DECLARED … so the round trip … is unverifiable by inspection"* — and `:990-993` on `payload['TOK']`, where `D-T3 is a live defect CAUSED by a key the file never had`.

**Demonstrated**
```
READING B (save records WORLD.geometry alone): in manifest & absent from recording = 16
['fab.dk','fab.rank','fab.slots','lm.ctx','lm.heads','lm.layers','lm.pos_max','lm.vocab_slots',
 'lm.width','sig.d','sig.space','world.feedback','world.hid','world.lat','world.nmax','world.route_d']
```
```
$ sed -n 1968,1971p src/spine/compose.py
    recorded = getattr(restored, "geometry", None) or {}
    side = recorded.get(prefix)
```

**What the answer should be instead**
Whatever option is adopted must **declare the recorded map's key spelling as part of the ruling**, in one sentence, in `ckpt/api.py`'s `Snapshot` record line — not leave it to P4. Option (a) as written cannot be implemented without it: "keyed by prefix" is ambiguous between `{"WORLD": {...}}` and `{"world.lat": ...}`, and `check_geometry`'s key-set comparison and `_sidecar`'s lookup want **opposite** answers. My option (e) resolves it by construction: one flat prefixed map, and `_sidecar` filters it by prefix instead of indexing a nested key.

---

### [MEDIUM] Option (a) arms a **second** comparison of three fields the gate already checks, from a different producer, with no declared precedence

**Which question(s)** Q-CKPT-2 — judging the recommendation.

**Why it is real**
`fab.slots`, `fab.rank`, `fab.dk` are already in `_geometry_manifest` (`compose.py:1918-1921`) with rules `MAY_WIDEN / EXACT / EXACT`. `FAB.load_state_dict` (`src/fabric/api.py:385-396`) refuses on **the same three**: *"rank and dk are INNER dimensions and cannot be prefix-widened; slots may widen but never narrow."* Under option (a) the FAB sidecar is written by `FAB.state_dict` while the manifest slice is written by `_geometry_manifest` — two producers, two recordings, three shared fields, and nothing says which is normative if they disagree. The genuinely additive content of FAB's sidecar is `emb_hid` and `signature_dim` — and `signature_dim` is `sig.d`, also already in the manifest.

SIG is cleaner (`width_units`, `alphabet_size`, `mode` are genuinely additive; `space` and `d` duplicate the manifest), but the same duplication applies to those two.

**Demonstrated**
```
$ grep -n "def load_state_dict" -A 12 src/fabric/api.py
385:def load_state_dict(fab: Config, pop, sd, *, sidecar):
388:    rank and dk are INNER dimensions and cannot be prefix-widened; slots may widen but never
389:    narrow; signature_dim must match. Each refusal NAMES the field.
393:    LEVERS READ: slots, n0, rank, dk, emb_hid (compared against the sidecar)
```
manifest keys (from the run above) include `fab.slots`, `fab.rank`, `fab.dk`, `sig.d`.

**What the answer should be instead**
Do not create a second recording of a field the gate already records. Under option (e) there is exactly **one** recorded map and one comparison; `SIG`/`FAB.load_state_dict` receive a *slice of it* rather than a parallel artifact, so the duplication cannot arise and `FAB.state_dict` never has to declare a sidecar — which removes the one item §3.9 says *"is not a row the root can write alone"*.

---

### [MEDIUM] The answer to Q-CKPT-2 is buried in a table whose own preamble says it holds two entries and is *"a place a row stops being read"* — and it holds 24

**Which question(s)** Q-CKPT-2; explains how finding 1 happened.

**Why it is real**
`compose.py:1285-1287`: *"IT IS DELIBERATELY TWO ENTRIES LONG. … an exemption table is a place a row stops being read, so it is for the two cases where writing the name INTO the row would be worse than not writing it"*. `docs/04_CONTRACT.md:542` heads the section *"`ROW_ARGUMENTS_ELSEWHERE` — two entries, and why only two"* and tabulates exactly two: `CKPT.check_geometry` and `LM.encode`. The dict has **24**, including `CKPT.save` — the entry that carries the normative answer to the first half of Q-CKPT-2.

**Demonstrated**
```
$ python3 -c "from spine import compose as C; print(len(C.ROW_ARGUMENTS_ELSEWHERE)); print(sorted(C.ROW_ARGUMENTS_ELSEWHERE))"
24 entries:
['CKPT.check_geometry', 'CKPT.save', 'DOM.observe', 'FAB.forward', 'FAB.load_state_dict',
 'LM.anchor_term', 'LM.encode', 'LM.lm_loss', 'MEM.maintain', 'MEM.write', 'OPT.build',
 'OPT.scaled_backward', 'RUN.RunClock.begin_epoch', 'RUN.bench_summary', 'RUN.cadence_audit',
 'RUN.new_cadences', 'SIG.build', 'SIG.cadence_due', 'SIG.encode', 'SIG.load_state_dict',
 'SIG.train_step', 'SIG.warm_up', 'TOK.judge_probation', 'WORLD.loss_terms']
```
(K1 passes because it compares the *public surface*, not this table; nothing checks the count against its own claim.)

**What the answer should be instead**
Note it as a contributing cause rather than as style: a declaration that says "two, and readers stop here" while holding 24 is how a normative statement about the save side went unread by the commit that filed C12 as critical. The Q-CKPT-2 ruling should move `CKPT.save`'s geometry producer **into the C row's own note**, where §3.0.1's stated rule puts every other helper-supplied argument, and the section heading should stop saying two.

---

### [LOW] Option (c) — narrowing the gate's key set — is now doubly refused, and should be said so in one line

**Which question(s)** Q-CKPT-2, option (c).

**Why it is real** The prompt asked me to be hard on it. Two independent refusals:
1. The repository's own: `ckpt/api.py:175-179` makes `if recorded and recorded != live` **unwritable** by construction, and `.rework/ISSUES.md:96` names (c) as *"the one that quietly checks nothing"*. It is the untrippable-guard family, 60 recorded instances.
2. A new one from finding 1: **there is nothing to narrow.** Under the declaration K10 reads, the live and recorded key sets already coincide. (c) would delete `sidecar` from two frozen signatures (`sig/api.py:232`, `fabric/api.py:385`) and throw away the H24/H31 refusals in exchange for a problem that, on the tree's own normative statement, does not exist.

**Demonstrated** `READING A … absent from recording = []` (finding 1); `PASS K10` (finding 1); `ckpt/api.py:177-179` quoted in finding 1.

**What the answer should be instead** Refuse (c) in one sentence, on ground 2 rather than on taste — it is the stronger ground and it is new.

---

### Signature audit for each option (asked directly: "does it require any frozen signature to move?")

| option | frozen signature moves? | verified how |
|---|---|---|
| (a) C block records `_geometry_manifest` keyed by prefix + FAB declares a sidecar | **No.** `FAB.state_dict(fab, pop)` (`fabric/api.py:363`) and `SIG.state_dict(sig, st)` (`sig/api.py:211`) change only in docstring; `SIG/FAB.load_state_dict(..., *, sidecar)` unchanged; `CKPT.save`'s `geometry` already exists | signatures read directly |
| (b) eleven new `geometry()` entry points | **Yes** — 121 → 132; `docs/04_CONTRACT.md` §7 and K1 move in the same commit | `docs/04_CONTRACT.md:1416` lists the frozen set; K1 compares both directions |
| (c) delete the `sidecar` parameters | **Yes**, two: `sig/api.py:232`, `fabric/api.py:385` | signatures read directly |
| **(e) — mine**: extend `_geometry_manifest` with `lm.arch`, `lm.compose`, `sig.mode`, `sig.width_units`, `sig.alphabet_size`, `fab.emb_hid`; re-point `_sidecar` at the prefix slice; merge `world.n` from `WORLD.geometry` | **No.** `_geometry_manifest` and `_sidecar` are private helpers of the composition root; the six added fields are frozen-Config or already-computed root arithmetic (`_signature_width` at `compose.py:1760-1773`, `_alphabet_size` at `:1776`, both called at `:1613-1614`, both available at the gate because `sysm.vocab` is built at `:1567-1568` and the gate runs at `:1581`) | ordering and helper definitions read directly |

**Does the recommended (a) close the gap?** Partly. It closes the field half — which finding 1 says may already be closed — and it closes the sidecars **only if** the owner also rules on the key spelling (finding 5) and FAB declares a sidecar it does not emit. It leaves a refusal that cannot fire in one place regardless: `FAB.load_state_dict`'s `emb_hid` comparison has no entry in either the manifest or any declared sidecar content, and `lm.arch` / `lm.compose` / `sig.mode` remain unrefused on both paths (finding 2). **Option (e) closes all of it, moves no frozen signature, and needs no owner's word from FAB.**

---

### What I could not settle

**NOT DEMONSTRATED — the reviewed recommendation's own text.** The agent array in my prompt is truncated inside the second agent's Q-OPT-5 answer; no Q-CKPT-2 section reached me. I judged `docs/04_CONTRACT.md:1284-1298`'s options (a)/(b)/(c) instead. What would settle it: the untruncated Q-CKPT-2 answer.

**NOT DEMONSTRATED — runtime behaviour of the gate.** `CKPT.check_geometry`, `CKPT.save`, `WORLD.geometry`, `SIG/FAB.state_dict` and `load_state_dict` are all stubs (`raise NotImplementedError`), and `compose()` dies earlier at `RUN.process_setup`, so no resume can actually be executed. Every claim about refusal behaviour above is derived from the specified semantics at `ckpt/api.py:175-186` plus the declared producers, and the key-set arithmetic is computed from the real `_geometry_manifest` output. What would settle it: a P4 `check_geometry` body plus a synthetic `Snapshot`, or — cheaper and available today — a test that builds `_geometry_manifest` twice and asserts the key sets are equal, which is the whole of the field-half question.

**NOT DEMONSTRATED — whether FAB's grown `n_live` needs the same treatment as `world.n`.** `FAB.load_state_dict`'s refusal covers `slots` (the cap), not the live count; `Population.n_live` is the analogous grown number and nothing records it in any geometry map. I did not trace whether the payload round-trip already refuses a narrowed population the way `WORLD.load_into` does. What would settle it: reading `fabric/api.py`'s `state_dict`/`load_state_dict` book list against `Population`'s declared fields.