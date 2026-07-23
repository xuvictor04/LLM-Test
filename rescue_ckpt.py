# rescue_ckpt.py -- pull a FULL promptable checkpoint out of an ALREADY-RUNNING self_organize.py
# process that predates mid-run checkpointing. Injected with pyrasite; runs INSIDE the live process:
#
#     pip install pyrasite
#     echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope     # allow attach (needs root; skip if already 0)
#     pyrasite <pid> rescue_ckpt.py                            # <pid> is printed by newer runs; else: nvidia-smi / ps
#
# It walks the running thread stack to find main()'s frame (where model/mem/enc live as LOCALS), then
# rebuilds the exact save dict self_organize.py writes at the end -- so prompt.py can load it normally.
# SAFE: everything is wrapped; a failure prints a traceback and the training thread keeps going untouched.
import sys, os, torch


def _rescue():
    frame = None
    for fr in sys._current_frames().values():                 # find the training frame by its locals
        lv = fr.f_locals
        if "model" in lv and "mem" in lv and "enc" in lv:
            frame = fr
            break
    if frame is None:
        print("RESCUE: no frame with model/mem/enc found -- is the run past setup and in the training loop?")
        return

    lv, gv = frame.f_locals, frame.f_globals
    def G(name, default=None):                                # look in locals, then module globals
        return lv[name] if name in lv else gv.get(name, default)
    def EI(k, d): return int(os.environ.get(k, d))
    def EF(k, d): return float(os.environ.get(k, d))

    model, mem, enc = G("model"), G("mem"), G("enc")
    TOK = G("TOK"); fab = G("fab")
    FABRIC = bool(G("FABRIC", 0)); SOCIETY = bool(G("SOCIETY", 0))
    USE_TOK = bool(G("USE_TOK", 1)); ONLINE = bool(G("ONLINE", 1))
    byte_stream = G("byte_stream")

    ck = os.environ.get("SAVE_CKPT") or "runs/rescue"         # same target the run would have used
    os.makedirs(ck, exist_ok=True)
    tok_path = os.environ.get("TOKENIZER_PATH", "data/dyntok.json")
    if USE_TOK and TOK is not None:
        try: TOK.save(tok_path)
        except Exception as e: print("RESCUE: tokenizer save skipped:", e)

    act = mem.active
    blob = {"model": model.state_dict(), "D": G("D"), "V": G("V"), "KW": G("KW"), "KEY_SRC": G("KEY_SRC"),
            "model_type": G("MODEL_TYPE"), "layers": EI("LAYERS", 1), "heads": EI("HEADS", 8), "maxlen": EI("MAXLEN", 512),
            "use_tok": USE_TOK, "tok_path": (tok_path if USE_TOK else None),
            "mem_keys": mem.keys[act].cpu(), "mem_tok": mem.tok[act].cpu(), "mem_src": mem.src[act].cpu(),
            "mem_ctx": (mem.ctx[act].cpu() if mem.ctx_w > 0 else None), "topk": mem.topk,
            "mem_pos": mem.pos[act].cpu(), "sig_d": G("SIG_D"), "win": G("WIN"), "enc": enc.state_dict(),
            "fab": (fab.state_dict() if FABRIC and fab is not None else None),
            "fab_cfg": ({"n": len(fab.bodies), "dk": EI("FAB_DK", 32), "alpha": EF("FAB_ALPHA", 0.5),
                         "max_steps": EI("FAB_STEPS", 4), "hid_mult": EI("FAB_HID_MULT", 2),
                         "min_steps": EI("FAB_MIN_STEPS", 0), "norm_only": bool(EI("FAB_NORM_ONLY", 0)),
                         "society": SOCIETY} if FABRIC and fab is not None else None)}
    torch.save(blob, f"{ck}/ckpt.pt")
    with open(f"{ck}/source.bin", "wb") as f:                 # corpus text retrieval points into (best-effort)
        f.write(bytes(byte_stream) if (ONLINE and byte_stream is not None) else b"")
    print(f"RESCUE OK -> {ck}/ckpt.pt | {int(act.sum())} memory entries | prompt: python3 prompt.py CKPT={ck}")


try:
    _rescue()
except Exception as e:
    import traceback; traceback.print_exc()
    print("RESCUE FAILED (training thread is unaffected -- safe to retry):", e)
