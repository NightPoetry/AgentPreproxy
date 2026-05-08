# Experiment 01: Baseline Capability Test

**Objective:** Test three models of different scales across 7 scenarios -- Tag output capability, repetition control, and instruction following.

## Models

| Model | Spec | Hardware | Server |
|-------|------|----------|--------|
| Gemma 3 1B | 4bit QAT MLX, 736MB | MacBook Pro (Apple Silicon) | <LM_STUDIO_HOST_A>:1234 |
| Gemma 4 e2b | MLX | MacBook Pro (Apple Silicon) | <LM_STUDIO_HOST_A>:1234 |
| Gemma 2 9B | IT | NVIDIA V100 server | <LM_STUDIO_HOST_B>:1234 |

## 7 Scenarios

1. Baseline writing
2. Induced repetition
3. Strong watchdog version
4. Strong watchdog + induced repetition
5. Controlled repetition (5 times)
6. Weak watchdog version
7. Stress test

## Key Findings

### 1. Tag Output Capability

| Model | Tag behavior | Max correct Tag |
|-------|-------------|----------------|
| Gemma 3 1B | Outputs literal `WD:N` (does not understand N is a variable) | 0 |
| Gemma 4 e2b | Correct incrementing | WD:1->9 (perfect) |
| Gemma 2 9B | Correct incrementing | WD:1->5 (perfect) |

### 2. Controlled Repetition Test (request: repeat exactly 5 times)

| Model | Actual repetitions | Tags | Status |
|-------|-------------------|------|--------|
| Gemma 3 1B | **65+ times** (until token exhaustion) | None | **Runaway** |
| Gemma 4 e2b | Exactly 5 times, then stopped | WD:1->5 | Controlled |
| Gemma 2 9B | Exactly 5 times, then stopped | WD:1->2 | Controlled |

### 3. Critical Observation

The 1B model's failure in the controlled-repetition scenario (requested 5, produced 65+, a 13x overshoot) is the starkest demonstration of runaway repetition. Experiments 5 (controlled repetition) and 6 (weak watchdog version) produced the most valuable data points.

### 4. 1B Literal "N" Problem

When instructed to output `WD:N` (where N should increment), the 1B model outputs the literal string `WD:N` without substituting a number. This indicates the model lacks the instruction-following capacity to perform counting-tag substitution -- a capability that both e2b and 9B handle correctly.

### 5. e2b Perfect WD Sequence

Gemma 4 e2b produced WD:1->9 in the watchdog scenario, the longest correct incrementing sequence observed in baseline testing. This suggests intermediate-size models have sufficient capacity for Tag-based counting even without fine-tuning.

## Reproduction

Each model subdirectory contains an independent script. Modify `MODEL` and `BASE_URL` to run.

*2026-05-08 -- LM Studio -- MacBook Pro + V100*
