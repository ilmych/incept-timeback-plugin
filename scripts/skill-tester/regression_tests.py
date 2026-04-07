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


# Allowlisted grader URL used by s4-u1-frq-01 (verified 2026-04-07).
# If the platform team rotates the host, update this constant and the
# allowlist-status table in create-frq.md.
CANONICAL_GRADER_URL = "https://coreapi.inceptstore.com/api/cs-autograder/score"


def _canonical_frq_xml(test_id: str, grader_url: str = CANONICAL_GRADER_URL) -> str:
    """Return a minimal but FULLY CANONICAL FRQ XML matching s4-u1-frq-01.

    Mirrors the structure documented in create-frq.md so a regression flip
    points straight at the rule that broke. Keep this in sync with that doc.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqtiasi_v3p0 https://purl.imsglobal.org/spec/qti/v3p0/schema/xsd/imsqti_asiv3p0_v1p0.xsd" identifier="{test_id}" title="FRQ Canonical Regression" adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="string">
    <qti-correct-response><qti-value /></qti-correct-response>
  </qti-response-declaration>
  <qti-outcome-declaration identifier="API_RESPONSE" cardinality="record" base-type="string">
    <qti-default-value>
      <qti-value base-type="string" field-identifier="FEEDBACK" />
      <qti-value base-type="string" field-identifier="feedback" />
      <qti-value base-type="float" field-identifier="SCORE">0</qti-value>
    </qti-default-value>
  </qti-outcome-declaration>
  <qti-outcome-declaration identifier="FEEDBACK_VISIBILITY" cardinality="single" base-type="identifier" />
  <qti-outcome-declaration identifier="GENERATED_FEEDBACK" cardinality="single" base-type="string" />
  <qti-outcome-declaration identifier="MAXSCORE" cardinality="single" base-type="float">
    <qti-default-value><qti-value>1</qti-value></qti-default-value>
  </qti-outcome-declaration>
  <qti-outcome-declaration identifier="SCORE" cardinality="single" base-type="float" normal-maximum="1">
    <qti-default-value><qti-value>0</qti-value></qti-default-value>
  </qti-outcome-declaration>
  <qti-item-body>
    <qti-extended-text-interaction response-identifier="RESPONSE">
      <qti-prompt><p>Write a Java method that returns the sum of two ints.</p></qti-prompt>
    </qti-extended-text-interaction>
    <qti-feedback-block outcome-identifier="FEEDBACK_VISIBILITY" identifier="VISIBLE">
      <qti-content-body>
        <div style="white-space: pre-line;">
          <qti-printed-variable identifier="GENERATED_FEEDBACK" class="qti-html-printed-variable" />
        </div>
      </qti-content-body>
    </qti-feedback-block>
    <qti-rubric-block use="ext:criteria" view="scorer">
      <qti-content-body>
        <h1>Sum Method Rubric (2 points)</h1>
        <p>1. Method signature is public, returns int, takes two int parameters.</p>
        <p>2. Body returns the sum of the two parameters.</p>
      </qti-content-body>
    </qti-rubric-block>
  </qti-item-body>
  <qti-response-processing>
    <qti-set-outcome-value identifier="API_RESPONSE">
      <qti-custom-operator class="com.alpha-1edtech.ExternalApiScore" definition="{grader_url}">
        <qti-variable identifier="RESPONSE" />
      </qti-custom-operator>
    </qti-set-outcome-value>
    <qti-set-outcome-value identifier="SCORE">
      <qti-field-value field-identifier="SCORE">
        <qti-variable identifier="API_RESPONSE" />
      </qti-field-value>
    </qti-set-outcome-value>
    <qti-set-outcome-value identifier="GENERATED_FEEDBACK">
      <qti-field-value field-identifier="feedback">
        <qti-variable identifier="API_RESPONSE" />
      </qti-field-value>
    </qti-set-outcome-value>
    <qti-response-condition>
      <qti-response-if>
        <qti-is-null><qti-variable identifier="GENERATED_FEEDBACK" /></qti-is-null>
        <qti-set-outcome-value identifier="GENERATED_FEEDBACK">
          <qti-field-value field-identifier="FEEDBACK">
            <qti-variable identifier="API_RESPONSE" />
          </qti-field-value>
        </qti-set-outcome-value>
      </qti-response-if>
    </qti-response-condition>
    <qti-set-outcome-value identifier="FEEDBACK_VISIBILITY">
      <qti-base-value base-type="identifier">VISIBLE</qti-base-value>
    </qti-set-outcome-value>
    <qti-response-condition>
      <qti-response-if>
        <qti-is-null><qti-variable identifier="RESPONSE" /></qti-is-null>
        <qti-set-outcome-value identifier="SCORE">
          <qti-base-value base-type="float">0</qti-base-value>
        </qti-set-outcome-value>
        <qti-set-outcome-value identifier="FEEDBACK_VISIBILITY">
          <qti-base-value base-type="identifier">VISIBLE</qti-base-value>
        </qti-set-outcome-value>
      </qti-response-if>
    </qti-response-condition>
  </qti-response-processing>
</qti-assessment-item>"""


