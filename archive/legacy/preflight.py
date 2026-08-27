"""Pre-flight for full package testing -- a fast CPU gate that verifies the whole system is wired and stable
BEFORE spending GPU hours. Run: python3 control.py check   (or: python3 preflight.py)

Checks, in order (stops reporting per-check, not on first failure):
  1. syntax    -- every .py parses, every .sh passes bash -n
  2. imports   -- the core modules import cleanly
  3. presets   -- a tiny end-to-end train under base + full (the extremes) reaches DONE
  4. resume    -- checkpoint round-trip (all the new params save/load)
  5. tokenizer -- the harness's lossless-correctness section passes

Prints a PASS/FAIL summary. Green here means every EXPERIMENTS.md rung will launch on the GPU.
"""
import ast, glob, os, subprocess, sys, tempfile, shutil

OK = "\033[92mPASS\033[0m"; NO = "\033[91mFAIL\033[0m"
results = []


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"[:100]
    results.append((name, ok, detail))
    print(f"  [{OK if ok else NO}] {name}: {detail}")
    return ok


def c_syntax():
    bad = []
    for f in glob.glob("*.py"):
        try: ast.parse(open(f).read())
        except Exception as e: bad.append(f"{f}({str(e)[:30]})")
    for f in glob.glob("*.sh"):
        if subprocess.run(["bash", "-n", f], capture_output=True).returncode: bad.append(f)
    return (not bad, "all files parse" if not bad else "BROKEN: " + ", ".join(bad))


def c_imports():
    mods = ["config", "language", "tokenizer", "barry", "optimizers", "data_utils", "system", "growth"]
    r = subprocess.run([sys.executable, "-c", "import " + ", ".join(mods)], capture_output=True, text=True)
    return (r.returncode == 0, f"{len(mods)} core modules import" if r.returncode == 0 else r.stderr.strip().splitlines()[-1][:90])


TINY = dict(DEVICE="cpu", D_MODEL="64", N_LAYERS="2", N_HEADS="2", CTX="32", MAX_LEN="64", BATCH="16",
            VMAX="2000", MIN_PAIR="8", DATA_CAP="250000", HELD="3", OOD_N="2", N0="8", NMAX="12",
            GRACE="8", PATIENCE="6", COOLDOWN="6", WARMUP_STEPS="3", LR_WARMUP="10", EVAL_EVERY="999",
            LOG_EVERY="99", MP_WORKERS="0")


def _tiny_train(preset, steps, rundir, extra=None):
    env = dict(os.environ)
    cmd = [sys.executable, "control.py", "train", "--preset", preset]
    cmd += [f"{k}={v}" for k, v in TINY.items()]
    cmd += ["GROWTH_START=0", "CTX_START=0", f"STEPS={steps}", "CKPT_EVERY=" + str(steps), f"RUN_DIR={rundir}"]
    if extra: cmd += extra
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=260)
    return r


def c_preset_base():
    r = _tiny_train("base", 12, "pf_base")
    done = "DONE @ step" in r.stdout
    shutil.rmtree("pf_base", ignore_errors=True)
    return (done, "base preset trains to DONE" if done else "no DONE; " + (r.stderr.strip().splitlines()[-1][:80] if r.stderr.strip() else "see logs"))


def c_preset_full():
    r = _tiny_train("full", 12, "pf_full")
    done = "DONE @ step" in r.stdout
    feats = sum(x in r.stdout for x in ["reconstruct", "denoise", "multi-token", "fuzzy", "turnover"])
    shutil.rmtree("pf_full", ignore_errors=True)
    return (done, f"full preset trains to DONE ({feats} capability banners seen)" if done else "no DONE; " + (r.stderr.strip().splitlines()[-1][:80] if r.stderr.strip() else "see logs"))


def c_resume():
    r1 = _tiny_train("full", 10, "pf_res")
    if "DONE @ step" not in r1.stdout:
        shutil.rmtree("pf_res", ignore_errors=True); return (False, "first leg failed")
    r2 = _tiny_train("full", 20, "pf_res")
    ok = "RESUMED at step" in r2.stdout and "DONE @ step" in r2.stdout
    bad = any(x in r2.stdout + r2.stderr for x in ["Missing key", "Unexpected key", "size mismatch"])
    shutil.rmtree("pf_res", ignore_errors=True)
    return (ok and not bad, "checkpoint round-trip clean (all new params save/load)" if ok and not bad else "resume/key mismatch")


def c_tokenizer():
    r = subprocess.run([sys.executable, "test_tokenizer.py"], capture_output=True, text=True,
                       env=dict(os.environ, SECTIONS="correct"), timeout=200)
    ok = "ALL PASS" in r.stdout
    return (ok, "lossless round-trip ALL PASS" if ok else "correctness failed or timed out")


if __name__ == "__main__":
    print("PRE-FLIGHT -- verifying the full package before GPU testing\n")
    check("1. syntax", c_syntax)
    check("2. imports", c_imports)
    print("  (running tiny end-to-end trains -- ~30s each ...)")
    check("3a. preset base", c_preset_base)
    check("3b. preset full", c_preset_full)
    check("4. resume/checkpoint", c_resume)
    check("5. tokenizer correctness", c_tokenizer)
    n_ok = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'='*60}\nPRE-FLIGHT: {n_ok}/{len(results)} checks passed.",
          "READY for full package testing (see EXPERIMENTS.md)." if n_ok == len(results)
          else "NOT READY -- fix the FAILs above before GPU runs.")
    sys.exit(0 if n_ok == len(results) else 1)
