"""Shared pieces of the context-model prototype: paths, tokenizer loading, the model."""
import math, os
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", ".cache", "lm")
EOT = "<eot>"   # separates paragraphs / marks the start of a sentence


def load_tokenizer(data=DATA):
    from tokenizers import Tokenizer
    return Tokenizer.from_file(os.path.join(data, "tokenizer.json"))


class Block(nn.Module):
    def __init__(self, d, heads):
        super().__init__()
        self.heads = heads
        self.ln1, self.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.proj = nn.Linear(d, d, bias=False)
        self.mlp = nn.Sequential(nn.Linear(d, 4 * d), nn.GELU(), nn.Linear(4 * d, d))

    def forward(self, x):
        b, t, d = x.shape
        q, k, v = self.qkv(self.ln1(x)).view(b, t, 3, self.heads, d // self.heads).permute(2, 0, 3, 1, 4)
        a = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.proj(a.transpose(1, 2).reshape(b, t, d))
        return x + self.mlp(self.ln2(x))


class GPT(nn.Module):
    """A small GPT-2-style language model: predicts the next token from the ones before it."""

    def __init__(self, vocab, ctx=96, d=256, layers=6, heads=4):
        super().__init__()
        self.cfg = dict(vocab=vocab, ctx=ctx, d=d, layers=layers, heads=heads)
        self.tok = nn.Embedding(vocab, d)
        self.pos = nn.Embedding(ctx, d)
        self.blocks = nn.ModuleList(Block(d, heads) for _ in range(layers))
        self.ln = nn.LayerNorm(d)
        self.head = nn.Linear(d, vocab, bias=False)
        self.head.weight = self.tok.weight   # tied weights: fewer parameters
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)
            if getattr(m, "bias", None) is not None:
                nn.init.zeros_(m.bias)

    def forward(self, idx):
        x = self.tok(idx) + self.pos(torch.arange(idx.shape[1], device=idx.device))
        for blk in self.blocks:
            x = blk(x)
        return self.head(self.ln(x))


def load_model(path=None):
    ck = torch.load(path or os.path.join(DATA, "model.pt"), map_location="cpu")
    model = GPT(**ck["cfg"])
    model.load_state_dict(ck["model"])
    return model.eval(), ck
