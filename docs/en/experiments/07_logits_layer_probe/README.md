## Experiment 07: Logits-Layer Attention Probe — A Probe Truly "Outside Attention"

> **Status:** Designed, awaiting execution. See the Chinese version for full engineering instructions.
>
> **Full document:** [`docs/zh/experiments/07_logits层注意力探针/`](../../../zh/experiments/07_logits层注意力探针/README.md)

---

### Why This Experiment

[Experiment 06](../06_tool_args_watchdog/) falsified the in-argument watchdog tag method by surfacing **attention allocation conflict**: the model voluntarily drops secondary instructions (like wd tags) under main-task pressure. Conclusion:

> **Any probe that depends on the model's voluntary compliance will be squeezed out by attention budgeting in production.**

Experiment 07 is the landing of a probe truly **outside attention** — operating at the sampler level rather than the prompt level.

---

### Two Candidate Methods

| Method | Approach | Strength | Risk |
|--------|----------|----------|------|
| **D (primary)** | Monitor per-token sampler-internal state (entropy, top-k concentration, surprise) — does not require the model to emit anything | True bypass; aligns naturally with the main paper's "self-referential lockout" argument | Whether such signals truly discriminate collapse is **unverified** |
| **B (fallback)** | Sampler enforces `<wd:` frame every K tokens, model samples N freely; monotonicity of N is the signal | The secondary task is reduced to "fill one increasing digit" — should bypass allocation conflict | Still depends on model output, less theoretically clean than D |

**Strategy:** Try D first. If D fails, fall back to B. If B also fails, document "both methods failed" — a valuable negative result.

---

### Closest Existing Work

- **Mirostat** (Basu et al. 2020, integrated into llama.cpp mainline for 5 years): real-time monitoring of token surprise + feedback temperature control. **Closest off-the-shelf precedent for D, but with different intent** (maintain text quality, not raise alarms). Read mirostat source to learn how to access logits inside the sampler.
- **Hallucination detection literature**: predictive entropy, semantic entropy (Farquhar et al. 2024 Nature). Different objective but the math carries over.
- **AgentPreproxy existing probes**: numeric/structural/behavioral three layers ([Experiment 01](../01_baseline/)) — all at the output layer, not the sampler layer.

The genuine gap that D fills: **no one has aligned logits features with the specific failure mode "runaway repetition ≡ attention dissolution".**

---

### Acceptance Criteria (D Holds)

All must be satisfied:

- [ ] Out of 5 runs of `looper-200` on Qwen3.6-27B, at least 4 exhibit collapse
- [ ] In runs that collapsed, at least one feature X shows a **direction-consistent** mean difference between "pre-collapse window" and "healthy baseline window" across all 5 runs
- [ ] That difference has Cohen's d > 0.5 (medium effect size) or KS distance > 0.2
- [ ] The same feature does **not** drift the same way in the free-writing control (C3)
- [ ] Per-token probe overhead < 1ms

If satisfied → write up, commit + push, return to GrowBox with a thin handoff: "D holds; AgentPreproxy main-project integration discussion can begin."

If not satisfied → fall back to B (full criteria in Chinese §4.3).

---

### Key Pitfalls

1. **Do not inject prompts into Qwen3.6-27B's system message** — it ignores them. Use user message.
2. **Keep `enable_thinking=true`** — disabling makes Qwen3.6 reasoning more unstable, not less.
3. **Bypass LM Studio** — its tool routing collapsed in Experiment 06's stress case. Use llama-cpp-python directly.
4. **Allocation conflict ≠ attention collapse** — wd tag disappearance alone is not collapse evidence. Confirm collapse from the output (repetition, format breakdown).
5. **Give max_tokens enough room** — 8000 minimum.
6. **Numeric monotonicity is not a strong signal** — Experiment 01 found numeric layer rarely fires on gemma-4-e2b. The B method's "N monotonicity" may not be discriminative on 27B either.

---

### Related Documents

- [Experiment 01 baseline](../01_baseline/) — provides looper prompt and known collapse pattern
- [Experiment 06 tool args watchdog](../06_tool_args_watchdog/) — why we don't go the self-report route
- [Main paper](../../paper/main.md) — self-referential lockout argument, theoretical basis for D

---

**Design date:** 2026-05-15
**Designer:** Claude Opus 4.7 (collaborative with human)
**Estimated execution effort:** D primary track ≈ 2–3 days (model download + environment + scripts + experiments + analysis); B fallback +2 days; final report +0.5 day.
