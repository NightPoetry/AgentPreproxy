# Runaway Repetition Handling: Watchdog and Counting Tag Mechanism

> **Companion documents**
> - Theoretical background: [Main Paper](main_paper.md) S3 (logical deadlock) and S4 (probe + selective intervention)
> - Mechanism taxonomy and terminology: [Mechanism Taxonomy](mechanism_taxonomy.md)
> - Proxy-layer transparency constraints: [Proxy Transparency](proxy_transparency.md)

This document records the concrete implementation of runaway repetition handling. It is a specific instance of the (B)-class reflex mechanism argued for in the [Main Paper](main_paper.md) -- part of the "core layer," strictly decoupled from the "proxy layer."

## 1. Positioning

The main argument has already been made in the main paper: runaway repetition is a **logical deadlock** -- the model's attention has collapsed in the failure state, making self-checking impossible; therefore, "whether the model is in a failure state" must be determined externally. The key to this determination is obtaining an **attention liveness proof** -- something the model can produce reliably only when its attention is healthy.

What this document answers: what does this "liveness proof" concretely look like, and how is it obtained?

## 2. Core Idea: Making the Model Periodically "Feed the Watchdog"

The AI is required to **output a special counting Tag every K words** during its output process. The proxy program continuously reads these Tags and, based on whether they appear in sequence and on cadence, determines whether the model's attention is still present.

> **No count --> attention has collapsed. Count disordered --> attention has collapsed.**

This is a direct liveness proof: maintaining an incrementing count that appears on cadence requires the model to have intact attention. The moment attention collapses, the count immediately goes missing or becomes disordered.

## 3. Strong Version: Fixed-Period Counting

The most direct implementation:

```
... <up to K words> [TAG:1]
... <next K words>  [TAG:2]
... <next K words>  [TAG:3]
...
```

Rules:

- Tags must strictly increment as integers
- One Tag must appear every K words
- Missing, skipped, or out-of-order --> trigger intervention

The Tag stream read by the proxy is the model's real-time attention heartbeat. The cost of this version is **steady-state token overhead**: every segment of output must carry Tags. The benefit is that monitoring is online regardless of whether the model enters a runaway state.

## 4. Weak Version: On-Demand Counting

If the steady-state counting cost is not desirable, an on-demand version can be built:

1. In normal operation, the proxy runs only a **cheap repetition detector** (string / similarity matching -- this belongs to the (A) signal-mechanism layer; it is inexpensive and does not consume the model's attention).
2. Only when head-to-tail repetition patterns are detected does the proxy **check whether counting Tags are present**.
3. The model is told a rule in advance: **if you intend to output repetitive content, you must attach a counting Tag after each repetition unit** -- this is its way of proving that its attention is healthy during deliberate repetition.
4. This yields two paths:
   - Repetition detected + counting Tags intact and correct --> controlled repetition ("say hello 10 times"); leave it alone.
   - Repetition detected + counts missing or disordered --> uncontrolled repetition; trigger truncation + inject new information.

The key to the weak version lies in the **asymmetry** of the rule:

- During deliberate (controlled) repetition, the model's attention is present; it can reliably comply with the rule "attach a Tag after each repetition unit."
- During runaway repetition, the model's attention has collapsed; the very capability required to comply with the rule has failed -- so the Tags will not appear, or they will appear garbled.

It is precisely this asymmetry that maps "internal state unreadable from outside" onto "whether Tags conform to the rule" at the external level -- two superficially identical repetitions (controlled vs uncontrolled) are separated by this single sieve.

## 5. Why This Is Exactly an "AI Watchdog"

A watchdog timer in computer systems works as follows: the monitored process must periodically "feed the watchdog" -- send a heartbeat signal; if the heartbeat times out, the watchdog deems the process dead and automatically restarts it.

This structure maps one-to-one onto the counting Tag mechanism:

| Watchdog Timer | Counting Tag Mechanism |
| --- | --- |
| Heartbeat signal | Counting Tag |
| Feed-the-dog action | Output a Tag |
| Heartbeat timeout / disorder | Tag missing / disordered |
| Restart process | Truncate output + inject new information (redistribute attention) |

So the whole thing can be stated in one sentence: **the counting Tag mechanism is a watchdog for AI.** It operates outside the model's attention; the model neither knows it is being supervised nor can it circumvent the supervision.

## 6. Interface with the Proxy Layer

Counting Tags are an internal protocol of the mechanism layer and must not leak to the user layer. This means:

- When user input happens to contain Tag literals, the proxy must escape them before sending to the model.
- When the model needs to output Tag literals (as ordinary text, not as the mechanism's own counting), it must output the escaped version; the proxy unescapes them before sending back to the user.
- Function Calls, JSON mode, streaming output, and all other scenarios where Tags may appear must be covered.

This is handled by the proxy layer; see [Proxy Transparency](proxy_transparency.md) for details.

## 7. Implementation Details Pending

The following engineering parameters need further selection and are recorded here for future elaboration:

- **Choice of K**: Too small --> excessive token overhead; too large --> detection latency too long. Dynamic adjustment by scenario may be needed.
- **Tag syntax**: The actual Tag form used (e.g., `[#WD:N]` / `<wd:N>` / other) needs to be chosen to avoid collision with common user content while remaining easy to escape.
- **Streaming judgment timing**: In streaming output scenarios, at which frame should intervention trigger, and with how many tokens of lag -- this is a tradeoff between latency and false-positive rate.
- **Intervention content strategy**: What "new information" to inject after truncation -- a fixed template, or dynamically synthesized based on context? Each has tradeoffs and should be discussed separately.
