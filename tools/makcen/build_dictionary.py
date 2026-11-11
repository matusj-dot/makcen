#!/usr/bin/env python3
"""Build the Mäkčeň Slovak main dictionary (AOSP .combined wordlist) from open data.

Sources
  SNC   Slovak National Corpus, prim-11.0-public-all: word-form frequencies (case-sensitive)
        and 2-grams. Edited written Slovak, 1.5 billion words.
  SUBS  OpenSubtitles 2018 word-form frequencies (FrequencyWords). Informal, chat-like,
        lower-cased, noisy.
  Hunspell sk_SK (sk-spell) decides which forms are valid Slovak.

Pipeline
  1. Candidates: forms seen often enough in SNC or SUBS.
  2. Casing comes from SNC: a form mostly written in lower case is stored in lower case;
     otherwise as Capitalised or UPPER (Bratislava, EÚ). A lower-case word that also has a
     strong upper-case twin keeps both (nato / NATO).
  3. Validity: Hunspell must accept the form. Superlatives (naj- + valid form) count as valid.
     Forms Hunspell does not know are NOT added automatically, with one exception: proper
     nouns that are frequent in SNC (Fico, Slovnaft) - written to build/auto_names.txt.
     Frequent unknown lower-case forms go to build/candidates.txt for a human to promote
     into extra_words.txt.
  4. Text typed without diacritics inflates plain forms ("zeny" for "ženy"). The sloppy-typing
     rate is estimated per source from unambiguous pairs and subtracted. A plain form is dropped
     when both sources explain it as sloppy typing, or when its accented twin is 50 times more
     frequent (mat / mať) - so the keyboard restores the accented word. This is a deliberate
     exception to "never correct a valid word": see build/dropped_plain_forms.txt, and list a
     word in extra_words.txt to keep it.
  5. Frequencies: the two sources are blended by relative frequency and mapped to the 0-255
     log scale of AOSP dictionaries.
  6. Hand-maintained lists are merged in: extra_words.txt, offensive.txt, blocklist.txt.
  7. Bigrams from SNC 2-grams: for each word, the most likely next words.

Run fetch_sources.sh first. Output: build/main_sk.combined and reports in build/.
Compile with: java -jar .cache/dicttool/dicttool_aosp.jar makedict -s build/main_sk.combined -d main_sk.dict
"""
import argparse, bz2, heapq, json, math, os, pickle, re, subprocess, sys, time, unicodedata
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
SK_LETTERS = "aáäbcčdďeéfghiíjklĺľmnňoóôpqrŕsštťuúvwxyýzž"
WORD_RE = re.compile(f"^[{SK_LETTERS}]+(-[{SK_LETTERS}]+)?$")
DIA = set("áäčďéíĺľňóôŕšťúýž")
STEP = math.log(1.15)   # one frequency unit = factor 1.15 in probability
TOP_F = 240


def strip_dia(w):
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")


def read_freq(path, min_count=1):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.split()
            if len(p) == 2 and p[1].isdigit() and int(p[1]) >= min_count:
                out[p[0]] = int(p[1])
    return out


