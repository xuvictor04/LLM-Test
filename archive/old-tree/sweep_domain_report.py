"""Parser/summarizer for sweep_domain_grid.sh. Pure stdlib -- no numpy (the box may not have it).

  python3 sweep_domain_report.py <OUTDIR>            -> SUMMARY.md on stdout
  python3 sweep_domain_report.py <OUTDIR> --pick     -> "ENC_POS_MAX=.. ENC_WARMUP=.. NEW_DIST=.. SHIFT_DIST=.."
                                                        for the best Stage-B cell (used to seed stages C/D/E)

Every number here is scraped from a line self_organize.py already prints, except the two
[sweep-audit*] lines, which the sweep's patched COPY adds (print-only, no behaviour change).
"""
import glob, os, re, sys

NP_TRUE = 4                       # eng,py,num,c
GATE_COMP, GATE_V, GATE_REC = 0.80, 0.85, 0.85          # K3 / K4

R_CELL = re.compile(r"\[sweep-cell\] name=(\S+) rc=(\d+) wall_s=(\d+) jobs=(\d+) env=(.*)")
R_AUD = re.compile(r"\[sweep-audit\] (.*)")
R_RES = re.compile(r"\[sweep-audit-resolved\] (.*)")
R_BND = re.compile(r"boundary detection: (\d+) found for (\d+) true switches \| "
                   r"precision ([\d.]+) recall ([\d.]+)")
R_CLU = re.compile(r"clustering purity: ([\d.]+) \| homogeneity: ([\d.]+) \| "
                   r"completeness: ([\d.]+) \| V-measure: ([\d.]+)")
R_MEM = re.compile(r"memory contributes ([+-][\d.]+)")
R_RATE = re.compile(r"\[rate @ (\d+)\] (\d+) steps/min.*?(\d+) domains / (\d+) boundaries")
R_LIVE = re.compile(r"SELF-ASSEMBLED (\d+) LIVE domains")
R_NPT = re.compile(r"for (\d+) true processes")


def kv(s):
    out = {}
    for tok in s.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            try:
                out[k] = int(v)
            except ValueError:
                try:
                    out[k] = float(v)
                except ValueError:
                    out[k] = v
    return out


