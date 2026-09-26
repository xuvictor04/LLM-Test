"""Time TOK.tokenize and TOK.splice over a ~17 MB tail (03b S0b secondary (3)). Read-only on the tree."""
import json, os, sys, time
sys.path.insert(0, "/home/user/LLM-Test/src")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import torch; torch.set_num_threads(1)
from spine import compose
import tok.api as T
nb = int(sys.argv[1]); src = sys.argv[2]
env = {"RUN_DEVICE": "cpu", "DATA_STREAM_BYTES": str(nb), "DATA_SOURCE": src,
       "DATA_DIR": "/home/user/LLM-Test/data"}
t0 = time.time(); sysm = compose.compose(environ=env); t_comp = time.time() - t0
tokc = sysm.configs["TOK"]; vocab = sysm.vocab; seg = sysm.segmentation
data, labels = sysm.stream.bytes, sysm.stream.labels
t0 = time.time(); s2 = T.splice(tokc, vocab, seg, data, labels, at=0, regularize=True); t_splice = time.time() - t0
mid = len(seg.ids) // 2
t0 = time.time(); s3 = T.splice(tokc, vocab, seg, data, labels, at=mid, regularize=True); t_half = time.time() - t0
t0 = time.time(); s4 = T.tokenize(tokc, vocab, data, labels, regularize=False, view=T.view_of(vocab)); t_tok = time.time() - t0
print(json.dumps({"stream_bytes": len(data), "ids": len(seg.ids), "vocab": int(vocab.size()),
                  "bpt": float(seg.bytes_per_token), "compose_s": round(t_comp, 1),
                  "splice_full_tail_s": round(t_splice, 2), "splice_half_tail_s": round(t_half, 2),
                  "tokenize_view_s": round(t_tok, 2)}))
