"""Replay a failed correction and finish only recognized, equivalent edits."""

from copy import deepcopy
import re

from . import procedure_rewrite_auto as auto
from . import procedure_rewrite_full as full
from .article_lifecycle_types import digest_json
from .procedure_rewrite_correction import (
    CorrectionResult,
    _apply_variants,
    _initial_draft,
    _introduction,
    _passage_errors,
    _validated_document,
    rebuild_retained_correction,
)

RECOVERY_METHOD = "source-bound-correction-recovery-v1"
FIRST_DRAFT_RECOVERY_METHOD = "source-bound-first-draft-recovery-v1"
FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD = "source-bound-first-draft-recovery-v2"
FIRST_DRAFT_COOLING_RECOVERY_METHOD = "source-bound-first-draft-recovery-v3"
FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD = "source-bound-first-draft-recovery-v4"
FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD = "source-bound-first-draft-recovery-v5"
REQUIRED_ACTION_WEAKENED = "REWRITE_REQUIRED_ACTION_WEAKENED"
FIRST_DRAFT_RECOVERY_METHODS = (
    FIRST_DRAFT_RECOVERY_METHOD, FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD, FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD, FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
)
_FIRST_DRAFT_RECASTABLE_ERRORS = frozenset({
    "REWRITE_UNCHANGED", "REWRITE_PROSE_TOO_SIMILAR", "REWRITE_ACTION_MUTATION",
    "REWRITE_QUALIFIER_MUTATION", "REWRITE_TECHNICAL_MUTATION",
    "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM",
})
FIRST_DRAFT_RECOVERABLE_ERRORS = _FIRST_DRAFT_RECASTABLE_ERRORS | {
    "REWRITE_SPEC_SCOPE_MUTATION", REQUIRED_ACTION_WEAKENED,
}
_PART_WORD = r"[a-z]+(?:-[a-z]+)*"
_PART = rf"{_PART_WORD}(?: {_PART_WORD}){{0,9}}"
_REFERENCE = r"\([0-9]{1,4}\)"
_REMOVE = re.compile(rf"Remove the (?P<part>{_PART})\.", re.I)
_REMOVAL_NOTE = re.compile(
    rf"(?P<prefix>Note: )the (?P<part>{_PART_WORD}) is removed for clarity\. (?P<directive>Remove the {_PART}\.)",
    re.I,
)
_REMOVAL_CHECK = re.compile(rf"Ensure that the (?P<part>{_PART} {_REFERENCE}) has been removed\.", re.I)
_LABEL_DIRECTIVE = re.compile(rf"(?P<part>{_PART} ?{_REFERENCE})\s*»\s*(?P<verb>Remove|Install)", re.I)
_TIGHTEN_AFTER_CONTACT = re.compile(
    rf"Install a (?P<part>{_PART}) and tighten "
    rf"(?P<amount>[0-9]+/[0-9]+(?: to [0-9]+(?: full)?| of [0-9]+ full)? turn) after "
    rf"the gasket makes contact with the (?P<surface>{_PART}) on the (?P<owner>{_PART})"
    rf"(?P<suffix>\.(?: ?{_REFERENCE})?)",
    re.I,
)
_INSTALL = re.compile(rf"Install (?P<article>the|a new) (?P<parts>{_PART})\.", re.I)
_INSTALL_SECTION = re.compile(
    rf"Install the (?P<part>{_PART})\. For additional information, refer to "
    rf"(?:(?P<number>Section [0-9]{{3}}-[0-9]{{2}}[A-Z]?)|(?P<name>{_PART}) in this section) *\.",
    re.I,
)
_COUNT = r"(?:[2-9]|[1-9][0-9]{1,2})"
_FASTENERS = r"(?:bolts|nuts|screws|fasteners)"
_POSITION_AND_INSTALL = re.compile(
    rf"Position the (?P<part>{_PART}) and install the (?P<count>{_COUNT}) bolts finger tight\.", re.I,
)
_TIGHTEN_COUNTED = re.compile(
    rf"Tighten the (?P<count>{_COUNT}) (?P<part>{_PART} )?(?P<fasteners>{_FASTENERS})\.", re.I,
)
_LOOSEN = re.compile(rf"Loosen the (?P<part>{_PART})\.", re.I)
_FILL_BLEED_REFERENCE = re.compile(
    r"Fill and bleed the (?P<system>cooling system)\. For additional information, refer to "
    r"(?P<title>Cooling System Draining, Filling and Bleeding) in this section\.",
    re.I,
)
_OPEN_PLACEMENT = re.compile(
    rf"(?:Place|Position|Set) the (?P<part>{_PART}) (?P<relation>in|on) the "
    rf"(?P<state>open|exposed) (?:area|part|portion|section) of the (?P<target>{_PART})\.", re.I,
)
_DIRECTIVE_LABEL_EXCLUSIONS = auto._TARGET_DELIMITERS | frozenset(
    "against down during facing finger inside instead last must never no not only outside should tight together up".split()
)
_PASSIVE_REQUIRED_ACTION = re.compile(
    rf"(?P<subject>(?:the|a|an|each|both) (?P<part>{_PART})) (?P<modal>should) be "
    rf"(?P<verb>installed|removed|tightened)"
    rf"(?P<scope> (?:at|from|in|into|on|onto|over|through|to|under) (?:the|a|an) (?P<target>{_PART}))?\.",
    re.I,
)
_IMPERATIVE_VERB = {"installed": "install", "removed": "remove", "tightened": "tighten"}
_COMPONENT_ENDINGS = frozenset(
    "belt bolt bolts bracket cover duct fasteners gasket housing mount nut nuts pipe plate pulley pump retainer "
    "ring screw screws seal shield spacer tube".split()
)


