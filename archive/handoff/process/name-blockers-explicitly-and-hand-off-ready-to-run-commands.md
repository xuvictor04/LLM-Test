# Name sandbox blockers explicitly; hand off ready-to-run commands

The user will run anything the assistant's environment cannot reach — large downloads, long training, GPU work,
network outside the allowlist. When blocked, say so plainly and hand off a precise, ready-to-run command or script.
NEVER silently route around a blocker, substitute something smaller, or present a local approximation as equivalent.

**Source:** `../../STATE.md §2` standing directives `[USER]`; context export §4.8, §13.
