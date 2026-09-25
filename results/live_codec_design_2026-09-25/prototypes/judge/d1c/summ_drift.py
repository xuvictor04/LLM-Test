import json, sys
for f in sys.argv[1:]:
    try: r = json.load(open(f))
    except Exception as e: print(f, e); continue
    for k, v in r.items():
        t = v["traj"]
        pA2 = [d["flipA_per_50"] for d in t if d["step"] <= 200]; pA3 = [d["flipA_per_50"] for d in t if d["step"] > 200]
        pB3 = [d["flipB_per_50"] for d in t if d["step"] > 200]
        print(f"{k:42s} A/50 P2 {sum(pA2)/len(pA2):.3f} P3 {sum(pA3)/len(pA3):.3f} | B/50 P3 {sum(pB3)/len(pB3):.3f} | A vs start {t[-1]['flipA_vs_start']:.3f} B {t[-1]['flipB_vs_start']:.3f} | "
              f"mel A {v['start']['A']['mel']}->{v['after_A']['A']['mel']}->{v['after_B']['A']['mel']}  B {v['start']['B']['mel']}->{v['after_B']['B']['mel']} | recx A {v['start']['A']['recx']}->{v['after_B']['A']['recx']} B {v['start']['B']['recx']}->{v['after_B']['B']['recx']}")
