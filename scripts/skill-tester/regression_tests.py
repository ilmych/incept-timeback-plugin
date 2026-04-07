"""Regression tests for the rules documented in skills/timeback/references/.

Each test creates a real item against the live QTI API, GETs it back, asserts
the rule held, and cleans up. Designed to be called both:
  - by the nightly skill-tester agent (via Phase 3 of agents/skill-tester.md)
  - manually: `python -m skill-tester.regression_tests` from the scripts/ dir

Tests are intentionally narrow — one rule per test — so a failure points
straight at the rule that broke.
"""

from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path
from typing import Callable

# The package directory has a hyphen, so we register it under a clean name
# in sys.modules and load api_client as a submodule of that package.
_HERE = Path(__file__).parent
_PARENT = _HERE.parent  # scripts/

if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

# Make `skill_tester` a synonym for the `skill-tester` directory so the
# relative `from .auth import ...` inside api_client.py resolves cleanly.
import importlib.util
_PKG_SPEC = importlib.util.spec_from_file_location(
    "skill_tester", _HERE / "__init__.py", submodule_search_locations=[str(_HERE)]
)
_PKG = importlib.util.module_from_spec(_PKG_SPEC)
sys.modules["skill_tester"] = _PKG
_PKG_SPEC.loader.exec_module(_PKG)

from skill_tester.api_client import APIClient  # noqa: E402


# ---------------------------------------------------------------------------
# Test cases — each returns (passed: bool, message: str)
# ---------------------------------------------------------------------------


def test_mcq_inline_feedback_round_trip(client: APIClient) -> tuple[bool, str]:
    """Verify per-option <qti-feedback-inline> blocks survive XML POST→GET.

    Rule (create-mcq.md): per-option explanations MUST live in
    <qti-feedback-inline> elements keyed by choice identifier, NOT embedded
    in the choice text.
    """
    test_id = client.gen_id("mcq-fb-inline")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0" identifier="{test_id}" title="Inline Feedback Regression" adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="identifier">
    <qti-correct-response><qti-value>A</qti-value></qti-correct-response>
  </qti-response-declaration>
  <qti-outcome-declaration identifier="SCORE" base-type="float" cardinality="single"/>
  <qti-outcome-declaration identifier="FEEDBACK" base-type="identifier" cardinality="single"/>
  <qti-outcome-declaration identifier="FEEDBACK-INLINE" base-type="identifier" cardinality="single"/>
  <qti-item-body>
    <qti-choice-interaction response-identifier="RESPONSE" max-choices="1" shuffle="false">
      <qti-prompt><p>Pick A.</p></qti-prompt>
      <qti-simple-choice identifier="A">Option A</qti-simple-choice>
      <qti-simple-choice identifier="B">Option B</qti-simple-choice>
      <qti-simple-choice identifier="C">Option C</qti-simple-choice>
      <qti-simple-choice identifier="D">Option D</qti-simple-choice>
    </qti-choice-interaction>
    <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="A" show-hide="show"><p>Correct.</p></qti-feedback-inline>
    <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="B" show-hide="show"><p>Wrong B.</p></qti-feedback-inline>
    <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="C" show-hide="show"><p>Wrong C.</p></qti-feedback-inline>
    <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="D" show-hide="show"><p>Wrong D.</p></qti-feedback-inline>
  </qti-item-body>
  <qti-response-processing template="https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/match_correct.xml"/>
