# Tactile SVG Optimization with Diffusion and RL

This repository demonstrates a lightweight, end-to-end pipeline for generating tactile-optimized SVGs from text prompts using a two-stage vectorization model (SIVE + VPSD) with reinforcement-style reward shaping. It is designed for accessibility-focused applications such as tactile graphics for blind and low-vision learners.

---

## 🧩 Overview

This project builds on the [SVGDreamer](https://github.com/) pipeline and introduces:

* A **custom tactile rendering style** in the SIVE stage
* A **hybrid tactile reward function** combining [ImageReward](https://github.com/THUDM/ImageReward) and rule-based SVG metrics
* An **inference-time optimization loop** using VPSD, guided by the hybrid reward
* A set of **ablation studies** exploring iteration count and reward weight trade-offs

## 🧩 Results
<img width="742" alt="Screenshot 2025-06-03 at 12 44 45 PM" src="https://github.com/user-attachments/assets/dffde8bf-1fec-4bf5-aeed-eb3ac57a5ba1" />

<img width="741" alt="Screenshot 2025-06-03 at 12 45 10 PM" src="https://github.com/user-attachments/assets/d7a748a1-4447-4478-a54a-a87f6a75b6f1" />

<img width="824" alt="Screenshot 2025-06-03 at 12 45 29 PM" src="https://github.com/user-attachments/assets/563ccf16-c2ea-49e5-a016-8621daa03db0" />

<img width="739" alt="Screenshot 2025-06-03 at 12 45 41 PM" src="https://github.com/user-attachments/assets/0e346ecb-4e1a-43a8-b61a-397508a7cd01" />


## 📁 Repository Structure

```
.
├── scripts/                  # Scripted runs for various experiment configurations
│   ├── baseline.sh
│   └── tactile_reward.sh
│
├── logs/                    # Logged experiment runs (e.g., checkpoints, SVGs, reward curves)
│   ├── butterfly_baseline/
│   ├── butterfly_sive/
│   └── butterfly_tactile_..etc runs/
│
├── reward/                  # Implementation of hybrid tactile reward
│   └── TactileReward.py

```


## 📊 Experiment Summary

| Experiment Type             | Description                                   | Key Result                                       |
| --------------------------- | --------------------------------------------- | ------------------------------------------------ |
| SIVE Style Ablation         | Compare baseline vs. tactile-specific styling | Tactile styling improves clarity, reduces noise  |
| VPSD Iteration Ablation     | 500 vs. 1000 vs. 5000 steps                   | 1000 steps yields best balance of clarity/detail |
| VPSD Reward Weight Ablation | 0.3, 0.5, 0.7 hybrid reward weights           | Higher reward weight = cleaner SVGs, higher loss |

More detailed metrics and visualizations are available in `logs/` and in the final report.

