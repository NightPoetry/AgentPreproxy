# Mechanism Taxonomy and Layer Structure

> **Companion documents**
> - Main paper: [Main Paper](main_paper.md)
> - Engineering implementation: [Watchdog Implementation](watchdog_implementation.md)
> - Proxy transparency: [Proxy Transparency](proxy_transparency.md)

This document provides the framework support for the main paper. It does not directly argue "why AgentPreproxy is necessary" -- that is the main paper's job. This document only pins down the precise definition of "mechanism" as used in this series of papers:

1. A mechanism is defined relative to an analysis level (avoiding the infinite regress of "there's a mechanism inside every mechanism");
2. At a fixed analysis level, the word "mechanism" itself carries two distinct senses;
3. The internal structure of a complete mechanism decomposes into four layers;
4. From this, mechanisms are classified into two types -- signal mechanism vs reflex mechanism;
5. These mechanisms share a general principle: macroscopic attention redistribution.

The (A)/(B) naming, "reflex mechanism," "self-referential lockout," and other terms appearing in the main paper all derive their meanings from here.

## 1. "Mechanism" Is Relative to an Analysis Level

Before the word "mechanism" can be used, its boundary must be drawn -- otherwise a latent misreading lurks: every mechanism has sub-mechanisms inside it, so do we have to drill down to the atomic level before we reach a "real" mechanism?

This problem is genuine, but the resolution is clean.

Any "mechanism" has its own sub-mechanisms internally. A pain reflex arc is a mechanism, but the reflex arc itself consists of neuronal firing, ion channels, protein conformations -- further down, those are still mechanisms; keep going and you reach atoms or below, with no natural stopping point. This is not a gap in the argument; it is a necessary property of any layered model.

The only operational treatment is: **"mechanism" is not an absolute category but a category that exists relative to an analysis level.** In any analysis, first select an **agent** (subject), and then:

> **Mechanism = the layer below the agent, which the agent can neither perceive nor modify.**

Different level, different mechanism:

- At the "person vs their own body" level, the pain reflex arc is a mechanism (a person cannot turn it off).
- At the "cellular physiology" level, the reflex arc is no longer a mechanism -- it becomes the object of study, and the mechanism shifts down to ion channels.
- At the "molecular biology" level, ion channels also shift down, and the mechanism becomes protein folding.

The analysis level locked in for this paper series is fixed:

> **Agent = the model itself** (behavioral interface: prompt and token output).
>
> **Mechanism = everything the model can neither perceive nor modify** (proxy, Core, the underlying hardware... all sit at this layer).

Below the hardware there are more microscopic physical processes, but they are irrelevant to this paper's argument -- they do not form a direct interface with the model's "self-perception" or "prompt constraints." So this paper does not need to answer "what is a mechanism in the ultimate sense," only "from the model's perspective, what lies below its interface." This is a finite, operational question.

## 2. At the Locked-In Level, "Mechanism" Still Has Two Senses

After locking in the level, a second thing must be clarified: within the "mechanism layer," the word "mechanism" actually serves **two different structural roles**. Conflating them causes confusion; they must be separated.

**(Sense 1) Signal sense** -- providing the agent with a signal source it otherwise would not have. Example: a light sensor. Without it, the agent has no way of knowing that "light" exists. Its function is **to let the agent know**.

**(Sense 2) Forced sense** -- a coupling that bypasses the agent's cognition and automatically triggers a response. Example: biological pain. It not only provides a signal; it has a built-in reflex arc -- the signal reaches the spinal cord and directly drives muscle contraction, **before cognition even begins processing**. Its function is **to make the system act**.

Both senses are valid, but they characterize different structural properties:

- Sense 1 concerns "whether a signal pathway exists" -- without it, the agent simply cannot see the thing in question.
- Sense 2 concerns "whether the response bypasses the cognitive layer and is forced to occur" -- without it, the agent's cognitive layer may fail to receive, ignore, or react too late to the signal.

Note: **the two are not mutually exclusive; they can stack.** A light sensor carries only Sense 1. Biological pain carries both (it is both a new signal source and a built-in forced reflex). A **complete and robust** mechanism typically **contains both layers** -- first you must be able to know (Sense 1), then you can be forced to act (Sense 2).

Why draw this distinction: because Sense 1 alone is insufficient. In the failure state where the model's attention has already collapsed, feeding in another signal is pointless -- no one is home to receive it. Only Sense 2 (forced coupling) can truly close the loop. This point is pushed to its extreme in the deadlock argument of [Main Paper](main_paper.md) S3, and it is also the reason that the two-class split in S4 is necessary.

## 3. Internal Structure of a Complete Mechanism: Four Layers

Sections 1 and 2 respectively locked in the analysis level for "mechanism" and the two senses it carries at that level. Before splitting mechanisms into (A)/(B), the **internal structure of a single mechanism** must be laid out -- otherwise, when discussing "what determines whether a mechanism is (A) or (B)," elements from different layers will get tangled.

A complete mechanism decomposes into four layers:

| Layer | Name | Function | Example ("prevent robot from hitting a wall") |
| --- | --- | --- | --- |
| Layer 1 | **Invariant** | The goal to be guaranteed | "Must not collide with anything" |
| Layer 2 | **Indicator** | Quantifies the goal | "Distance < 5 cm counts as dangerous" |
| Layer 3 | **Sensor** | The means used to obtain the quantity | Light / sonar / lidar |
| Layer 4 | **Forced coupling** | What is automatically triggered once the quantity is obtained | Below threshold --> forced braking |