def _removal_passive(text):
    match = _REMOVE.fullmatch(text)
    if (match is not None and auto._TARGET_DELIMITERS.isdisjoint(match["part"].casefold().split())
            and tuple(action.lastgroup for action in auto._action_matches(text)) == ("remove",)):
        return f"The {match['part']} must be removed."
    return None


def _equivalent_wording(text):
    text = text.strip()
    if wording := _removal_passive(text):
        return wording
    if (note := _REMOVAL_NOTE.fullmatch(text)) and (wording := _removal_passive(note["directive"])):
        return f"{note['prefix']}For clarity, the {note['part']} is removed. {wording}"
    if check := _REMOVAL_CHECK.fullmatch(text):
        return f"Confirm the removal of the {check['part']}."
    if label := _LABEL_DIRECTIVE.fullmatch(text):
        return f"{label['verb'].capitalize()} {label['part']}."
    if contact := _TIGHTEN_AFTER_CONTACT.fullmatch(text):
        return (f"Fit a {contact['part']}. After the {contact['surface']} on the {contact['owner']} comes "
                f"into contact with the gasket, tighten {contact['amount']}{contact['suffix']}")
    if text.casefold() == "oil filter":
        return "Filter for the oil"
    return None


def _plain_label(text):
    return _DIRECTIVE_LABEL_EXCLUSIONS.isdisjoint(re.split(r"[\s-]+", text.casefold()))


def _part_label(text):
    return _plain_label(text) and text.casefold().split()[-1] in _COMPONENT_ENDINGS


