import os, sys, math, random
os.environ["OMP_NUM_THREADS"]="1"; os.environ["MKL_NUM_THREADS"]="1"
sys.path.insert(0, sys.argv[1] + "/src")
import torch; torch.set_num_threads(1)
from spine import assemble, rng, derive
from data import api as data_api
from tok import api as tok_api
cfgs, wires, warns = assemble.build(environ={"DATA_STREAM_BYTES": "120000"})
dat, tok, lm = cfgs["DATA"], cfgs["TOK"], cfgs["LM"]
areas = data_api.open_areas(dat, seed=0)
text = dict(areas.bodies)
n = len(next(iter(text.values())))
r = random.Random(0)
# "codec" bytes: (a) uniform 256-code VQ stream serialized one byte per code
codec_uniform = bytes(r.randrange(256) for _ in range(n))
# (b) 8-bit mu-law-ish quantized sine sweep: smooth, highly repetitive
codec_sine = bytes(int(127.5 + 127 * math.sin(0.02 * i + 0.00001 * i * i)) & 0xFF for i in range(n))
def run(label, heads):
    rng.reset_issued()
    v = tok_api.build_vocabulary(tok, area_heads=heads, seed=0, soft_cap=None)
    # how many minted tokens contain a byte outside the 5 text alphabets (i.e. were minted from codec material)
    textbytes = set(b"".join(text.values()))
    minted = v.id2bytes[256:]
    codec_mints = sum(1 for s in minted if any(b not in textbytes for b in s))
    # measure bpt on text only, with this vocabulary
    seg = tok_api.tokenize(tok, v, b"".join(text.values())[:60000])
    w = derive.signature_width_bytes(int(lm.ctx), float(v.bytes_per_token))
    print(f"{label:28s} size={v.size():4d} build_bpt={v.bytes_per_token:.3f} text_bpt={seg.bytes_per_token:.3f} "
          f"sig_width={w} minted={len(minted)} minted_from_codec={codec_mints}")
run("text only", text)
run("text + uniform codec", {**text, "aud": codec_uniform})
run("text + sine codec", {**text, "aud": codec_sine})
