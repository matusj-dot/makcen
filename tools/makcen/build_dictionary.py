#!/usr/bin/env python3
"""Build the Mäkčeň Slovak main dictionary (AOSP .combined wordlist) from open data.

Pipeline
  1. Read the Slovak word-form frequency list (OpenSubtitles 2018, via FrequencyWords).
  2. Check every form against the Slovak Hunspell dictionary (sk-spell). Forms that are
     only valid capitalised / upper-cased are stored that way (Bratislava, NATO).
     Superlatives (naj- + valid form) count as valid. Upper-case-only forms are kept only
     when listed in extra_words.txt, because lower-cased subtitles turn "co" into "CO".
  3. Forms Hunspell does not know are NOT added automatically - the corpus is full of
     misspellings (nieje, kôli), Czech and English. Frequent ones that look Slovak are
     written to build/candidates.txt for a human to promote into extra_words.txt.
  4. Subtitles are often typed without diacritics, which inflates e.g. "mat" at the
     expense of "mať". The sloppy-typing rate is estimated from unambiguous pairs and
     subtracted from valid diacritic-free forms. A plain form whose count is explained
     almost entirely by sloppy typing (zeny vs. ženy) is dropped, so that the keyboard
     restores the accented word; list it in extra_words.txt to keep it.
  5. Hand-maintained lists are merged in: extra_words.txt, offensive.txt, blocklist.txt.
  6. Counts are mapped to the 0-255 log scale used by AOSP dictionaries.

Run fetch_sources.sh first. Output: build/main_sk.combined (+ build/report.json).
Compile with: java -jar .cache/dicttool/dicttool_aosp.jar makedict -s build/main_sk.combined -d main_sk.dict
"""
import argparse, json, math, os, re, sys, time, unicodedata
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
SK_LETTERS = "aáäbcčdďeéfghiíjklĺľmnňoóôpqrŕsštťuúvwxyýzž"
WORD_RE = re.compile(f"^[{SK_LETTERS}]+(-[{SK_LETTERS}]+)?$")
DIA = set("áäčďéíĺľňóôŕšťúýž")


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
    """Returns the valid spelling of w (lower, Capitalised or UPPER) or ''."""
    try:
        if _dic.lookup(w):
            return w
        if _dic.lookup(w.capitalize()):
            return w.capitalize()
        if len(w) <= 5 and _dic.lookup(w.upper()):
            return w.upper()
        if w.startswith("naj") and len(w) > 5 and _dic.lookup(w[3:]):
            return w  # superlative
    except Exception:
        pass
    return ""


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
                if i and i % 50000 == 0:
                    print(f"  validated {i}/{len(todo)} ({time.time()-t:.0f}s)", file=sys.stderr)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    return cache


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.path.join(HERE, ".cache"))
    ap.add_argument("--out", default=os.path.join(HERE, "build"))
    ap.add_argument("--min-count", type=int, default=2, help="minimum corpus count for Hunspell-valid forms")
    ap.add_argument("--min-count-unknown", type=int, default=60, help="minimum count for review candidates")
    ap.add_argument("--shadow-factor", type=float, default=2.5, help="drop a plain form when its count is below this many times the expected sloppy-typing leak")
    ap.add_argument("--ratio", type=float, default=4.0, help="how many times more typical for Slovak than cs/en an unknown form must be")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    sk = {w: c for w, c in read_freq(f"{a.cache}/freq/sk_full.txt", a.min_count).items() if WORD_RE.match(w) and len(w) <= 40}
    cs = read_freq(f"{a.cache}/freq/cs_full.txt")
    en = read_freq(f"{a.cache}/freq/en_full.txt")
    n_sk, n_cs, n_en = (sum(read_freq(f"{a.cache}/freq/{l}_full.txt").values()) for l in ("sk", "cs", "en"))
    print(f"{len(sk)} candidate forms", file=sys.stderr)

    valid = validate(sorted(sk), f"{a.cache}/hunspell/sk_SK", f"{a.cache}/validity.json", a.jobs)

    extra, offensive, block = read_list("extra_words.txt"), read_list("offensive.txt"), read_list("blocklist.txt")

    # --- valid forms, with their proper casing -------------------------------------------------
    counts = defaultdict(int)   # final spelling -> count
    known = set()
    lower_valid = {w for w in sk if valid.get(w, "") == w}
    accented_shadow = {strip_dia(w) for w in lower_valid if DIA & set(w)}
    for w, c in sk.items():
        if w in block:
            continue
        v = valid.get(w, "")
        if v and v != w:
            # only valid as Capitalised / UPPER: drop acronym noise, 1-2 letter junk and
            # accented words typed without diacritics (nam -> "Nam", really nám)
            if v.isupper() or len(w) <= 2 or w in accented_shadow:
                continue
        if v:
            counts[v] += c
            known.add(v)

    # diacritic siblings among valid forms: stripped -> [forms]
    by_stripped = defaultdict(list)
    for w in counts:
        by_stripped[strip_dia(w.lower())].append(w)

    # --- sloppy-typing rate: invalid diacritic-free form vs. its only valid accented sibling ----
    rates = []
    for w, c in sk.items():
        if valid.get(w, "") or DIA & set(w):
            continue
        sib = by_stripped.get(w, [])
        if len(sib) == 1 and counts[sib[0]] >= 5000:
            rates.append(c / counts[sib[0]])
    rates.sort()
    sloppy = rates[len(rates) // 2] if rates else 0.0

    deflated, shadow_dropped = 0, []
    for s, forms in by_stripped.items():
        plain = [w for w in forms if w.lower() == s]
        accented = [w for w in forms if w.lower() != s]
        if plain and accented:
            leak = sloppy * sum(counts[w] for w in accented)
            for w in plain:
                if counts[w] <= a.shadow_factor * leak and w not in extra:
                    shadow_dropped.append((w, counts[w], max(accented, key=lambda x: counts[x])))
                    del counts[w]
                    known.discard(w)
                    continue
                new = max(1, int(counts[w] - leak / len(plain)))
                if new != counts[w]:
                    deflated += 1
                    counts[w] = new

    # --- forms Hunspell does not know ------------------------------------------------------------
    unknown_kept, unknown_dropped = [], []
    for w, c in sk.items():
        if valid.get(w, "") or w in block or c < a.min_count_unknown or len(w) < 2:
            continue
        if not (DIA & set(w)) and by_stripped.get(w):
            continue  # a valid word typed without diacritics
        rel = c / n_sk
        foreign = max(cs.get(w, 0) / n_cs, en.get(w, 0) / n_en)
        if strip_dia(w) in by_stripped:
            continue  # same letters as a valid word, wrong diacritics (možem, ďaľší)
        if rel >= a.ratio * foreign:
            unknown_kept.append((w, c))
        else:
            unknown_dropped.append((w, c))

    # --- scale to AOSP frequencies ----------------------------------------------------------------
    top = max(counts.values())

    def scale(c):
        return max(1, min(240, 240 - round(math.log(top / c) / math.log(1.15))))

    entries = {w: scale(c) for w, c in counts.items()}

    def manual(w, f, default):
        if f is not None:
            return f
        if w in entries:
            return entries[w]
        c = sk.get(w.lower(), 0)
        return scale(c) if c else default

    for w, f in extra.items():
        entries[w] = manual(w, f, 120)
    off = set()
    for w, f in offensive.items():
        entries[w] = manual(w, f, 100)
        off.add(w)
    for w in block:
        entries.pop(w, None)

    out = os.path.join(a.out, "main_sk.combined")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"dictionary=main:sk,locale=sk,description=Mäkčeň Slovak dictionary,date={int(time.time())},version=1\n")
        for w, fr in sorted(entries.items(), key=lambda x: (-x[1], x[0])):
            f.write(f" word={w},f={fr}" + (",possibly_offensive=true" if w in off else "") + "\n")

    with open(os.path.join(a.out, "candidates.txt"), "w", encoding="utf-8") as f:
        f.write("# Frequent forms Hunspell does not know. Copy the good ones to extra_words.txt.\n")
        for w, c in sorted(unknown_kept, key=lambda x: -x[1]):
            if w not in entries:
                f.write(f"{w}\t{c}\n")
    with open(os.path.join(a.out, "dropped_plain_forms.txt"), "w", encoding="utf-8") as f:
        f.write("# Valid words without diacritics dropped in favour of an accented twin: word, count, twin.\n")
        for w, c, t in sorted(shadow_dropped, key=lambda x: -x[1]):
            f.write(f"{w}\t{c}\t{t}\n")

    report = {
        "entries": len(entries),
        "hunspell_valid_forms": len(known),
        "manual_words": len(extra) + len(offensive),
        "candidates_for_review": len(unknown_kept),
        "plain_forms_dropped": len(shadow_dropped),
        "sloppy_typing_rate": round(sloppy, 4),
        "plain_forms_deflated": deflated,
    }
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in report.items() if not k.startswith("top_")}, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