def _equivalent_directive(text):
    """Recast complete instruction forms, keeping their parts and quantities literal."""
    if match := _INSTALL_SECTION.fullmatch(text):
        part, number, name = match["part"], match["number"], match["name"]
        if _part_label(part) and (name is None or _plain_label(name)):
            if number:
                return f"Fit the {part}. Details are in {number}."
            return f"Fit the {part}. See {name} in this section for details."
    if match := _POSITION_AND_INSTALL.fullmatch(text):
        if _part_label(match["part"]):
            return f"Bring the {match['part']} into position. Install the {match['count']} bolts finger tight."
    if match := _TIGHTEN_COUNTED.fullmatch(text):
        part = match["part"] or ""
        if _part_label(part + match["fasteners"]):
            return f"Tighten each of the {match['count']} {part}{match['fasteners']}."
    if match := _INSTALL.fullmatch(text):
        article, parts = match["article"], match["parts"]
        labels = [re.sub(r"^the ", "", part, flags=re.I) for part in re.split(r" and ", parts, flags=re.I)]
        if (len(labels) <= 2 and all(_part_label(label) for label in labels)
                and auto._execution_order(text) == ("install",)):
            return f"{article.capitalize()} {parts} must be installed."
    return None


def _equivalent_cooling_directive(text):
    if match := _LOOSEN.fullmatch(text):
        if _part_label(match["part"]) and auto._execution_order(text) == ("loosen",):
            return f"The {match['part']} must be loosened."
    if match := _FILL_BLEED_REFERENCE.fullmatch(text):
        return f"Fill the {match['system']} and bleed it. See {match['title']} in this section for details."
    return None


def _restore_open_placement(source, replacement):
    original = _OPEN_PLACEMENT.fullmatch(source)
    draft = _OPEN_PLACEMENT.fullmatch(replacement)
    if not original or not draft or original["state"].casefold() != "open" or draft["state"].casefold() != "exposed":
        return None
    labels = ("part", "target")
    if any(not _plain_label(original[label]) for label in labels):
        return None
    if any(original[key].casefold() != draft[key].casefold() for key in (*labels, "relation")):
        return None
    start, end = draft.span("state")
    return replacement[:start] + original["state"] + replacement[end:]


def _restore_required_action(source, replacement):
    modal = auto.advisory_required_action(source, replacement)
    if modal is None:
        return None
    prefix = auto.authored_note_prefix(replacement) or ""
    if prefix != (auto.authored_note_prefix(source) or ""):
        return None
    passive = _PASSIVE_REQUIRED_ACTION.fullmatch(replacement, len(prefix))
    if passive is None or passive.start("modal") != modal.start():
        return None
    if not _plain_label(passive["part"]) or (passive["target"] and not _plain_label(passive["target"])):
        return None

    # Reconstruct the authored directive from the explicit passive subject
    # and the stationary scope phrase. Every word outside the verb must match.
    verb = _IMPERATIVE_VERB[passive["verb"].casefold()]
    imperative = f"{verb} {passive['subject']}{passive['scope'] or ''}."
    if source[len(prefix):].casefold() != imperative.casefold():
        return None
    start, end = passive.span("modal")
    required = "MUST" if passive["modal"].isupper() else "must"
    return replacement[:start] + required + replacement[end:]


def _validate_first_draft(source, raw, draft, corrected_paths, *, prompt_version, method, original_error):
    introduction_replaced = raw["introduction"] != draft["introduction"]
    if not corrected_paths and not introduction_replaced:
        return None
    try:
        document = auto.render_auto(source, draft, prompt_version=prompt_version)
        validation = auto.validate_auto(source, document, response=draft, prompt_version=prompt_version)
        if not validation.passed:
            return None
        auto.require_current_publication_checks(source, document, saved_prompt_version=prompt_version)
        if method == FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD:
            rewritten_paths = validation.report["changed_prose_slots"]
            auto.require_distinct_generated_introduction(source, document, rewritten_paths=rewritten_paths)
            auto.require_preserved_display_quotations(source, document, rewritten_paths=rewritten_paths)
            auto.require_required_procedure_actions(source, document, rewritten_paths=rewritten_paths)
    except ValueError:
        return None
    return CorrectionResult(draft, document, None, {
        "method": method,
        "original_error_code": original_error,
        "guard_version": prompt_version,
        "input_hash": digest_json(source),
        "raw_response_hash": digest_json(raw),
        "draft_hash": digest_json(draft),
        "output_hash": digest_json(document),
        "corrected_paths": corrected_paths,
        **({"introduction_replaced": introduction_replaced}
           if method in (FIRST_DRAFT_COOLING_RECOVERY_METHOD, FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD) else {}),
    })


