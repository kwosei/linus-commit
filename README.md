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

Generate a Claude Code commit skill in the style of Linus Torvalds from the Linux repo:

```bash
export ANTHROPIC_API_KEY=<your-key>

python -m commit_style_tool generate \
  --repo torvalds/linux \
  --username torvalds
```

The default provider is Anthropic (`claude-opus-4-6`). Pass `--provider` to switch:

| `--provider` | Default model | API key env var |
|---|---|---|
| `anthropic` *(default)* | `claude-opus-4-6` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4.1-mini` | `OPENAI_API_KEY` |
| `gemini` | `gemini-2.5-flash` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `none` | — | falls back to deterministic heuristics |

Use `--model` to override the default for any provider.

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
uv venv && uv pip install -e .
source .venv/bin/activate
commit-style --help
```

## Notes

- Repository inputs can be local paths, `owner/repo`, or full clone URLs.
- By default, merge commits are excluded.
- Set `--limit` during iteration to speed up runs.
