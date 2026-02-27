from __future__ import annotations

import shutil
from pathlib import Path

from .types import StageResult
from .utils import ensure_dir, read_json, read_jsonl, slugify, write_json


def _format_rules(rules: list[dict]) -> str:
    lines: list[str] = []
    for item in rules:
        instruction = str(item.get("instruction", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        if not instruction:
            continue
        lines.append(f"- {instruction}")
        if rationale:
            lines.append(f"  Rationale: {rationale}")
    return "\n".join(lines) if lines else "- Use concise, behavior-focused commit messages."


def _format_anti_rules(anti_rules: list[dict]) -> str:
    lines: list[str] = []
    for item in anti_rules:
        instruction = str(item.get("instruction", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        if not instruction:
            continue
        lines.append(f"- {instruction}")
        if rationale:
            lines.append(f"  Rationale: {rationale}")
    return "\n".join(lines) if lines else "- Avoid vague and non-technical subjects."


def _build_skill_markdown(
    skill_name: str,
    username: str,
    repo: str,
    guidelines: dict,
) -> str:
    description = (
        "Generate and rewrite git commit messages following a style guide "
        f"inferred from {username}'s commits in {repo}. The rules are generalized "
        "and portable — use them when drafting commit messages in any repository, "
        "reviewing message quality, or converting raw change notes into a final commit message."
    )

    rules_block = _format_rules(guidelines.get("rules", []))
    anti_rules_block = _format_anti_rules(guidelines.get("anti_rules", []))
    tone = guidelines.get("tone", {}) if isinstance(guidelines.get("tone"), dict) else {}
    do_items = [str(item).strip() for item in tone.get("do", []) if str(item).strip()] if isinstance(tone.get("do"), list) else []
    avoid_items = [str(item).strip() for item in tone.get("avoid", []) if str(item).strip()] if isinstance(tone.get("avoid"), list) else []
    do_block = "\n".join(f"- {item}" for item in do_items) if do_items else "- Keep language technical and direct."
    avoid_block = "\n".join(f"- {item}" for item in avoid_items) if avoid_items else "- Avoid over-explaining obvious mechanics."

    format_block = guidelines.get("format", {}) if isinstance(guidelines.get("format"), dict) else {}
    subject_fmt = str(format_block.get("subject", "[optional subsystem:] imperative summary")).strip()
    body_fmt = str(format_block.get("body", "Explain why, then key details.")).strip()
    trailer_fmt = str(format_block.get("trailers", "Include only when needed.")).strip()

    return f"""---
name: {skill_name}
description: {description}
---

# Commit Message Workflow

1. Identify the change scope and expected behavior impact.
2. Draft the subject line using the style rules below.
3. Add body context only when rationale or constraints are needed.
4. Add trailers only when traceability requires them.
5. Run the quality checklist before finalizing.

# Style Rules

{rules_block}

# Anti-Rules

{anti_rules_block}

# Tone

Summary: {str(tone.get('summary', 'Technical, concise, behavior-focused.')).strip()}

Do:
{do_block}

Avoid:
{avoid_block}

# Output Format

Subject: {subject_fmt}

Body: {body_fmt}

Trailers: {trailer_fmt}

# Quality Checklist

- Confirm subject describes behavior change, not implementation effort.
- Confirm wording is concrete and technically precise.
- Confirm body explains rationale when present.
- Confirm trailers are purposeful and correctly formatted.

# References

- See `references/style-profile.json` for quantitative corpus metrics.
- See `references/inference-guidelines.json` for extracted rules and evidence.
- See `references/commit-examples.md` for concrete style examples.
"""


def _build_examples_markdown(commits: list[dict], limit: int = 20) -> str:
    lines = [
        "# Commit Examples",
        "",
        "Representative commits from the analyzed corpus.",
        "",
    ]
    for commit in commits[:limit]:
        subject = str(commit.get("subject", "")).strip() or "(empty subject)"
        body = str(commit.get("body", "")).rstrip()
        commit_hash = str(commit.get("hash", "")).strip()
        lines.append(f"## {commit_hash[:12]} - {subject}")
        lines.append("")
        if body:
            lines.append(body)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def package_skill(
    guidelines_path: Path,
    profile_path: Path,
    commits_path: Path,
    output_dir: Path,
    skill_name: str,
    username: str,
    repo: str,
) -> StageResult:
    guidelines = read_json(guidelines_path)
    profile = read_json(profile_path)
    commits = list(read_jsonl(commits_path))

    safe_skill_name = slugify(skill_name)
    skill_root = output_dir / safe_skill_name
    references_dir = skill_root / "references"

    if skill_root.exists():
        shutil.rmtree(skill_root)

    ensure_dir(references_dir)

    skill_markdown = _build_skill_markdown(
        skill_name=safe_skill_name,
        username=username,
        repo=repo,
        guidelines=guidelines,
    )
    (skill_root / "SKILL.md").write_text(skill_markdown, encoding="utf-8")

    write_json(references_dir / "style-profile.json", profile)
    write_json(references_dir / "inference-guidelines.json", guidelines)
    (references_dir / "commit-examples.md").write_text(
        _build_examples_markdown(commits), encoding="utf-8"
    )

    return StageResult(
        path=str(skill_root),
        record_count=len(guidelines.get("rules", [])),
        metadata={
            "references": [
                str(references_dir / "style-profile.json"),
                str(references_dir / "inference-guidelines.json"),
                str(references_dir / "commit-examples.md"),
            ]
        },
    )