def _recover_placement_draft(source, raw, slots, *, prompt_version, original_error):
    draft = deepcopy(raw)
    if original_error == "REWRITE_SPEC_SCOPE_MUTATION":
        # A specification may be removed from the generated introduction.
        # A changed authored specification must still fail the full validation.
        try:
            auto.check_automatic_introduction(source, raw["introduction"])
        except ValueError as error:
            if str(error) != original_error:
                return None
        else:
            return None
        try:
            draft["introduction"] = _introduction(source, raw["introduction"])
        except ValueError:
            return None
    action_paths = {issue["path"] for issue in auto.failed_rewrite_passages(
        source, raw, prompt_version=prompt_version,
    ) if issue["code"] == "REWRITE_ACTION_MUTATION"}
    corrected = []
    for slot, row in zip(slots, draft["replacements"], strict=True):
        if row["action"] == "rewrite" and slot["path"] in action_paths:
            if wording := _restore_open_placement(slot["text"], row["text"]):
                row["text"] = wording
                corrected.append(slot["path"])
    return _validate_first_draft(
        source, raw, draft, corrected, prompt_version=prompt_version,
        method=FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD, original_error=original_error,
    )


def _recover_required_action_draft(source, raw, slots, *, prompt_version):
    draft = deepcopy(raw)
    corrected = []
    for slot, row in zip(slots, draft["replacements"], strict=True):
        if row["action"] == "rewrite" and (wording := _restore_required_action(slot["text"], row["text"])):
            row["text"] = wording
            corrected.append(slot["path"])
    return _validate_first_draft(
        source, raw, draft, corrected, prompt_version=prompt_version,
        method=FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD, original_error=REQUIRED_ACTION_WEAKENED,
    )


