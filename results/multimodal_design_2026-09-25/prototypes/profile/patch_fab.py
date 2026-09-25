import sys
p=sys.argv[1]+"/src/fabric/api.py"
s=open(p).read()
old='''        pairs = []
        for i in range(n_live):
            for j in range(i + 1, n_live):
                if float(1.0 - sim[i, j]) <= merge_dist:
                    pairs.append((float(sim[i, j]), i, j))
        pairs.sort(reverse=True)'''
new='''        # VECTORISED PAIR SCAN: the same fp32 `1.0 - sim` the scalar loop computed, compared in
        # float64 against merge_dist exactly as float(...) <= merge_dist did, one host transfer.
        _dist = (1.0 - sim).double()
        _hit = torch.triu(_dist <= merge_dist, diagonal=1)
        _ij = _hit.nonzero()
        _sv = sim[_ij[:, 0], _ij[:, 1]]
        pairs = list(zip(_sv.tolist(), _ij[:, 0].tolist(), _ij[:, 1].tolist()))
        pairs.sort(reverse=True)
        if __import__("os").environ.get("FAB_PAIRSCAN_CHECK"):
            _ref = []
            for i in range(n_live):
                for j in range(i + 1, n_live):
                    if float(1.0 - sim[i, j]) <= merge_dist:
                        _ref.append((float(sim[i, j]), i, j))
            _ref.sort(reverse=True)
            assert _ref == pairs, (len(_ref), len(pairs))
            print("PAIRSCAN_CHECK ok n=%d pairs=%d" % (n_live, len(pairs)), flush=True)'''
assert s.count(old)==1
s=s.replace(old,new)
open(p,"w").write(s)
