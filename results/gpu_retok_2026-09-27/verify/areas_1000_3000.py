"""k1000 - k3000 per area over the whole run (byte-share split), per seed. python3 areas_1000_3000.py <gpu_retok_out>"""
import sys, runpy
sys.argv = [sys.argv[0], sys.argv[1]]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path("areas_check.py", run_name="areas_check")
V, NAMES = g["V"], g["NAMES"]
for a in range(4):
    d = []
    for s in range(3):
        def w(arm):
            Ab, Ay = V[(arm, s)][0], V[(arm, s)][1]
            return sum(Ab[p * 4 + a] for p in range(4)) / sum(Ay[p * 4 + a] for p in range(4))
        d.append(w("k1000") - w("k3000"))
    print(f"  {NAMES[a]:4} k1000 - k3000 whole run: mean {sum(d) / 3:+.4f}  per seed {' '.join(f'{x:+.4f}' for x in d)}")
