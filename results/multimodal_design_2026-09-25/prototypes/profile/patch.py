import re,sys
p=sys.argv[1]+"/src/spine/loop.py"
s=open(p).read()
def rep(old,new,count=1):
    global s
    assert s.count(old)>=1,(old[:80])
    s=s.replace(old,new,count)
# dom.manage span
rep('''            if cadences.due("dom.manage", periods["dom.manage"], clock):
                _c = mem_api.census''','''            if cadences.due("dom.manage", periods["dom.manage"], clock):
              with _timing.span("dom.manage"):
                _c = mem_api.census''')
# need to indent the rest of dom.manage block: lines until 'if cadences.due("fab.manage"'
i=s.index('with _timing.span("dom.manage"):')
j=s.index('            if cadences.due("fab.manage"',i)
blk=s[i:j]
lines=blk.split("\n")
out=[lines[0]]
for L in lines[1:]:
    if L.startswith("                ") : out.append("  "+L[2:] if False else L)
    else: out.append(L)
s=s[:i]+"\n".join(out)+s[j:]
rep('''                dom_api.rekey(dom_cfg, sysm.partition, encode=sig_encode)''','''                with _timing.span("dom.rekey"):
                    dom_api.rekey(dom_cfg, sysm.partition, encode=sig_encode)''')
rep('''            sample = _c_sample_window(sysm, st, i)''','''            with _timing.span("sample_window"):
                sample = _c_sample_window(sysm, st, i)''')
# trace
rep('''            if cadences.due("ckpt", periods["ckpt"], clock):''','''            _TR(sysm, tick, pop, vocab, _timing)
            if cadences.due("ckpt", periods["ckpt"], clock):''')
# flush sub-spans
rep('''    cast = sysm.process.autocast
    with cast():
        obs_emb = lm_api.embed''','''    cast = sysm.process.autocast
    with cast(), _timing.span("flush/lm.embed_encode_world"):
        obs_emb = lm_api.embed''')
rep('''        if out.logits is not None:
            logits = out.logits''','''        _dsp = _timing.span("flush/decode_loss"); _dsp.__enter__()
        if out.logits is not None:
            logits = out.logits''')
rep('''        wstep = world_api.loss_terms(''','''        _dsp.__exit__(None,None,None)
        with _timing.span("flush/world.loss"):
          wstep = world_api.loss_terms(''')
rep('''        anchor = lm_api.anchor_term(''','''        with _timing.span("flush/anchor"):
          anchor = lm_api.anchor_term(''')
rep('''    opt_api.remap_rows(opt_cfg, sysm.optimizer, out.row_events)''','''    with _timing.span("flush/opt.remap_rows"):
        opt_api.remap_rows(opt_cfg, sysm.optimizer, out.row_events)''')
rep('''    caps = cap_api.caps(cfg_cap, sysm.valve)''','''    with _timing.span("flush/cap.caps"):
        caps = cap_api.caps(cfg_cap, sysm.valve)''')
rep('''    fab_api.observe(fab_cfg, pop, out, per_window_loss=per_window.detach(),
                    domain_id=list(dids) if dids else domain_id)''','''    with _timing.span("flush/fab.observe"):
        fab_api.observe(fab_cfg, pop, out, per_window_loss=per_window.detach(),
                    domain_id=list(dids) if dids else domain_id)''')
rep('''    due = sysm.due
    sysm.due = None''','''    _tsp = _timing.span("flush/tok.due"); _tsp.__enter__()
    due = sysm.due
    sysm.due = None''')
rep('''    _ln2 = math.log(2.0)''','''    _tsp.__exit__(None,None,None)
    _ln2 = math.log(2.0)''')
s += '''

import time as _time, json as _json, os as _os
_TR_STATE = {"t0": None, "last": None}
def _TR(sysm, tick, pop, vocab, timing):
    every = int(_os.environ.get("TRACE_EVERY", "100"))
    st = int(tick.step)
    now = _time.perf_counter()
    if _TR_STATE["t0"] is None:
        _TR_STATE["t0"] = now; _TR_STATE["last"] = (st, now)
    if st % every: return
    ls, lt = _TR_STATE["last"]
    rate = (st - ls) / max(now - lt, 1e-9)
    _TR_STATE["last"] = (st, now)
    rec = {"step": st, "wall": round(now - _TR_STATE["t0"], 2), "win_per_s": round(rate, 3),
           "n_live": int(getattr(pop, "n_live", -1)), "vocab": int(vocab.size()),
           "spans": {k: round(v, 3) for k, v in timing.spans().items()}}
    try:
        from memory import api as _m
        c = _m.census(sysm.configs["MEM"], sysm.store)
        rec["mem_pressure"] = float(c.pressure) if c.pressure is not None else None
        rec["mem_n"] = int(sum(c.counts.values())) if hasattr(c.counts, "values") else None
    except Exception as e:
        rec["mem_err"] = repr(e)[:80]
    try:
        from domains import api as _d
        rec["dom_live"] = int(_d.census(sysm.configs["DOM"], sysm.partition).n_live)
    except Exception as e:
        rec["dom_err"] = repr(e)[:80]
    p = _os.environ.get("TRACE_FILE")
    if p:
        with open(p, "a") as f: f.write(_json.dumps(rec) + "\\n")
'''
open(p,"w").write(s)
