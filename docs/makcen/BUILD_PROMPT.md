# Build prompt

The standing brief for building Mäkčeň with Claude Code. Start a session with: *"Read docs/makcen/BUILD_PROMPT.md and continue with the next open item in docs/makcen/ROADMAP.md."*

## Goal
Mäkčeň is an Android keyboard for Slovak that beats Gboard and SwiftKey on three things users complain about: poor suggestions, autocorrect that mangles valid words, and no grasp of inflected forms. It is a public, non-commercial, GPL-3.0 fork of HeliBoard. The owner is a Slovak linguist and translator, not a full-time developer: explain decisions in plain language and leave linguistic judgement calls to him as reviewable lists, not hard-coded guesses.

## What "better" means
1. A valid Slovak word form is never autocorrected.
2. Text typed without diacritics comes out with them (`ziadne` → `žiadne`).
3. The first suggestion agrees with the sentence (`v novom` → `dome`, not `dom`).
Each claim must be backed by a number from `tools/makcen/evaluate.py` or an engine test, recorded in `docs/makcen/`.

## Constraints
- No internet permission, no telemetry, no cloud.
- All data must have a licence compatible with GPL-3.0 and be credited in the README. No Slovak National Corpus data unless its terms are confirmed to allow redistribution.
- Keep the diff against HeliBoard small so upstream changes can be merged: do not rename the `helium314.keyboard` code namespace, mark edits in upstream files with a `Mäkčeň:` comment, put new work in `tools/makcen/` and `docs/makcen/`.
- Nothing goes upstream to HeliBoard from an AI session.
- The Android build is verified by GitHub Actions (`Build debug APK`). A change to `app/` is not done until that workflow is green.

## How to work
1. Read `docs/makcen/ROADMAP.md`; take the first open item under "Next".
2. For anything touching the suggestion engine, plan first (architect agent), write the plan into `docs/makcen/`, then implement (builder agent).
3. Dictionary changes: edit the rules or lists in `tools/makcen/`, rebuild, run `evaluate.py`, and commit the new `main_sk.dict` together with the refreshed reports in `docs/makcen/`. Say what moved in the numbers.
4. One topic per commit, message in plain English.
5. Finish by updating the roadmap.

## Definition of done for v1.0
- Diacritics restoration ≥ 97% of tokens on a held-out Slovak text (not the training corpus).
- Zero autocorrections of Hunspell-valid forms in the engine test set.
- A week of the owner's daily use without switching back to another keyboard.
