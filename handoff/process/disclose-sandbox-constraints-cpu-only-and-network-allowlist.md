# Disclose the sandbox constraints — don't hide them

The assistant's build environment is: CPU-only (no GPU, ever); individual tool calls limited to a few minutes; network
allowlisted to GitHub / PyPI / npm / crates / Ubuntu mirrors only — **NOT** HuggingFace, S3/Common Crawl, or Wikimedia.
This is why `fetch_data.sh` (GitHub) is fully verifiable here but `fetch_big.py` (HuggingFace) is not. All real training,
large downloads, and long runs are the user's to execute on their H100. Disclose these rather than working around them silently.

**Source:** context export §13; `../../STATE.md §2`.
