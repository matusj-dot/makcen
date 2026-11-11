#!/usr/bin/env bash
# Downloads the source data for the Slovak dictionary into tools/makcen/.cache (not committed).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .cache/freq .cache/hunspell .cache/dicttool
FW=https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018
for l in sk cs en; do
  [ -s .cache/freq/${l}_full.txt ] || curl -fsSL -o .cache/freq/${l}_full.txt "$FW/$l/${l}_full.txt"
done
HS=https://raw.githubusercontent.com/sk-spell/hunspell-sk/master
for f in sk_SK.aff sk_SK.dic; do
  [ -s .cache/hunspell/$f ] || curl -fsSL -o .cache/hunspell/$f "$HS/$f"
done
[ -s .cache/dicttool/dicttool_aosp.jar ] || curl -fsSL -o .cache/dicttool/dicttool_aosp.jar \
  https://raw.githubusercontent.com/remi0s/aosp-dictionary-tools/master/dicttool_aosp.jar
# Slovak National Corpus, prim-11.0-public-all: word forms (36 MB) and 2-grams (630 MB)
SNC=https://korpus.juls.savba.sk/files/prim-11.0
mkdir -p .cache/snc
[ -s .cache/snc/word_frequency.txt.bz2 ] || curl -fSL -o .cache/snc/word_frequency.txt.bz2 "$SNC/prim-11.0-public-all-word_frequency.txt.bz2"
[ -s .cache/snc/2gramy.txt.bz2 ] || curl -fSL -o .cache/snc/2gramy.txt.bz2 "$SNC/ngram/prim-11.0-public-all-2-gramy.txt.bz2"
echo "Sources ready in $(pwd)/.cache"
