# Roadmap

## Done (v0.1)
- Fork of HeliBoard renamed to Mäkčeň, application id `sk.makcen.keyboard`, Slovak as the default language.
- Slovak dictionary pipeline (`tools/makcen/`) and a bundled `main_sk.dict` with ~220,000 validated word forms.
- Measured baseline: see `dictionary-evaluation.md`.
- CI builds a debug APK on every push to `main`.

## Done (v0.2)
- Dictionary rebuilt from the Slovak National Corpus (written Slovak, correct capitalisation) blended with subtitles: ~460,000 word forms.
- 1.25 million word pairs (bigrams) from the corpus for next-word suggestions and context.
- Proper nouns frequent in the corpus are added automatically (`auto_names.txt`).

## Next
1. **Test on a phone.** Install the debug APK, type for a week, note every wrong correction and missing word.
2. **Curate the word lists.** Review `candidates.txt` and `dropped_plain_forms.txt`; grow `extra_words.txt` and `offensive.txt`.
3. **Confirm the corpus licence.** Ask the Slovak National Corpus team whether a dictionary derived from their frequency lists may be distributed in a GPL-3.0 app; if not, rebuild from subtitles only (`--snc-weight 0 --no-bigrams` needs a small script change) or from Wikipedia.
   **Context for ambiguous pairs** is now in the data (`chcem byť`), and HeliBoard's `Suggest.shouldBeAutoCorrected` does compare scores in the n-gram context even when the typed word is valid – but whether `byt` actually becomes `byť` after `chcem` must be checked on a phone.
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
