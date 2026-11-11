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
echo "Sources ready in $(pwd)/.cache"
