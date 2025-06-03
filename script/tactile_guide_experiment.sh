#!/usr/bin/env bash
set -e

# jump back to repo root (where svgdreamer.py lives)
cd "$(dirname "$0")"/..

python svgdreamer.py \
  x=lowpoly \
  skip_sive=False \
  "prompt='A tactile graphic of a black and white butterfly diagram. The image should be simple and use only black and white. A tactile graphic is a graphic felt by touch the strokes should outline the key features. Remove excessive detail.'" \
  "neg_prompt='text, extra, missing, unfinished, watermark, signature, username, scan, frame, complex, detailed, intricate'" \
  result_path=./logs/tactile_butterfly_guide \
  seed=262 \
  multirun=False \
  diffuser.download=True