Each layer addresses a fundamentally different question:

- Layer 1 is **goal selection** -- what to protect.
- Layer 2 is **quantification standard** -- how to measure.
- Layer 3 is **engineering implementation** -- what to measure with. The same indicator can be realized by different sensors (light-based ranging / sonar-based ranging); this is engineering discretion, not a structural difference.
- Layer 4 is **the qualitative shift** -- whether a forced response exists. Layers 1 through 3 together only yield "able to know"; Layer 4 is what transforms it into "must act."

This layering corresponds to the two senses in S2:

- **Sense 1 (signal sense) = Layers 1-3**: with the invariant, indicator, and sensor, the agent "can know."
- **Sense 2 (forced sense) = Layer 4**: with forced coupling, the system "must act."

With this four-layer decomposition, the (A)/(B) classification in the next section becomes a one-sentence matter.

### Note: Swapping the Sensor Does Not Change the Category

The four-layer structure also resolves an easily confused question: **does a given sensor belong to (A) or (B)?**

The answer is: **the sensor itself belongs to neither (A) nor (B).** The (A)/(B) split classifies not sensors but **which layers the complete control loop includes**.

- Light sensor + main controller reads it and decides what to do --> the loop reaches only Layer 3; this is (A).
- Light sensor + below threshold triggers forced braking (bypassing the main controller) --> the loop reaches Layer 4; this is (B).

**The same sensor can be part of (A) or (B) -- what determines its classification is not the sensor itself, but what it is coupled to downstream.**

Similarly, substituting light-based ranging for sonar-based ranging is a swap within Layer 3 -- an engineering choice, not a classification difference.

A single invariant can also be supported by multiple parallel sensor chains (sensor fusion). This does not make it "multiple mechanisms" -- the invariant is one, the forced coupling is one; only the input end is jointly supplied by multiple sensors.

## 4. Two Classes Below the Mechanism Layer: Signal Mechanism and Reflex Mechanism

With the groundwork laid -- level-locking (S1), two senses (S2), four-layer structure (S3) -- the classification of the mechanism layer is clear. The core is a single sentence: **(A) contains only the first three layers; (B) contains all four.** Expanded:

**(A) Signal mechanism** -- contains only Layers 1-3 (invariant + indicator + sensor), without Layer 4. It gives the model a new signal pathway, letting it "know." The model must still use its own attention to act on that signal. A light sensor belongs to this class; injecting external material into the context (RAG-style approaches) also belongs to this class.

**(B) Reflex mechanism** -- contains all four layers. On top of the signal pathway in Layers 1-3, it adds Layer 4 -- a **forced coupling that fires without passing through the model's cognition**. Biological pain belongs to this class; runaway-repetition handling (probe + truncation + new-information injection) also belongs to this class -- the probe provides Layers 1-3, and truncation plus injection provide Layer 4.

So (B) is structurally an extension of (A): **any (B)-class mechanism already contains a (A)-class signal pathway inside it** (otherwise it would not know when to trigger); it simply adds Layer 4 -- forced coupling. **This additional forced coupling is the true source of the core property "mechanism = guaranteed enforcement."**

Both classes satisfy "runs outside the attention budget, cannot be modified by prompts," so both belong to the mechanism layer. But they solve different problems:

- (A) solves "signal absence." Its failure mode: when attention itself has collapsed, feeding in more signal does no good.
- (B) solves "signal present but unreceivedable." It adds Layer 4 on top of (A), taking the decision of "whether to act" away from the model and placing it externally.

Once this cut is clean, the example in the main paper slots into its correct position: runaway repetition is a (B)-class problem, but it is very easy to mistakenly think of it as (A) ("can't we just give the model a signal saying 'you're repeating'?"). If the wrong framework is applied, the argument stalls and the solution goes astray -- in a runaway-repetition scenario, the model's attention has already collapsed; signal alone is useless; Layer 4's forced coupling is required. The complete argument for runaway repetition is in [Main Paper](main_paper.md) S3.

## 5. Generalization: Macroscopic Attention Redistribution

The mechanism layer will ultimately house far more than just the runaway-repetition mechanism. In general, many similar small mechanisms need to be built: segment-by-segment checking, periodically pausing to see whether output is becoming repetitive, and so on.

These mechanisms share a common trait:

> **Replace a single monolithic expenditure of attention with many discrete, purpose-built actions.**

What monolithic attention cannot achieve, decomposed into discrete, purpose-specific checkpoints, can.

This is in fact **macroscopic attention redistribution**. Note: the entity performing the redistribution is not the model -- it is the mechanism-layer designer. The model cannot redistribute its own attention well (that is the very problem to be solved); the external mechanism pre-crystallizes "at what cadence and to which checkpoints to return," causing the model to repeatedly return to the right places at a fixed rhythm.

This principle applies to both (A) and (B) classes: (A)-class signal mechanisms can periodically inject specific checkpoint signals into the model at a set cadence; (B)-class reflex mechanisms can trigger external liveness verification at a set cadence. The mix varies by scenario, but the underlying pattern -- "fragmented, purpose-built actions replacing monolithic attention" -- is universal.