</qti-assessment-item>"""

    create = client.create_item_xml(xml)
    if not create.get("success"):
        return False, f"create failed: status={create.get('status')} err={create.get('error', '')[:200]}"

    time.sleep(0.5)
    got = client.get_item(test_id)
    client.delete_item(test_id)

    if not got.get("success"):
        return False, f"get failed: {got}"

    raw = got["data"].get("rawXml", "")
    expected_count = 4
    actual_count = raw.count("qti-feedback-inline")
    # qti-feedback-inline appears twice per element (open + close tag)
    open_count = raw.count("<qti-feedback-inline ")
    if open_count != expected_count:
        return False, f"expected {expected_count} <qti-feedback-inline> elements in rawXml, got {open_count}"

    # Each choice identifier should appear in a feedback-inline block
    for choice in ("A", "B", "C", "D"):
        marker = f'identifier="{choice}"'
        # find feedback-inline opening tag with this identifier
        if f'<qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="{choice}"' not in raw:
            return False, f"feedback-inline for choice {choice} missing from rawXml"

    return True, f"4 feedback-inline blocks present in rawXml for {test_id}"


def test_mcq_explanations_not_in_choice_text(client: APIClient) -> tuple[bool, str]:
    """Negative-pattern check: confirm choice content does NOT bleed explanations.

    Rule (create-mcq.md): choice content must contain ONLY the option text.
    """
    test_id = client.gen_id("mcq-clean-choices")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0" identifier="{test_id}" title="Clean choices" adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="identifier">
    <qti-correct-response><qti-value>A</qti-value></qti-correct-response>
  </qti-response-declaration>
  <qti-outcome-declaration identifier="SCORE" base-type="float" cardinality="single"/>
  <qti-outcome-declaration identifier="FEEDBACK" base-type="identifier" cardinality="single"/>
  <qti-outcome-declaration identifier="FEEDBACK-INLINE" base-type="identifier" cardinality="single"/>
  <qti-item-body>
    <qti-choice-interaction response-identifier="RESPONSE" max-choices="1" shuffle="false">
      <qti-prompt><p>Q?</p></qti-prompt>
      <qti-simple-choice identifier="A">Dog</qti-simple-choice>
      <qti-simple-choice identifier="B">Lizard</qti-simple-choice>
      <qti-simple-choice identifier="C">Trout</qti-simple-choice>
      <qti-simple-choice identifier="D">Eagle</qti-simple-choice>
    </qti-choice-interaction>
    <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="A" show-hide="show"><p>Dogs are mammals.</p></qti-feedback-inline>
    <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="B" show-hide="show"><p>Lizards are reptiles.</p></qti-feedback-inline>
    <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="C" show-hide="show"><p>Trout are fish.</p></qti-feedback-inline>
    <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="D" show-hide="show"><p>Eagles are birds.</p></qti-feedback-inline>
  </qti-item-body>
  <qti-response-processing template="https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/match_correct.xml"/>
</qti-assessment-item>"""

    create = client.create_item_xml(xml)
    if not create.get("success"):
        return False, f"create failed: {create}"

    time.sleep(0.3)
    got = client.get_item(test_id)
    client.delete_item(test_id)

    if not got.get("success"):
        return False, f"get failed: {got}"

    raw = got["data"].get("rawXml", "")
    # Confirm none of the explanation phrases leaked into qti-simple-choice tags
    leaked_phrases = ["mammals.</qti-simple-choice>", "reptiles.</qti-simple-choice>",
                      "fish.</qti-simple-choice>", "birds.</qti-simple-choice>"]
    for phrase in leaked_phrases:
        if phrase in raw:
            return False, f"explanation leaked into qti-simple-choice: {phrase}"

    return True, "choice text contains only option labels"


def test_frq_xml_post_persists_rubric_block(client: APIClient,
                                             grader_url: str | None) -> tuple[bool, str]:
    """Verify <qti-rubric-block> in body survives XML POST→GET.

    Rule (create-frq.md): rubric MUST live in <qti-rubric-block> inside
    <qti-item-body>, not just in metadata.rubric.
    """
    test_id = client.gen_id("frq-rubric")
    # Use a minimal item WITHOUT custom-operator so we don't trip the allowlist.
    # This isolates the rubric-block round-trip from the grader-URL test.
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0" identifier="{test_id}" title="FRQ Rubric Regression" adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="string"><qti-correct-response/></qti-response-declaration>
  <qti-outcome-declaration identifier="SCORE" base-type="float" cardinality="single"/>
  <qti-outcome-declaration identifier="FEEDBACK" base-type="identifier" cardinality="single"/>
  <qti-outcome-declaration identifier="API_RESPONSE" base-type="string" cardinality="single"/>
  <qti-outcome-declaration identifier="GRADING_RESPONSE" base-type="string" cardinality="single"/>
  <qti-outcome-declaration identifier="FEEDBACK_VISIBILITY" base-type="boolean" cardinality="single"/>
  <qti-item-body>
    <qti-extended-text-interaction response-identifier="RESPONSE">
      <qti-prompt><p>Write a Java method that returns the sum of two ints.</p></qti-prompt>
    </qti-extended-text-interaction>
    <qti-rubric-block view="scorer">
      <div data-part="a">Method signature is public, returns int, takes two int parameters.</div>
    </qti-rubric-block>
    <qti-rubric-block view="scorer">
      <div data-part="b">Body returns the sum of the two parameters.</div>
    </qti-rubric-block>
  </qti-item-body>
