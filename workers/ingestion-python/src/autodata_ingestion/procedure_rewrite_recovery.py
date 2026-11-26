"""Replay a failed correction and finish only recognized, equivalent edits."""

from copy import deepcopy
import re

from . import procedure_rewrite_auto as auto
from . import procedure_rewrite_full as full
from .article_lifecycle_types import SOURCE_BOUND_CORRECTION_PROFILE, digest_json
from .procedure_rewrite_correction import (
    ARCHIVED_FIRST_DRAFT_METHOD,
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
FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD = "source-bound-first-draft-recovery-v6"
FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD = "source-bound-first-draft-recovery-v7"
FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD = "source-bound-first-draft-recovery-v8"
FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD = "source-bound-first-draft-introduction-v1"
FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD = "source-bound-first-draft-diagnostic-v1"
FIRST_DRAFT_POSITIONED_FIGURE_RECOVERY_METHOD = "source-bound-positioned-figure-first-draft-v1"
NEUTRAL_INTRODUCTION = "This article describes the service information that follows."
REQUIRED_ACTION_WEAKENED = "REWRITE_REQUIRED_ACTION_WEAKENED"
_TECHNICAL_AMBIGUITY = "REWRITE_TECHNICAL_AMBIGUOUS"
FIRST_DRAFT_RECOVERY_METHODS = (
    FIRST_DRAFT_RECOVERY_METHOD, FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD, FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD, FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
    FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD, FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD,
    FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD, FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD,
    FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD,
)
BANKONE_STRUCTURAL_RECOVERY_METHOD = "source-bound-bankone-first-draft-v1"
BANKONE_LINKED_RECOVERY_METHOD = "source-bound-bankone-first-draft-v2"
BANKONE_REFERENCED_RECOVERY_METHOD = "source-bound-bankone-first-draft-v3"
BANKONE_ARCHIVE_STRUCTURE_VERSIONS = {
    BANKONE_STRUCTURAL_RECOVERY_METHOD: 1,
    BANKONE_LINKED_RECOVERY_METHOD: 2,
    BANKONE_REFERENCED_RECOVERY_METHOD: 3,
}
ARCHIVED_FIRST_DRAFT_RECOVERY_METHODS = (*FIRST_DRAFT_RECOVERY_METHODS, *BANKONE_ARCHIVE_STRUCTURE_VERSIONS)
_FIRST_DRAFT_RECASTABLE_ERRORS = frozenset({
    "REWRITE_UNCHANGED", "REWRITE_PROSE_TOO_SIMILAR", "REWRITE_ACTION_MUTATION",
    "REWRITE_QUALIFIER_MUTATION", "REWRITE_TECHNICAL_MUTATION",
    "REWRITE_INTRODUCTION_UNSUPPORTED_CLAIM",
})
_LUBRICATION_MUTATION = "REWRITE_LUBRICATION_MUTATION"
FIRST_DRAFT_RECOVERABLE_ERRORS = _FIRST_DRAFT_RECASTABLE_ERRORS | {
    "REWRITE_SPEC_SCOPE_MUTATION", REQUIRED_ACTION_WEAKENED,
    _LUBRICATION_MUTATION, _TECHNICAL_AMBIGUITY,
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
_COMPOUND_REMOVAL = re.compile(rf"Remove the (?P<first>{_PART}) and the (?P<rest>{_PART})\.", re.I)
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


def _recast_compound_removal(source, replacement):
    match = _COMPOUND_REMOVAL.fullmatch(source)
    if (match is None or auto._execution_order(source) != ("remove",)
            or auto._action_matches(replacement)):
        return None
    parts = (match["first"], *re.split(r" and ", match["rest"], flags=re.I))
    endings = _COMPONENT_ENDINGS | {"screen"}
    if len(parts) > 3 or not all(_plain_label(part) and part.casefold().split()[-1] in endings for part in parts):
        return None
    return f"The {match['first']} and the {match['rest']} must be removed."


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


def _validate_first_draft(source, raw, draft, corrected_paths, *, prompt_version, method, original_error,
                          bankone_structure=None):
    introduction_replaced = raw["introduction"] != draft["introduction"]
    if not corrected_paths and not introduction_replaced:
        return None
    try:
        document = auto.render_auto(source, draft, prompt_version=prompt_version, bankone_structure=bankone_structure)
        validation = auto.validate_auto(
            source, document, response=draft, prompt_version=prompt_version, bankone_structure=bankone_structure,
        )
        if not validation.passed:
            return None
        auto.require_current_publication_checks(
            source, document, saved_prompt_version=prompt_version, bankone_structure=bankone_structure,
        )
        if method in (FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD, FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD,
                      FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD, FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD,
                      FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD,
                      FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD,
                      FIRST_DRAFT_POSITIONED_FIGURE_RECOVERY_METHOD,
                      *BANKONE_ARCHIVE_STRUCTURE_VERSIONS):
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
           if method in (FIRST_DRAFT_COOLING_RECOVERY_METHOD, FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD,
                         FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD, FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD,
                         FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD, FIRST_DRAFT_POSITIONED_FIGURE_RECOVERY_METHOD) else {}),
        **({"bankone_structure_hash": digest_json(bankone_structure)} if bankone_structure is not None else {}),
    }, bankone_structure=bankone_structure)


