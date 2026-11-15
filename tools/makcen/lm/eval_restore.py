#!/usr/bin/env python3
"""Step 3: does the model beat the dictionary at restoring diacritics?

Takes held-out sentences (never seen in training), strips the diacritics, and restores each
word left to right the way a keyboard would - only the words before it are known.
Candidates for a typed word are the dictionary words with the same letters ignoring
diacritics (from build/main_sk.combined), so the model can only choose real words.

  dictionary   a typed form that is itself a word stays; otherwise the most frequent candidate
  model        the candidate that the language model finds most likely after the words so far
  model + dictionary frequency   the same, with the word's general frequency added in

Also reported: how many wanted words are missing from the dictionary altogether - no method
that only chooses among dictionary words can get those right.

Reported: accuracy on words that need diacritics, on words that must stay plain (a model
that adds accents everywhere would fail here), and on both together.
"""
import argparse, os, re, sys
import torch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from build_dictionary import strip_dia, HERE as TOOLS
from common import DATA, EOT, load_model, load_tokenizer

LN_STEP = 0.1398   # ln(1.15): one dictionary frequency unit is a factor of 1.15 in probability
WORD = re.compile(r"[A-Za-záäčďéíĺľňóôŕšťúýžÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ]+")


def load_dictionary(path):
    freq = {}
    if path.endswith(".gz"):        # the word list shipped in the repo: word<TAB>frequency
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                w, fr = line.rstrip("\n").split("\t")
                freq[w] = int(fr)
    else:                           # a freshly built build/main_sk.combined
        with open(path, encoding="utf-8") as f:
            next(f)
            for line in f:
                line = line.strip()
                if line.startswith("word="):
                    p = dict(x.split("=", 1) for x in line.split(","))
                    freq[p["word"]] = int(p["f"])
    by = {}
    for w, fr in freq.items():
        by.setdefault(strip_dia(w).lower(), []).append(w)
    return freq, by


