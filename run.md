
<!-- Remove Docker -->
sudo docker rm svgdreamer2


<!-- Start/Rerun Docker ENV -->

sudo docker run --gpus all -it --ipc=host \
  -v "$(pwd)":/workspace \
  --name svgdreamer2 \
  ximingxing/svgrender:v1 \
  /bin/bash


<!-- Inside the container -->

source /opt/conda/etc/profile.d/conda.sh
conda activate svgrender

<!-- (Don't repeat unless new file created) -->
pip install cairosvg
apt update && apt install -y libcairo2-dev


# then run SVGDreamer (from /workspace)
python svgdreamer.py \
  x=sketch \
  skip_sive=False \
  prompt="A tactile diagram of a butterfly. Raised-dot style, black and white." \
  image_size=256 \
  x.vpsd.num_iter=500 \
  result_path=./logs/butterfly_quick \
  multirun=False \
  diffuser.download=True
