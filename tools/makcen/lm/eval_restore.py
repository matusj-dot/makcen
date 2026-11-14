#!/usr/bin/env python3
"""Step 3: does the model beat the dictionary at restoring diacritics?

Takes held-out sentences (never seen in training), strips the diacritics, and restores each
word left to right the way a keyboard would - only the words before it are known.
Candidates for a typed word are the dictionary words with the same letters ignoring
diacritics (from build/main_sk.combined), so the model can only choose real words.

  dictionary   a typed form that is itself a word stays; otherwise the most frequent candidate
  model        the candidate that the language model finds most likely after the words so far

Reported: accuracy on words that need diacritics, on words that must stay plain (a model
that adds accents everywhere would fail here), and on both together.
"""
import argparse, os, re, sys
import torch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from build_dictionary import strip_dia, HERE as TOOLS
from common import DATA, EOT, load_model, load_tokenizer

WORD = re.compile(r"[A-Za-záäčďéíĺľňóôŕšťúýžÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ]+")


def load_dictionary(path):
    freq = {}
    if path.endswith(".gz"):        # the word list shipped in the repo: word<TAB>frequency
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                w, fr = line.rstrip("\n").split("\t")
                if w == w.lower():
                    freq[w] = int(fr)
    else:                           # a freshly built build/main_sk.combined
        with open(path, encoding="utf-8") as f:
            next(f)
            for line in f:
                line = line.strip()
                if line.startswith("word="):
                    p = dict(x.split("=", 1) for x in line.split(","))
                    w = p["word"]
                    if w == w.lower():
                        freq[w] = int(p["f"])
    by = {}
    for w, fr in freq.items():
        by.setdefault(strip_dia(w), []).append(w)
    return freq, by


def recase(word, like):
    if like.isupper() and len(like) > 1:
        return word.upper()
    return word.capitalize() if like[0].isupper() else word


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=int, default=1000)
    built = os.path.join(TOOLS, "build", "main_sk.combined")
    ap.add_argument("--dictionary", default=built if os.path.exists(built) else os.path.join(TOOLS, "lm", "wordlist.tsv.gz"))
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--show", type=int, default=15, help="print this many sentences the model got wrong")
    a = ap.parse_args()

    freq, by = load_dictionary(a.dictionary)
    tok = load_tokenizer(a.data)
    model, ck = load_model(os.path.join(a.data, "model.pt"))
    ctx = model.cfg["ctx"]
    with open(os.path.join(a.data, "test_sentences.txt"), encoding="utf-8") as f:
        sents = [l.strip() for l in f if l.strip()][:a.sentences]

    @torch.no_grad()
    def pick(prefix, cands):
        """Candidate whose sentence-so-far the model finds most likely."""
        encs = [tok.encode(prefix + c).ids[-(ctx - 1):] for c in cands]
        n = max(len(e) for e in encs)
        eot = tok.token_to_id(EOT)
        x = torch.tensor([[eot] + e + [0] * (n - len(e)) for e in encs])
        logp = torch.log_softmax(model(x[:, :-1]), -1).gather(2, x[:, 1:, None])[..., 0]
        scores = [logp[i, :len(e)].sum().item() for i, e in enumerate(encs)]
        return cands[max(range(len(cands)), key=scores.__getitem__)]

    stats = {k: [0, 0, 0] for k in ("accented", "plain")}   # total, dictionary right, model right
    wrong = []
    for s in sents:
        out_model, pos, bad = "", 0, False
        for m in WORD.finditer(s):
            gold = m.group()
            typed = strip_dia(gold)
            out_model += s[pos:m.start()]
            pos = m.end()
            cands = by.get(typed.lower(), [])
            if len(cands) == 0:
                out_model += typed      # unknown to the dictionary: nobody can restore it
                d_choice = m_choice = typed
            else:
                d = typed.lower() if typed.lower() in freq else max(cands, key=freq.get)
                d_choice = recase(d, typed)
                if len(cands) == 1 and typed.lower() not in freq:
                    m_choice = d_choice
                else:
                    tail = " ".join(out_model.split()[-40:])
                    glue = "" if out_model.endswith(tuple("(„\"-–")) or not out_model else " "
                    prefix = tail + glue if not out_model.endswith(" ") else tail + " "
                    m_choice = pick(prefix, [recase(c, typed) for c in cands])
                out_model += m_choice
            kind = "accented" if gold != typed else "plain"
            stats[kind][0] += 1
            stats[kind][1] += d_choice == gold
            stats[kind][2] += m_choice == gold
            bad |= m_choice != gold
        out_model += s[pos:]
        if bad:
            wrong.append((s, out_model))

    print(f"model trained {ck.get('hours_done', 0):.1f} h, {len(sents)} held-out sentences\n")
    print(f"{'':28}{'words':>8}{'dictionary':>12}{'model':>9}")
    tot = [sum(stats[k][i] for k in stats) for i in range(3)]
    for name, (n, d, mm) in (("words needing diacritics", stats["accented"]), ("words that stay plain", stats["plain"]), ("all words", tot)):
        print(f"{name:28}{n:8d}{d/max(n,1):12.1%}{mm/max(n,1):9.1%}")
    print(f"\nsentences fully correct with the model: {1 - len(wrong)/len(sents):.1%}")
    for s, o in wrong[:a.show]:
        print("\n  wanted:", s, "\n  model: ", o)


if __name__ == "__main__":
    main()
