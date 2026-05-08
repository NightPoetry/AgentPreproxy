# AgentPreproxy Main Paper: Runaway Repetition = A Logical Deadlock

> **Companion documents**
> - Framework background (mechanism taxonomy, signal mechanism vs reflex mechanism, etc.): [Mechanism Taxonomy](mechanism_taxonomy.md)
> - Engineering implementation (counting Tag watchdog): [Watchdog Implementation](watchdog_implementation.md)
> - Proxy transparency: [Proxy Transparency](proxy_transparency.md)

## Core Argument

**While stronger compute can make a model aware of its own repetition in most cases, AgentPreproxy exists precisely for the moment when it cannot.**

> **No matter how much compute you add, under the current architecture there will always be a moment when the model cannot perceive its own repetition -- which is to say, cannot perceive that its attention has already collapsed.**

Why must this moment exist? Because:

> **When the model has the capacity to notice its own repetition, it does not repeat; once the model begins repeating, its attention has already collapsed.**

In other words, the resource the model needs in order to notice its repetition (attention) **is the very resource that has been depleted by the failure state**. This is a **structural logical deadlock** -- it cannot be closed from the inside. The term we use in this paper is **self-referential lockout**: the evaluator and the object being evaluated are the same resource; once the failure has exhausted that resource, evaluation becomes impossible, and the system is locked from within.

From this follows the single most important corollary of this paper:

> **Even if a magical training method perfectly installs repetition detection inside the model, it would be useless against runaway repetition -- because the failure state IS the state where the detector's required resource has been depleted.**

This corollary establishes the **irreplaceability** of AgentPreproxy with respect to this problem. What it addresses is not a temporary shortfall in compute, but a structural issue that persists regardless of how compute scales or how training methods improve. The entire paper is built around this single sentence.

## 1. Software Positioning

AgentPreproxy is a secondary proxy for AI -- a local, secondary proxy whose purpose is to strengthen AI execution capability. It can be inserted directly in front of any agent software to provide preprocessing. Internally it is divided into a proxy layer and a core-function layer, strictly decoupled from each other so that each can be updated independently.

## 2. Problem Landscape: Controlled vs Uncontrolled Repetition

Before discussing uncontrolled (runaway) repetition, it must be distinguished from "controlled repetition" -- otherwise the logic of the solution collapses.

**Some repetition is controlled. For example, if you ask the model to say "hello" ten times, that repetition is controlled -- after ten iterations it stops, fully aware of what it is doing.** In contrast, **when a small model "falls into" repetition, its attention has effectively failed.**

**These two kinds of repetition may be completely indistinguishable at the surface of the text** -- both are simply the same passage appearing N times. The difference lies entirely in internal state: whether attention is present. This internal state cannot be read from the outside; all the outside can see is the output text itself.

A naive strategy -- "truncate whenever repetition is detected" -- sweeps both kinds into the same bucket, killing controlled repetition along with uncontrolled. This is precisely what cannot be tolerated: **brute-force truncation disables the model's controlled repetition as well.** An anti-repetition strategy that kills legitimate use cases violates the very baseline of reliability.

So the problem is not "how to detect repetition" -- repetition is visible on the surface. The real problem is **"how to tell whether a given stretch of repetition is controlled or uncontrolled."** This is equivalent to answering: **"Is the model's attention still present right now?"**

False positive rates illustrate the stakes concretely: naive truncation kills 46--50% of legitimate tasks; the watchdog approach kills 0--8%.

## 3. Why It Cannot Be Solved from the Inside -- The Logical Deadlock

The critical insight at this step is that asking the model itself to answer "is my attention still present?" is **impossible in principle**.

### 3.1 The Deadlock Structure

Stated plainly:

> **The model genuinely cannot notice that it is repeating. This is a logical deadlock.**

Expanded into two clauses:

- **When the model has the capacity to notice its own repetition, it does not repeat;**
- **Once the model begins repeating, its attention has already collapsed.**

These two clauses are not sequential cause-and-effect, nor are they two sides of the same coin -- they describe **the same event**. "Uncontrolled repetition is occurring" and "attention has collapsed" point to a single internal event: uncontrolled repetition is the surface manifestation of attention collapse.

One more decomposition step reveals why the loop cannot be closed from inside:

- The model's attention wants to check "is attention still present?";
- This check **itself requires attention to execute**;
- Therefore: **the resource the detector depends on is the very object it is evaluating.**

Resource present --> can detect --> no problem --> no need to detect. Resource absent --> cannot detect --> problem occurring --> detection most needed, yet precisely impossible.

