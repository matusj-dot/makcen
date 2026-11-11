# Slovak dictionary pipeline

Builds `app/src/main/assets/dicts/main_sk.dict`, the bundled Slovak dictionary.

| File | What it is |
|---|---|
| `fetch_sources.sh` | Downloads source data and the dictionary compiler into `.cache/` (not committed). |
| `build_dictionary.py` | Frequency list + Hunspell validity → `build/main_sk.combined`. The rules are described at the top of the script. |
| `evaluate.py` | Measures diacritics restoration and coverage → `build/evaluation.md`. |
| `extra_words.txt` | Words added by hand (Hunspell gaps, colloquial words, abbreviations). |
| `offensive.txt` | Vulgar words: valid, but only suggested when the user allows it. |
| `blocklist.txt` | Forms that must never be in the dictionary. |

Outputs worth reading after a build:

- `build/candidates.txt` – frequent forms Hunspell does not know. Promote the good ones to `extra_words.txt`.
- `build/dropped_plain_forms.txt` – valid words without diacritics that were dropped so their accented twin gets restored (`zeny` → `ženy`, `mat` → `mať`). List a word in `extra_words.txt` to keep it.
- `build/auto_names.txt` – proper nouns Hunspell does not know, added because they are frequent in the corpus (Tóth, Reuters). Put unwanted ones into `blocklist.txt`.
- `build/evaluation.md` – the "biggest losses" table is the list of pairs that need sentence context (`byt`/`byť`).

Copies of the last committed build's reports live in `docs/makcen/`.

The downloads total about 700 MB. The first run validates ~880,000 forms with Hunspell and takes about twelve minutes on two cores; results are cached in `.cache/validity2.json`.

## Data licences

- Slovak National Corpus frequency lists (prim-11.0-public-all word forms and 2-grams): free download, no reuse terms stated on the page – confirmation requested from the corpus team
- FrequencyWords (OpenSubtitles 2018): CC BY-SA 4.0
- sk-spell Hunspell dictionary: GPL 2 / LGPL 2.1 / MPL 1.1
- Corpus counts for Czech and English are used only as a noise filter.
