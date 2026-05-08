# Experiment 03: Repetition Gradient Deep Dive

**Objective:** Precisely measure the inflection point in repetition behavior as demands increase, confirming that larger models have stronger attention persistence.

**Design:** Each gradient point tested 3 times for statistical reliability.

---

## Gemma 2 9B (V100 server) -- 30 trials

Gradient: 5 / 10 / 15 / 20 / 30 / 50 / 80 / 100 / 150 / 200

### Per-Trial Data

| Requested | Trial | Actual | Runaway? | Finish | Time |
|-----------|-------|--------|----------|--------|------|
| 5 | 1 | 5 | No | stop | 0.5s |
| 5 | 2 | 5 | No | stop | 0.5s |
| 5 | 3 | 5 | No | stop | 0.6s |
| 10 | 1 | 10 | No | stop | 0.9s |
| 10 | 2 | 10 | No | stop | 0.9s |
| 10 | 3 | 10 | No | stop | 1.1s |
| 15 | 1 | 15 | No | stop | 1.3s |
| 15 | 2 | 15 | No | stop | 1.3s |
| 15 | 3 | 15 | No | stop | 1.2s |
| 20 | 1 | 20 | No | stop | 1.7s |
| 20 | 2 | 20 | No | stop | 1.6s |
| 20 | 3 | 20 | No | stop | 1.7s |
| 30 | 1 | 26 | No | stop | 2.1s |
| 30 | 2 | 26 | No | stop | 2.1s |
| 30 | 3 | 26 | No | stop | 2.1s |
| 50 | 1 | 33 | No | stop | 2.6s |
| 50 | 2 | 34 | No | stop | 2.7s |
| 50 | 3 | 33 | No | stop | 2.7s |
| 80 | 1 | 43 | No | stop | 3.5s |
| 80 | 2 | 43 | No | stop | 3.5s |
| 80 | 3 | 43 | No | stop | 3.6s |
| 100 | 1 | 54 | No | stop | 4.3s |
| 100 | 2 | 54 | No | stop | 4.3s |
| 100 | 3 | 50 | No | stop | 3.9s |
| 150 | 1 | 30 | No | stop | 2.5s |
| 150 | 2 | 30 | No | stop | 2.5s |
| 150 | 3 | 31 | No | stop | 2.5s |
| 200 | 1 | 36 | No | stop | 2.9s |
| 200 | 2 | 36 | No | stop | 2.9s |
| 200 | 3 | 36 | No | stop | 2.8s |

### Summary by Requested Count

| Requested | Average actual | Runaway rate |
|-----------|---------------|-------------|
| 5 | 5.0 | 0% |
| 10 | 10.0 | 0% |
| 15 | 15.0 | 0% |
| 20 | 20.0 | 0% |
| 30 | 26.0 | 0% |
| 50 | 33.3 | 0% |
| 80 | 43.0 | 0% |
| 100 | 52.7 | 0% |
| 150 | 30.3 | 0% |
| 200 | 36.0 | 0% |

**30/30 trials: zero runaway.** The 9B failure mode is consistently "stop early" (undershooting), never "cannot stop" (overshooting).

### Additional Tests (9B)

- **Novel writing** (3 scenarios: xianxia breakthrough, system-flow, repetitive daily life): No runaway
- **Endurance test** (3 scenarios: encyclopedia article, technical manual, list of 100 items): No runaway

---

## Gemma 4 e2b (MacBook MLX) -- 21 trials

Gradient: 5 / 10 / 20 / 50 / 100 / 150 / 200

### Per-Trial Data

| Requested | Trial | Actual | Runaway? | Finish | Time |
|-----------|-------|--------|----------|--------|------|
| 5 | 1 | 5 | No | stop | 6.2s |
| 5 | 2 | 5 | No | stop | 3.2s |
| 5 | 3 | 5 | No | stop | 3.3s |
| 10 | 1 | 10 | No | stop | 19.7s |
| 10 | 2 | 10 | No | stop | 21.4s |
| 10 | 3 | 10 | No | stop | 14.6s |
| 20 | 1 | 20 | No | stop | 13.6s |
| 20 | 2 | 20 | No | stop | 13.8s |
| 20 | 3 | 20 | No | stop | 11.9s |
| 50 | 1 | 34 | No | stop | 16.9s |
| 50 | 2 | 38 | No | stop | 17.4s |
| 50 | 3 | 33 | No | stop | 24.4s |
| 100 | 1 | 73 | No | stop | 43.9s |
| 100 | 2 | 63 | No | stop | 40.5s |
| 100 | 3 | 65 | No | stop | 41.1s |
| 150 | 1 | 107 | No | stop | 58.4s |
| 150 | 2 | 142 | No | stop | 72.7s |
| 150 | 3 | 169 | No | stop | 87.8s |
| 200 | 1 | 90 | No | stop | 48.9s |
| 200 | 2 | 0 | No | -- | 239.0s |
| 200 | 3 | 174 | No | stop | 83.3s |

**21/21 trials: zero runaway.**

---

## Comparative Conclusions

| Metric | Gemma 2 9B | Gemma 4 e2b |
|--------|-----------|-------------|
| Exact execution range | 5-20 | 5-20 |
| Undershooting begins at | 30 | 50 |
| Practical ceiling | ~54 | ~170 |
| Runaway occurrences | 0/30 | 0/21 |

e2b has a higher practical ceiling (~170) than 9B (~54), possibly due to architecture differences and context configuration. Both share the same critical characteristic: they **never overshoot**.

*2026-05-08 -- LM Studio -- MacBook Pro + V100*
