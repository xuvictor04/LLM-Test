import sys, time, torch; torch.set_num_threads(1)
sys.path.insert(0, "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm/design-world/proto")
import synth as S
G = S.grammar(1234)
t = time.time()
tr = S.make_set(4000, 1, G, keep=lambda p: not S.heldout_combo(p))
ho = S.make_set(400, 2, G, keep=lambda p: not S.heldout_combo(p))
hc = S.make_set(200, 3, G, keep=S.heldout_combo)
el = time.time() - t
torch.save({"G": G, "train": tr, "hold": ho, "combo": hc}, "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm/design-world/proto/data.pt")
print("gen s", round(el, 1), "clips", 4600, "sec/clip-of-2.56s", el / 4600, tr[1].shape, tr[1].mean().item(), tr[1].std().item())
print([S.caption(p) for p in tr[0][:5]])
