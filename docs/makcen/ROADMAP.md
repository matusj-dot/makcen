# Roadmap

## Done (v0.1)
- Fork of HeliBoard renamed to Mäkčeň, application id `sk.makcen.keyboard`, Slovak as the default language.
- Slovak dictionary pipeline (`tools/makcen/`) and a bundled `main_sk.dict` with ~220,000 validated word forms.
- Measured baseline: see `dictionary-evaluation.md`.
- CI builds a debug APK on every push to `main`.

## Next
1. **Test on a phone.** Install the debug APK, type for a week, note every wrong correction and missing word.
2. **Curate the word lists.** Review `candidates.txt` and `dropped_plain_forms.txt`; grow `extra_words.txt` and `offensive.txt`.
3. **Context for ambiguous pairs.** `byt`/`byť`, `ma`/`má`, `rad`/`rád` cannot be decided by a word list. Add bigrams to the dictionary (the AOSP format supports them) from a sentence-level corpus. Needs a corpus with clean licence: Slovak Wikipedia dump or OpenSubtitles raw text.
4. **Verify the engine, not just the model.** Add unit tests that run the real suggestion engine on diacritic-free input (HeliBoard has `SuggestTest`/`InputLogicTest` to build on).
5. **Diacritics-aware autocorrect cost.** Check how HeliBoard's native engine weighs a missing accent against a wrong letter; tune if `ziadne` ever loses to a non-accent neighbour.
6. **More data.** Subtitles are informal and translated; add a second frequency source (Wikipedia, news) and names of Slovak towns and people.
7. **Own identity.** App icon, store texts in `fastlane/`, release signing, F-Droid.
8. **Layout.** Decide on QWERTY vs QWERTZ default and whether a diacritics row helps.

## Principles
- Never "correct" a valid Slovak word.
- A missing diacritic is not a typo; restoring it must be cheap.
- No internet permission.
- Stay mergeable with HeliBoard: small, well-marked changes in upstream files; Mäkčeň's own work lives in `tools/makcen/` and `docs/makcen/`.
- Do not send AI-written issues or pull requests to HeliBoard (their `AI_USAGE.md` asks not to).
