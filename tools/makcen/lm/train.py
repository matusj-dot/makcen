#!/usr/bin/env python3
"""Step 2: train the small language model. Built for a PC without a graphics card.

Runs for a fixed time (--hours), saving a checkpoint every few minutes, so it can be
stopped with Ctrl+C and continued later with --resume.
"""
import argparse, math, os, time
import numpy as np
import torch
import torch.nn.functional as F
from common import DATA, GPT, load_tokenizer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=3.0)
    ap.add_argument("--batch", type=int, default=48)
    ap.add_argument("--ctx", type=int, default=96)
    ap.add_argument("--d", type=int, default=256)
    ap.add_argument("--layers", type=int, default=6)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--data", default=DATA)
    a = ap.parse_args()

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    train = np.memmap(os.path.join(a.data, "train.bin"), dtype=np.uint16, mode="r")
    val = np.memmap(os.path.join(a.data, "val.bin"), dtype=np.uint16, mode="r")
    vocab = load_tokenizer(a.data).get_vocab_size()
    path = os.path.join(a.data, "model.pt")

    done = 0.0
    if a.resume and os.path.exists(path):
        ck = torch.load(path, map_location="cpu")
        model = GPT(**ck["cfg"])
        model.load_state_dict(ck["model"])
        done = ck.get("hours_done", 0.0)
    else:
        model = GPT(vocab, a.ctx, a.d, a.layers, a.heads)
    model.to(dev)
    ctx = model.cfg["ctx"]
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01, betas=(0.9, 0.95))
    print(f"{sum(p.numel() for p in model.parameters())/1e6:.1f} M parameters, {len(train)/1e6:.1f} M training tokens, "
          f"device {dev}, {torch.get_num_threads()} threads", flush=True)

    def batch(data):
        ix = np.random.randint(0, len(data) - ctx - 1, a.batch)
        x = np.stack([data[i:i + ctx] for i in ix]).astype(np.int64)
        y = np.stack([data[i + 1:i + ctx + 1] for i in ix]).astype(np.int64)
        return torch.from_numpy(x).to(dev), torch.from_numpy(y).to(dev)

    @torch.no_grad()
    def val_loss():
        model.eval()
        tot = sum(F.cross_entropy(model(x).flatten(0, 1), y.flatten()).item() for x, y in (batch(val) for _ in range(20)))
        model.train()
        return tot / 20

    def save(hours):
        torch.save({"model": model.state_dict(), "cfg": model.cfg, "hours_done": hours}, path)

    budget = a.hours * 3600
    start = last_log = last_save = time.time()
    step, model_ = 0, model.train()
    try:
        while True:
            el = time.time() - start
            if el >= budget:
                break
            frac = el / budget
            lr = a.lr * min(1.0, (step + 1) / 200) * (0.05 + 0.95 * 0.5 * (1 + math.cos(math.pi * frac)))
            for g in opt.param_groups:
                g["lr"] = lr
            x, y = batch(train)
            loss = F.cross_entropy(model(x).flatten(0, 1), y.flatten())
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            step += 1
            now = time.time()
            if now - last_log > 120 or step == 20:
                print(f"{el/60:6.1f} min  step {step:7d}  {step*a.batch*ctx/max(el,1)/1000:6.1f}k tokens/s  "
                      f"train loss {loss.item():.3f}  val loss {val_loss():.3f}", flush=True)
                last_log = now
            if now - last_save > 600:
                save(done + el / 3600)
                last_save = now
    except KeyboardInterrupt:
        print("stopped - saving", flush=True)
    save(done + (time.time() - start) / 3600)
    print(f"saved {path}  final val loss {val_loss():.3f}", flush=True)


if __name__ == "__main__":
    main()
