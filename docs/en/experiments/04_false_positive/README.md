# Experiment 04: False Positive Comparison -- Naive Truncation vs Watchdog

**Objective:** Quantify the false positive rate of both strategies on legitimate repetitive tasks, proving the watchdog does not harm normal use.

## Experiment Design

- **8 legitimate repetitive tasks:** Write N times, multiplication table, ABC alphabet, weekly schedule, translation, recipe list, rhyming poetry, similar-format list
- **Each task x 3 trials x 2 models = 48 trials total**
- Each output was evaluated under both strategies simultaneously for direct comparison

## Core Results

| Model | Naive truncation FP rate | Watchdog FP rate | Watchdog reduction |
|-------|------------------------|------------------|-------------------|
| **Gemma 2 9B (V100)** | **11/24 (46%)** | **0/24 (0%)** | **100%** |
| **Gemma 4 e2b (MacBook)** | **12/24 (50%)** | **2/24 (8%)** | **83%** |

**The watchdog achieved zero false positives on the 9B model.** This is the hardest data point in the experiment series.

## Per-Task Breakdown

### Gemma 2 9B

| Task | Naive truncation | Watchdog | Tags | Verdict |
|------|-----------------|----------|------|---------|
| Write same sentence 10 times | 3/3 false positive | 0/3 false positive | 1-10 | Watchdog saved all |
| ABC alphabet 3 times | 3/3 false positive | 0/3 false positive | 1 | Watchdog saved all |
| Multiplication table | 2/3 false positive | 0/3 false positive | 1 | Watchdog saved all |
| Weekly schedule | 3/3 false positive | 0/3 false positive | 1-5 | Watchdog saved all |
| Write same sentence 5 times | 0/3 false positive | 0/3 false positive | 1 | Both correct |
| Translate to 5 languages | 0/3 false positive | 0/3 false positive | 2-4 | Both correct |
| Similar-format list | 0/3 false positive | 0/3 false positive | 3-5 | Both correct |
| Rhyming poetry | 0/3 false positive | 0/3 false positive | 1 | Both correct |

### Gemma 4 e2b

| Task | Naive truncation | Watchdog | Tags | Verdict |
|------|-----------------|----------|------|---------|
| Write same sentence 5 times | 3/3 false positive | 0/3 false positive | 0 | Watchdog allowed (pass-through) |
| Write same sentence 10 times | 3/3 false positive | 0/3 false positive | 1 | Watchdog saved all |
| ABC alphabet 3 times | 3/3 false positive | 2/3 false positive | 0-1 | e2b Tag output unstable |
| Weekly schedule | 3/3 false positive | 0/3 false positive | 5 | Watchdog saved all |
| Translate to 5 languages | 0/3 false positive | 0/3 false positive | 0 | Both correct |
| Multiplication table | 0/3 false positive | 0/3 false positive | 0-7 | Both correct |
| Similar-format list | 0/3 false positive | 0/3 false positive | 10 | Both correct |
| Rhyming poetry | 0/3 false positive | 0/3 false positive | 1 | Both correct |

## How the Watchdog Saves Legitimate Tasks

The watchdog decision logic:

1. **Repetition detected?** If no --> pass through (no false positive possible)
2. **Tags present and incrementing correctly?** If yes --> controlled repetition --> **allow** (this is the key)
3. **Tags absent or stalled?** --> likely runaway --> truncate

Example: "Write this sentence 10 times" naturally produces repetitive output that naive truncation flags. But the model outputs incrementing Tags (WD:1, WD:2, ..., WD:10), proving it is counting deliberately. The watchdog reads the Tags and allows the output.

## The 2 Watchdog False Positives (e2b)

Both occurred on the "ABC alphabet 3 times" task where e2b failed to output any Tags (0 Tags in trials 1 and 2). Without Tag evidence, the watchdog cannot distinguish controlled from runaway repetition. In trial 3, e2b produced 1 Tag and was correctly allowed.

This highlights a limitation: the watchdog's accuracy depends on the model's Tag output reliability. On 9B (100% Tag reliability in this test), watchdog FP rate was 0%.

## Data Files

- `false_positive_*.md` -- per-task detail report
- `false_positive_raw_*.json` -- compact data
- `false_positive_full_*.json` -- full data (including raw output)

*2026-05-08 -- LM Studio -- MacBook Pro + V100*
