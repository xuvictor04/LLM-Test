# Develop on the designated branch, commit, and push

Work happens on a designated feature branch (this session: `claude/hub-addition-1ueehb`, which — because
the repo started empty — is also the repo's DEFAULT branch). Commit with clear messages; push with
`git push -u origin <branch>` (retry with exponential backoff on network errors). Do NOT push to a
different branch without explicit permission. Do NOT open a PR unless the user asks.

NOTE: if a designated PR is already MERGED, treat follow-up as a fresh change — restart the branch from
the latest default branch rather than stacking on merged history.

**Source:** session task instructions (git development-branch requirements).
