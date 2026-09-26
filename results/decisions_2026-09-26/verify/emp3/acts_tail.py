import sys, os
sys.path.insert(0, "/home/user/LLM-Test/src")
seed, every, NB = sys.argv[1], sys.argv[2], sys.argv[3]
env = dict(os.environ); env.update({"DATA_STREAM_BYTES": NB, "RUN_SEED": seed, "RUN_DEVICE": "cpu", "TOK_RETOK_EVERY": every})
from spine import compose as C, units as U
from tok import api as T
s = C.compose(env); tok, vocab, seg = s.configs["TOK"], s.vocab, s.segmentation; ctx = int(s.configs["LM"].ctx)
E0 = (len(seg.ids) - 1) // ctx; w = 0; base_bpw = seg.byte_pos[E0 * ctx] / E0
print(f"seed {seed} every {every} bytes {NB}: epoch {E0} windows, {base_bpw:.2f} B/window at build")
while w < (len(seg.ids) - 1) // ctx:
    step = w + 1
    due = T.on_window(tok, vocab, seg.ids[w * ctx:(w + 1) * ctx], step=U.Windows(step))
    if due.mint: T.mint_burst(tok, vocab, step=U.Windows(step))
    if due.retok:
        k0 = step * ctx; before = len(seg.ids) - k0
        seg = T.splice(tok, vocab, seg, s.stream.bytes, s.stream.labels, at=k0, regularize=True)
        after = len(seg.ids) - k0
        print(f"  act at {step}: vocab {vocab.size()} tail ids {before} -> {after}: whole-tail bytes/token {before/after-1:+.2%}; epoch now {(len(seg.ids)-1)//ctx} windows")
    w += 1
W = (len(seg.ids) - 1) // ctx
print(f"  run average bytes/window {seg.byte_pos[W*ctx]/W:.2f} vs build {base_bpw:.2f}: {seg.byte_pos[W*ctx]/W/base_bpw-1:+.2%}")
