"""Correct a retained draft in one passage round and one sentence round."""

from hashlib import sha256
from itertools import islice, product
import json
import re

from . import procedure_rewrite_auto as auto
from . import procedure_rewrite_full as full
from .article_lifecycle_types import digest_json
from .procedure_rewrite_correction import (
    CorrectionResult, _MARKER, _MAX_PROMPT_BYTES, _MAX_REPLY_BYTES, _apply_variants,
    _initial_draft, _mask_literals, _passage_errors, _replay_transcript, _validated_document, _variants,
)
from .procedure_rewrite_recovery import _PART, _REFERENCE, _equivalent_wording, _plain_label


SENTENCE_CORRECTION_METHOD = "source-bound-sentence-correction-v1"
SENTENCE_RECOVERY_METHOD = "source-bound-sentence-recovery-v1"
SENTENCE_INSTRUCTION_RECOVERY_METHOD = "source-bound-sentence-recovery-v2"
SENTENCE_TOOL_RECOVERY_METHOD = "source-bound-sentence-recovery-v3"
SENTENCE_SERVICE_PROCEDURE_RECOVERY_METHOD = "source-bound-sentence-recovery-v4"
MAX_SENTENCE_CORRECTION_CALLS = 2
_MAX_STATEMENTS = 60
_MAX_COMBINATIONS = 27
_ALTERNATIVES = 3
_CONDITIONAL_INSTALLATION = re.compile(
    r"(?P<condition>If [^,.;!?]{1,85}),? check to make sure "
    r"(?P<subject>the [^,.;!?]{1,95}?) is installed\.", re.I,
)
_NOUN_PHRASE = r"[\w-]+(?: [\w-]+){0,8}"
_WIRING_EXPLANATION = re.compile(
    rf"(?P<subject>{_NOUN_PHRASE}) are not wired to (?P<target>the {_NOUN_PHRASE}), thus "
    rf"the (?P<component>{_NOUN_PHRASE}) does not communicate directly on a (?P<network>{_NOUN_PHRASE})\."
)
_HARNESS_CONNECTION = re.compile(
    rf"(?P<owner>{_PART}) Wiring Harness ?(?P<harness>{_REFERENCE}) *@ *"
    rf"(?P<target>{_PART}) ?(?P<reference>{_REFERENCE}) *» *(?P<action>Connect|Disconnect)",
    re.I,
)
_LINKED_REMOVAL = re.compile(
    rf"(?P<part>{_PART}) ?(?P<reference>{_REFERENCE}) *» *Remove— *(?P<title>{_PART} Replacement)",
    re.I,
)
_ASSEMBLY_REMOVAL = re.compile(
    rf"Remove the (?P<first>{_PART}) and (?:the )?(?P<second>{_PART}) "
    rf"as an assembly (?P<reference>{_REFERENCE})\.",
    re.I,
)
_LOOSEN_THEN_SLIDE = re.compile(
    rf"Loosen the (?P<screw>(?P<tool>[A-Z]{{2,5}}-[0-9]{{4,6}}) {_PART} screw {_REFERENCE}), then slide "
    rf"the (?P<part>{_PART}) of the (?P<assembly>(?P=tool) {_PART} {_REFERENCE}) "
    rf"away from the (?P<target>{_PART})\.",
    re.I,
)
_TOOL_INSTALLATION = re.compile(
    rf"Install the (?P<tool>(?:{_PART} )?(?:wrench|socket)) (?P<reference>{_REFERENCE}) "
    rf"to the (?P<target>{_PART})\.",
    re.I,
)
_COVER_REMOVAL = re.compile(
    r"Remove the bolts, pin-type retainer and the (?P<cover>(?:LH|RH) cowl cover)\."
)
_HARNESS_RETAINER_REMOVAL = re.compile(
    rf"Disconnect the (?P<harness>{_PART} harness) pin-type retainers, remove the fasteners and bracket\."
)
_SERVICE_TOOL_ID = r"[0-9]{3}-[A-Z0-9]{2,8}(?:-[0-9]{2,3})?"
_ENGINE_SUPPORT = re.compile(
    rf"Using the feet from (?P<feet>{_SERVICE_TOOL_ID}) and the car bar adapters "
    rf"(?P<adapters>{_SERVICE_TOOL_ID}) assemble them on the (?P<bar>{_SERVICE_TOOL_ID}) "
    r"engine support bar and support the engine\. "
    r"Install Special Service Tool: (?P=bar) (?P<bar_label>Support Bar, Engine)\. "
    r"Install Suggested Tool: (?P=adapters) (?P<adapter_label>Adapter, Car-Bar)\. "
    r"Tool shown or a commercially available equivalent can be used\., (?P=feet) (?P=bar_label)\. "
    r"Tool shown or a commercially available equivalent can be used\."
)
_SECTION_REFERENCE = (
    r"(?P<reference>(?P<title>[A-Za-z0-9][A-Za-z0-9 -]{0,96}) "
    r"\([0-9]{3}-[0-9]{2} [A-Za-z0-9 -]{1,96}, (?:General Procedures|Removal and Installation)\))"
)
_CLEAN_SURFACE_REFERENCE = re.compile(
    rf"Make sure that the mating surface is clean and free of foreign material\. Refer to: {_SECTION_REFERENCE}\."
)
_INSTALLATION_REFERENCE = re.compile(
    rf"Install the (?P<part>{_PART})\. Refer to: {_SECTION_REFERENCE}\."
)
_FINGER_TIGHT_OIL_PAN = re.compile(
    r"(?P<note>(?i:note):) Only tighten the bolts finger tight at this stage\. Install the oil pan and the bolts\."
)
_COPY_REJECTIONS = {"REWRITE_UNCHANGED", "REWRITE_PROSE_TOO_SIMILAR"}