def _recover_action_draft(source, raw, slots, *, prompt_version, original_error, method):
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
    recast = (_restore_open_placement if method == FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD
              else _recast_compound_removal)
    corrected = []
    for slot, row in zip(slots, draft["replacements"], strict=True):
        if row["action"] == "rewrite" and slot["path"] in action_paths:
            if wording := recast(slot["text"], row["text"]):
                row["text"] = wording
                corrected.append(slot["path"])
    if method == FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD and not corrected:
        return None
    return _validate_first_draft(
        source, raw, draft, corrected, prompt_version=prompt_version,
        method=method, original_error=original_error,
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


def _recover_diagnostic_draft(source, raw, slots, *, prompt_version, original_error):
    from .procedure_rewrite_diagnostic_recovery import recast_diagnostic_passage, scan_reading_instruction

    if original_error not in {"REWRITE_UNCHANGED", "REWRITE_SPEC_SCOPE_MUTATION"}:
        return None
    if not any(scan_reading_instruction(slot["text"]) for slot in slots):
        return None
    failures = {item["path"] for item in auto.failed_rewrite_passages(source, raw, prompt_version=prompt_version)}
    draft = deepcopy(raw)
    corrected = []
    for slot, row in zip(slots, draft["replacements"], strict=True):
        path = slot["path"]
        if path in failures and row["action"] == "rewrite":
            if wording := recast_diagnostic_passage(slot["text"], reading="/items/" in path):
                row["text"] = wording
                corrected.append(path)
    if not corrected:
        return None
    try:
        auto.check_automatic_introduction(source, raw["introduction"])
    except ValueError as error:
        if str(error) != "REWRITE_SPEC_SCOPE_MUTATION":
            return None
        draft["introduction"] = NEUTRAL_INTRODUCTION
    return _validate_first_draft(
        source, raw, draft, corrected, prompt_version=prompt_version,
        method=FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD, original_error=original_error,
    )


def _recover_cooling_sequence(source, raw, slots, invalid, *, prompt_version, original_error):
    from .procedure_rewrite_cooling_recovery import recast_cooling_passage

    draft = deepcopy(raw)
    corrected_paths = []
    sequence_recast = False
    for slot, row in zip(slots, draft["replacements"], strict=True):
        path = slot["path"]
        error = invalid.get(path)
        if row["action"] != "rewrite" or error not in _FIRST_DRAFT_RECASTABLE_ERRORS:
            continue
        wording = _equivalent_directive(slot["text"]) if error == "REWRITE_ACTION_MUTATION" else None
        if wording is None:
            recast_error = error
            if (prompt_version in auto._PROCEDURE_FIDELITY_PROMPT_VERSIONS
                    and error == "REWRITE_QUALIFIER_MUTATION"):
                recast_error = "REWRITE_ACTION_MUTATION"
            wording = recast_cooling_passage(slot["text"], recast_error)
            sequence_recast |= wording is not None
        if wording is not None:
            row["text"] = wording
            corrected_paths.append(path)
    if not sequence_recast:
        return None
    return _validate_first_draft(
        source, raw, draft, corrected_paths, prompt_version=prompt_version,
        method=FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD, original_error=original_error,
    )


def _recover_maintenance_draft(source, raw, slots, invalid, *, prompt_version, original_error):
    from .procedure_rewrite_maintenance_recovery import recast_maintenance_passage

    draft = deepcopy(raw)
    corrected = []
    maintenance_recast = False
    for slot, row in zip(slots, draft["replacements"], strict=True):
        error = invalid.get(slot["path"])
        if row["action"] != "rewrite" or (
            error not in _FIRST_DRAFT_RECASTABLE_ERRORS and error != _LUBRICATION_MUTATION
        ):
            continue
        text = slot["text"]
        wording = _equivalent_directive(text) or _equivalent_wording(text)
        if wording is None:
            wording = recast_maintenance_passage(text)
            maintenance_recast |= wording is not None
        if wording is not None:
            row.update(text=wording, reason="Distinct source-bound prose.")
            corrected.append(slot["path"])
    if not maintenance_recast:
        return None
    return _validate_first_draft(
        source, raw, draft, corrected, prompt_version=prompt_version,
        method=FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD, original_error=original_error,
    )


def recover_structured_bankone_first_draft(
    source, attempt, bankone_structure, *, method=BANKONE_STRUCTURAL_RECOVERY_METHOD,
):
    """Recover an exact stored Bankone reply with its verified authored slots."""
    from .bankone_first_draft_recovery import recover_bankone_draft
    from .bankone_first_draft_structure import validate_bankone_structure

    structure_version = BANKONE_ARCHIVE_STRUCTURE_VERSIONS.get(method)
    if structure_version is None:
        return None
    try:
        validate_bankone_structure(source, bankone_structure, expected_version=structure_version)
    except ValueError:
        return None

    guard, raw = attempt["guard_version"], attempt["response"]
    try:
        auto.render_auto(source, raw, prompt_version=guard)
    except ValueError as error:
        original_error = str(error)
    else:
        return None
    if original_error != attempt["error_code"]:
        return None
    recovered = recover_bankone_draft(source, raw, prompt_version=guard, structure=bankone_structure)
    if recovered is None:
        return None
    response, corrected_paths = recovered
    return _validate_first_draft(
        source, raw, response, corrected_paths, prompt_version=guard, method=method,
        original_error=original_error, bankone_structure=bankone_structure,
    )


def recover_archived_first_draft(source, attempt, *, method, expected_hash, bankone_structure=None, previous_source=None):
    """Check the recovered v1 digest and render the same reply under its new v3 owner."""
    guard = attempt["guard_version"]
    if method == FIRST_DRAFT_POSITIONED_FIGURE_RECOVERY_METHOD and previous_source is not None and bankone_structure is None:
        from .positioned_figure_draft import recover_positioned_figure_draft

        recovered = recover_positioned_figure_draft(previous_source, source, attempt)
    elif previous_source is not None:
        recovered = None
    elif method in BANKONE_ARCHIVE_STRUCTURE_VERSIONS and bankone_structure is not None:
        recovered = recover_structured_bankone_first_draft(source, attempt, bankone_structure, method=method)
    elif method in FIRST_DRAFT_RECOVERY_METHODS and bankone_structure is None:
        recovered = recover_first_draft(source, attempt["response"], prompt_version=guard, method=method)
    else:
        recovered = None
    if (recovered is None or recovered.error_code is not None
        or recovered.evidence["original_error_code"] != attempt["error_code"]
        or recovered.evidence["output_hash"] != expected_hash):
        raise ValueError("FIRST_DRAFT_ARCHIVE_RECOVERY_MISMATCH")
    document = auto.render_auto(
        source, recovered.response, prompt_version=guard, profile_version=SOURCE_BOUND_CORRECTION_PROFILE,
        bankone_structure=bankone_structure,
    )
    return CorrectionResult(recovered.response, document, None, {
        "method": ARCHIVED_FIRST_DRAFT_METHOD, "guard_version": guard, "exchanges": [],
        "first_draft_recovery": recovered.evidence,
        "prior_attempt_id": str(attempt["rewrite_attempt_id"]), "prior_prompt_hash": attempt["prompt_hash"],
    }, archived_attempt={key: value for key, value in attempt.items() if key not in {"guard_version", "observation_id"}},
       bankone_structure=bankone_structure)


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
    if original_error == _TECHNICAL_AMBIGUITY:
        if method not in (None, FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD):
            return None
        try:
            auto.check_automatic_introduction(source, raw["introduction"])
        except ValueError as intro_error:
            if str(intro_error) == original_error:
                return _validate_first_draft(
                    source, raw, {**raw, "introduction": NEUTRAL_INTRODUCTION}, [],
                    prompt_version=prompt_version, method=FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD,
                    original_error=original_error,
                )
        return None
    if method == FIRST_DRAFT_INTRODUCTION_RECOVERY_METHOD:
        return None
    if method in (None, FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD):
        diagnostic = _recover_diagnostic_draft(source, raw, slots, prompt_version=prompt_version, original_error=original_error)
        if diagnostic is not None or method == FIRST_DRAFT_DIAGNOSTIC_RECOVERY_METHOD:
            return diagnostic
    action_methods = (FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD, FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD)
    if original_error in ("REWRITE_ACTION_MUTATION", "REWRITE_SPEC_SCOPE_MUTATION"):
        for action_method in action_methods:
            if method not in (None, action_method):
                continue
            recovered = _recover_action_draft(
                source, raw, slots, prompt_version=prompt_version, original_error=original_error, method=action_method,
            )
            if recovered is not None:
                return recovered
    if method in action_methods or original_error == "REWRITE_SPEC_SCOPE_MUTATION":
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
    if method == FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD or original_error == _LUBRICATION_MUTATION:
        if method not in (None, FIRST_DRAFT_MAINTENANCE_RECOVERY_METHOD):
            return None
        return _recover_maintenance_draft(
            source, raw, slots, invalid, prompt_version=prompt_version, original_error=original_error,
        )
    if method == FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD:
        return _recover_cooling_sequence(
            source, raw, slots, invalid, prompt_version=prompt_version, original_error=original_error,
        )
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
    cooling = _recover_legacy_cooling_draft(
        source, raw, draft, slots, corrected, invalid, prompt_version=prompt_version, original_error=original_error,
    )
    if cooling is not None or method == FIRST_DRAFT_COOLING_RECOVERY_METHOD:
        return cooling
    cooling_sequence = _recover_cooling_sequence(
        source, raw, slots, invalid, prompt_version=prompt_version, original_error=original_error,
    )
    if cooling_sequence is not None or method is not None:
        return cooling_sequence
    return _recover_maintenance_draft(
        source, raw, slots, invalid, prompt_version=prompt_version, original_error=original_error,
    )


def _recover_legacy_cooling_draft(source, raw, draft, slots, corrected, invalid, *, prompt_version, original_error):
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