def read_text_file(path):
    """Lines of a text or .srt file as test sentences; subtitle numbers, timings and tags are dropped."""
    out = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = re.sub(r"<[^>]+>|\{[^}]+\}", "", line).strip().lstrip("-– ").strip()
            if not line or line.isdigit() or "-->" in line:
                continue
            if len(WORD.findall(line)) >= 3:
                out.append(line)
    return out


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
    ap.add_argument("--test-file", help="test on your own text instead of Wikipedia: a plain-text or .srt subtitle file with correct diacritics")
    ap.add_argument("--onnx", help="score with an exported .onnx file instead of model.pt")
    ap.add_argument("--weight", type=float, help="weight of the dictionary frequency next to the model; default: tuned on 300 extra sentences")
    ap.add_argument("--show", type=int, default=15, help="print this many sentences the model got wrong")
    a = ap.parse_args()

    freq, by = load_dictionary(a.dictionary)
    tok = load_tokenizer(a.data)
    model, ck = load_model(os.path.join(a.data, "model.pt"))
    ctx = model.cfg["ctx"]
    if a.test_file:
        all_sents = read_text_file(a.test_file)
    else:
        with open(os.path.join(a.data, "test_sentences.txt"), encoding="utf-8") as f:
            all_sents = [l.strip() for l in f if l.strip()]
    sents = all_sents[:a.sentences]

    eot = tok.token_to_id(EOT)
    cache = {}
    if a.onnx:      # score with the exported file, i.e. exactly what the phone will run
        import onnxruntime as ort
        sess = ort.InferenceSession(a.onnx, providers=["CPUExecutionProvider"])
        logp_all = lambda x: torch.from_numpy(sess.run(None, {"ids": x.numpy()})[0])
        print("scoring with", a.onnx)
    else:
        logp_all = lambda x: torch.log_softmax(model(x), -1)

    @torch.no_grad()
    def lm_scores(prefix, cands):
        """How likely the model finds the sentence so far, ending in each candidate."""
        key = (prefix, tuple(cands))
        if key not in cache:
            encs = [tok.encode(prefix + c).ids[-(ctx - 1):] for c in cands]
            n = max(len(e) for e in encs)
            x = torch.tensor([[eot] + e + [0] * (n - len(e)) for e in encs])
            logp = logp_all(x[:, :-1]).gather(2, x[:, 1:, None])[..., 0]
            cache[key] = [logp[i, :len(e)].sum().item() for i, e in enumerate(encs)]
        return cache[key]

    def run(sentences, weight):
        """weight: how much the dictionary frequency counts next to the model (0 = model alone)."""
        stats = {k: [0, 0, 0] for k in ("accented", "plain")}   # total, dictionary right, model right
        wrong, unreachable = [], 0
        for s in sentences:
            out, pos, bad = "", 0, False
            for m in WORD.finditer(s):
                gold = m.group()
                typed = strip_dia(gold)
                out += s[pos:m.start()]
                pos = m.end()
                # candidate spellings and their dictionary frequency. Names (Bytča, Čína) are stored
                # capitalised and only apply when the typed word is capitalised too.
                cf = {}
                for e in by.get(typed.lower(), []):
                    if typed.isupper() and len(typed) > 1 and e != e.upper():
                        continue     # VRS, DLB: a word in capitals only matches a dictionary entry in capitals
                    if e == e.lower():
                        surface = recase(e, typed)
                    elif typed[0].isupper():
                        surface = e
                    else:
                        continue
                    cf[surface] = max(cf.get(surface, 0), freq[e])
                cands = list(cf)
                if gold not in cf and gold != typed:
                    unreachable += 1     # the wanted word is not in the dictionary at all
                if not cands:
                    d_choice = m_choice = typed
                else:
                    d_choice = typed if typed in cf else max(cands, key=cf.get)
                    if len(cands) == 1:
                        m_choice = cands[0]
                    else:
                        tail = " ".join(out.split()[-40:])
                        glue = "" if not out or out.endswith(tuple("(„\"-–")) else " "
                        sc = lm_scores(tail + glue, cands)
                        m_choice = cands[max(range(len(cands)), key=lambda i: sc[i] + weight * LN_STEP * cf[cands[i]])]
                out += m_choice
                kind = "accented" if gold != typed else "plain"
                stats[kind][0] += 1
                stats[kind][1] += d_choice == gold
                stats[kind][2] += m_choice == gold
                bad |= m_choice != gold
            out += s[pos:]
            if bad:
                wrong.append((s, out))
        return stats, wrong, unreachable

    def acc(stats):
        return sum(v[2] for v in stats.values()) / max(1, sum(v[0] for v in stats.values()))

    # choose how much weight the dictionary frequency gets, on sentences that are NOT in the test
    weight = a.weight
    if weight is None:
        dev = all_sents[a.sentences:a.sentences + 300]
        weight = max((0.0, 0.25, 0.5, 1.0, 2.0), key=lambda w: acc(run(dev, w)[0])) if len(dev) >= 50 else 0.0

    print(f"model trained {ck.get('hours_done', 0):.1f} h, {len(sents)} held-out sentences\n")
    results = [("model alone", run(sents, 0.0))]
    if weight:
        results.append((f"model + dictionary frequency (weight {weight})", run(sents, weight)))
    for title, (stats, wrong, unreachable) in results:
        print(f"--- {title}")
        print(f"{'':28}{'words':>8}{'dictionary':>12}{'model':>9}")
        tot = [sum(stats[k][i] for k in stats) for i in range(3)]
        for name, (n, d, mm) in (("words needing diacritics", stats["accented"]), ("words that stay plain", stats["plain"]), ("all words", tot)):
            print(f"{name:28}{n:8d}{d/max(n,1):12.1%}{mm/max(n,1):9.1%}")
        print(f"sentences fully correct: {1 - len(wrong)/len(sents):.1%}\n")
    n_acc = stats["accented"][0]
    print(f"accented words missing from the dictionary (nothing can restore them): {unreachable} = {unreachable/max(n_acc,1):.1%} of words needing diacritics")
    for s_, o in wrong[:a.show]:
        print("\n  wanted:", s_, "\n  model: ", o)


if __name__ == "__main__":
    main()
