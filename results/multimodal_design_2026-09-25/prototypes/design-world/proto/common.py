import sys, time, json, torch
from torch import nn
from torch.nn import functional as F
P = "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm/design-world/proto"
sys.path.insert(0, P)
import synth as S
torch.set_num_threads(1)

class CConv(nn.Conv1d):
    """causal conv: left pad only, so latent t never sees mel frames after t's receptive end"""
    def forward(self, x):
        k, d, s = self.kernel_size[0], self.dilation[0], self.stride[0]
        return super().forward(F.pad(x, ((k - 1) * d - (s - 1), 0)))

class AudCodec(nn.Module):
    """AUD's learned continuous codec: log-mel (B,64,T50) <-> latent (B,D,T25). Causal both ways."""
    def __init__(self, D=32, C=128):
        super().__init__()
        self.enc = nn.Sequential(CConv(64, C, 3), nn.ELU(), CConv(C, C, 3, dilation=2), nn.ELU(),
                                 CConv(C, C, 4, stride=2), nn.ELU(), CConv(C, C, 3), nn.ELU(), CConv(C, D, 1))
        self.dec = nn.Sequential(CConv(D, C, 3), nn.ELU(), CConv(C, C, 3, dilation=2), nn.ELU(),
                                 nn.Upsample(scale_factor=2), CConv(C, C, 3), nn.ELU(), CConv(C, 64, 1))
        self.mu = nn.Parameter(torch.full((64, 1), -4.1), requires_grad=False)
    def encode(self, mel): return torch.tanh(self.enc((mel - self.mu) / 3.0))
    def decode(self, z): return self.dec(z) * 3.0 + self.mu

class Probe(nn.Module):
    """parameter-recovery probe (from scratch, trained on TRUE mels): per-note pitch + clip timbre"""
    def __init__(self):
        super().__init__()
        self.note = nn.Sequential(nn.Linear(64 * 2, 128), nn.ReLU(), nn.Linear(128, 8))
        self.tim = nn.Sequential(nn.Linear(64 * 2, 128), nn.ReLU(), nn.Linear(128, 3))
    def feats(self, mel):  # (B,64,128) -> (B,4,128): mean+max of middle of each note
        seg = mel.reshape(mel.shape[0], 64, 4, 32)[..., 4:28]
        return torch.cat([seg.mean(-1), seg.amax(-1)], 1).permute(0, 2, 1)
    def forward(self, mel):
        f = self.feats(mel); return self.note(f), self.tim(f.mean(1))

def labels(Ps):
    return (torch.tensor([p["notes"] for p in Ps]), torch.tensor([p["timbre"] for p in Ps]))

def probe_acc(probe, mel, Ps, notes_idx=(0, 1, 2, 3)):
    n, t = labels(Ps)
    with torch.no_grad():
        ln, lt = probe(mel)
    ni = list(notes_idx)
    return {"note_acc": round((ln.argmax(-1)[:, ni] == n[:, ni]).float().mean().item(), 4),
            "timbre_acc": round((lt.argmax(-1) == t).float().mean().item(), 4)}

def load():
    return torch.load(P + "/data.pt", weights_only=False)