def parse(path):
    txt = open(path, errors="replace").read()
    c = {"name": os.path.basename(path)[:-4], "rc": None, "wall": None, "jobs": None, "env": ""}
    m = R_CELL.search(txt)
    if m:
        c.update(name=m.group(1), rc=int(m.group(2)), wall=int(m.group(3)),
                 jobs=int(m.group(4)), env=m.group(5).strip())
    m = R_AUD.search(txt)
    c["audit"] = kv(m.group(1)) if m else {}
    m = R_RES.search(txt)
    c["res"] = kv(m.group(1)) if m else {}
    m = R_BND.search(txt)
    if m:
        c["bnd_found"], c["bnd_true"] = int(m.group(1)), int(m.group(2))
        c["prec"], c["rec"] = float(m.group(3)), float(m.group(4))
    m = R_CLU.search(txt)
    if m:
        c["pur"], c["hom"], c["comp"], c["V"] = [float(g) for g in m.groups()]
    m = R_MEM.search(txt)
    c["mem"] = float(m.group(1)) if m else None
    rates = R_RATE.findall(txt)
    c["rate"] = int(rates[-1][1]) if rates else None
    c["traj"] = [(int(a), int(cc)) for a, b, cc, d in rates]           # (step, live domains)
    m = R_LIVE.search(txt)
    c["live"] = int(m.group(1)) if m else c["audit"].get("live")
    m = R_NPT.search(txt)
    if m:
        global NP_TRUE
        NP_TRUE = int(m.group(1))                     # true class count, read from the run itself
    # growth rate over the last third of the trajectory: a converged population has dN/dstep -> 0
    t = c["traj"]
    c["dNdstep"] = None
    if len(t) >= 4:
        t = t[len(t) * 2 // 3:] or t[-2:]
        n = len(t)
        mx = sum(p[0] for p in t) / n
        my = sum(p[1] for p in t) / n
        den = sum((p[0] - mx) ** 2 for p in t)
        if den > 0:
            c["dNdstep"] = sum((p[0] - mx) * (p[1] - my) for p in t) / den
    c["ok"] = (c["rc"] == 0) and bool(c["audit"]) and ("V" in c)
    c["void"] = bool(c["audit"].get("capped", 0))
    return c


def load(out):
    cells = {}
    for p in sorted(glob.glob(os.path.join(out, "cells", "*.log"))):
        c = parse(p)
        c["name"] = os.path.basename(p)[:-4]      # the FILE is the identity, not the echoed name
        cells[c["name"]] = c
    return cells


def f(v, spec="{:.2f}", dash="-"):
    if v is None:
        return dash
    try:
        if spec.endswith("d}"):
            v = int(v)
        return spec.format(v)
    except (ValueError, TypeError):
        return str(v)


def row(c):
    a, r = c["audit"], c["res"]
    return "| {n} | {live} | {cap} | {pur} | {hom} | {comp} | {V} | {Vr} | {p}/{rc} | {bf}/{bt} | {mem} | {sm} | {w} |".format(
        n=c["name"], live=f(c.get("live"), "{:d}"), cap=f(a.get("capped"), "{:d}"),
        pur=f(c.get("pur")), hom=f(c.get("hom")), comp=f(c.get("comp")), V=f(c.get("V")),
        Vr=f(r.get("vmeasure")), p=f(c.get("prec")), rc=f(c.get("rec")),
        bf=f(c.get("bnd_found"), "{:d}"), bt=f(c.get("bnd_true"), "{:d}"),
        mem=f(c.get("mem"), "{:+.3f}"), sm=f(c.get("rate"), "{:d}"), w=f(c.get("wall"), "{:d}"))


HDR = ("| cell | live | capped | purity | homog | **compl** | **V** | V(res) | bnd P/R | "
       "found/true | mem Δb/B | steps/min | wall s |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def diag_row(c):
    a, r = c["audit"], c["res"]
    return "| {n} | {cr}/{mg}/{cu} | {crw}/{crs} | {mw} | {lg} | {dn} | {cr2} | {rc} |".format(
        n=c["name"], cr=f(a.get("created"), "{:d}"), mg=f(a.get("merged"), "{:d}"),
        cu=f(a.get("culled"), "{:d}"), crw=f(a.get("clusters_raw"), "{:d}"),
        crs=f(a.get("clusters_resolved"), "{:d}"), mw=f(a.get("median_wins"), "{:d}"),
        lg=f(a.get("largest"), "{:d}"), dn=f(c.get("dNdstep"), "{:.4f}"),
        cr2=f(r.get("completeness")), rc=("ok" if c["rc"] == 0 else "rc=%s" % c["rc"]))


DHDR = ("| cell | created/merged/culled | clusters raw/resolved | median wins/dom | largest | "
        "dN/dstep | compl(res) | run |\n|---|---|---|---|---|---|---|---|")


def pick(cells, prefixes=("B_",)):
    cand = [c for c in cells.values()
            if c["name"].startswith(prefixes) and c["ok"] and not c["void"]]
    gated = [c for c in cand if (c.get("rec") or 0) >= GATE_REC]
    pool = gated or cand
    if not pool:
        return None, "no Stage-B cell parsed"
    def key(c):
        v = c["res"].get("vmeasure", c.get("V", 0.0))
        return (v, -abs((c.get("live") or 999) - NP_TRUE))
    best = max(pool, key=key)
    why = "" if gated else ("  (WARNING: no cell met boundary recall >= %.2f -- the winner is the "
                            "best of a field that may have won by not detecting boundaries)" % GATE_REC)
    return best, why


def env_of(c):
    """The four threshold/encoder knobs only -- this string is CARRIED into later stages, which set
    the rule knobs themselves, so it must not pin them."""
    a = c["audit"]
    return "ENC_POS_MAX={} ENC_WARMUP={} NEW_DIST={} SHIFT_DIST={}".format(
        a.get("enc_pos_max", 256), a.get("enc_warmup", 800),
        a.get("new_dist", 0.35), a.get("shift_dist", 0.30))


def full_env_of(c):
    """Everything needed to reproduce the cell, including any rule variant it had switched on."""
    a = c["audit"]
    out = [env_of(c)]
    if a.get("dom_relative"):
        out.append("DOM_RELATIVE=1 DOM_MARGIN=%s" % a.get("dom_margin", 0.75))
    if a.get("shift_rel"):
        out.append("SHIFT_REL=1 SHIFT_Q=%s SHIFT_MULT=%s"
                   % (a.get("shift_q", 0.5), a.get("shift_mult", 1.5)))
    if a.get("dom_adaptive"):
        out.append("DOM_ADAPTIVE=1 DOM_SPAWN_K=%s" % a.get("dom_spawn_k", 3.0))
    if a.get("sig_mode") and a["sig_mode"] != "learned":
        out.append("SIG_MODE=%s" % a["sig_mode"])
    return " ".join(out)


def verdicts(cells, best):
    L = []
    caps = [cells.get("A_cap8"), cells.get("A_cap64"), cells.get("A_cap4096")]
    if all(c and c["ok"] for c in caps):
        v = [c["live"] for c in caps]
        moved = max(v) - min(v) > 1
        c64 = cells["A_cap64"]["audit"].get("capped", 0)
        L.append("**K1 cap invariance** — MAX_DOMAINS 8/64/4096 gave live = %d / %d / %d, capped@64 = %d. "
                 "→ %s" % (v[0], v[1], v[2], c64,
                           "THE CAP IS THE MECHANISM: the population is cap-limited, and every conclusion drawn "
                           "from a domain count at a binding cap is void." if moved else
                           "**THE CAP IS NOT THE MECHANISM.** The count is set by creation minus merge; "
                           "'the number went down' is not evidence for anything on its own."))
    else:
        L.append("**K1 cap invariance** — Stage A incomplete (run STAGES=A).")

    voids = [c["name"] for c in cells.values() if c["ok"] and c["void"]]
    L.append("**K2 capped==0** — %s" % ("all cells clean." if not voids else
             "VOID (cap bound, results uninterpretable): " + ", ".join(sorted(voids))))

    if best:
        r = best["res"]
        comp = r.get("completeness", best.get("comp", 0))
        V = r.get("vmeasure", best.get("V", 0))
        rec = best.get("rec", 0)
        passed = comp >= GATE_COMP and V >= GATE_V and NP_TRUE <= (best.get("live") or 0) <= 2 * NP_TRUE
        L.append("**K3 success gate** — best cell `%s` (%s): completeness %.2f (need ≥%.2f), V %.2f "
                 "(need ≥%.2f), live %s (need %d-%d) → %s"
                 % (best["name"], env_of(best), comp, GATE_COMP, V, GATE_V,
                    best.get("live"), NP_TRUE, 2 * NP_TRUE, "PASS" if passed else "FAIL"))
        L.append("**K4 boundary recall** — %.2f (need ≥%.2f), %s boundaries found for %s true switches → %s"
                 % (rec, GATE_REC, best.get("bnd_found"), best.get("bnd_true"),
                    "PASS" if rec >= GATE_REC else
                    "FAIL — this cell reached its domain count by NOT DETECTING boundaries, which is a dead "
                    "detector, not convergence."))

    dcells = [cells.get("D_len120000"), cells.get("D_len240000"), cells.get("D_len480000")]
    if all(c and c["ok"] for c in dcells):
        v = [c["live"] for c in dcells]
        flat = max(v) - min(v) <= 1
        L.append("**K5 extensivity** — live domains at 120k/240k/480k = %d / %d / %d → %s"
                 % (v[0], v[1], v[2],
                    "FLAT: the population is a fixed point, not a truncated ramp." if flat else
                    "SCALES WITH THE STREAM (%.2fx over 4x bytes): the population is extensive in bytes "
                    "consumed. NOTHING CONVERGED — the run just ended." % (v[2] / max(1, v[0]))))
    else:
        L.append("**K5 extensivity** — Stage D incomplete (run STAGES=D).")

    # K7: the incumbent is the shipped fixed-threshold config, V=0.42 at boundary recall 0.96.
    inc = cells.get("C_stock_all") or cells.get("A_cap64") or cells.get("smoke")
    if inc and inc["ok"] and best:
        iv = inc["res"].get("vmeasure", inc.get("V", 0))
        bv = best["res"].get("vmeasure", best.get("V", 0))
        L.append("**K7 beats the incumbent** — measured incumbent (`%s`) V %.2f at recall %.2f; best cell "
                 "V %.2f at recall %.2f → %s"
                 % (inc["name"], iv, inc.get("rec", 0), bv, best.get("rec", 0),
                    "improvement." if bv > iv else
                    "NO IMPROVEMENT. The reference point for this project is V=0.42 with recall 0.96 on "
                    "fixed thresholds; a variant that does not beat it is rejected regardless of how few "
                    "domains it produces."))

    bg = cells.get("C_bigram")
    if bg and bg["ok"] and best:
        bv = bg["res"].get("vmeasure", bg.get("V", 0))
        lv = best["res"].get("vmeasure", best.get("V", 0))
        L.append("**K6 bigram control** — untrained bigram V %.2f (live %d) vs best learned V %.2f (live %s) → %s"
                 % (bv, bg["live"], lv, best.get("live"),
                    "the learned encoder EARNS ITS KEEP." if lv > bv else
                    "**a 512-bin bigram histogram with no training beats the learned signature.** The binding "
                    "defect is the InfoNCE objective (positive radius < segment length), not the thresholds."))
    return L


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "sweep_out"
    cells = load(out)
    best, why = pick(cells)
    if "--pick" in sys.argv:
        if best:
            sys.stderr.write(why + "\n" if why else "")
            print(env_of(best))
        return

    winner, wwhy = pick(cells, ("B_", "R_"))          # overall winner may be a rule variant
    order = ["smoke"]
    for p in ("A_", "B_", "R_", "C_", "D_", "E_"):
        order += [n for n in sorted(cells) if n.startswith(p)]
    order = [n for n in order if n in cells]

    P = print
    P("# Domain-assembly sweep — results")
    P("")
    pf = os.path.join(out, "preflight.txt")
    if os.path.exists(pf):
        P("```")
        P(open(pf, errors="replace").read().strip())
        P("```")
    P("")
    P("## Verdicts against the pre-registered criteria")
    P("")
    for v in verdicts(cells, best):
        P("- " + v)
    P("")
    P("## Main table")
    P("")
    P("`compl` and `V` are the only admissible cluster scores (purity and homogeneity rise monotonically with")
    P("fragmentation). `V(res)` is V recomputed after resolving merge chains — the shipped V is computed on the")
    P("raw assign-time domain id, so it cannot see consolidation that happened by MERGE. `capped` must be 0 or")
    P("the row is void. `found/true` is the boundary count: a low `found` with few domains is a dead detector,")
    P("not convergence. `mem Δb/B` is `bits/byte(model alone) - bits/byte(model+memory)`, so POSITIVE means the")
    P("memory helped; the LM is identical in every cell, so the column is comparable across rows but is not a")
    P("headline number.")
    P("")
    P(HDR)
    for n in order:
        c = cells[n]
        P(row(c) + ("  <!-- VOID: cap bound -->" if c["void"] else ""))
    P("")
    P("## Diagnostics")
    P("")
    P("`dN/dstep` is the live-domain growth rate fitted over the last third of the run: a converged population")
    P("has it at ~0. `median wins/dom` below ~%d means each 'domain' is about one splice segment."
      % (120000 // (128 * NP_TRUE) // 2))
    P("")
    P(DHDR)
    for n in order:
        P(diag_row(cells[n]))
    P("")
    if winner:
        P("## Winner (across the grid AND the rule variants)")
        P("")
        P("`%s`%s" % (winner["name"], wwhy))
        P("")
        P("Reproduce it:")
        P("")
        P("```bash")
        P("DATA_MODE=real DATA_DIR=data DOMAINS=eng,py,num,c DEVICE=cuda \\")
        P("  MAX_DOMAINS=4096 MANAGE_MERGE=0 MERGE_FRAC=0.8 ENC_WARMUP_MIN=1000000000 \\")
        P("  %s \\" % full_env_of(winner))
        P("  python3 self_organize.py")
        P("```")
        if best and best["name"] != winner["name"]:
            P("")
            P("(Stage-B grid winner, which is what stages R/C/D/E were run at: `%s` → `%s`)"
              % (best["name"], env_of(best)))


if __name__ == "__main__":
    main()
