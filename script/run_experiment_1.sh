#!/usr/bin/env bash
set -e

# jump back to repo root (where svgdreamer.py lives)
cd "$(dirname "$0")"/..

# sketch style
# python svgdreamer.py \
#   x=sketch \
#   skip_sive=False\
#   "prompt='A tactile diagram of a butterfly. Raised-dot style, black and white.'" \
#   result_path=./logs/butterfly_sive_safe \
#   multirun=False \
#   diffuser.download=True


#  iconography
# python svgdreamer.py \
#   x=sketch \
#   skip_sive=False \
#   "prompt='A tactile diagram of a butterfly. Black and White. Simple. Coloring book style.'" \
#   token_ind=4 \
#   x.vpsd.t_schedule=randint \
#   +vpsd.num_iter=100 \
#   result_path=./logs/butterfly_quick \
#   multirun=False \
#   diffuser.download=True