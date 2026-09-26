import sys
sys.path.insert(0, "/home/user/LLM-Test/src")
from spine import derive
names = ["eng","py","num","c"]
sch = derive.phase_schedule(4, 4, None)
print("schedule", sch)
for total in (20_000_000, 120000):
    P = len(sch)
    b = [(round(k*total/P), round((k+1)*total/P)) for k in range(P)]
    print(total, b)
for bpw in (189, 189*1.068, 202):
    print("bpw", bpw, "20k windows ->", 20000*bpw, "bytes; phase1 end 5e6; windows to leave phase 1:", 5_000_000/bpw)
# with act at 3000 raising bpw by 6.8%
print("mixed k3000:", 3000*189 + 17000*189*1.068)
print("areas live in phase1:", [names[i] for i in sch[0]])