</qti-assessment-item>"""

    create = client.create_item_xml(xml)
    if not create.get("success"):
        return False, f"create failed: status={create.get('status')} err={create.get('error', '')[:300]}"

    time.sleep(0.5)
    got = client.get_item(test_id)
    client.delete_item(test_id)

    if not got.get("success"):
        return False, f"get failed: {got}"

    raw = got["data"].get("rawXml", "")
    rubric_count = raw.count("<qti-rubric-block")
    if rubric_count < 2:
        return False, f"expected ≥2 <qti-rubric-block> in rawXml, got {rubric_count}"
    if 'view="scorer"' not in raw:
        return False, "rubric-block missing view=\"scorer\" attribute after round-trip"
    if "data-part=\"a\"" not in raw or "data-part=\"b\"" not in raw:
        return False, "data-part attributes lost after round-trip"

    return True, f"2 rubric-blocks with view=scorer + data-part attrs persisted for {test_id}"


def test_frq_json_post_drops_rubric_and_operator(client: APIClient) -> tuple[bool, str]:
    """Negative confirmation: JSON POST silently drops rubric-block and custom-operator from rawXml.

    This is the trap documented in create-frq.md. We confirm it still holds — if the API
    is fixed someday, this test will FAIL and the docs need updating.
    """
    test_id = client.gen_id("frq-json-trap")
    payload = {
        "identifier": test_id,
        "title": "JSON FRQ Trap",
        "type": "extended-text",
        "interaction": {
            "type": "extended-text",
            "responseIdentifier": "RESPONSE",
            "questionStructure": {"prompt": "<p>Write a Java method.</p>"},
        },
        "responseDeclarations": [{"identifier": "RESPONSE", "cardinality": "single", "baseType": "string"}],
        "outcomeDeclarations": [
            {"identifier": "SCORE", "cardinality": "single", "baseType": "float"},
            {"identifier": "FEEDBACK", "cardinality": "single", "baseType": "identifier"},
            {"identifier": "API_RESPONSE", "cardinality": "single", "baseType": "string"},
            {"identifier": "GRADING_RESPONSE", "cardinality": "single", "baseType": "string"},
            {"identifier": "FEEDBACK_VISIBILITY", "cardinality": "single", "baseType": "boolean"},
        ],
        "responseProcessing": {
            "templateType": "custom",
            "customOperator": {
                "class": "com.alpha-1edtech.ExternalApiScore",
                "definition": "https://cs-autograder.onrender.com/cs-autograder/score",
            },
        },
        "metadata": {
            "rubric": "<qti-rubric-block>Criterion A</qti-rubric-block><qti-rubric-block>Criterion B</qti-rubric-block>",
        },
    }

    create = client.create_item_json(payload)
    if not create.get("success"):
        return False, f"create failed: {create}"

    time.sleep(0.5)
    got = client.get_item(test_id)
    client.delete_item(test_id)

    if not got.get("success"):
        return False, f"get failed: {got}"

    raw = got["data"].get("rawXml", "")
    has_rubric = "qti-rubric-block" in raw
    has_operator = "ExternalApiScore" in raw
    if has_rubric or has_operator:
        return False, (
            "TRAP CLOSED — JSON POST now propagates rubric/operator to rawXml. "
            "Update create-frq.md: JSON POST may be safe again. "
            f"has_rubric_block={has_rubric}, has_operator={has_operator}"
        )

    return True, "trap still active: JSON POST drops rubric-block + custom-operator from rawXml"


def test_frq_grader_url_allowlist_enforced(client: APIClient) -> tuple[bool, str]:
    """Verify XML POST still rejects an obviously-bogus grader hostname.

    Rule (create-frq.md): XML POST validates grader URL hostnames against an
    internal allowlist. If this returns 201 instead of 500, the validator was
    removed and the docs need updating.
    """
    test_id = client.gen_id("frq-allowlist")
    bogus_url = "https://definitely-not-allowlisted.example/score"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0" identifier="{test_id}" title="Allowlist Probe" adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="string"><qti-correct-response/></qti-response-declaration>
  <qti-outcome-declaration identifier="SCORE" base-type="float" cardinality="single"/>
  <qti-item-body>
    <qti-extended-text-interaction response-identifier="RESPONSE"><qti-prompt><p>X</p></qti-prompt></qti-extended-text-interaction>
  </qti-item-body>
  <qti-response-processing>
    <qti-response-condition><qti-response-if>
      <qti-custom-operator class="com.alpha-1edtech.ExternalApiScore" definition="{bogus_url}">
        <qti-variable identifier="RESPONSE"/>
      </qti-custom-operator>
      <qti-set-outcome-value identifier="SCORE"><qti-base-value base-type="float">1</qti-base-value></qti-set-outcome-value>
    </qti-response-if></qti-response-condition>
  </qti-response-processing>
</qti-assessment-item>"""

    create = client.create_item_xml(xml)
    if create.get("success"):
        # If we accidentally created it, clean up
        client.delete_item(test_id)
        return False, f"allowlist NOT enforced: bogus URL accepted (status={create.get('status')})"

    err = create.get("error", "")
    if "allowlist" in err.lower() or "not in the approved" in err.lower():
        return True, "allowlist enforced — bogus grader URL rejected with allowlist error"

    return False, f"unexpected rejection (not allowlist-related): status={create.get('status')} err={err[:200]}"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS: list[tuple[str, Callable[[APIClient], tuple[bool, str]]]] = [
    ("mcq_inline_feedback_round_trip", test_mcq_inline_feedback_round_trip),
    ("mcq_explanations_not_in_choice_text", test_mcq_explanations_not_in_choice_text),
    ("frq_xml_post_persists_rubric_block",
     lambda c: test_frq_xml_post_persists_rubric_block(c, grader_url=None)),
    ("frq_json_post_drops_rubric_and_operator", test_frq_json_post_drops_rubric_and_operator),
    ("frq_grader_url_allowlist_enforced", test_frq_grader_url_allowlist_enforced),
]


def run_all() -> int:
    client = APIClient("regression")
    passed = 0
    failed = 0
    results = []
    for name, fn in TESTS:
        try:
            ok, msg = fn(client)
        except Exception as exc:  # noqa: BLE001
            ok, msg = False, f"exception: {exc}"
        status = "PASS" if ok else "FAIL"
        results.append((status, name, msg))
        print(f"  {status}  {name} — {msg}")
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    print(f"Summary: {passed} passed / {failed} failed / {len(TESTS)} total")
    print(f"Log: {client.log_file}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
