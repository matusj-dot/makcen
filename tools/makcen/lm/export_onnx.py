#!/usr/bin/env python3
"""Step 4: turn the trained model into the file the keyboard will load.

Writes two versions next to the model and checks both against the original:
  makcen_lm.onnx        full precision
  makcen_lm_q8.onnx     8-bit weights: about a quarter of the size, the one meant for the phone
Also measures how long one decision takes on a single processor core.

Input:  token ids, shape (candidates, length)
Output: log-probabilities of the next token at every position, shape (candidates, length, vocabulary)
"""
import argparse, os, time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from common import DATA, load_model


class Exportable(nn.Module):
    """The same computation as common.GPT, with the causal mask written out so that it
    follows the input length in the exported file."""

    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, idx):
        m = self.m
        t = idx.shape[1]
        x = m.tok(idx) + m.pos(torch.arange(t))
        mask = torch.triu(torch.full((t, t), float("-inf")), diagonal=1)
        for blk in m.blocks:
            b, _, d = x.shape
            h = blk.heads
            q, k, v = blk.qkv(blk.ln1(x)).view(b, t, 3, h, d // h).permute(2, 0, 3, 1, 4)
            att = (q @ k.transpose(-2, -1)) / (d // h) ** 0.5 + mask
            a = torch.softmax(att, dim=-1) @ v
            x = x + blk.proj(a.transpose(1, 2).reshape(b, t, d))
            x = x + blk.mlp(blk.ln2(x))
        return F.log_softmax(m.head(m.ln(x)), dim=-1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    a = ap.parse_args()
    import onnxruntime as ort
    from onnxruntime.quantization import quantize_dynamic, QuantType

    model, ck = load_model(os.path.join(a.data, "model.pt"))
    vocab, ctx = model.cfg["vocab"], model.cfg["ctx"]
    wrapped = Exportable(model).eval()
    full = os.path.join(a.data, "makcen_lm.onnx")
    q8 = os.path.join(a.data, "makcen_lm_q8.onnx")
    example = torch.randint(0, vocab, (2, 12))
    torch.onnx.export(wrapped, (example,), full, input_names=["ids"], output_names=["logp"],
                      dynamic_axes={"ids": {0: "candidates", 1: "length"}, "logp": {0: "candidates", 1: "length"}},
                      opset_version=17, dynamo=False)
    quantize_dynamic(full, q8, weight_type=QuantType.QInt8)

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    print(f"model trained {ck.get('hours_done', 0):.1f} h, vocabulary {vocab}, context {ctx}")
    for name, path in (("full precision", full), ("8-bit", q8)):
        sess = ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])
        worst = 0.0
        agree = total = 0
        for shape in ((1, 5), (3, 40), (4, ctx)):
            ids = torch.randint(0, vocab, shape)
            with torch.no_grad():
                ref = F.log_softmax(model(ids), -1).numpy()
            out = sess.run(None, {"ids": ids.numpy()})[0]
            worst = max(worst, float(np.abs(out - ref).max()))
            agree += int((out.argmax(-1) == ref.argmax(-1)).sum())
            total += ref.shape[0] * ref.shape[1]
        ids = np.random.randint(0, vocab, (3, 40)).astype(np.int64)
        sess.run(None, {"ids": ids})
        t = time.time()
        for _ in range(20):
            sess.run(None, {"ids": ids})
        ms = (time.time() - t) / 20 * 1000
        print(f"{name:15} {os.path.getsize(path)/1e6:5.1f} MB   largest difference from the original {worst:.4f}   "
              f"same top prediction {agree/total:.1%}   one decision (3 candidates, 40 tokens, 1 core): {ms:.0f} ms")
    print(f"\nwrote {full}\nwrote {q8}")


if __name__ == "__main__":
    main()