def _statement_facts(text):
    return {
        "action_words": [match.group() for match in auto._action_matches(text)],
        "ordered_action_groups": auto._execution_order(text),
        "directions": auto._direction_labels(text),
    }


def _preserves_conditional_installation(source, wording):
    source_sentences = auto._SENTENCES.split(source)
    conditions = [
        (index, match)
        for index, text in enumerate(source_sentences)
        if (match := _CONDITIONAL_INSTALLATION.fullmatch(text.strip())) is not None
    ]
    if not conditions:
        return True
    sentences = auto._SENTENCES.split(wording)
    if len(sentences) != len(source_sentences):
        return False
    for index, match in conditions:
        condition = r"(?i:if)" + re.escape(match["condition"][2:])
        subject = re.escape(match["subject"])
        inspection = rf"(?i:check to (?:confirm|make sure)|confirm|verify)(?: that)? {subject} (?i:is installed)"
        if re.fullmatch(rf"(?:{condition},? {inspection}|{inspection},? {condition})\.", sentences[index].strip()) is None:
            return False
    return True


def _remaining_passage_errors(source, slots, draft):
    failures = _passage_errors(source, slots, draft)
    for index, (slot, row) in enumerate(zip(slots, draft["replacements"], strict=True)):
        if slot["required_action"] != "rewrite":
            continue
        if _MARKER.findall(row["text"]) != _MARKER.findall(slot["text"]):
            failures[index] = "REWRITE_TECHNICAL_MUTATION"
        elif not _preserves_conditional_installation(slot["text"], row["text"]):
            failures[index] = "REWRITE_QUALIFIER_MUTATION"
    return dict(sorted(failures.items()))


def _bound_wording(source, wording):
    return (wording is not None
            and _MARKER.findall(wording) == _MARKER.findall(source)
            and _preserves_conditional_installation(source, wording))