The consequence of this structure is hard: **for the model to notice from the inside that it is in runaway repetition is impossible by definition.** Not "difficult" -- **self-referential lockout** (this paper's term: the evaluator and the object being evaluated are the same resource; once the failure exhausts that resource, evaluation is impossible, locked from within). The resource needed for this detection (attention) is the very resource the failure has consumed.

By the same logic, **the prompt has become a dead zone at this point** -- prompts depend on attention, and attention is no longer present. So "adding a line to the system prompt saying don't repeat" is equally ineffective.

### 3.2 Stronger Compute Does Not Solve This

The hard substance of the deadlock is here: **it has nothing to do with the model's overall capability level.**

Stronger compute can help the model maintain attention more stably during normal operation, execute controlled repetition more precisely, and reason more deeply on complex tasks -- all of which are improvements within the "attention-healthy" state. But runaway repetition is not about the "attention-healthy" state; it is about the **"attention-has-already-collapsed" state**. In that state, no matter how much compute has been installed or how perfectly the model has been trained, the runtime environment itself is gone.

From this we can give the corollary in its complete form:

> **Even if a magical training method perfectly installs repetition detection inside the model, it would be useless against runaway repetition -- because the failure state IS the state where the detector's required resource has been depleted.**

AgentPreproxy's value on this problem is therefore **permanent**: it addresses not a temporary weakness of current models, but a structural blind spot that the current architecture necessarily leaves behind.

## 4. The Solution: External Probe + Selective Intervention

Since the loop cannot be closed from inside and no amount of compute can help, the shape of the solution is determined by negation:

> **We only intervene when the model's attention has collapsed.**

How do we determine whether the model's attention is still present? Since the model itself cannot report "which state I am in" (this is precisely what the deadlock forbids), we force it to externally manifest the answer -- **by requiring it to produce additional output that proves its attention is still healthy, thereby determining whether it is capable of noticing its own repetition.**

This additional output is, in essence, a "liveness proof" for attention. Its role is not to detect "whether repetition is happening" -- repetition is visible to the naked eye -- but to detect **whether, at the moment this repetition was produced, attention was still present.**

With this, the same surface-level "repetition" can be sorted into two bins based on the state of the probe:

- Probe normal --> controlled repetition; leave it alone.
- Probe failed --> uncontrolled repetition; **truncate and inject new information to redistribute attention.**

The "inject new information" step is critical -- **truncation alone is not enough**, because the next segment may continue in the collapsed state. New information is injected to **redistribute attention**, pushing the model out of the collapsed state and back into a workable one.

> The engineering implementation of this approach is a **counting Tag watchdog** -- the model outputs incrementing special Tags at a fixed cadence, and the proxy reads them to determine attention liveness. The strong and weak versions of this scheme are detailed in [Watchdog Implementation](watchdog_implementation.md).

### External Implementation and Internal Training: The Same Path

This watchdog has two implementation paths:

**(1) External implementation** -- what AgentPreproxy currently does: leveraging the model's own generalization capability, using prompt injection to make the model output counting Tags, read and evaluated by an external proxy. No modification to the model itself is needed; cost is low, iteration is fast.

**(2) Internal training** -- internalizing the watchdog as an end-to-end training objective within the model, teaching it to output a signal indicating "whether my attention is still healthy right now." This amounts to training the model to develop built-in self-awareness -- knowing when it "doesn't know anymore," when it is "fatigued," when its "attention has drifted."

The relationship between these two paths mirrors the developmental history of reasoning capability: the earliest chain-of-thought reasoning was a single prompt -- "let's think step by step"; once validated as effective, the approach was trained into the model and became native reasoning ability. The watchdog can follow the same path -- first validated externally via prompts, then internalized as a training signal.

AgentPreproxy chooses the external implementation first in order to validate the core logic at the lowest possible cost.

## 5. Architecture: Why "Proxy + Core" as a Two-Layer Design

AgentPreproxy's "proxy + core, strictly decoupled" structure is not an engineering preference -- it is derived directly from the preceding argument:

- **Proxy layer** -- intercepts traffic. This is inherently an action that occurs outside the model's attention budget.
- **Core layer** -- determines "whether the model can currently self-check" and intervenes when necessary. This too must run outside the model's attention.

Both layers must live outside the model's attention, so they remain external together; and because they concern different things (one handles communication, the other handles state evaluation), they are strictly decoupled for independent updates.

> The specific constraints on proxy-layer transparency (input escaping / output unescaping / Function Call and JSON mode coverage, etc.) are detailed in [Proxy Transparency](proxy_transparency.md).

## 6. Conclusion

AgentPreproxy's value in addressing runaway repetition is **structural and permanent**: it handles a moment of attention collapse that necessarily exists under any current architecture, and that moment cannot be resolved from inside the model no matter how strong the compute or how good the training. The entire argument of this paper serves a single sentence:

> **No amount of compute changes the fact that "when attention collapses, the model itself cannot perceive it." This is the one and only problem AgentPreproxy exists to solve.**
