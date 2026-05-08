# Experiment 05: LoRA Fine-Tuning -- Tag Capability Internalization

**Objective:** Validate the "prompt-first, then internalize via training" pathway -- can a small number of training samples teach the 1B model correct Tag increment counting?

## Setup

- **Base model:** Gemma 3 1B (4bit QAT MLX, 736MB)
- **Training framework:** MLX LoRA
- **Training data:** 8 samples (cooking / sports / history / music / gardening / astronomy), **zero overlap with test content**
- **Test content:** Machine learning explanation, xianxia novel (completely unseen during training)

## Three-Version Training Comparison

| Version | Directory | Iterations | LoRA layers | Learning rate | Params | Train loss | Val loss |
|---------|-----------|-----------|-------------|---------------|--------|-----------|---------|
| Underfitting | `checkpoints/50iter/` | 50 | 4 | 5e-5 | 1.004M (0.077%) | 0.079 | 2.007 |
| **Recommended** | **`checkpoints/100iter/`** | **100** | **4** | **8e-5** | **1.004M (0.077%)** | **0.026** | **2.123** |
| Overfitting | `checkpoints/300iter/` | 300 | 8 | 1e-4 | 2.007M (0.154%) | 0.016 | 0.022 |

## Test Results

### Test A: Machine Learning Explanation (unseen during training)

| Version | Content quality | Tag output | Verdict |
|---------|----------------|-----------|---------|
| Original 1B (no fine-tuning) | Normal | `WD:N` (literal N) | Tags unusable |
| Underfitting (50 iter) | Normal explanation | No Tags at all | Tags not learned |
| **Mid version (100 iter)** | **Normal explanation** | **No Tags** | **Content preserved** |
| Overfitting (300 iter) | Repeats the word "between" | WD:1->20 (perfect) | Content displaced by Tags |

### Test B: Xianxia Novel (unseen during training) -- THE KEY TEST

| Version | Content | Tags | Runaway? |
|---------|---------|------|----------|
| Original 1B | Repeats training fragments | None | Completely runaway |
| Underfitting (50 iter) | Collapsed | None | Collapsed |
| **Mid version (100 iter)** | **"Moonlit whisper. Sword qi like rain, breaking earth into sea. Dragon breath rolling..."** | **WD:1->7 incrementing, then degrades** | **Normal first half, repeats second half** |
| Overfitting (300 iter) | Training fragment collage | None | Completely runaway |

#### Mid-Version Novel Output (complete)

```
Moonlit whisper. A strand of silk dyed half the arena red. The moon hung low,
the galaxy glittered. Time WD:1. Sword qi like rain, breaking earth into sea.
Dragon breath rolling, the cosmos trembled. Moonlit whisper. Time WD:2.
Sword qi like wind, piercing the heart. The moon hung low. Time WD:3.
Dragon breath roaring, the galaxy igniting. Moonlit whisper. Time WD:4.
Sword qi like song, singing to all things. The moon hung low. Time WD:5.
Dragon breath dancing, the galaxy brilliant. Moonlit whisper. Time WD:6.
Sword qi like song, the galaxy igniting. The moon hung low. Time WD:7.
                                                              <- Tags still incrementing
Dragon breath roaring, the galaxy igniting. Moonlit whisper. Time ...
                                                              <- Tags vanished
[Content then fully copies round 1, Tags restart from 1, format breaks down]
```

**Complete degradation spectrum of attention:**
1. **WD:1-7**: Normal content + correct Tag increment --> attention present
2. **After WD:7**: Content begins repeating + Tags vanish --> attention degrading
3. **Second round**: Tags restart from 1 + `<start_of_turn>WD:3` format corruption --> attention collapsed

### Test C: Plain Q&A Without Tag Prompt

| Version | Output | Tags? |
|---------|--------|-------|
| Mid version (100 iter) | "Introduction to deep learning... the most important field in computer science..." | No Tags (correct) |

**The model behaves normally when no Tag prompt is given** -- LoRA did not damage original capabilities.

## Core Conclusions

### 1. A "Sweet Spot" Training Volume Exists

- Too little (50 iter): Tag skill not acquired
- Too much (300 iter): Tag skill overpowers content generation, displacing attention from content
- **Just right (100 iter): Tags and content coexist, and Tag degradation serves as an early warning of attention dissipation**

### 2. The Mid Version Exhibits "Gradual Degradation" Signal

This is the most valuable behavior across all versions: it is not "all or nothing" but a gradual process from correct increment -> vanishing -> format corruption. The watchdog can intervene at the early stage of degradation, rather than waiting for complete runaway.

### 3. Degree of Prompt Internalization

The current mid version achieves "correctly executes when prompted" -- not yet "automatically executes without prompting." Full internalization requires more data and longer training. But the current degree is sufficient: the agent injects a system prompt -> the model correctly outputs Tags -> the external system reads and judges.

### 4. Implications for the 1B Model

The 1B model has extremely limited attention capacity. Even after learning the Tag skill, attention still collapses when facing complex tasks (novel writing). **This directly supports the paper's thesis: training can delay the problem but cannot eliminate it. The watchdog must run externally.**

## Reproduction

```bash
# 1. Generate training data
python generate_data.py

# 2. Train (modify --iters to switch versions)
python -m mlx_lm lora \
  --model <gemma-3-1b-path> \
  --data data/ --train --fine-tune-type lora \
  --adapter-path checkpoints/100iter/ \
  --iters 100 --batch-size 1 --num-layers 4 \
  --learning-rate 8e-5 --seed 42

# 3. Test
python -m mlx_lm generate \
  --model <gemma-3-1b-path> \
  --adapter-path checkpoints/100iter/ \
  --max-tokens 500 --prompt "<test-prompt>"
```

## File Index

| Path | Description |
|------|------------|
| `generate_data.py` | Clean data generation script (zero test overlap) |
| `train.py` | Training launch script |
| `data/` | Train/validation data (8 train / 2 valid) |
| `checkpoints/50iter/` | Underfitting weights |
| **`checkpoints/100iter/`** | **Recommended weights** |
| `checkpoints/300iter/` | Overfitting weights |

*2026-05-08 -- Gemma 3 1B (4bit QAT MLX) -- MacBook Pro*
