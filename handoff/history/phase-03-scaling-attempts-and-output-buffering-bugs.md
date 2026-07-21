# Phase 3 — scaling attempts, silent stalls, output-buffering bugs

On "expand to the H100 and see how good it gets," recognized the single-layer GRU was the quality ceiling and added a
**Transformer** option (`MODEL=transformer`), multi-layer GRU, `build_lm()`, checkpoint architecture metadata, and a
pre-run timing **probe** (real per-step cost before a long run — satisfies estimate-before-GPU with a live number).

Then a run appeared stuck for 30 min showing only a harmless PyTorch warning. Two compounding causes: (1) launch missing
`python3 -u` → Python block-buffers stdout through `tee`, so all progress was invisible; (2) config too heavy (800k-entry
memory re-keyed every 400 steps through a large Transformer at batch 1). **Fixed the buffering IN THE CODE**
(`sys.stdout.reconfigure(line_buffering=True)`) so it no longer depends on launch flags. Lesson: anything that can
silently fail to surface progress will eventually cost a wasted run — fix it in code, not instructions.
</content>
