import torch,time,torch.nn as nn
torch.set_num_threads(1)
V=40;B=16;T=128;d=128
class TF(nn.Module):
    def __init__(s):
        super().__init__();s.e=nn.Embedding(V,d);s.p=nn.Embedding(T,d)
        s.l=nn.TransformerEncoder(nn.TransformerEncoderLayer(d,4,4*d,0.0,batch_first=True,norm_first=True),2);s.o=nn.Linear(d,V)
    def forward(s,x):
        m=nn.Transformer.generate_square_subsequent_mask(x.shape[1])
        return s.o(s.l(s.e(x)+s.p.weight[:x.shape[1]],mask=m,is_causal=True))
class G(nn.Module):
    def __init__(s):
        super().__init__();s.e=nn.Embedding(V,d);s.g=nn.GRU(d,d,batch_first=True);s.o=nn.Linear(d,V)
    def forward(s,x): return s.o(s.g(s.e(x))[0])
for M in (TF,G):
    m=M();o=torch.optim.AdamW(m.parameters(),1e-3);x=torch.randint(0,V,(B,T+1))
    for i in range(12):
        if i==2:t=time.time()
        l=nn.functional.cross_entropy(m(x[:,:-1]).reshape(-1,V),x[:,1:].reshape(-1));o.zero_grad();l.backward();o.step()
    dt=(time.time()-t)/10;print(M.__name__,f"{dt*1000:.1f} ms/step {B*T/dt:.0f} tok/s")
