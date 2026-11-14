#!/usr/bin/env python3
"""Step 1: get Slovak text, hold some out for testing, train the tokenizer, encode.

Default source is Slovak Wikipedia (CC BY-SA), downloaded ready-cleaned from Hugging Face
(dataset wikimedia/wikipedia, about 400 MB). Use --text-file to train on any plain-text file
instead (one paragraph per line).

Writes to tools/makcen/.cache/lm: tokenizer.json, train.bin, val.bin, test_sentences.txt
"""
import argparse, os, random, re, sys
import numpy as np
from common import DATA, EOT

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ])")
SENT_OK = re.compile(r"^[A-ZÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ][A-Za-záäčďéíĺľňóôŕšťúýžÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ ,;:\-–()„“\"]+[.!?]$")


def wikipedia(config):
    from datasets import load_dataset
    ds = load_dataset("wikimedia/wikipedia", config, split="train")
    for row in ds:
        yield row["text"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-file", help="plain text, one paragraph per line (instead of Wikipedia)")
    ap.add_argument("--wiki-config", default="20231101.sk")
    ap.add_argument("--vocab", type=int, default=8000)
    ap.add_argument("--heldout", type=float, default=0.01, help="share of documents kept out of training")
    ap.add_argument("--test-sentences", type=int, default=3000)
    ap.add_argument("--out", default=DATA)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    if a.text_file:
        with open(a.text_file, encoding="utf-8") as f:
            docs = [l.strip() for l in f if l.strip()]
    else:
        docs = list(wikipedia(a.wiki_config))
    random.Random(0).shuffle(docs)
    n_held = max(20, int(len(docs) * a.heldout))
    held, train = docs[:n_held], docs[n_held:]

    def paragraphs(ds):
        for d in ds:
            for p in d.split("\n"):
                p = " ".join(p.split())
                if len(p) >= 40:
                    yield p

    train_p = list(paragraphs(train))
    held_p = list(paragraphs(held))
    val_p, test_p = held_p[::2], held_p[1::2]
    print(f"{len(docs)} documents, {len(train_p)} training paragraphs, {sum(len(p) for p in train_p)/1e6:.0f} M characters", flush=True)

    sents = []
    for p in test_p:
        for s in SENT_SPLIT.split(p):
            if 5 <= len(s.split()) <= 30 and SENT_OK.match(s):
                sents.append(s)
    random.Random(1).shuffle(sents)
    with open(os.path.join(a.out, "test_sentences.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sents[:a.test_sentences]) + "\n")
    print(f"{min(len(sents), a.test_sentences)} held-out test sentences", flush=True)

    from tokenizers import Tokenizer, models, trainers, pre_tokenizers, decoders, normalizers
    tok = Tokenizer(models.BPE(unk_token="<unk>"))
    tok.normalizer = normalizers.NFC()
    tok.pre_tokenizer = pre_tokenizers.Metaspace()
    tok.decoder = decoders.Metaspace()
    tok.train_from_iterator(train_p, trainers.BpeTrainer(vocab_size=a.vocab, special_tokens=["<unk>", EOT], show_progress=False))
    tok.save(os.path.join(a.out, "tokenizer.json"))
    eot = tok.token_to_id(EOT)

    for name, ps in (("train", train_p), ("val", val_p)):
        ids = []
        for i in range(0, len(ps), 20000):
            for enc in tok.encode_batch(ps[i:i + 20000]):
                ids.append(eot)
                ids.extend(enc.ids)
        arr = np.array(ids, dtype=np.uint16)
        arr.tofile(os.path.join(a.out, f"{name}.bin"))
        print(f"{name}: {len(arr)/1e6:.1f} M tokens", flush=True)


if __name__ == "__main__":
    main()
