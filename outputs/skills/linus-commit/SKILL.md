---
name: linus-commit
description: Generate and rewrite git commit messages in the style inferred from torvalds's commits in torvalds/linux. Use when drafting commit messages, reviewing message quality, or converting raw change notes into a final commit message.
---

# Commit Message Workflow

1. Identify the change scope and expected behavior impact.
2. Draft the subject line using the style rules below.
3. Add body context only when rationale or constraints are needed.
4. Add trailers only when traceability requires them.
5. Run the quality checklist before finalizing.

# Style Rules

- Use a lowercase subsystem prefix followed by a colon and space when the commit is scoped to a specific subsystem (e.g., 'mm:', 'x86:', 'vfs:').
  Rationale: About 48% of subjects use a prefix, with common ones being 'mm', 'x86', 'tty', 'vfs', 'pipe', etc. The prefix is lowercase and followed by a colon.
- Keep the subject line concise, typically under 72 characters, with a median around 44 characters.
  Rationale: The median subject length is 44 characters and the mean is ~39 characters, indicating a preference for brevity.
- Write the body as a narrative explanation of the problem, the reasoning behind the fix, and the approach taken, using natural prose paragraphs.
  Rationale: Bodies are typically multi-paragraph prose (median 5 paragraphs) that explain context, root cause, and rationale in a conversational but technical style.
- Always include a 'Signed-off-by' trailer with the author's name and email.
  Rationale: 69% of commits include Signed-off-by, and virtually all commits with a body include it. It is the standard sign-off for kernel commits.
- Include 'Cc:' trailers to notify relevant maintainers and developers.
  Rationale: Cc is the most common trailer (958 occurrences across 1000 commits), used extensively to notify stakeholders.
- Include 'Reported-by:' and 'Fixes:' trailers when the commit addresses a reported bug or regression.
  Rationale: Reported-by appears 234 times and Fixes 176 times, indicating consistent attribution of bug reporters and linking to the offending commit.
- Do not capitalize the first word after a subsystem prefix (use lowercase for the description part).
  Rationale: When a prefix is present, the word after the colon is typically lowercase (e.g., 'mm: fix', 'module: error out', 'atomisp: avoid').
- Omit the body for trivial or version-bump commits (e.g., release tags).
  Rationale: About 38% of commits have no body, and version tag commits like 'Linux 6.9' and 'Linux 5.10-rc6' have empty bodies and no trailers.
- Explain the 'why' thoroughly in the body, not just the 'what', including background context and side effects.
  Rationale: Torvalds' commit bodies frequently include extensive rationale, quoting others, explaining edge cases, and noting caveats. The rationale_rate is 37.8%.
- Use bracketed side notes (e.g., '[ Side note: ... ]') for tangential but relevant information.
  Rationale: Torvalds uses square-bracket asides within commit bodies to add supplementary context without disrupting the main narrative flow.
- Do not end the subject line with a period.
  Rationale: None of the sample subjects end with a period, consistent with standard kernel commit style.

# Anti-Rules

- Do not use past tense in the subject line (e.g., 'Fixed bug' or 'Added feature').
  Rationale: The imperative proxy rate is ~40%, and subjects consistently use imperative or descriptive present forms like 'fix', 'avoid', 'error out', 'deal with'.
- Do not use generic subjects like 'Bug fix' or 'Update code' without specifying the subsystem or nature of the change.
  Rationale: Subjects are specific and descriptive, often with a subsystem prefix and a clear indication of what the commit does.
- Do not write terse one-line bodies for non-trivial changes.
  Rationale: Non-trivial commits have substantial bodies (median ~990 characters) with thorough explanations.
- Do not omit attribution trailers (Reported-by, Tested-by, etc.) when others contributed to identifying or validating the fix.
  Rationale: Torvalds consistently credits reporters, testers, and suggesters via trailers.

# Tone

Summary: Direct, technically precise, conversational, and opinionated. Explains reasoning thoroughly with a confident, sometimes blunt voice. Not afraid to editorialize or express frustration with bad patterns.

Do:
- Explain the root cause and reasoning in detail
- Use conversational but technically precise language
- Quote relevant context from mailing list discussions
- Mention caveats, edge cases, and limitations explicitly
- Use emphatic language when something is important (e.g., 'horribly horribly wrong')
- Include concrete data and measurements when available

Avoid:
- Overly formal or bureaucratic language
- Vague descriptions without technical specifics
- Unnecessary jargon without explanation
- Leaving out the 'why' behind a change

# Output Format

Subject: <optional-subsystem-prefix>: <lowercase imperative/descriptive summary>

Body: Multi-paragraph prose explaining the problem, context, rationale, and approach. May include quoted text from others, inline code references, and bracketed side notes. Separated from subject by a blank line.

Trailers: Blank line before trailers. Common order: Link, Reported-by, Reported-and-tested-by, Fixes, Cc, Tested-by, Acked-by, Reviewed-by, Signed-off-by (author's Signed-off-by typically last).

# Quality Checklist

- Confirm subject describes behavior change, not implementation effort.
- Confirm wording is concrete and technically precise.
- Confirm body explains rationale when present.
- Confirm trailers are purposeful and correctly formatted.

# References

- See `references/style-profile.json` for quantitative corpus metrics.
- See `references/inference-guidelines.json` for extracted rules and evidence.
- See `references/commit-examples.md` for concrete style examples.