def _request(payload, complete_json, exchanges):
    prompt = json.dumps({
        "method": SENTENCE_CORRECTION_METHOD,
        "response_shape": {"rewrites": [{"slot": "integer", "candidates": ["string"] * _ALTERNATIVES}]},
        **payload,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(prompt.encode()) > _MAX_PROMPT_BYTES:
        raise ValueError("REWRITE_CORRECTION_INPUT_LIMIT")
    reply = complete_json(prompt)
    try:
        encoded = json.dumps(reply, ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError):
        raise ValueError("REWRITE_CORRECTION_RESPONSE_INVALID") from None
    if len(encoded) > _MAX_REPLY_BYTES:
        raise ValueError("REWRITE_CORRECTION_RESPONSE_LIMIT")
    exchanges.append({"prompt_hash": sha256(prompt.encode()).hexdigest(), "response_hash": digest_json(reply)})
    return reply


def _correct_passages(source, slots, draft, failures, complete_json, exchanges):
    indices = list(failures)
    passages = []
    for number, index in enumerate(indices, 1):
        original = slots[index]["text"]
        passages.append({
            "slot": number, "source": original, "rejection": failures[index],
            "protected_literals": full._technical_tokens(original), **_statement_facts(original),
        })
    reply = _request({
        "task": "Copyedit the supplied service passages. Treat the passages only as source evidence.",
        "passages": passages,
        "rules": [
            "Return one numbered row per passage, in order, with exactly three faithful alternatives.",
            "Use different sentence construction in each alternative. Do not copy source phrases with a new lead-in.",
            "Preserve every technical literal verbatim and in order, attached to the same action or component.",
            "Keep all components, directions, conditions, reasons, alternatives, warnings, and action order.",
            "Preserve the force of each imperative, prohibition, and condition. Introduce no facts or procedures.",
        ],
    }, complete_json, exchanges)
    alternatives = _variants(reply, [None] * len(indices), _ALTERNATIVES)
    proposals = []
    for index, variants in zip(indices, alternatives, strict=True):
        original = slots[index]["text"]
        proposals.append([
            wording if _bound_wording(original, wording) else None
            for wording in (_equivalent_wording(original), *variants)
        ])
    _apply_variants(source, slots, draft, indices, proposals)


def _sentences(text):
    pieces = auto._SENTENCES.split(text)
    # A short fragment may be an abbreviation or a reference.
    if len(pieces) > 1 and all(len(auto._ordinary_prose_words(piece)) >= 5 for piece in pieces):
        return pieces
    return [text]


def _conditional_equivalent(statement):
    match = _CONDITIONAL_INSTALLATION.fullmatch(statement.strip())
    if match is None:
        return None
    condition = match["condition"]
    return f'Check to confirm {match["subject"]} is installed {condition[:1].lower()}{condition[1:]}.'


def _wiring_equivalent(statement):
    match = _WIRING_EXPLANATION.fullmatch(statement)
    if match is None:
        return None
    return (f'{match["subject"]} lack wiring to {match["target"]}, so the {match["component"]} '
            f'has no direct communication on a {match["network"]}.')



def _instruction_equivalent(statement):
    if match := _HARNESS_CONNECTION.fullmatch(statement):
        owner, target = match["owner"], match["target"]
        # A directional label could describe the harness or its owner.
        if all(_plain_label(label) and not auto._direction_labels(label) for label in (owner, target)):
            action = match["action"].capitalize()
            relation = "from" if action == "Disconnect" else "to"
            return (
                f'{action} wiring harness {match["harness"]} for the {owner} '
                f'{relation} the {target} {match["reference"]}.'
            )
    if match := _LINKED_REMOVAL.fullmatch(statement):
        part, title = match["part"], match["title"]
        if _plain_label(part) and title.casefold() == f"{part} Replacement".casefold():
            return f'Remove the component identified by {match["reference"]} using the steps in {title}.'
    if match := _ASSEMBLY_REMOVAL.fullmatch(statement):
        first, second = match["first"], match["second"]
        if _plain_label(first) and _plain_label(second):
            return (
                f'Remove assembly {match["reference"]} in one piece, '
                f"keeping the {first} together with the {second}."
            )
    if match := _LOOSEN_THEN_SLIDE.fullmatch(statement):
        if all(_plain_label(match[label]) for label in ("screw", "part", "assembly", "target")):
            return (
                f'Loosen the {match["screw"]} first. Then move the {match["part"]} of the {match["assembly"]} '
                f'by sliding it away from the {match["target"]}.'
            )
    return None


def _statement_options(source, alternatives):
    def acceptable(wording):
        return (_bound_wording(source, wording)
                and full._technical_tokens(wording) == full._technical_tokens(source)
                and auto._execution_order(wording) == auto._execution_order(source)
                and auto._direction_scope(wording) == auto._direction_scope(source)
                and not auto._near_copy(source, wording, check_sentences=True))

    return list(dict.fromkeys(
        wording for wording in (*alternatives, _conditional_equivalent(source)) if acceptable(wording)
    ))


def _statement_variants(reply, texts, literals):
    rows = _variants(reply, [None] * len(texts), _ALTERNATIVES)
    for text, choices, tokens in zip(texts, rows, literals, strict=True):
        if tokens is None:
            yield choices
            continue
        restored = []
        for wording in choices:
            markers = _MARKER.findall(wording)
            if markers == list(tokens):
                restored.append(_MARKER.sub(lambda match: tokens[match.group()], wording))
            elif not markers and full._technical_tokens(wording) == full._technical_tokens(text):
                restored.append(wording)
            else:
                restored.append(None)
        yield restored


def _combined_options(original, options):
    combined = (" ".join(parts) for parts in islice(product(*options), _MAX_COMBINATIONS))
    return [wording for wording in combined if _bound_wording(original, wording)]


def _correct_sentences(source, slots, draft, failures, complete_json, exchanges, *, recover=False):
    groups, texts, literals, statements = [], [], [], []
    for index in failures:
        pieces = _sentences(slots[index]["text"])
        if len(texts) + len(pieces) > _MAX_STATEMENTS:
            raise ValueError("REWRITE_CORRECTION_INPUT_LIMIT")
        groups.append((index, len(pieces)))
        texts.extend(pieces)
        for text in pieces:
            masked, tokens = _mask_literals(text)
            literals.append(tokens)
            statements.append({
                "slot": len(statements) + 1,
                "statement": text if masked is None else masked,
                **_statement_facts(text),
            })
    reply = _request({
        "task": "Copyedit each service statement using only the supplied source.",
        "statements": statements,
        "rules": [
            "Return one numbered row per statement, in order, with exactly three faithful alternatives.",
            "Change the clause structure of every sentence. Use concise equivalent wording for a short label.",
            "Keep every condition, warning, qualifier, action, component, direction, and original action order.",
            "Preserve whether a condition holds or an action is required, optional, or forbidden.",
            "Copy all [TOKENn] markers once in order, with the original action or component.",
            "Introduce no new procedures or facts.",
        ],
    }, complete_json, exchanges)
    variants = _statement_variants(reply, texts, literals)
    options = [_statement_options(text, rows) for text, rows in zip(texts, variants, strict=True)]
    recovery = {}
    offset = 0
    for index, count in groups:
        original = slots[index]["text"]
        group = options[offset:offset + count]
        if bounded := _combined_options(original, group):
            _apply_variants(source, slots, draft, [index], [bounded])
        if recover:
            for position, text in enumerate(texts[offset:offset + count]):
                wording = _wiring_equivalent(text)
                if wording and wording in _statement_options(text, [wording]):
                    recovery[index] = _combined_options(
                        original, [*group[:position], [wording], *group[position + 1:]],
                    )
                    break
        offset += count
    return recovery


def correct_sentence_draft(source, previous, *, complete_json, model_call_budget, preserve_notes=False):
    """Keep valid retained prose and correct failed passages with at most two calls."""
    return _correct_sentence_draft(
        source, previous, complete_json=complete_json, model_call_budget=model_call_budget,
        preserve_notes=preserve_notes,
    )


def _validate_sentence_draft(source, slots, draft, version):
    document, error_code = _validated_document(source, slots, draft, version)
    if document is not None and (failures := _remaining_passage_errors(source, slots, draft)):
        return None, next(iter(failures.values()))
    return document, error_code


def _correct_sentence_draft(source, previous, *, complete_json, model_call_budget, recover=False, preserve_notes=False):
    if type(model_call_budget) is not int or not 1 <= model_call_budget <= MAX_SENTENCE_CORRECTION_CALLS:
        raise ValueError("REWRITE_CORRECTION_BUDGET_INVALID")
    version, slots, draft = _initial_draft(source, previous, preserve_notes=preserve_notes)
    exchanges = []
    recovery = {}
    failures = _remaining_passage_errors(source, slots, draft)
    if failures:
        _correct_passages(source, slots, draft, failures, complete_json, exchanges)
        if model_call_budget == MAX_SENTENCE_CORRECTION_CALLS:
            failures = _remaining_passage_errors(source, slots, draft)
            if failures:
                recovery = _correct_sentences(source, slots, draft, failures, complete_json, exchanges, recover=recover)
    document, error_code = _validate_sentence_draft(source, slots, draft, version)
    evidence = {
        "method": SENTENCE_CORRECTION_METHOD, "input_hash": digest_json(source),
        "guard_version": version, "prior_response_hash": digest_json(previous),
        "model_call_budget": model_call_budget, "exchanges": exchanges, "draft_hash": digest_json(draft),
    }
    if recover:
        evidence.update(method=SENTENCE_RECOVERY_METHOD, base_draft_hash=evidence["draft_hash"],
                        original_error_code=error_code)
        for index in _remaining_passage_errors(source, slots, draft):
            if options := recovery.get(index):
                _apply_variants(source, slots, draft, [index], [options])
        document, error_code = _validate_sentence_draft(source, slots, draft, version)
        evidence["draft_hash"] = digest_json(draft)
    return CorrectionResult(draft, document, error_code, evidence)


def recover_sentence_correction(source, previous, *, model_call_budget, attempts, preserve_notes=False):
    """Replay the terminal draft and reframe proven wiring explanations without dispatch."""
    def recover(source, previous, **options):
        return _correct_sentence_draft(source, previous, recover=True, **options)

    return _replay_transcript(recover, source, previous, model_call_budget=model_call_budget, attempts=attempts,
                              preserve_notes=preserve_notes)


def recover_numbered_sentence_instructions(source, previous, *, model_call_budget, attempts, preserve_notes=False):
    """Finish recognized diagram instructions using the exact saved correction."""
    baseline = recover_sentence_correction(
        source, previous, model_call_budget=model_call_budget, attempts=attempts, preserve_notes=preserve_notes,
    )
    return _recover_sentence_passages(
        source, previous, baseline, preserve_notes=preserve_notes, errors=_COPY_REJECTIONS,
        equivalent=_instruction_equivalent, method=SENTENCE_INSTRUCTION_RECOVERY_METHOD,
    )


def _tool_installation_equivalent(statement):
    if (match := _TOOL_INSTALLATION.fullmatch(statement)) and all(
        _plain_label(match[label]) for label in ("tool", "target")
    ):
        tool, reference, target = match.group("tool", "reference", "target")
        return f"The {tool} {reference} must be fitted to the {target}."
    return None


def recover_tool_installation_sentence(source, previous, *, model_call_budget, attempts, preserve_notes=False):
    """Keep the authored tool, figure reference and installation target."""
    baseline = recover_numbered_sentence_instructions(
        source, previous, model_call_budget=model_call_budget, attempts=attempts, preserve_notes=preserve_notes,
    )
    return _recover_sentence_passages(
        source, previous, baseline, preserve_notes=preserve_notes,
        errors=_COPY_REJECTIONS | {"REWRITE_ACTION_MUTATION"},
        equivalent=_tool_installation_equivalent, method=SENTENCE_TOOL_RECOVERY_METHOD,
    )


def _service_procedure_equivalent(statement):
    if match := _COVER_REMOVAL.fullmatch(statement):
        return f'The bolts and pin-type retainer must be removed along with the {match["cover"]}.'
    if (match := _HARNESS_RETAINER_REMOVAL.fullmatch(statement)) and _plain_label(match["harness"]):
        return (
            f'First disconnect the pin-type retainers for the {match["harness"]}. '
            "Then remove both the fasteners and bracket."
        )
    if match := _ENGINE_SUPPORT.fullmatch(statement):
        feet, adapters, bar, bar_label, adapter_label = match.groups()
        if len({feet, adapters, bar}) == 3:
            return (
                f"Fit the feet from {feet} and the car bar adapters {adapters} onto the {bar} engine support bar. "
                f"Support the engine with the assembled bar. The special service tool to install is the {bar} {bar_label}. "
                f"For the suggested tool, install the {adapters} {adapter_label}. "
                "The illustrated adapter or a commercially available equivalent is acceptable. "
                f"For {feet} {bar_label}, use the illustrated tool or a commercially available equivalent."
            )
    if match := _CLEAN_SURFACE_REFERENCE.fullmatch(statement):
        return f'Confirm the mating surface is clean and clear of any foreign material. Follow the method in {match["reference"]}.'
    if (match := _INSTALLATION_REFERENCE.fullmatch(statement)) and (
        _plain_label(match["part"]) and match["part"].casefold() == match["title"].casefold()
    ):
        return f'The {match["part"]} must be fitted. Follow the steps in {match["reference"]} to fit it.'
    if match := _FINGER_TIGHT_OIL_PAN.fullmatch(statement):
        return f'{match["note"]} Limit bolt tightening to finger tight at this stage. Fit the oil pan together with its bolts.'
    return None


def recover_service_procedure_sentences(source, previous, *, model_call_budget, attempts, preserve_notes=False):
    """Recast held service steps with the same actions, tools and manual references."""
    baseline = recover_tool_installation_sentence(
        source, previous, model_call_budget=model_call_budget, attempts=attempts, preserve_notes=preserve_notes,
    )
    return _recover_sentence_passages(
        source, previous, baseline, preserve_notes=preserve_notes,
        errors=_COPY_REJECTIONS | {"REWRITE_ACTION_MUTATION", "REWRITE_DIRECTION_MUTATION"},
        equivalent=_service_procedure_equivalent, method=SENTENCE_SERVICE_PROCEDURE_RECOVERY_METHOD,
    )


def _recover_sentence_passages(source, previous, baseline, *, preserve_notes, errors, equivalent, method):
    if baseline.document is not None:
        return baseline

    version, slots, _ = _initial_draft(source, previous, preserve_notes=preserve_notes)
    draft = baseline.response
    indices, proposals = [], []
    for index, error in _remaining_passage_errors(source, slots, draft).items():
        if error not in errors:
            continue
        original = slots[index]["text"].strip()
        wording = equivalent(original)
        if wording and wording in _statement_options(original, [wording]):
            indices.append(index)
            proposals.append([wording])
    if not proposals:
        return baseline
    _apply_variants(source, slots, draft, indices, proposals)
    document, error_code = _validate_sentence_draft(source, slots, draft, version)
    evidence = {**baseline.evidence, "method": method, "draft_hash": digest_json(draft)}
    return CorrectionResult(draft, document, error_code, evidence)
