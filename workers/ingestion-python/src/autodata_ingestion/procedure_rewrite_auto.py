"""Automatic full-prose rewriting with permanent, mechanically checked output.

Checks preserve structure and literal technical tokens; they do not certify
semantic equivalence. Historical human-review behavior stays in its own profile.
"""
from copy import deepcopy
import json
import re

from . import procedure_rewrite_full as full
from .article_lifecycle_types import ValidationResult

PROFILE = "full-prose-auto-v1"


def _technical_only(text):
    """Only token-only specifications can stay verbatim without a prose rewrite."""
    return not any(char.isalpha() for char in full._TOKENS.sub("", text))


def _build_auto_prompt_v1(document, *, context):
    payload = json.loads(full.build_full_prompt(document, context=context))
    payload.update(profile_version=PROFILE, prompt_version="full-prose-auto-prompt-v1")
    payload["rules"] = [rule for rule in payload["rules"] if "human" not in rule.lower()
        and not rule.startswith("Preserve ambiguous numeric notation")
        and not rule.startswith("Rewrite every ordinary prose leaf completely")]
    payload["rules"].extend([
        "A valid result is published automatically. Rewrite every ordinary prose leaf; no ordinary prose retention is allowed.",
        "Use retain only for a leaf consisting solely of exact numeric/unit/identifier/reference tokens and punctuation. Include a concrete reason.",
        "If ambiguous technical notation occurs in ordinary prose, do not invent a conversion or omit instructions; the article stays as stored source if its rewrite cannot pass the guards.",
    ])
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def build_auto_prompt(document, *, context):
    payload = json.loads(_build_auto_prompt_v1(document, context=context))
    payload["prompt_version"] = "full-prose-auto-prompt-v2"
    payload["response_shape"] = {"introduction": "string", "replacements": [
        {"block_id": "string", "path": "string", "action": "rewrite|retain", "text": "string", "reason": "string"}]}
    for slot in payload["slots"]:
        slot["required_action"] = "rewrite_or_retain" if _technical_only(slot["text"]) else "rewrite"
    payload["rules"].extend([
        "Return one JSON object with exactly introduction and replacements. Each replacement must have exactly five keys: block_id, path, action, text, reason; all five values are strings. Never omit reason.",
        'Every rewrite row must include reason:"". A retain row must include a concrete nonempty reason and exact original text; retain is allowed only for technical-only leaves marked required_action=rewrite_or_retain.',
        "Follow each server-supplied required_action: rewrite means action=rewrite and complete rewording of ordinary prose; rewrite_or_retain permits either a valid rewrite or exact technical-only retention. Do not copy required_action into the response.",
        "Use genuinely reworded ordinary prose in every slot. Identical wording, casing, whitespace or punctuation changes alone fail; do not echo source text, retain ordinary prose, skip slots or change supplied slot order.",
    ])
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _matches_auto_prompt_hash(document, *, context, prompt_hash):
    """Accept only exact server-reconstructed historical and current prompts."""
    from hashlib import sha256
    return prompt_hash in {sha256(builder(document, context=context).encode()).hexdigest()
        for builder in (_build_auto_prompt_v1, build_auto_prompt)}


def _require_changes(source, candidate):
    # Restoring source order and structure is full.validate_full's responsibility.
    restored = deepcopy(candidate)
    restored["blocks"].pop(0)
    for slot in full.prose_slots(source):
        if re.findall(r"\w+", full._get(restored, slot["path"]).casefold()) == re.findall(r"\w+", slot["text"].casefold()):
            if not _technical_only(slot["text"]):
                raise ValueError("REWRITE_UNCHANGED")


def render_auto(source, response):
    candidate = full.render_full(source, response, profile_version=PROFILE)
    _require_changes(source, candidate)
    return candidate


def validate_auto(source, candidate, *, response=None):
    validation = full.validate_full(source, candidate, response=response, profile_version=PROFILE)
    errors = list(validation.error_codes)
    if validation.passed:
        try:
            _require_changes(source, candidate)
        except ValueError as error:
            errors.append(str(error))
    report = dict(validation.report)
    errors = sorted(set(errors))
    report.update(validator_version="full-prose-auto-validator-v1", profile_version=PROFILE,
        publication_mode="automatic", content_acceptance_required=False,
        complete_rewrite=False, passed=not errors, error_codes=errors)
    return ValidationResult(not errors, tuple(errors), report)
