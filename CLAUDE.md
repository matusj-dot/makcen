# Mäkčeň

Android keyboard for Slovak; a public GPL-3.0 fork of HeliBoard. Read `docs/makcen/BUILD_PROMPT.md` for the goal, constraints and way of working, and `docs/makcen/ROADMAP.md` for what is next.

## Layout
- `app/` – the HeliBoard app (Kotlin/Java + native C++ in `app/src/main/jni`). Code namespace stays `helium314.keyboard`; the application id is `sk.makcen.keyboard`.
- `app/src/main/assets/dicts/main_sk.dict` – the bundled Slovak dictionary, generated; never edit by hand.
- `tools/makcen/` – Python pipeline that builds and evaluates the dictionary.
- `docs/makcen/` – roadmap, build prompt, evaluation reports.

## Commands
- Dictionary (downloads ~700 MB on first run): `tools/makcen/fetch_sources.sh && python3 tools/makcen/build_dictionary.py && python3 tools/makcen/evaluate.py`
- Compile: `java -jar tools/makcen/.cache/dicttool/dicttool_aosp.jar makedict -s tools/makcen/build/main_sk.combined -d app/src/main/assets/dicts/main_sk.dict`
- App: `./gradlew assembleDebug` (needs the Android SDK and NDK; otherwise push and let the `Build debug APK` workflow do it)
- Tests: `./gradlew testRunTestsUnitTest`

## Rules
- Never autocorrect a valid Slovak word; a missing diacritic is not a typo.
- No internet permission.
- Mark edits in upstream HeliBoard files with a `Mäkčeň:` comment and keep them small.
- Only use data with a GPL-compatible licence, and credit it in `README.md`.
- Do not open issues or pull requests on HeliBoard.
- The owner is a Slovak linguist: put word-level decisions into the reviewable lists in `tools/makcen/`, and explain technical choices plainly.