def read_snc(cache):
    """lower-case form -> {spelling as written: count}"""
    pk = f"{cache}/snc/word_frequency.pickle"
    if os.path.exists(pk):
        with open(pk, "rb") as f:
            return pickle.load(f)
    agg = defaultdict(dict)
    with bz2.open(f"{cache}/snc/word_frequency.txt.bz2", "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) != 2 or not p[1].isdigit():
                continue
            lw = p[0].lower()
            if WORD_RE.match(lw) and len(lw) <= 40:
                agg[lw][p[0]] = agg[lw].get(p[0], 0) + int(p[1])
    agg = dict(agg)
    with open(pk, "wb") as f:
        pickle.dump(agg, f)
    return agg


def read_list(name):
    """word [frequency] per line, '#' comments."""
    path = os.path.join(HERE, name)
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if line:
                    p = line.split()
                    out[p[0]] = int(p[1]) if len(p) > 1 else None
    return out


_dic = None


def _init(base):
    global _dic
    from spylls.hunspell import Dictionary
    _dic = Dictionary.from_files(base)


def _check(w):
    try:
        if _dic.lookup(w):
            return True
        lw = w.lower()
        return lw.startswith("naj") and len(lw) > 5 and bool(_dic.lookup(lw[3:]))  # superlative
    except Exception:
        return False


def validate(words, base, cache_path, jobs):
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    todo = [w for w in words if w not in cache]
    if todo:
        t = time.time()
        with Pool(jobs, initializer=_init, initargs=(base,)) as pool:
            for i, res in enumerate(pool.imap(_check, todo, chunksize=500)):
                cache[todo[i]] = res
                if i and i % 100000 == 0:
                    print(f"  validated {i}/{len(todo)} ({time.time()-t:.0f}s)", file=sys.stderr, flush=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    return cache


def casings(variants, min_lower=0.15, min_upper=0.4):
    """Which spellings of a lower-case form to keep, from SNC casing counts -> {spelling: count}."""
    total = sum(variants.values())
    lw = next(iter(variants)).lower()
    lower = variants.get(lw, 0)
    upper = variants.get(lw.upper(), 0) if len(lw) > 1 else 0
    out = {}
    if lower / total >= min_lower:
        out[lw] = total - (upper if upper / total >= min_upper else 0)
        if upper / total >= min_upper:
            out[lw.upper()] = upper
    else:
        # a name or abbreviation: keep it exactly as it is most often written (Smer-SD, ObFZ, iPhone)
        cased = {v: c for v, c in variants.items() if v != lw}
        out[max(cased, key=cased.get)] = total
    return out


def sloppy_rate(counts, valid_lower, by_stripped, min_twin):
    """Median of count(plain invalid form) / count(its only valid accented twin)."""
    rates = []
    for s, twins in by_stripped.items():
        if s in valid_lower or len(twins) != 1:
            continue
        t = counts.get(twins[0], 0)
        if t >= min_twin:
            rates.append(counts.get(s, 0) / t)
    rates.sort()
    return rates[len(rates) // 2] if rates else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.path.join(HERE, ".cache"))
    ap.add_argument("--out", default=os.path.join(HERE, "build"))
    ap.add_argument("--min-snc", type=int, default=20, help="minimum SNC count for a candidate form")
    ap.add_argument("--min-subs", type=int, default=3, help="minimum subtitle count for a candidate form")
    ap.add_argument("--snc-weight", type=float, default=0.5, help="weight of SNC in the blended frequency (rest: subtitles)")
    ap.add_argument("--min-name", type=int, default=3000, help="SNC count from which an unknown proper noun is added automatically")
    ap.add_argument("--shadow-factor", type=float, default=2.5, help="drop a plain form when its count is below this many times the expected sloppy-typing leak in both sources")
    ap.add_argument("--twin-ratio", type=float, default=50, help="also drop a plain form when its accented twin is this many times more frequent")
    ap.add_argument("--bigrams-per-word", type=int, default=8)
    ap.add_argument("--min-bigram", type=int, default=10, help="minimum SNC count of a word pair")
    ap.add_argument("--no-bigrams", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    subs = {w: c for w, c in read_freq(f"{a.cache}/freq/sk_full.txt").items() if WORD_RE.match(w) and len(w) <= 40}
    snc = read_snc(a.cache)
    n_subs = sum(subs.values())
    n_snc = sum(sum(v.values()) for v in snc.values())
    snc_total = {lw: sum(v.values()) for lw, v in snc.items()}
    extra, offensive, block = read_list("extra_words.txt"), read_list("offensive.txt"), read_list("blocklist.txt")

    # --- 1+2: candidates with their spelling -------------------------------------------------------
    # form -> [snc count, subs count]
    forms = {}
    for lw, total in snc_total.items():
        if total >= a.min_snc or subs.get(lw, 0) >= a.min_subs:
            spellings = casings(snc[lw])
            main = max(spellings, key=spellings.get)
            for sp, c in spellings.items():
                forms[sp] = [c, subs.get(lw, 0) if sp == (lw if lw in spellings else main) else 0]
    subs_only = [w for w, c in subs.items() if c >= a.min_subs and w not in snc_total]
    for w in subs_only:
        forms[w] = [0, subs[w]]
    print(f"{len(forms)} candidate forms", file=sys.stderr, flush=True)

    # --- 3: validity ---------------------------------------------------------------------------------
    to_check = set(forms) | {w.capitalize() for w in subs_only}
    valid = validate(sorted(to_check), f"{a.cache}/hunspell/sk_SK", f"{a.cache}/validity2.json", a.jobs)
    for w in subs_only:   # subtitles are lower-cased: restore names Hunspell knows (peter -> Peter)
        cap = w.capitalize()
        if not valid[w] and valid[cap] and len(w) > 2 and cap not in forms:
            forms[cap] = forms.pop(w)

    good = {w for w in forms if valid.get(w) and w not in block}
    valid_lower = {w for w in good if w == w.lower()}

    # accented valid forms by their diacritic-free spelling
    by_stripped = defaultdict(list)
    for w in valid_lower:
        if DIA & set(w):
            by_stripped[strip_dia(w)].append(w)

    # --- 4: sloppy typing ----------------------------------------------------------------------------
    snc_c = {w: v[0] for w, v in forms.items()}
    subs_c = {w: v[1] for w, v in forms.items()}
    # plain invalid forms are needed for the estimate even if they are not candidates
    rate_snc = sloppy_rate({**snc_total, **{w: snc_c[w] for w in valid_lower}}, valid_lower, by_stripped, 100000)
    rate_subs = sloppy_rate({**subs, **{w: subs_c[w] for w in valid_lower}}, valid_lower, by_stripped, 5000)

    shadow_dropped, deflated = [], 0
    for s, twins in by_stripped.items():
        if s not in valid_lower:
            continue
        leak_snc = rate_snc * sum(snc_c[t] for t in twins)
        leak_subs = rate_subs * sum(subs_c[t] for t in twins)
        p_plain = a.snc_weight * max(0, snc_c[s] - leak_snc) / n_snc + (1 - a.snc_weight) * max(0, subs_c[s] - leak_subs) / n_subs
        p_twins = sum(a.snc_weight * snc_c[t] / n_snc + (1 - a.snc_weight) * subs_c[t] / n_subs for t in twins)
        sloppy_only = snc_c[s] <= a.shadow_factor * leak_snc and subs_c[s] <= a.shadow_factor * leak_subs
        if s not in extra and (sloppy_only or p_plain * a.twin_ratio < p_twins):
            shadow_dropped.append((s, snc_c[s], subs_c[s], max(twins, key=lambda t: snc_c[t] + subs_c[t])))
            good.discard(s)
            continue
        forms[s] = [max(0, int(snc_c[s] - leak_snc)), max(0, int(subs_c[s] - leak_subs))]
        deflated += 1
    # wrongly cased twins of accented words (subtitle "nam" -> Hunspell "Nam", really "nám")
    for w in list(good):
        if w != w.lower() and forms[w][0] == 0 and w.lower() in by_stripped:
            good.discard(w)

    # --- proper nouns Hunspell does not know, review candidates -----------------------------------
    cs_sub, en_sub = read_freq(f"{a.cache}/freq/cs_full.txt"), read_freq(f"{a.cache}/freq/en_full.txt")
    n_cs_sub, n_en_sub = sum(cs_sub.values()), sum(en_sub.values())   # Czech/English subtitles: noise filter only
    auto_names, candidates = [], []
    all_stripped = {strip_dia(w.lower()) for w in good}
    for w, (cs, cb) in forms.items():
        if valid.get(w) or w in block:
            continue
        if w != w.lower() and cs >= a.min_name and len(w) > 2:
            auto_names.append((w, cs))
        elif w == w.lower() and len(w) > 1 and strip_dia(w) not in all_stripped:
            score = a.snc_weight * cs / n_snc + (1 - a.snc_weight) * cb / n_subs
            foreign = max(cs_sub.get(w, 0) / n_cs_sub, en_sub.get(w, 0) / n_en_sub)
            if (cs >= 3000 or cb >= 100) and score >= 4 * foreign:
                candidates.append((w, cs, cb, score))
    good |= {w for w, _ in auto_names}

    # --- 5: blended frequency -------------------------------------------------------------------------
    def prob(w):
        cs, cb = forms[w]
        return a.snc_weight * cs / n_snc + (1 - a.snc_weight) * cb / n_subs

    probs = {w: prob(w) for w in good}
    probs = {w: p for w, p in probs.items() if p > 0}
    top = max(probs.values())

    def scale(p):
        return max(1, min(TOP_F, TOP_F - round(math.log(top / p) / STEP)))

    entries = {w: scale(p) for w, p in probs.items()}

    # --- 6: manual lists -------------------------------------------------------------------------------
    def manual(w, f, default):
        if f is not None:
            return f
        if w in entries:
            return entries[w]
        lw = w.lower()
        p = a.snc_weight * snc_total.get(lw, 0) / n_snc + (1 - a.snc_weight) * subs.get(lw, 0) / n_subs
        return scale(p) if p > 0 else default

    for w, f in extra.items():
        entries[w] = manual(w, f, 120)
    off = set()
    for w, f in offensive.items():
        entries[w] = manual(w, f, 100)
        off.add(w)
    for w in block:
        entries.pop(w, None)

    # --- 7: bigrams --------------------------------------------------------------------------------------
    bigrams = {}
    ngram_path = f"{a.cache}/snc/2gramy.txt.bz2"
    if not a.no_bigrams and os.path.exists(ngram_path):
        bigrams = read_bigrams(ngram_path, entries, off, snc_total, a)

    out = os.path.join(a.out, "main_sk.combined")
    n_bi = 0
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"dictionary=main:sk,locale=sk,description=Mäkčeň Slovak dictionary,date={int(time.time())},version=2\n")
        for w, fr in sorted(entries.items(), key=lambda x: (-x[1], x[0])):
            f.write(f" word={w},f={fr}" + (",possibly_offensive=true" if w in off else "") + "\n")
            for w2, bf in bigrams.get(w, ()):
                f.write(f"  bigram={w2},f={bf}\n")
                n_bi += 1

    with open(os.path.join(a.out, "candidates.txt"), "w", encoding="utf-8") as f:
        f.write("# Frequent lower-case forms Hunspell does not know: word, SNC count, subtitle count.\n# Copy the good ones to extra_words.txt.\n")
        for w, cs, cb, _ in sorted(candidates, key=lambda x: -x[3]):
            if w not in entries:
                f.write(f"{w}\t{cs}\t{cb}\n")
    with open(os.path.join(a.out, "auto_names.txt"), "w", encoding="utf-8") as f:
        f.write("# Proper nouns Hunspell does not know, added because they are frequent in SNC: word, SNC count.\n# Put unwanted ones into blocklist.txt.\n")
        for w, c in sorted(auto_names, key=lambda x: -x[1]):
            f.write(f"{w}\t{c}\n")
    with open(os.path.join(a.out, "dropped_plain_forms.txt"), "w", encoding="utf-8") as f:
        f.write("# Valid words without diacritics dropped in favour of an accented twin:\n# word, SNC count, subtitle count, twin.\n")
        for w, cs, cb, t in sorted(shadow_dropped, key=lambda x: -(x[1] + x[2])):
            f.write(f"{w}\t{cs}\t{cb}\t{t}\n")

    report = {
        "entries": len(entries),
        "bigrams": n_bi,
        "hunspell_valid_forms": len(good) - len(auto_names),
        "auto_names": len(auto_names),
        "manual_words": len(extra) + len(offensive),
        "candidates_for_review": len(candidates),
        "plain_forms_dropped": len(shadow_dropped),
        "plain_forms_deflated": deflated,
        "sloppy_typing_rate_snc": round(rate_snc, 5),
        "sloppy_typing_rate_subtitles": round(rate_subs, 5),
    }
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, indent=1))
    print("wrote", out)


def read_bigrams(path, entries, off, snc_total, a):
    """SNC 2-grams ("count<TAB>w1<TAB>w2" or "count w1<TAB>w2") -> {w1: [(w2, f)]}."""
    lower_entry = {}
    for w in entries:
        lw = w.lower()
        if lw not in lower_entry or w == lw:
            lower_entry[lw] = w

    def entry(tok):
        if tok in entries:
            return tok
        return lower_entry.get(tok.lower())

    pairs = defaultdict(lambda: defaultdict(int))
    t = time.time()
    proc = subprocess.Popen(["bzcat", path], stdout=subprocess.PIPE)
    n = 0
    for raw in proc.stdout:
        n += 1
        if n % 20000000 == 0:
            print(f"  2-grams: {n/1e6:.0f}M lines ({time.time()-t:.0f}s)", file=sys.stderr, flush=True)
        p = raw.decode("utf-8", "replace").split()
        if len(p) != 3 or not p[0].isdigit():
            continue
        c = int(p[0])
        if c < a.min_bigram:
            break   # the file is sorted by count, highest first
        w1, w2 = entry(p[1]), entry(p[2])
        if w1 and w2 and w2 not in off:
            pairs[w1][w2] += c
    proc.kill()
    proc.wait()

    # same log scale as unigrams, applied to P(w2 | w1)
    top_f_word = max(entries, key=entries.get)
    p_top = snc_total.get(top_f_word.lower(), 1) / sum(snc_total.values())
    out = {}
    for w1, nxt in pairs.items():
        c1 = max(snc_total.get(w1.lower(), 0), sum(nxt.values()))
        best = heapq.nlargest(a.bigrams_per_word, nxt.items(), key=lambda x: x[1])
        lst = []
        for w2, c in best:
            f = TOP_F - round(math.log(p_top / (c / c1)) / STEP) if c / c1 < p_top else 255
            f = max(entries[w2] + 1, min(255, f))
            lst.append((w2, f))
        out[w1] = lst
    return out


if __name__ == "__main__":
    main()
