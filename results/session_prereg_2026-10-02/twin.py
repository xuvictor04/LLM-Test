"""Why register §8 5.3a's nuisance twin is P at OPT_LR x 1.0001 and not FAB_BIRTH_JITTER 0.1501 (read-only, from the two
committed retok archives). FAB reads FAB_BIRTH_JITTER only at a growth birth (src/fabric/api.py, grow_check), never at
a spawn (_spawn_check decodes the router's query), and the GPU fleets' reruns are bit-exact, so a jitter twin parts from
P at its first growth birth. This counts each k1000 run's births by path over its whole epoch, at FAB_COOLDOWN 400 as
the sessions run: fab.spawned against fab.replicated (every growth birth: grown_regression + grown_stall, replicate
on), and the growth births per 1,000 windows -- at that rate, the windows a 5,000-window session waits for its first
one, and the chance it has none.

    python3 twin.py                            # twin.out

Run it in place, by its path, from any directory (it reads ../gpu_retok_2026-09-2{7,8}/*.tgz)."""
import math
import os
import re
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.dirname(HERE)
rates = []
for day in ("2026-09-27", "2026-09-28"):
    with tarfile.open(os.path.join(R, f"gpu_retok_{day}", f"gpu_retok_{day}.tgz")) as tf:
        names = sorted(n for n in tf.getnames() if re.search(r"/logs/k1000\.s\d+\.log$", n))
        pb = [n for n in tf.getnames() if n.endswith("/PASTE_BACK.txt")]
        rr = re.search(r"^k0_rerun: .*$", tf.extractfile(pb[0]).read().decode(), re.M) if pb else None
        print(f"{day}: {rr.group(0) if rr else 'no rerun line'}")
        for n in names:
            t = tf.extractfile(n).read().decode(errors="replace")
            c = {k: int(v) for k, v in re.findall(r"^\s+fab\.(spawned|replicated|grown_regression|grown_stall)\s+(\d+)\s*$",
                                                   t, re.M)}
            w = int(re.search(r"^=== (\d+) windows", t, re.M).group(1))
            g = c.get("replicated", 0)
            rates.append(1000 * g / w)
            print(f"  {os.path.basename(n)[:-4]:<16} {w:>6} windows: spawned {c.get('spawned', 0):>5}, growth births {g:>3} "
                  f"(regression {c.get('grown_regression', 0)}, stall {c.get('grown_stall', 0)}): "
                  f"{100 * g / max(1, g + c.get('spawned', 0)):.2f}% of births, {1000 * g / w:.2f} per 1,000 windows")
lo, hi = min(rates), max(rates)
print(f"growth births per 1,000 windows: {lo:.2f}-{hi:.2f}; at that rate (Poisson) a 5,000-window session's first one "
      f"comes after {1000 / hi:,.0f}-{1000 / lo:,.0f} windows on average, and a session has none with chance "
      f"{math.exp(-5 * hi):.1%}-{math.exp(-5 * lo):.1%}")
