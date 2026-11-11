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
- `build/dropped_plain_forms.txt` – valid words without diacritics that were dropped so their accented twin gets restored (`zeny` → `ženy`). List a word in `extra_words.txt` to keep it.
- `build/evaluation.md` – the "biggest losses" table is the list of pairs that need sentence context (`byt`/`byť`).

Copies of the last committed build's reports live in `docs/makcen/`.

The first run validates ~380,000 forms with Hunspell and takes about six minutes; results are cached in `.cache/validity.json`.

## Data licences

- FrequencyWords (OpenSubtitles 2018): CC BY-SA 4.0
- sk-spell Hunspell dictionary: GPL 2 / LGPL 2.1 / MPL 1.1
- Corpus counts for Czech and English are used only as a noise filter.
