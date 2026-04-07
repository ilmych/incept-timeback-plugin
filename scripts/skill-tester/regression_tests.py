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


def _canonical_mcq_xml(test_id: str) -> str:
    """Return a minimal but FULLY CANONICAL MCQ XML matching WORH23-qti103821-q1119893-v1.

    Key structural rules (verified 2026-04-07):
      - <qti-feedback-inline> is a CHILD of each <qti-simple-choice>, not a sibling
        of <qti-choice-interaction>
      - feedback content is in <span> (inline), not <p> (block)
      - outcome declarations: FEEDBACK-INLINE (with empty default), MAXSCORE, SCORE
        — NO standalone FEEDBACK outcome
      - response-processing: set FEEDBACK-INLINE = RESPONSE, then qti-match scoring
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="{test_id}" title="MCQ Canonical Regression" adaptive="false" time-dependent="false" xml:lang="en">
  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="identifier">
    <qti-correct-response><qti-value>B</qti-value></qti-correct-response>
  </qti-response-declaration>
  <qti-outcome-declaration identifier="FEEDBACK-INLINE" base-type="identifier" cardinality="single">
    <qti-default-value><qti-value/></qti-default-value>
  </qti-outcome-declaration>
  <qti-outcome-declaration identifier="MAXSCORE" cardinality="single" base-type="float">
    <qti-default-value><qti-value>1</qti-value></qti-default-value>
  </qti-outcome-declaration>
  <qti-outcome-declaration identifier="SCORE" cardinality="single" base-type="float" normal-maximum="1">
    <qti-default-value><qti-value>0</qti-value></qti-default-value>
  </qti-outcome-declaration>
  <qti-item-body>
    <qti-choice-interaction response-identifier="RESPONSE" shuffle="true" max-choices="1" min-choices="1">
      <qti-prompt>
        <p class="stem_paragraph">Which option is correct?</p>
      </qti-prompt>
      <qti-simple-choice identifier="A">
        <p class="choice_paragraph">Option A text</p>
        <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="A" show-hide="show">
          <span>This answer is incorrect. Reason A.</span>
        </qti-feedback-inline>
      </qti-simple-choice>
      <qti-simple-choice identifier="B">
        <p class="choice_paragraph">Option B text</p>
        <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="B" show-hide="show">
          <span>This answer is correct. Reason B.</span>
        </qti-feedback-inline>
      </qti-simple-choice>
      <qti-simple-choice identifier="C">
        <p class="choice_paragraph">Option C text</p>
        <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="C" show-hide="show">
          <span>This answer is incorrect. Reason C.</span>
        </qti-feedback-inline>
      </qti-simple-choice>
      <qti-simple-choice identifier="D">
        <p class="choice_paragraph">Option D text</p>
        <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="D" show-hide="show">
          <span>This answer is incorrect. Reason D.</span>
        </qti-feedback-inline>
      </qti-simple-choice>
    </qti-choice-interaction>
  </qti-item-body>
  <qti-response-processing>
    <qti-set-outcome-value identifier="FEEDBACK-INLINE">
      <qti-variable identifier="RESPONSE"/>
    </qti-set-outcome-value>
    <qti-response-condition>
      <qti-response-if>
        <qti-match>
          <qti-variable identifier="RESPONSE"/>
          <qti-correct identifier="RESPONSE"/>
        </qti-match>
        <qti-set-outcome-value identifier="SCORE">
          <qti-base-value base-type="float">1</qti-base-value>
        </qti-set-outcome-value>
      </qti-response-if>
      <qti-response-else>
        <qti-set-outcome-value identifier="SCORE">
          <qti-base-value base-type="float">0</qti-base-value>
        </qti-set-outcome-value>
      </qti-response-else>
    </qti-response-condition>
  </qti-response-processing>
</qti-assessment-item>"""