def test_frq_xml_post_persists_canonical_pattern(client: APIClient,
                                                  grader_url: str | None = None) -> tuple[bool, str]:
    """Verify the FULL canonical FRQ XML survives XML POST→GET.

    Rule (create-frq.md): the canonical pattern requires rubric-block (with
    use=ext:criteria, view=scorer, qti-content-body wrapper), feedback-block
    + printed-variable, custom-operator, and 6 outcome declarations with the
    correct cardinalities and base-types — all in rawXml. This test asserts
    every one of those pieces round-trips through POST→GET.
    """
    url = grader_url or CANONICAL_GRADER_URL
    test_id = client.gen_id("frq-canonical")
    xml = _canonical_frq_xml(test_id, url)

    create = client.create_item_xml(xml)
    if not create.get("success"):
        return False, f"create failed: status={create.get('status')} err={create.get('error', '')[:400]}"

    time.sleep(0.5)
    got = client.get_item(test_id)
    client.delete_item(test_id)

    if not got.get("success"):
        return False, f"get failed: {got}"

    raw = got["data"].get("rawXml", "")
    checks: list[tuple[str, bool]] = [
        ("rubric-block",                 "<qti-rubric-block" in raw),
        ('use="ext:criteria"',           'use="ext:criteria"' in raw),
        ('view="scorer"',                'view="scorer"' in raw),
        ("qti-content-body wrapper",     "<qti-content-body" in raw),
        ("custom-operator",              "<qti-custom-operator" in raw),
        ("ExternalApiScore class",       "ExternalApiScore" in raw),
        ("grader URL preserved",         url in raw),
        ("no double-protocol typo",      "https://https://" not in raw and "http://http://" not in raw),
        ("feedback-block",               "<qti-feedback-block" in raw),
        ("printed-variable",             "<qti-printed-variable" in raw),
        ("GENERATED_FEEDBACK outcome",   'identifier="GENERATED_FEEDBACK"' in raw),
        ("MAXSCORE outcome",             'identifier="MAXSCORE"' in raw),
        ("API_RESPONSE record cardinality",
         'identifier="API_RESPONSE"' in raw and 'cardinality="record"' in raw),
        ("FEEDBACK_VISIBILITY identifier base-type",
         'identifier="FEEDBACK_VISIBILITY"' in raw and 'base-type="identifier"' in raw),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        return False, f"missing from rawXml after round-trip: {failed}"
    return True, f"all {len(checks)} canonical pieces persisted for {test_id}"


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
    ("frq_xml_post_persists_canonical_pattern",
     lambda c: test_frq_xml_post_persists_canonical_pattern(c, grader_url=None)),
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
