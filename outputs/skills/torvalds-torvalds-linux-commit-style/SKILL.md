---
name: torvalds-torvalds-linux-commit-style
description: Generate and rewrite git commit messages in the style inferred from torvalds's commits in torvalds/linux. Use when drafting commit messages, reviewing message quality, or converting raw change notes into a final commit message.
---

# Commit Message Workflow

1. Identify the change scope and expected behavior impact.
2. Draft the subject line using the style rules below.
3. Add body context only when rationale or constraints are needed.
4. Add trailers only when traceability requires them.
5. Run the quality checklist before finalizing.

# Style Rules

- Write a concise, technical subject line that focuses on the behavioral change.
  Rationale: Observed median subject length is about 19.5 characters.
- Start the actionable part of the subject with an imperative verb.
  Rationale: The corpus shows frequent imperative-leading subjects (proxy rate 0.35).
- Use a subsystem prefix (`subsystem: summary`) when the change is scoped.
  Rationale: Prefix usage appears common (rate 0.26).
- Include trailers only when they add review, fix, or sign-off traceability.
  Rationale: Trailer usage is non-trivial (rate 0.50).

# Anti-Rules

- Avoid vague subjects that describe effort instead of behavior.
  Rationale: The style tends to emphasize concrete technical effect.
- Avoid filler body text that repeats the subject without rationale.
  Rationale: Body content is most useful when it adds causal context.

# Tone

Summary: Technical, direct, and behavior-focused.

Do:
- State concrete effects
- Call out constraints and regressions
- Use plain technical language

Avoid:
- Marketing language
- Vague intent statements
- Unqualified certainty when uncertain

# Output Format

Subject: [optional subsystem:] imperative summary

Body: Explain why, then key constraints or caveats.

Trailers: Include only when needed for traceability.

# Quality Checklist

- Confirm subject describes behavior change, not implementation effort.
- Confirm wording is concrete and technically precise.
- Confirm body explains rationale when present.
- Confirm trailers are purposeful and correctly formatted.

# References

- See `references/style-profile.json` for quantitative corpus metrics.
- See `references/inference-guidelines.json` for extracted rules and evidence.
- See `references/commit-examples.md` for concrete style examples.
