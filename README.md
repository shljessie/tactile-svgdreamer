# Tactile SVG Optimization with Diffusion and RL

This repository demonstrates a lightweight, end-to-end pipeline for generating tactile-optimized SVGs from text prompts using a two-stage vectorization model (SIVE + VPSD) with reinforcement-style reward shaping. It is designed for accessibility-focused applications such as tactile graphics for blind and low-vision learners.

---

## 🧩 Overview

This project builds on the [SVGDreamer](https://github.com/) pipeline and introduces:

* A **custom tactile rendering style** in the SIVE stage (e.g., thicker strokes, minimal background)
* A **hybrid tactile reward function** combining [ImageReward](https://github.com/THUDM/ImageReward) with rule-based SVG metrics (stroke consistency, path simplicity, spacing, and background clarity)
* An **inference-time optimization loop** (VPSD) that uses this reward to refine SVGs via partial denoising updates
* A set of **ablation studies** evaluating the effect of hyperparameters such as reward strength and iteration count


## 📊 Results and Insights

### 🔁 Demonstration of an End-to-End Diffusion + RL Pipeline

By combining diffusion-based vectorization (SIVE) with reward-guided optimization (VPSD), this pipeline produces SVGs that are not only editable and aesthetically pleasing but also structured for tactile clarity. Applying a “tactile” style at the SIVE stage—removing clutter, boosting contrast, and simplifying shapes—already improves the output significantly. VPSD further refines the results by optimizing toward a reward function that blends visual quality and haptic legibility.


<img width="742" alt="Screenshot 2025-06-03 at 12 44 45 PM" src="https://github.com/user-attachments/assets/dffde8bf-1fec-4bf5-aeed-eb3ac57a5ba1" />

<img width="741" alt="Screenshot 2025-06-03 at 12 45 10 PM" src="https://github.com/user-attachments/assets/d7a748a1-4447-4478-a54a-a87f6a75b6f1" />

<img width="824" alt="Screenshot 2025-06-03 at 12 45 29 PM" src="https://github.com/user-attachments/assets/563ccf16-c2ea-49e5-a016-8621daa03db0" />

<img width="739" alt="Screenshot 2025-06-03 at 12 45 41 PM" src="https://github.com/user-attachments/assets/0e346ecb-4e1a-43a8-b61a-397508a7cd01" />


### ⚙️ Hyperparameter Tuning and Reward Trade-Offs

Ablation experiments show that both iteration count and reward weight play a critical role in SVG quality:

* At **500 VPSD steps**, outputs are still noisy and unrefined.
* At **1,000 steps**, the model converges to a clean, balanced output.
* At **5,000 steps**, the model overfits to tactile constraints, reintroducing complexity.

Similarly, increasing the tactile-reward weight improves structural clarity, but excessive emphasis can lead to artifacts. A moderate balance (e.g., 0.5) yields optimal results in most cases.

### 🌍 Broader Impact and Applications

This work provides a foundation for producing tactile-friendly diagrams that can be 3D printed, embossed, or used in digital tactile displays. The pipeline is also modular and extendable, offering practical guidance for researchers and developers looking to combine vector graphics, diffusion models, and reinforcement learning for accessibility or design automation.



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







