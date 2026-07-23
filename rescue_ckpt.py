# rescue_ckpt.py -- pull a FULL promptable checkpoint out of an ALREADY-RUNNING self_organize.py
# process that predates mid-run checkpointing. Injected with pyrasite; runs INSIDE the live process:
#
#     pip install pyrasite
#     echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope     # allow attach (needs root; skip if already 0)
#     pyrasite <pid> rescue_ckpt.py                            # <pid> from: pgrep -f self_organize.py
#     cat ~/rescue_status.txt                                  # <-- durable result (stdout from injection is unreliable)
#
# It walks the running thread stack to find main()'s frame (where model/mem/enc live as LOCALS), rebuilds the
# exact save dict self_organize.py writes, and logs every step to ~/rescue_status.txt (a FILE, because print()
# from an injected thread is often buffered/lost). SAFE: fully wrapped -- a failure is logged and the training
# thread keeps running, so it is always safe to retry.
import os, sys, time, traceback

_LOG = os.path.expanduser("~/rescue_status.txt")


def _say(msg):                                                # durable + flushed; print() alone is unreliable here
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        with open(_LOG, "a") as f:
            f.write(line + "\n"); f.flush()
    except Exception:
        pass
    try:
        print("RESCUE:", msg, flush=True)
    except Exception:
        pass


def _rescue():
    _say("injection EXECUTED (pid %d, cwd %s, SAVE_CKPT=%r)" % (os.getpid(), os.getcwd(), os.environ.get("SAVE_CKPT")))
    import torch

    frame = None
    for fr in sys._current_frames().values():                 # find the training frame by its locals
        lv = fr.f_locals
        if "model" in lv and "mem" in lv and "enc" in lv:
            frame = fr
            break
    if frame is None:
        _say("NO training frame with model/mem/enc found -- still in setup, or names differ. ABORT.")
        return

    lv, gv = frame.f_locals, frame.f_globals
    def G(name, default=None):
        return lv[name] if name in lv else gv.get(name, default)
    def EI(k, d): return int(os.environ.get(k, d))
    def EF(k, d): return float(os.environ.get(k, d))

    model, mem, enc = G("model"), G("mem"), G("enc")
    TOK = G("TOK"); fab = G("fab")
    FABRIC = bool(G("FABRIC", 0)); SOCIETY = bool(G("SOCIETY", 0))
    USE_TOK = bool(G("USE_TOK", 1)); ONLINE = bool(G("ONLINE", 1))
    byte_stream = G("byte_stream")
    _say("found frame; step=%s mem.n=%s domains=%s fabric=%s" % (G("step"), getattr(mem, "n", "?"),
         (len(G("asm").cent) if G("asm") is not None else "?"), (len(fab.bodies) if (FABRIC and fab is not None) else 0)))

    ck = os.environ.get("SAVE_CKPT") or os.path.expanduser("~/rescue_run")   # absolute fallback so it's always findable
    os.makedirs(ck, exist_ok=True)
    tok_path = os.environ.get("TOKENIZER_PATH", "data/dyntok.json")
    if USE_TOK and TOK is not None:
        try: TOK.save(tok_path); _say("tokenizer saved -> %s" % tok_path)
        except Exception as e: _say("tokenizer save skipped: %r" % e)

    _say("serializing model+memory (GPU->CPU copy; the one step with real risk)...")
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
    torch.save(blob, os.path.join(ck, "ckpt.pt"))
    with open(os.path.join(ck, "source.bin"), "wb") as f:
        f.write(bytes(byte_stream) if (ONLINE and byte_stream is not None) else b"")
    _say("RESCUE OK -> %s/ckpt.pt | %d memory entries | prompt: python3 prompt.py CKPT=%s" % (ck, int(act.sum()), ck))


try:
    _rescue()
except Exception as e:
    _say("RESCUE FAILED (training thread unaffected -- safe to retry): %r\n%s" % (e, traceback.format_exc()))
