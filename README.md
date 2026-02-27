# commit-style-tool

CLI pipeline to infer a commit-message style from a GitHub repo + author and package the result as a Claude-style skill.

## What it does

1. Collect commit metadata for a target author (`collect`)
2. Normalize and clean dataset (`prepare`)
3. Compute style metrics (`analyze`)
4. Infer writing rules with LLM or heuristics (`synthesize`)
5. Evaluate fit on a holdout split (`evaluate`)
6. Generate a skill folder (`package-skill`)

The `generate` command runs all stages.

## Quick start

```bash
python -m commit_style_tool generate \
  --repo torvalds/linux \
  --username torvalds \
  --provider gemini
```

Provider API keys:

- `--provider openai` uses `OPENAI_API_KEY`
- `--provider gemini` uses `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- Missing key falls back to deterministic heuristics

## Example output layout

```text
data/
  raw/<slug>.jsonl
  prepared/<slug>.jsonl
outputs/
  profiles/
    <slug>.analysis.json
    <slug>.guidelines.json
    <slug>.evaluation.json
  skills/
    <skill-name>/
      SKILL.md
      references/
        style-profile.json
        inference-guidelines.json
        commit-examples.md
```

## Install as a local command

```bash
pip install -e .
commit-style --help
```

## Notes

- Repository inputs can be local paths, `owner/repo`, or full clone URLs.
- By default, merge commits are excluded.
- Set `--limit` during iteration to speed up runs.
