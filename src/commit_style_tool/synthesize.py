from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .types import StageResult
from .utils import iso_now, read_json, slugify, write_json

DEFAULT_MODEL_BY_PROVIDER = {
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
}


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        return json.loads(snippet)
    raise ValueError("Could not parse model response as JSON")


def _openai_chat_completion(api_key: str, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        url="https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc


def _gemini_generate_content(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    request = Request(
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini request failed with HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc


def _extract_gemini_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini response did not include candidates")

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        text_chunks = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                text_chunks.append(text)
        if text_chunks:
            return "\n".join(text_chunks)

    raise ValueError("Gemini response candidates did not include text content")


def _build_prompt(analysis: dict[str, Any], username: str, repo: str) -> str:
    # Keep the prompt compact but include enough signal for concrete guidance.
    compact = {
        "record_count": analysis.get("record_count"),
        "subject": analysis.get("subject"),
        "body": analysis.get("body"),
        "trailers": analysis.get("trailers"),
        "semantic_cues": analysis.get("semantic_cues"),
        "samples": analysis.get("samples", [])[:8],
    }
    return (
        "Infer commit-message style rules from this author profile and return only JSON.\n"
        f"Target author: {username}\n"
        f"Repository: {repo}\n\n"
        "Schema:\n"
        "{\n"
        '  "rules": [{"instruction": string, "rationale": string, "evidence_commit_ids": [string]}],\n'
        '  "anti_rules": [{"instruction": string, "rationale": string}],\n'
        '  "format": {"subject": string, "body": string, "trailers": string},\n'
        '  "tone": {"summary": string, "do": [string], "avoid": [string]},\n'
        '  "examples": [{"good_subject": string, "good_body": string, "why": string, "source_commit_id": string}],\n'
        '  "confidence": {"score": number, "notes": [string]}\n'
        "}\n\n"
        "Constraints:\n"
        "- Use imperative language in each rule.\n"
        "- Keep rules specific and testable.\n"
        "- Cite evidence commit IDs from samples when possible.\n"
        "- Preserve ambiguity by adding confidence notes instead of over-claiming.\n\n"
        f"Profile JSON:\n{json.dumps(compact, indent=2)}"
    )


def _fallback_guidelines(analysis: dict[str, Any], username: str, repo: str, reason: str) -> dict[str, Any]:
    subject_stats = analysis.get("subject", {}).get("char_length", {})
    body_stats = analysis.get("body", {})
    prefix_rate = float(analysis.get("subject", {}).get("prefix_rate", 0.0))
    imperative_rate = float(analysis.get("subject", {}).get("imperative_proxy_rate", 0.0))
    trailer_rate = float(analysis.get("trailers", {}).get("present_rate", 0.0))

    samples = analysis.get("samples", [])
    evidence_ids = [sample.get("hash", "") for sample in samples[:4] if sample.get("hash")]

    rules: list[dict[str, Any]] = [
        {
            "instruction": (
                "Write a concise, technical subject line that focuses on the behavioral change."
            ),
            "rationale": (
                f"Observed median subject length is about {round(float(subject_stats.get('median', 0.0)), 1)} characters."
            ),
            "evidence_commit_ids": evidence_ids,
        },
        {
            "instruction": "Start the actionable part of the subject with an imperative verb.",
            "rationale": (
                "The corpus shows frequent imperative-leading subjects "
                f"(proxy rate {imperative_rate:.2f})."
            ),
            "evidence_commit_ids": evidence_ids,
        },
    ]

    if prefix_rate >= 0.25:
        rules.append(
            {
                "instruction": "Use a subsystem prefix (`subsystem: summary`) when the change is scoped.",
                "rationale": f"Prefix usage appears common (rate {prefix_rate:.2f}).",
                "evidence_commit_ids": evidence_ids,
            }
        )

    if float(body_stats.get("present_rate", 0.0)) >= 0.55:
        rules.append(
            {
                "instruction": "Add a body paragraph that explains why the change is needed before implementation detail.",
                "rationale": (
                    "Most commits include a body; the style usually carries rationale in prose."
                ),
                "evidence_commit_ids": evidence_ids,
            }
        )

    if trailer_rate >= 0.2:
        rules.append(
            {
                "instruction": "Include trailers only when they add review, fix, or sign-off traceability.",
                "rationale": f"Trailer usage is non-trivial (rate {trailer_rate:.2f}).",
                "evidence_commit_ids": evidence_ids,
            }
        )

    examples = []
    for sample in samples[:3]:
        examples.append(
            {
                "good_subject": sample.get("subject", ""),
                "good_body": sample.get("body", ""),
                "why": "Representative commit selected from the analyzed corpus.",
                "source_commit_id": sample.get("hash", ""),
            }
        )

    return {
        "rules": rules,
        "anti_rules": [
            {
                "instruction": "Avoid vague subjects that describe effort instead of behavior.",
                "rationale": "The style tends to emphasize concrete technical effect.",
            },
            {
                "instruction": "Avoid filler body text that repeats the subject without rationale.",
                "rationale": "Body content is most useful when it adds causal context.",
            },
        ],
        "format": {
            "subject": "[optional subsystem:] imperative summary",
            "body": "Explain why, then key constraints or caveats.",
            "trailers": "Include only when needed for traceability.",
        },
        "tone": {
            "summary": "Technical, direct, and behavior-focused.",
            "do": [
                "State concrete effects",
                "Call out constraints and regressions",
                "Use plain technical language",
            ],
            "avoid": [
                "Marketing language",
                "Vague intent statements",
                "Unqualified certainty when uncertain",
            ],
        },
        "examples": examples,
        "confidence": {
            "score": 0.66,
            "notes": [
                "Generated with deterministic fallback heuristics.",
                f"Fallback reason: {reason}",
            ],
        },
    }


def _normalize_guidelines(payload: dict[str, Any], analysis: dict[str, Any], source: str) -> dict[str, Any]:
    rules = payload.get("rules") if isinstance(payload.get("rules"), list) else []
    anti_rules = payload.get("anti_rules") if isinstance(payload.get("anti_rules"), list) else []
    examples = payload.get("examples") if isinstance(payload.get("examples"), list) else []

    normalized_rules: list[dict[str, Any]] = []
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        instruction = str(rule.get("instruction", "")).strip()
        if not instruction:
            continue
        rationale = str(rule.get("rationale", "")).strip()
        evidence = rule.get("evidence_commit_ids", [])
        evidence_ids = [str(item) for item in evidence if str(item).strip()] if isinstance(evidence, list) else []
        normalized_rules.append(
            {
                "id": f"rule-{idx + 1}",
                "instruction": instruction,
                "rationale": rationale,
                "evidence_commit_ids": evidence_ids,
            }
        )

    normalized_anti_rules: list[dict[str, str]] = []
    for item in anti_rules:
        if not isinstance(item, dict):
            continue
        instruction = str(item.get("instruction", "")).strip()
        if not instruction:
            continue
        normalized_anti_rules.append(
            {
                "instruction": instruction,
                "rationale": str(item.get("rationale", "")).strip(),
            }
        )

    normalized_examples: list[dict[str, str]] = []
    for item in examples[:8]:
        if not isinstance(item, dict):
            continue
        normalized_examples.append(
            {
                "good_subject": str(item.get("good_subject", "")).strip(),
                "good_body": str(item.get("good_body", "")).rstrip(),
                "why": str(item.get("why", "")).strip(),
                "source_commit_id": str(item.get("source_commit_id", "")).strip(),
            }
        )

    if not normalized_rules:
        fallback = _fallback_guidelines(analysis, username="unknown", repo="unknown", reason="invalid-model-output")
        return _normalize_guidelines(fallback, analysis, source="fallback")

    confidence = payload.get("confidence") if isinstance(payload.get("confidence"), dict) else {}
    score_raw = confidence.get("score", 0.5)
    try:
        score = float(score_raw)
    except (TypeError, ValueError):
        score = 0.5

    format_section = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    tone = payload.get("tone") if isinstance(payload.get("tone"), dict) else {}

    return {
        "generated_at": iso_now(),
        "source": source,
        "style_id": slugify(f"{analysis.get('record_count', 0)}-commits-style"),
        "rules": normalized_rules,
        "anti_rules": normalized_anti_rules,
        "format": {
            "subject": str(format_section.get("subject", "")).strip(),
            "body": str(format_section.get("body", "")).strip(),
            "trailers": str(format_section.get("trailers", "")).strip(),
        },
        "tone": {
            "summary": str(tone.get("summary", "")).strip(),
            "do": [str(item).strip() for item in tone.get("do", []) if str(item).strip()] if isinstance(tone.get("do"), list) else [],
            "avoid": [str(item).strip() for item in tone.get("avoid", []) if str(item).strip()] if isinstance(tone.get("avoid"), list) else [],
        },
        "examples": normalized_examples,
        "confidence": {
            "score": max(0.0, min(1.0, score)),
            "notes": [str(item).strip() for item in confidence.get("notes", []) if str(item).strip()] if isinstance(confidence.get("notes"), list) else [],
        },
    }


def synthesize_guidelines(
    analysis_path: Path,
    output_path: Path,
    username: str,
    repo: str,
    provider: str = "openai",
    model: str | None = None,
) -> StageResult:
    analysis = read_json(analysis_path)

    provider_clean = provider.strip().lower()
    if provider_clean == "none":
        payload = _fallback_guidelines(analysis, username=username, repo=repo, reason="provider=none")
        normalized = _normalize_guidelines(payload, analysis, source="heuristic")
        write_json(output_path, normalized)
        return StageResult(path=str(output_path), record_count=len(normalized.get("rules", [])))

    if provider_clean not in {"openai", "gemini"}:
        raise ValueError(f"Unsupported provider: {provider}")

    model_name = model.strip() if isinstance(model, str) and model.strip() else DEFAULT_MODEL_BY_PROVIDER[provider_clean]

    prompt = _build_prompt(analysis, username=username, repo=repo)
    system_prompt = "You are a precise commit-style analyst. Return valid JSON only and follow the schema exactly."
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {"role": "user", "content": prompt},
    ]

    if provider_clean == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            payload = _fallback_guidelines(analysis, username=username, repo=repo, reason="OPENAI_API_KEY missing")
            normalized = _normalize_guidelines(payload, analysis, source="heuristic")
            write_json(output_path, normalized)
            return StageResult(path=str(output_path), record_count=len(normalized.get("rules", [])))
    else:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
        if not api_key:
            payload = _fallback_guidelines(
                analysis,
                username=username,
                repo=repo,
                reason="GEMINI_API_KEY/GOOGLE_API_KEY missing",
            )
            normalized = _normalize_guidelines(payload, analysis, source="heuristic")
            write_json(output_path, normalized)
            return StageResult(path=str(output_path), record_count=len(normalized.get("rules", [])))

    try:
        if provider_clean == "openai":
            response = _openai_chat_completion(api_key=api_key, model=model_name, messages=messages)
            raw_content = response["choices"][0]["message"]["content"]
        else:
            response = _gemini_generate_content(
                api_key=api_key,
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=prompt,
            )
            raw_content = _extract_gemini_text(response)
        parsed_payload = _extract_json_object(raw_content)
        normalized = _normalize_guidelines(parsed_payload, analysis, source=provider_clean)
    except Exception as exc:  # noqa: BLE001
        payload = _fallback_guidelines(analysis, username=username, repo=repo, reason=str(exc))
        normalized = _normalize_guidelines(payload, analysis, source="heuristic")

    write_json(output_path, normalized)
    return StageResult(path=str(output_path), record_count=len(normalized.get("rules", [])))
