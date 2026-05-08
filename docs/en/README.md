# AgentPreproxy Documentation (English)

## Papers

| File | Description |
|------|-------------|
| [main_paper.md](paper/main_paper.md) | Core: Runaway Repetition = A Logical Deadlock |
| [mechanism_taxonomy.md](paper/mechanism_taxonomy.md) | Framework: level-relativity, signal vs reflex mechanisms |
| [watchdog_implementation.md](paper/watchdog_implementation.md) | Engineering: counting Tag watchdog (strong/weak) |
| [proxy_transparency.md](paper/proxy_transparency.md) | Engineering: Tag escaping, JSON mode, streaming |

## Experiments

| Experiment | Description | Key Data |
|------------|-------------|----------|
| [01_baseline](experiments/01_baseline/) | 3 models × 7 scenarios | 1B runs away 65+ times vs e2b exact 5 |
| [02_trigger_explore](experiments/02_trigger_explore/) | Finding runaway triggers | 1B explodes to 282 at 50x request |
| [03_repetition_gradient](experiments/03_repetition_gradient/) | Precise behavior inflection points | 9B: 0 runaway (30/30) |
| [04_false_positive](experiments/04_false_positive/) | Naive truncation vs watchdog | **46% vs 0% false positive** |
| [05_lora_training](experiments/05_lora_training/) | Tag internalization via LoRA | 100 iter is the sweet spot |

- [Full Experiment Report](experiments/experiment_report.md)
- [Interactive Dashboard](experiments/index.html)
