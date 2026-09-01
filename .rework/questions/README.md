# The 38 open contract questions — evaluations and adversarial checks

Raw output from the `p3-questions` workflow (8 agents), kept verbatim. **These are recommendations,
not decisions.** Nothing here has been applied except where a separate commit says so.

| file | what it is |
|---|---|
| `answers_*.md` | five slices, one section per question: what was read, what is true today, the options, a recommendation, why it fits the framework, what changes, confidence, and whether literature bore |
| `blocking_*.md` | each slice's view of which questions block P4, plus its cross-slice dependencies |
| `review_compatibility.md` | is each recommendation actually compatible with the framework — the owner's stated decision rule |
| `review_ckpt2.md` | Q-CKPT-2 alone, given a reviewer to itself because the owner said they had no answer |
| `review_consistency.md` | do the five slices contradict each other, and did anything fall between them |

## Known limits of this run, stated rather than discovered later

**The consistency reviewer saw only 2 of the 5 answer sets.** The workflow script passed the answers
into the review prompts through `JSON.stringify(...).slice(0, 90000)`, and five slices of this size
do not fit — the second is cut off mid-sentence inside Q-OPT-5. So `review_consistency.md` opens by
saying the cross-slice check **could not be completed for 24 of the 38 questions**, and it is right.
That is a defect in the orchestration, not in the reviewer; its findings about the two slices it did
see stand, and the rest of the cross-slice check has not been done.

**The Q-CKPT-2 reviewer likewise received no recommendation text** for the question it was assigned,
for the same reason — and verified the chain from the tree instead, which is why its findings hold
anyway. They are about the tree, not about an answer.

**Read the reviews before the answers.** Both reviewers that saw enough to judge found recommendations
resting on stale readings of the tree — several questions predate the last two rounds of repairs and
some are already answered, which is itself a useful result.