def recover_first_draft(source, raw, *, prompt_version, method=None):
    """Rebuild an automatic draft from the saved reply and source-only recasts."""
    if (not full._source_valid(source) or not isinstance(raw, dict)
            or set(raw) != {"introduction", "replacements"}
            or not isinstance(raw["introduction"], str) or not isinstance(raw["replacements"], list)):
        return None
    if method is not None and method not in FIRST_DRAFT_RECOVERY_METHODS:
        return None
    slots = full.prose_slots(source, include_cell_blocks=auto._include_cell_blocks(prompt_version))
    if (prompt_version is None or not auto._uses_prose_guards(prompt_version, len(slots))
            or len(raw["replacements"]) != len(slots)):
        return None
    for slot, row in zip(slots, raw["replacements"], strict=True):
        if (not isinstance(row, dict) or set(row) != {"block_id", "path", "action", "text", "reason"}
                or not all(isinstance(value, str) for value in row.values())
                or row["block_id"] != slot["block_id"] or row["path"] != slot["path"]
                or row["action"] not in {"retain", "rewrite"} or not row["text"].strip()):
            return None
    try:
        auto.render_auto(source, raw, prompt_version=prompt_version)
    except ValueError as error:
        original_error = str(error)
    else:
        if method == FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD:
            return _recover_required_action_draft(source, raw, slots, prompt_version=prompt_version)
        return None
    if method == FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD:
        return None
    if original_error not in FIRST_DRAFT_RECOVERABLE_ERRORS:
        return None
    if method in (None, FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD) and original_error in (
        "REWRITE_ACTION_MUTATION", "REWRITE_SPEC_SCOPE_MUTATION",
    ):
        placement = _recover_placement_draft(source, raw, slots, prompt_version=prompt_version, original_error=original_error)
        if placement is not None:
            return placement
    if method == FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD or original_error == "REWRITE_SPEC_SCOPE_MUTATION":
        return None
    if method in (None, FIRST_DRAFT_RECOVERY_METHOD) and original_error == "REWRITE_UNCHANGED":
        draft = deepcopy(raw)
        corrected = []
        for slot, row in zip(slots, draft["replacements"], strict=True):
            if row["action"] == "rewrite" and row["text"] == slot["text"]:
                if wording := _equivalent_wording(slot["text"]):
                    row.update(text=wording, reason="Distinct source-bound prose.")
                    corrected.append(slot["path"])
        legacy = _validate_first_draft(
            source, raw, draft, corrected, prompt_version=prompt_version,
            method=FIRST_DRAFT_RECOVERY_METHOD, original_error=original_error,
        )
        if legacy is not None:
            return legacy
    if method == FIRST_DRAFT_RECOVERY_METHOD:
        return None
    invalid = {issue["path"]: issue["code"] for issue in auto.failed_rewrite_passages(
        source, raw, prompt_version=prompt_version,
    )}
    draft = deepcopy(raw)
    corrected = []
    for slot, row in zip(slots, draft["replacements"], strict=True):
        error = invalid.get(slot["path"])
        if row["action"] != "rewrite" or error not in _FIRST_DRAFT_RECASTABLE_ERRORS:
            continue
        wording = _equivalent_directive(slot["text"])
        if wording is None and row["text"] == slot["text"]:
            wording = _equivalent_wording(slot["text"])
        if wording is not None:
            row.update(text=wording, reason="Distinct source-bound prose.")
            corrected.append(slot["path"])
    if method in (None, FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD):
        directive = _validate_first_draft(
            source, raw, draft, corrected, prompt_version=prompt_version,
            method=FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD, original_error=original_error,
        )
        if directive is not None or method == FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD:
            return directive

    # A newly published recast must remain reproducible under the method saved
    # with its response. Earlier methods never use these extra source edits.
    already_corrected = set(corrected)
    for slot, row in zip(slots, draft["replacements"], strict=True):
        path = slot["path"]
        if (path in already_corrected or row["action"] != "rewrite"
                or invalid.get(path) not in _FIRST_DRAFT_RECASTABLE_ERRORS):
            continue
        if wording := _equivalent_cooling_directive(slot["text"]):
            row.update(text=wording, reason="Distinct source-bound prose.")
            already_corrected.add(path)
    try:
        draft["introduction"] = _introduction(source, raw["introduction"])
    except ValueError:
        return None
    if len(already_corrected) == len(corrected) and draft["introduction"] == raw["introduction"]:
        return None
    return _validate_first_draft(
        source, raw, draft, [slot["path"] for slot in slots if slot["path"] in already_corrected],
        prompt_version=prompt_version, method=FIRST_DRAFT_COOLING_RECOVERY_METHOD, original_error=original_error,
    )


def recover_retained_correction(source, previous, *, model_call_budget, attempts, preserve_notes=False):
    """Verify the original transcript and reframe only unresolved passages."""
    original = rebuild_retained_correction(source, previous, model_call_budget=model_call_budget, attempts=attempts,
                                            preserve_notes=preserve_notes)
    version, slots, _ = _initial_draft(source, previous, preserve_notes=preserve_notes)
    draft = deepcopy(original.response)
    batch, alternatives = [], []
    for index in _passage_errors(source, slots, draft):
        if wording := _equivalent_wording(slots[index]["text"]):
            batch.append(index)
            alternatives.append([wording])
    if batch:
        _apply_variants(source, slots, draft, batch, alternatives)
    document, error_code = _validated_document(source, slots, draft, version)
    return CorrectionResult(draft, document, error_code, {
        **original.evidence,
        "method": RECOVERY_METHOD,
        "base_draft_hash": original.evidence["draft_hash"],
        "original_error_code": original.error_code,
        "draft_hash": digest_json(draft),
    })
