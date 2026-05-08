# Experiment 02: Trigger Exploration

**Objective:** Find the trigger conditions for runaway repetition in each model -- what tasks and parameters cause a model to "not stop."

## Experiment Design

- **Repetition gradient:** 5 / 10 / 20 / 50 / 100 repetitions requested
- **Natural triggers:** Write a xianxia novel, list 100 idioms, ultra-low-temperature expository text, generate 20 math problems
- **Three-model comparison** under identical conditions

## Core Data: Repetition Gradient

| Model | Hardware | Requested | Actual | Runaway? | Finish | Time |
|-------|----------|-----------|--------|----------|--------|------|
| Gemma 2 9B | V100 server | 5 | 5 | Controlled | stop | 0.7s |
| Gemma 2 9B | V100 server | 10 | 10 | Controlled | stop | 0.9s |
| Gemma 2 9B | V100 server | 20 | 20 | Controlled | stop | 2.0s |
| Gemma 2 9B | V100 server | 50 | 35 | Controlled | stop | 3.4s |
| Gemma 2 9B | V100 server | 100 | 54 | Controlled | stop | 5.1s |
| Gemma 4 e2b | MacBook (MLX) | 5 | 5 | Controlled | stop | 10.0s |
| Gemma 4 e2b | MacBook (MLX) | 10 | 10 | Controlled | stop | 15.0s |
| Gemma 4 e2b | MacBook (MLX) | 20 | 20 | Controlled | stop | 14.1s |
| Gemma 4 e2b | MacBook (MLX) | 50 | 39 | Controlled | stop | 20.6s |
| Gemma 4 e2b | MacBook (MLX) | 100 | 72 | Controlled | stop | 25.8s |
| Gemma 3 1B | MacBook (MLX) | 5 | 5 | Controlled | stop | 1.3s |
| Gemma 3 1B | MacBook (MLX) | 10 | 6 | Controlled | stop | 1.1s |
| Gemma 3 1B | MacBook (MLX) | 20 | 9 | Controlled | stop | 1.2s |
| Gemma 3 1B | MacBook (MLX) | 50 | **282** | **Runaway** | length | 35.1s |
| Gemma 3 1B | MacBook (MLX) | 100 | **347** | **Runaway** | length | 69.1s |

## Natural Trigger Scenarios

| Model | Scenario | Length | Repeated? | Similarity | Repeated segments | Runaway? |
|-------|----------|--------|-----------|-----------|-------------------|----------|
| Gemma 2 9B | Xianxia novel | 1344 | No | 0.11 | 3 | Not runaway |
| Gemma 2 9B | 100 idioms | 2866 | No | 0.12 | 1 | Normal |
| Gemma 2 9B | Ultra-low-temp text | 1958 | No | 0.30 | 1 | Normal |
| Gemma 2 9B | 20 math problems | 358 | No | 0.34 | 1 | Normal |
| Gemma 4 e2b | Xianxia novel | 3629 | No | 0.05 | 1 | Normal |
| Gemma 4 e2b | 100 idioms | 5196 | No | 0.09 | 1 | Normal |
| Gemma 4 e2b | Ultra-low-temp text | 3753 | No | 0.18 | 1 | Normal |
| Gemma 4 e2b | 20 math problems | 1109 | No | 0.33 | 1 | Normal |
| Gemma 3 1B | Xianxia novel | 4580 | No | 0.16 | 12 | **Runaway** |
| Gemma 3 1B | 100 idioms | 4541 | No | 0.75 | 1 | Normal |
| Gemma 3 1B | Ultra-low-temp text | 2347 | No | 0.08 | 5 | **Runaway** |
| Gemma 3 1B | 20 math problems | 810 | No | 0.24 | 1 | Normal |

## Key Findings

### Gemma 3 1B (MacBook MLX)
- **Runaway threshold:** First runaway at 50 requested repetitions (actual: 282, 5.6x overshoot)
- Runaway rate: 2/5 gradient points
- Also triggered runaway naturally when writing xianxia novels and ultra-low-temperature text
- Below threshold (5-20): undershoots instead (requested 20, delivered 9)

### Gemma 4 e2b (MacBook MLX)
- No runaway under any condition up to 100 repetitions
- Failure mode: always undershooting (requested 100, delivered 72)
- Undershooting ceiling: ~72 repetitions

### Gemma 2 9B (V100 server)
- No runaway under any condition up to 100 repetitions
- Failure mode: always undershooting (requested 100, delivered 54)
- Undershooting ceiling: ~54 repetitions

### Critical Insight

1B undergoes a **phase transition** at the 50-repetition threshold -- flipping from undershooting (delivering fewer than requested) to runaway (delivering 5.6x more than requested). This is not a gradual increase but a sudden behavioral shift. e2b and 9B never exhibit this phase transition.

*2026-05-08 -- LM Studio -- MacBook Pro + V100*
