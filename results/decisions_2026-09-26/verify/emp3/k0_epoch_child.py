# What horizon does a child get when it continues a FINISHED no-act (k0) parent for one more epoch?
# compose re-tokenizes the resumed epoch with the RESTORED (grown) vocabulary (spine/compose.py:2408-2413,
# :2476-2478) and OPT.build prices it at RUN.epochs x windows_in_epoch (compose.py:3122-3123), then
# OPT.load_state takes the horizon-changed branch (opt/api.py:2874-2905). Model-free: replays TOK's
# per-window tally and mint bursts (spine/loop.py:1110, :2355) over the whole parent epoch, then re-tokenizes.
import sys, os, time
sys.path.insert(0, "/home/user/LLM-Test/src")
seed = sys.argv[1]; NB = sys.argv[2] if len(sys.argv) > 2 else "20000000"
env = dict(os.environ)
env.update({"DATA_STREAM_BYTES": NB, "RUN_SEED": seed, "RUN_DEVICE": "cpu", "TOK_RETOK_EVERY": "0"})
from spine import compose as C, units as U
from tok import api as T
t0 = time.time()
s = C.compose(env)
tok, vocab, seg = s.configs["TOK"], s.vocab, s.segmentation
ctx = int(s.configs["LM"].ctx)
E = (len(seg.ids) - 1) // ctx
print(f"seed {seed} bytes {NB}: parent epoch {E} windows, vocab {vocab.size()} (compose {time.time()-t0:.0f}s)", flush=True)
for w in range(E):
    step = w + 1
    due = T.on_window(tok, vocab, seg.ids[w * ctx:(w + 1) * ctx], step=U.Windows(step))
    if due.mint:
        T.mint_burst(tok, vocab, step=U.Windows(step))
    if step % 20000 == 0:
        print(f"  window {step}: vocab {vocab.size()} t={time.time()-t0:.0f}s", flush=True)
print(f"  parent end: vocab {vocab.size()} t={time.time()-t0:.0f}s", flush=True)
seg1 = T.tokenize(tok, vocab, s.stream.bytes, s.stream.labels, regularize=True, seed=int(seed))
W1 = (len(seg1.ids) - 1) // ctx
print(f"  child epoch re-tokenized with the parent's final vocab: {W1} windows ({W1/E:.3f} of the parent's); t={time.time()-t0:.0f}s", flush=True)
import torch
from opt import api as O
opt = s.configs["OPT"]; PEAK = float(opt.lr)
def new(rw):
    g = {"base": [torch.nn.Parameter(torch.zeros(3, 3))], "encoder": [torch.nn.Parameter(torch.zeros(3))]}
    return O.build(opt, param_groups=g, run_windows=U.Windows(int(rw)))
p = new(E); p.opt_step = U.Steps(E)
for label, horizon in (("equal-length child 2E", 2 * E), ("actual child 2*W1", 2 * W1)):
    c = new(horizon); O.load_state(opt, c, O.state_dict(opt, p))
    print(f"  {label:24s} horizon {horizon}: child first step at {O.lr_at(opt, c, U.Steps(E + 1)) / PEAK:.4f} of peak")
