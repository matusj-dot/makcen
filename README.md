# Mäkčeň

An Android keyboard built for Slovak. Private by design: no internet permission, everything stays on the phone.

Mäkčeň is a fork of [HeliBoard](https://github.com/HeliBorg/HeliBoard) (itself based on AOSP LatinIME / OpenBoard). HeliBoard does the keyboard; Mäkčeň adds what Slovak needs:

- **A Slovak dictionary of word forms, not lemmas** – about 220,000 inflected forms, each checked against the Slovak Hunspell dictionary, ranked by real-world frequency.
- **Diacritics restoration** – type `ziadne`, get `žiadne`.
- **No "correcting" of valid Slovak words** – an inflected form like `stoloch` is in the dictionary, so it is left alone.
- **Slovak first** – Slovak is the default language whatever the phone's system language is.

Status: early. See [docs/makcen/ROADMAP.md](docs/makcen/ROADMAP.md) for what is done and what is next, and [docs/makcen/dictionary-evaluation.md](docs/makcen/dictionary-evaluation.md) for measured results.

## Install

Debug builds are produced by GitHub Actions on every push to `main`: open the latest run under **Actions → Build debug APK** and download the `Makcen-debug` artifact.

## Build the dictionary

```
pip install spylls
tools/makcen/fetch_sources.sh
python3 tools/makcen/build_dictionary.py
python3 tools/makcen/evaluate.py
java -jar tools/makcen/.cache/dicttool/dicttool_aosp.jar makedict -s tools/makcen/build/main_sk.combined -d app/src/main/assets/dicts/main_sk.dict
```

Details: [tools/makcen/README.md](tools/makcen/README.md).

## Credits and licence

- Keyboard: [HeliBoard](https://github.com/HeliBorg/HeliBoard) and its contributors, GPL-3.0. The original README is kept in [docs/HELIBOARD_README.md](docs/HELIBOARD_README.md).
- Word frequencies: [FrequencyWords](https://github.com/hermitdave/FrequencyWords) by Hermit Dave, from OpenSubtitles 2018, CC BY-SA 4.0.
- Word validity: [Slovak Hunspell dictionary](https://github.com/sk-spell/hunspell-sk) by the sk-spell project, GPL / LGPL / MPL.
- Dictionary compiler: AOSP dicttool via [aosp-dictionary-tools](https://github.com/remi0s/aosp-dictionary-tools), Apache-2.0.

Mäkčeň is licensed under [GPL-3.0](LICENSE), like HeliBoard. Mäkčeň is an independent project: please report its problems here, not to HeliBoard.
