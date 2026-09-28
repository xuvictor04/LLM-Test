# results/ — the evidence behind the documents

One folder per workflow or GPU fleet, named `<topic>_<YYYY-MM-DD>`. A GPU folder carries its fleet's own
archive name: `gpu_world.sh` packs `OUT` as `<OUT without _out>_<launch date>.tgz`. Each folder is the
evidence a document was written from: a workflow's or a fleet's raw output (results, logs, archives,
scripts beside what they printed) and, for a fleet, the reading written from it. The scripts carry the
paths of the day they ran (scratch directories, `/home/user/LLM-Test`). The live conclusion is in the
document each row names: read that first.

| folder | evidence for | cited by |
|---|---|---|
| `gpu_world_2026-09-24/` | the WORLD fleet, Q-WORLD-10's four arms at five seeds, which shipped `WORLD_FEEDBACK` False: `ANALYSIS.txt` (transcribed from the owner's terminal), the fleet's archive `gpu_world_2026-09-24.tgz` (uploaded 2026-09-26; also `tests/test_gpu_world.py` F11's fixture), `ARCHIVE_READS.md` (what the archive adds, for four register rows) and `archive_reads.txt` (`tools/read_fleet_archive.sh`'s output) | `docs/proposals/05_DECISIONS.md`, `docs/04_CONTRACT.md`, `notes/OWNER_BRIEF.md`, `notes/AGENT_STATE.md`; `gpu_world.sh` and `tools/read_fleet_archive.sh` name it |
| `multimodal_design_2026-09-25/` | Proposal 03, audio and video: the design workflow's output and its CPU prototypes | `docs/proposals/03_AUDIO_VIDEO.md`, `docs/proposals/05_DECISIONS.md`, `notes/AGENT_STATE.md` |
| `live_codec_design_2026-09-25/` | Proposal 03b, the live codec and the measured rate: the workflow's output and its CPU prototypes | `docs/proposals/03b_LIVE_CODEC.md`, `docs/proposals/05_DECISIONS.md`, `notes/AGENT_STATE.md` |
| `self_regulation_design_2026-09-26/` | Proposal 04, self-regulation: the workflow's output and its prototypes on a shared synthetic testbed. Its `prototypes/judge/04_SELF_REGULATION.md` is the judge's early draft under the live proposal's name and title (812 lines against the committed 1,593): read `docs/proposals/04_SELF_REGULATION.md` | `docs/proposals/04_SELF_REGULATION.md`, `docs/proposals/05_DECISIONS.md`, `notes/AGENT_STATE.md` |
| `decisions_2026-09-26/` | Proposal 05, the decision register: the ruling workflow, its verification rounds (`verify/`), and `s0b/`, a CPU operation check of the mid-epoch retokenization act | `docs/proposals/05_DECISIONS.md` (by paths relative to the folder), `docs/proposals/README.md`, `docs/04_CONTRACT.md`, `notes/AGENT_STATE.md` |
| `gpu_retok_2026-09-27/` | the retok fleet, which shipped `TOK_RETOK_EVERY` 1000 (provisional until E2): `RESULTS.md` (the reading), `PASTE_BACK.txt` (the fleet's block), the fleet's archive `gpu_retok_2026-09-27.tgz` (also `tests/test_gpu_world.py` F26's fixture), `CHECKPOINTS.md` (the checkpoint tars kept off the repository, and their checksums) and `verify/` (the re-reads, each script beside its output) | `docs/proposals/05_DECISIONS.md`, `docs/04_CONTRACT.md`, `notes/OWNER_BRIEF.md`, `notes/AGENT_STATE.md`, `src/tok/levers.py` |
| `gpu_retok_2026-09-28/` | the cooldown fleet (register §8 2.2), which kept `TOK_RETOK_EVERY` 1000 and `FAB_COOLDOWN` 400: `RESULTS.md` (the reading), `PASTE_BACK.txt` (the fleet's block), the fleet's archive `gpu_retok_2026-09-28.tgz` and `verify/` (the re-reads, each script beside its output) | `docs/proposals/05_DECISIONS.md`, `docs/04_CONTRACT.md`, `notes/OWNER_BRIEF.md`, `notes/AGENT_STATE.md`; `results/gpu_retok_2026-09-27/RESULTS.md` names its `verify/j_logs.out` |

The folders keep their names and places: two of the archives are test fixtures, and the documents
cite files inside the folders by path.
