# Context model prototype

A desktop experiment, not part of the app yet. Question: does a small language model that reads
the sentence so far restore diacritics better than the dictionary alone (`byt` / `byť`)?
If yes, the next step is putting it into the keyboard; if no, we stop here.

Everything runs on a PC without a graphics card.

## Setup (once)

```
cd tools/makcen/lm
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install tokenizers datasets numpy
```

## Run

```
python prepare_data.py          # downloads Slovak Wikipedia, ~10-20 minutes
python train.py --hours 3       # prints progress every 2 minutes; Ctrl+C stops and saves
python eval_restore.py          # the result table
```

- `train.py --resume --hours 5` continues from the saved model. Longer is better; overnight is fine.
- The model and data are stored in `tools/makcen/.cache/lm/` (not committed).
- `eval_restore.py` tests on sentences that were held out of training and compares the model
  with the dictionary on the same words. Send back its whole output.

## What the files do

| File | |
|---|---|
| `prepare_data.py` | Gets the text, sets 1% of articles aside for testing, trains the tokenizer (8,000 word pieces), encodes the text. `--text-file` uses your own text instead of Wikipedia. |
| `train.py` | Trains a GPT-2-style model with about 7 million parameters for a fixed time. |
| `eval_restore.py` | Strips diacritics from the test sentences and restores them word by word, left to right, choosing only among dictionary words. |
| `common.py` | The model itself. |
| `wordlist.tsv.gz` | The dictionary's words and frequencies, so the evaluation works without rebuilding the dictionary. |

## Status

Checked end to end on a tiny sample (87,000 words from the Universal Dependencies Slovak treebank,
five minutes of training) only to confirm the scripts run. The Wikipedia download step has not
been run yet. No real result exists until the model is trained on the full text.
