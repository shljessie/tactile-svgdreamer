# Start the stopped container
sudo docker start svgdreamer

# Open an interactive shell inside it
sudo docker exec -it svgdreamer /bin/bash

# Inside the container, reload your shell setup
source /root/.bashrc

# Now list all conda environments
conda env list

conda activate svgrender



# refresh every 1 second
watch -n 5 nvidia-smi



# gpu check
sudo docker run --gpus all -it \
  --name svgdreamer \
  -v "$(pwd)":/workspace \
  ximingxing/svgrender:v1 \
  /bin/bash


<!-- Running Script Files -->
chmod +x baseline_experiment.sh
./baseline_experiment.sh