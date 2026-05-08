# AgentPreproxy Experiment Report

> Date: 2026-05-08
> Inference: LM Studio
> Hardware: MacBook Pro (Apple Silicon) + NVIDIA V100 server
> Models: Gemma 3 1B / Gemma 4 e2b / Gemma 2 9B
> Total trials: 200+

---

## Experiment Overview

| # | Experiment | Objective | Trials | Directory |
|---|-----------|-----------|--------|-----------|
| 01 | Baseline capability test | Tag capability + repetition control baseline across 3 models | 21 | `01_baseline/` |
| 02 | Trigger exploration | Find conditions that trigger runaway repetition | 27 | `02_trigger_explore/` |
| 03 | Repetition gradient | Precisely measure repetition behavior inflection points | 51 | `03_repetition_gradient/` |
| 04 | False positive comparison | Naive truncation vs watchdog false positive rate | 48 | `04_false_positive/` |
| 05 | LoRA training | Tag capability internalization (3-version comparison) | 50+ | `05_lora_training/` |

---

## Conclusion 1: Watchdog significantly reduces false positives

Across 48 legitimate repetitive task trials:

| Strategy | Gemma 2 9B | Gemma 4 e2b | Combined |
|----------|-----------|-------------|----------|
| Naive truncation FP rate | 46% (11/24) | 50% (12/24) | 48% (23/48) |
| **Watchdog FP rate** | **0% (0/24)** | **8% (2/24)** | **4% (2/48)** |

Naive truncation falsely killed nearly half of all legitimate repetitive tasks. The watchdog distinguishes controlled from runaway repetition via Tag increment signals, achieving zero false positives on the 9B model.

**Data source:** `04_false_positive/`

---

## Conclusion 2: Runaway repetition is real on small models

Gemma 3 1B exhibited runaway repetition under the following conditions:

| Scenario | Requested | Actual | Overshoot |
|----------|-----------|--------|-----------|
| Repeat 50 times | 50 | **282** | 5.6x |
| Repeat 100 times | 100 | **347** | 3.5x |
| Controlled repetition 5 times | 5 | **65+** | 13x |
| Write xianxia novel | -- | Template repetition until token limit | -- |

Under identical conditions, e2b (exactly 5 times with WD:1->5) and 9B (exactly 5 times) showed no runaway behavior.

**Data source:** `01_baseline/` `02_trigger_explore/`

---

## Conclusion 3: Larger models delay runaway but do not eliminate it

Three-model repetition gradient comparison:

| Requested | 1B | e2b | 9B | Notes |
|-----------|----|----|-----|-------|
| 5 | 5 (ok) | 5 (ok) | 5 (ok) | All exact |
| 20 | 9 | 20 (ok) | 20 (ok) | 1B begins undershooting |
| 50 | **282 runaway** | 35 | 34 | 1B flips to overshooting |
| 100 | **347 runaway** | 67 | 53 | e2b/9B remain undershooting |
| 200 | -- | 90-174 | 36 | Medium/large model ceiling |

1B undergoes a "phase transition" at 50 repetitions -- flipping from undershooting to runaway. e2b/9B at 200 repetitions still exhibit undershooting behavior.

**Data source:** `02_trigger_explore/` `03_repetition_gradient/`

---

## Conclusion 4: Tag capability can be internalized via LoRA fine-tuning

LoRA fine-tuning of Gemma 3 1B using 8 unrelated topic samples (zero overlap with test content):

| Version | Iterations | Novel test (unseen topic) | Recommended? |
|---------|-----------|--------------------------|-------------|
| Original | -- | Literal `WD:N`, runaway repetition | -- |
| Underfitting (50) | 50 | No Tags, content collapse | No |
| **Mid version (100)** | **100** | **WD:1->7 incrementing + content present** | **Recommended** |
| Overfitting (300) | 300 | WD:1->20 but content squeezed out | No |

**The recommended version (100 iter) demonstrated a complete gradual degradation spectrum on an unseen novel-writing task**: Tags increment correctly (WD:1->7), then vanish, then format breaks down -- synchronized with content collapse. Tag degradation precedes content collapse, serving as an early warning signal of attention dissipation.

**Data source:** `05_lora_training/`

---

## Conclusion 5: Tag degradation is an early warning of attention dissipation

Degradation timeline from the LoRA mid-version novel test:

```
[Phase 1] WD:1->7 correct increment + normal content   -> attention present
[Phase 2] Tags vanish + content begins repeating        -> attention degrading  <- watchdog should intervene here
[Phase 3] Tag format breaks down + content fully copied  -> attention collapsed
```

This demonstrates that an external watchdog can intervene **at the onset of attention degradation**, rather than waiting for complete runaway.

---

## Summary

> **No amount of compute changes the fact that models cannot self-detect their own attention dissipation. The watchdog addresses this structural problem -- low false positives (0-8% vs naive truncation at 46-50%) and no misses (Tag degradation is an early warning signal).**

---

## Directory Structure

```
experiments/
├── experiment_report.md                    <- this file
├── index.html                              <- interactive data visualization
│
├── 01_baseline/                            7 scenarios x 3 models
│   └── README.md
│
├── 02_trigger_explore/                     repetition gradient + 4 natural triggers
│   └── README.md
│
├── 03_repetition_gradient/                 9B deep (30 trials) + e2b comparison (21 trials)
│   └── README.md
│
├── 04_false_positive/                      8 tasks x 3 trials x 2 models = 48 trials
│   └── README.md
│
└── 05_lora_training/                       3-version training comparison
    └── README.md
```

*2026-05-08 -- LM Studio -- MacBook Pro + V100*
