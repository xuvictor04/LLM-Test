# Count cells per row in every markdown table of DECISIONS.md (unescaped '|' only); report mismatches.
import re, sys
lines = open(sys.argv[1] if len(sys.argv) > 1 else 'DECISIONS.md').read().split('\n')
def ncells(s):
    s = s.strip()
    parts = re.split(r'(?<!\\)\|', s)
    return len(parts) - 2  # leading and trailing empty pieces
bad = 0; tables = 0; i = 0
while i < len(lines):
    if lines[i].lstrip().startswith('|'):
        start = i; rows = []
        while i < len(lines) and lines[i].lstrip().startswith('|'):
            rows.append((i + 1, lines[i])); i += 1
        tables += 1
        want = ncells(rows[0][1])
        for ln, r in rows:
            n = ncells(r)
            if n != want or not r.rstrip().endswith('|'):
                bad += 1; print(f"table at {start+1}: line {ln} has {n} cells, header {want}: {r[:90]}")
    else:
        i += 1
print(f"{tables} tables checked, {bad} bad rows")