def test_mcq_inline_feedback_canonical_pattern(client: APIClient) -> tuple[bool, str]:
    """Verify the canonical MCQ pattern (feedback-inline nested in simple-choice)
    survives XML POST→GET.

    Rule (create-mcq.md, verified 2026-04-07): per-option <qti-feedback-inline>
    elements MUST be children of their <qti-simple-choice>, not siblings of
    <qti-choice-interaction>. Feedback content must use <span> not <p>.
    Outcome declarations must be FEEDBACK-INLINE/MAXSCORE/SCORE — not FEEDBACK.
    """
    import re

    test_id = client.gen_id("mcq-canonical")
    xml = _canonical_mcq_xml(test_id)

    create = client.create_item_xml(xml)
    if not create.get("success"):
        return False, f"create failed: status={create.get('status')} err={create.get('error', '')[:300]}"

    time.sleep(0.5)
    got = client.get_item(test_id)
    client.delete_item(test_id)

    if not got.get("success"):
        return False, f"get failed: {got}"

    raw = got["data"].get("rawXml", "")

    # Structural check: every qti-simple-choice block must contain a qti-feedback-inline
    choice_blocks = re.findall(
        r"<qti-simple-choice[^>]*>(.*?)</qti-simple-choice>", raw, re.DOTALL
    )
    nested_count = sum(1 for b in choice_blocks if "<qti-feedback-inline" in b)

    checks: list[tuple[str, bool]] = [
        ("4 simple-choice blocks",           len(choice_blocks) == 4),
        ("4 feedback-inline NESTED inside simple-choice",  nested_count == 4),
        ("feedback-inline open count == 4",  raw.count("<qti-feedback-inline ") == 4),
        ("FEEDBACK-INLINE outcome decl",     'identifier="FEEDBACK-INLINE"' in raw),
        ("MAXSCORE outcome decl",            'identifier="MAXSCORE"' in raw),
        ("NO standalone FEEDBACK outcome",
         'identifier="FEEDBACK"' not in raw.replace('identifier="FEEDBACK-INLINE"', "")),
        ("set-outcome FEEDBACK-INLINE from RESPONSE",
         "qti-set-outcome-value" in raw and "FEEDBACK-INLINE" in raw and "qti-variable" in raw),
        ("qti-match used for scoring",       "qti-match" in raw),
        ("no <p> inside feedback-inline (uses <span>)",
         "<p>" not in "".join(
             re.findall(r"<qti-feedback-inline[^>]*>(.*?)</qti-feedback-inline>",
                        raw, re.DOTALL)
         )),
    ]
    for choice in ("A", "B", "C", "D"):
        checks.append(
            (f"feedback-inline identifier={choice} present",
             f'<qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="{choice}"' in raw)
        )

    failed = [name for name, ok in checks if not ok]
    if failed:
        return False, f"failures: {failed}"
    return True, f"all {len(checks)} canonical MCQ assertions passed for {test_id}"


def test_mcq_feedback_not_sibling_of_choice_interaction(client: APIClient) -> tuple[bool, str]:
    """Verify that the rawXml has NO <qti-feedback-inline> as a direct sibling
    of <qti-choice-interaction> (the wrong pattern from v1.1/v1.2 of this skill).
    """
    import re

    test_id = client.gen_id("mcq-no-sibling-fb")
    xml = _canonical_mcq_xml(test_id)

    create = client.create_item_xml(xml)
    if not create.get("success"):
        return False, f"create failed: {create}"

    time.sleep(0.3)
    got = client.get_item(test_id)
    client.delete_item(test_id)

    if not got.get("success"):
        return False, f"get failed: {got}"

    raw = got["data"].get("rawXml", "")

    # Look for the wrong pattern: </qti-choice-interaction> followed by
    # (whitespace + <qti-feedback-inline>) before </qti-item-body>
    wrong_pattern = re.search(
        r"</qti-choice-interaction>\s*<qti-feedback-inline",
        raw,
    )
    if wrong_pattern:
        return False, "WRONG PATTERN: found <qti-feedback-inline> as sibling of </qti-choice-interaction>"

    return True, "no sibling-placed feedback-inline (all are correctly nested in simple-choice)"


def test_mcq_explanations_not_in_choice_text(client: APIClient) -> tuple[bool, str]:
    """Negative-pattern check: confirm the explanation span content does NOT
    leak into <p class="choice_paragraph"> choice text.

    Rule (create-mcq.md): choice text must contain ONLY the option label.
    The explanation lives in the nested <qti-feedback-inline><span>.
    """
    import re

    test_id = client.gen_id("mcq-clean-choices")
    xml = _canonical_mcq_xml(test_id)

    create = client.create_item_xml(xml)
    if not create.get("success"):
        return False, f"create failed: {create}"

    time.sleep(0.3)
    got = client.get_item(test_id)
    client.delete_item(test_id)

    if not got.get("success"):
        return False, f"get failed: {got}"

    raw = got["data"].get("rawXml", "")

    # Extract <p class="choice_paragraph"> text inside each simple-choice and confirm
    # no "This answer is" or "Reason" phrases (which belong in feedback-inline, not choice text).
    choice_paragraphs = re.findall(
        r'<p class="choice_paragraph">([^<]*)</p>', raw
    )
    if len(choice_paragraphs) < 4:
        return False, f"expected 4 choice paragraphs, found {len(choice_paragraphs)}"

    leaked_phrases = ["This answer is", "Reason A", "Reason B", "Reason C", "Reason D", "correct because", "incorrect because"]
    for cp in choice_paragraphs:
        for phrase in leaked_phrases:
            if phrase in cp:
                return False, f"explanation leaked into choice text: {cp!r} contains {phrase!r}"

    return True, "choice text contains only option labels; explanations confined to feedback-inline"


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
    ("mcq_inline_feedback_canonical_pattern", test_mcq_inline_feedback_canonical_pattern),
    ("mcq_feedback_not_sibling_of_choice_interaction", test_mcq_feedback_not_sibling_of_choice_interaction),
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
