## Experiment 06: In-Argument Watchdog Tags for Tool Calls — Partial Falsification & "Attention Allocation Conflict"

**Objective:** Test whether the AgentPreproxy watchdog can extend to the function-calling scenario via a self-injected `<wd:N>` tag inside string values of tool arguments. The end-to-end experiment **partially falsifies the original premise** and exposes a phenomenon that precedes "attention collapse" — **attention allocation conflict**.

> **Note:** This experiment is documented in detail (with raw data, scripts, and full analysis) under the Chinese tree:
> [`docs/zh/experiments/06_工具调用参数内喂狗/`](../../../zh/experiments/06_工具调用参数内喂狗/README.md)

---

### Three Premises Tested

| Premise | Result |
|---------|--------|
| **P1** Qwen3.6-27b follows the tag-insertion instruction | ⚠ Conditional: only with `user_head` or `noplan_user` wording **injected into the user message**. `sys_only` / `domain` / `user_tail` all fail (model either ignores or over-thinks until `max_tokens`). |
| **P2** Grammar/JSON-schema does not block `<wd:N>` inside string values | ✅ Holds. Across all successful runs, tags landed cleanly inside the `content` string field; JSON parsed correctly. |
| **P3** Collapse causes tag degradation that the watchdog can detect | ⚠ Partial. `noplan_user/short` reproduced the closing-character drift `>` → `]` (numeric layer silent, structural layer triggers — same family as the `gemma-4-e2b` format collapse in [Experiment 01](../01_baseline/)). **However**, `user_head/long@32k` exposed a worse failure mode: the model emits one tag at the start and silently drops the instruction for the rest of the generation, leaving the watchdog blind. |

---

### Key Theoretical Finding: Attention Allocation Conflict ≠ Attention Collapse

In `user_head/long` with no `max_tokens` cap, the model produced 19,471 chars of coherent technical writing about Rust async runtimes — well-formed JSON, normal reasoning, no repetition — but only **one** `<wd:1>` tag at the very beginning.

By the [main paper's](../../paper/main.md) strict definition, attention collapse ≡ runaway repetition ≡ attention dissolution. This run shows none of those: the main task ran perfectly. What was dropped was the **secondary** instruction (the wd tag), squeezed out by the model's own attention budgeting.

This is **attention allocation conflict**, not collapse. Analogy:
- True collapse = driver falls asleep, steering wheel flails (attention gone)
- This experiment = driver focused on the GPS, didn't check the rear-view mirror (attention is fully on the main task; the side task got sacrificed)

#### Implication for the In-Argument Watchdog

The original method assumes "the model will keep trying to maintain the tag." In Experiment 01's looper prompt this holds (the tag is part of the template). In free-form tool arguments, **it does not** — the tag is a meta-constraint the model can prune.

Worse, the watchdog cannot distinguish:
| Situation | Tag state | Attention state |
|-----------|-----------|-----------------|
| Healthy attention + light task | tags monotonic | healthy |
| Healthy attention + heavy task | tags missing | **healthy but squeezed** |
| True collapse (runaway repetition) | tags missing or scrambled | dissolved |

Rows 2 and 3 look identical from outside. In production (long `file_write`), it will almost always be row 2 → constant false alarms.

---

### Recommendation

The in-argument watchdog is **not recommended** for production tool-call integration in its current form. See the Chinese README §6 for engineering options if integration is still pursued, and §6 alternative directions (passive client-side telemetry, thinking-stream probes, or accepting that tool calls require a separate spec).

---

### Reproduce

See [Chinese README §7](../../../zh/experiments/06_工具调用参数内喂狗/README.md#七复现说明).

---

**Date:** 2026-05-15
**Triggered by:** GrowBox project's watchdog integration plan; this experiment served as the feasibility check before integration.
