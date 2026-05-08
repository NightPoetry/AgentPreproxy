# Proxy Layer: Transparency Handling for Special Tags

> **Companion documents**
> - The counting Tag mechanism itself: [Watchdog Implementation](watchdog_implementation.md)
> - Overall theory: [Main Paper](main_paper.md) (especially S5 on the proxy layer)
> - Mechanism taxonomy and terminology: [Mechanism Taxonomy](mechanism_taxonomy.md)

This document records the proxy layer's transparency handling for counting Tags (and other mechanism-layer internal protocol Tags). It belongs to the "proxy layer," strictly decoupled from the "core layer" -- the core layer is responsible for the mechanism itself (e.g., how counting Tags are used), while the proxy layer only ensures that the mechanism is completely invisible to the end user.

## 1. The Transparency Principle

**The user should not be able to perceive the mechanism layer's existence.** What they send in and what they get back should be identical to what they would experience without the proxy. Counting Tags are an internal protocol of the mechanism layer and must remain strictly inside that layer, with no leakage outward.

Formally, this translates into two **symmetric** escaping constraints:

1. **User input side**: When user input happens to contain Tag literals, the proxy must escape them before sending to the model.
2. **Model output side**: When the model needs to output Tag literals (as ordinary text, not as the mechanism's own counting), it must output the escaped version; the proxy unescapes them before sending back to the user.

As long as both symmetric constraints are satisfied, Tag literals appear on the entire round-trip path only within the "proxy <-> model" internal link. The external user never sees them.

## 2. The Model Must Be Informed of the Escaping Rules

The proxy layer has a prerequisite task: in the system prompt or injected instructions, it must explicitly tell the model --

> **"If you need to include this Tag's literal text in your output (as part of ordinary text), output the escaped version instead of the literal."**

This constraint must have high priority. The reason: once the model outputs an unescaped Tag literal, the proxy cannot distinguish between two things:

- This is a mechanism-layer counting Tag (should be consumed by the proxy, never forwarded to the user)
- This is a Tag string that the user expects to see as normal text in the output (should be forwarded to the user as-is)

When these two intents are mixed in the same sequence, the mechanism breaks. So this rule is not "advice" -- it is a **hard constraint**. It must be obeyed by the model as strictly as any output format constraint.

## 3. Escaping Must Cover All Input/Output Modes

Special Tag escaping cannot work only in free-text mode. **Every input or output channel where a Tag might appear must be covered**, including at minimum:

- Plain text output
- Streaming output
- Function Call argument bodies
- JSON mode (structured output)
- Tool-use parameters and return values
- Text segments within multimodal inputs

If escaping is missed on any single channel, the entire transparency guarantee is broken -- the user side will see mechanism-layer internal protocol literals, or the mechanism layer itself will be polluted by user input.

## 4. Specific Handling for JSON Mode

JSON mode deserves separate discussion because it involves rewriting the schema passed in by the user.

**Typical flow**:

1. The user passes in a JSON schema (describing the output structure they want).
2. The proxy inspects this schema: if a field's value could potentially contain Tag literals, the proxy **rewrites the schema or injects field-level constraints** before sending to the model -- requiring that all Tag characters in that field appear in escaped form.
3. The model outputs according to the modified schema; the result is JSON with escaped Tags.
4. Before sending the result back to the user, the proxy **unescapes** the relevant fields -- restoring escaped Tags to their literal form.
5. The JSON the user receives is identical to what they would get without the proxy: the structure is unchanged, the field values are clean literals.

**Key points**:

- From the user's perspective, the schema they passed in has not been altered and the JSON they receive has not been deformed -- transparency holds.
- From the model's perspective, the schema it receives and the JSON it actually outputs both follow the "Tags must be escaped" rule -- the mechanism-layer protocol is maintained.
- This flow -- "user's schema unchanged --> model actually sees a modified schema --> output is unescaped back to original" -- is the core of maintaining transparency in JSON mode.

Function Call and Tool Use argument bodies follow exactly the same pattern: the proxy performs symmetric escaping/unescaping on Tag characters in these channels.

## 5. Handling Streaming Output

Streaming output is a special case because the model emits one token at a time, and the proxy must perform boundary identification:

- If the current token stream constitutes a complete counting Tag --> the proxy consumes it; does not forward to the user.
- If the current token stream is an escaped Tag literal --> the proxy unescapes and forwards to the user.
- If the current token stream is other normal text --> forward directly.

A common practical complication: a Tag may span multiple tokens, requiring the proxy to perform buffering and boundary identification. This is an engineering implementation detail outside the scope of this document's principles, to be elaborated during concrete implementation.

## 6. Summary

The entire transparency constraint can be summarized in one sentence:

> **No matter what mode the user operates in or what content they send, they should not be able to perceive the proxy's existence.** Escape on the input side, unescape on the output side; counting Tags run inside the closed loop, and nothing is visible outside of it.

Only when this is satisfied can the mechanism layer (counting Tag watchdog, etc.) operate without disturbing the user while functioning normally. Transparency is the core value proposition of the proxy layer's existence -- and this is one of the reasons the "proxy + core" two-layer structure must be strictly decoupled: the core manages "what the mechanism does," the proxy manages "how the mechanism remains unseen."
