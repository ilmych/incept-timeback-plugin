# Create MCQ (Choice) Items

## Canonical Full XML Pattern (verified 2026-04-07 via WORH23-qti103821-q1119893-v1)

This is the verified-working production pattern for an MCQ with per-option inline feedback. **Use XML POST** — the JSON payload shape does not give you control over where `<qti-feedback-inline>` lives, and incorrect placement is the #1 cause of broken inline feedback.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item
    xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    identifier="s4-..." title="..." adaptive="false" time-dependent="false" xml:lang="en">

  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="identifier">
    <qti-correct-response>
      <qti-value>B</qti-value>
    </qti-correct-response>
  </qti-response-declaration>

  <!-- Three outcomes total. Note: NO standalone "FEEDBACK" outcome. -->
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
        <p class="stem_paragraph">Pick the correct answer.</p>
      </qti-prompt>

      <!-- Each choice contains its OWN feedback-inline as a CHILD element. -->
      <qti-simple-choice identifier="A">
        <p class="choice_paragraph">Option A text</p>
        <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="A" show-hide="show">
          <span>This answer is incorrect. [reason here]</span>
        </qti-feedback-inline>
      </qti-simple-choice>
      <qti-simple-choice identifier="B">
        <p class="choice_paragraph">Option B text</p>
        <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="B" show-hide="show">
          <span>This answer is correct. [reason here]</span>
        </qti-feedback-inline>
      </qti-simple-choice>
      <qti-simple-choice identifier="C">
        <p class="choice_paragraph">Option C text</p>
        <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="C" show-hide="show">
          <span>This answer is incorrect. [reason here]</span>
        </qti-feedback-inline>
      </qti-simple-choice>
      <qti-simple-choice identifier="D">
        <p class="choice_paragraph">Option D text</p>
        <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="D" show-hide="show">
          <span>This answer is incorrect. [reason here]</span>
        </qti-feedback-inline>
      </qti-simple-choice>
    </qti-choice-interaction>
  </qti-item-body>

  <qti-response-processing>
    <!-- Step 1: Set FEEDBACK-INLINE = the chosen identifier (A/B/C/D).
         The renderer matches this against each <qti-feedback-inline identifier="..."/>
         to decide which one to display. -->
    <qti-set-outcome-value identifier="FEEDBACK-INLINE">
      <qti-variable identifier="RESPONSE"/>
    </qti-set-outcome-value>

    <!-- Step 2: Score 1 if correct, 0 otherwise. -->
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
</qti-assessment-item>
```

### Why each piece exists

- **`<qti-feedback-inline>` is a CHILD of `<qti-simple-choice>`, not a sibling at item-body level.** This is the most common mistake. The renderer expects the feedback element to be lexically inside the choice it belongs to. Putting it after `</qti-choice-interaction>` (as a sibling) is silently accepted on POST but breaks the rendering wire-up.
- **`<span>` (inline) inside feedback-inline, not `<p>` (block).** `qti-feedback-inline` is an *inline* element. Block-level children get sanitized away or break XHTML validation. Use `<span>` for the feedback text. If you need block-level feedback (paragraphs, lists, tables), use `<qti-feedback-block>` instead — different element, different placement rules.
- **Three outcomes — `FEEDBACK-INLINE`, `MAXSCORE`, `SCORE` — and NO standalone `FEEDBACK`.** Earlier versions of this skill listed a `FEEDBACK` (identifier) outcome as required for inline feedback. That was wrong. The renderer only needs `FEEDBACK-INLINE` to gate display. `MAXSCORE` (default 1) and `SCORE` (default 0, `normal-maximum="1"`) round out the scoring.
- **`FEEDBACK-INLINE` outcome has a `<qti-default-value><qti-value/></qti-default-value>`** — empty default lets the response-processing assignment work cleanly without a null check.
- **Response-processing is dead-simple**: assign `FEEDBACK-INLINE = RESPONSE` (the chosen identifier flows directly into the gating outcome), then a single `qti-response-condition` for scoring. There is no JSON `inlineFeedback` block — that's a JSON-template construct that doesn't apply to XML POST.
- **`shuffle="true"`** is the default for a real assessment. Set `shuffle="false"` if option order matters (e.g. "all of the above" / Likert scales).
- **`min-choices="1"`** ensures the student must pick something before submitting. Pair with `max-choices="1"` for single-answer MCQs.
- **`<p class="choice_paragraph">` and `<p class="stem_paragraph">`** wrappers are the production convention — gives the renderer hooks for typography. Not strictly required but matches the WORH23 reference and other working items.

## JSON Payload (alternative — limited control)

If you must POST as JSON (e.g. for a simple MCQ without inline feedback), this template works:

```python
{
    "identifier": "s4-xxxxxxxxxxxx",
    "title": "...",
    "type": "choice",
    "interaction": {
        "type": "choice",
        "responseIdentifier": "RESPONSE",
        "shuffle": False,
        "maxChoices": 1,
        "questionStructure": {
            "prompt": "<p>HTML stem here</p>",
            "choices": [
                {"identifier": "A", "content": "Option A text"},
                {"identifier": "B", "content": "Option B text"},
                {"identifier": "C", "content": "Option C text"},
                {"identifier": "D", "content": "Option D text"},
            ],
        },
    },
    "responseDeclarations": [{
        "identifier": "RESPONSE",
        "cardinality": "single",
        "baseType": "identifier",
        "correctResponse": {"value": ["A"]},
    }],
    "outcomeDeclarations": [
        {"identifier": "SCORE", "cardinality": "single", "baseType": "float"},
    ],
    "responseProcessing": {"templateType": "match_correct"},
    "metadata": {},
}
```

**Limitation: JSON POST cannot place `<qti-feedback-inline>` inside `<qti-simple-choice>`.** There is no JSON field for "explanation per choice." If you need per-option inline feedback, you MUST POST as XML using the canonical pattern above.

## Endpoint

```
POST {QTI_BASE}/assessment-items
```

## Hard Rules

### Type Fields
- `type` at root AND `interaction.type` MUST both be `"choice"` -- mismatch causes silent failures
- `maxChoices`: Set to `1` for standard MCQ. **Multi-select (`maxChoices: 2+`) IS supported** -- set `cardinality` to `"multiple"` and `correctResponse.value` to an array of all correct identifiers (e.g., `["A", "C"]`). XML correctly stores `max-choices` and `cardinality="multiple"`.

### Correct Answer
- `correctResponse.value` is an ARRAY of strings: `["A"]`, NOT a bare string `"A"`
- The value must match one of the choice identifiers exactly

### Choices
- **API accepts 2-6+ choices** (no minimum/maximum enforced at API level). Timeback workflow typically uses 4, but 2 (True/False) and 5-6 also work and render correctly.
- Option identifiers must be unique and non-empty
- Choice `content` field accepts HTML but must be valid XHTML (see html-sanitization reference)

### HTML in Stem
- `<table>` inside `<p>` is the #1 rendering bug -- block elements must NOT be nested inside `<p>`
- Split block elements out: close the `<p>` before the `<table>`, reopen after
- Platform strips `<style>` blocks -- all CSS must be inline (`style="..."` attributes)
- MathML: wrap in `<math xmlns="http://www.w3.org/1998/Math/MathML">` -- no bare `<mfrac>` etc.

### Feedback / Explanations (CRITICAL — verified 2026-04-07 against WORH23-qti103821-q1119893-v1)

**HARD RULE: per-option explanations MUST live in `<qti-feedback-inline>` blocks that are CHILD ELEMENTS of their corresponding `<qti-simple-choice>`. They MUST NOT be embedded in the choice text, AND they MUST NOT be siblings of the choice-interaction.**

There are THREE wrong patterns and ONE right pattern.

#### WRONG #1 — explanation glued onto the option text
```xml
<qti-simple-choice identifier="A">Dogs are mammals. (Correct because dogs are warm-blooded vertebrates.)</qti-simple-choice>
<qti-simple-choice identifier="B">Lizards are mammals. (Wrong — lizards are reptiles.)</qti-simple-choice>
```
This shows the explanation BEFORE the student answers, defeats the assessment, and renders as garbled option text.

#### WRONG #2 — feedback-inline as a sibling of qti-choice-interaction (outside the choices)
```xml
<qti-item-body>
  <qti-choice-interaction response-identifier="RESPONSE" max-choices="1">
    <qti-simple-choice identifier="A">Dog</qti-simple-choice>
    <qti-simple-choice identifier="B">Lizard</qti-simple-choice>
  </qti-choice-interaction>
  <!-- WRONG: these belong INSIDE their respective qti-simple-choice -->
  <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="A" show-hide="show">
    <p>Correct.</p>
  </qti-feedback-inline>
  <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="B" show-hide="show">
    <p>Wrong.</p>
  </qti-feedback-inline>
</qti-item-body>
```
API accepts this (POST returns 201, rawXml round-trips) but the renderer does not display feedback reliably because the feedback elements are not associated with their choices. This was the pattern in v1.1/v1.2 of this skill — it was wrong. Use WRONG #2 as a tell when auditing existing items.

#### WRONG #3 — `<p>` (block) inside `<qti-feedback-inline>`
```xml
<qti-simple-choice identifier="A">
  <p class="choice_paragraph">Dog</p>
  <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="A" show-hide="show">
    <p>Correct.</p>  <!-- WRONG: qti-feedback-inline is inline-level, needs span -->
  </qti-feedback-inline>
</qti-simple-choice>
```
`qti-feedback-inline` is an inline element. Its direct children must be inline (span, strong, em, a, etc.). Block-level children are stripped or cause XHTML failures. If you need block-level feedback content, use `<qti-feedback-block>` instead and rework the placement (see "block-level feedback" section below).

#### RIGHT — feedback-inline as a CHILD of qti-simple-choice, with span content
```xml
<qti-item-body>
  <qti-choice-interaction response-identifier="RESPONSE" shuffle="true" max-choices="1" min-choices="1">
    <qti-prompt><p class="stem_paragraph">Which of these is a mammal?</p></qti-prompt>

    <qti-simple-choice identifier="A">
      <p class="choice_paragraph">Dog</p>
      <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="A" show-hide="show">
        <span>This answer is correct. Dogs are warm-blooded vertebrates that nurse their young.</span>
      </qti-feedback-inline>
    </qti-simple-choice>
    <qti-simple-choice identifier="B">
      <p class="choice_paragraph">Lizard</p>
      <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="B" show-hide="show">
        <span>This answer is incorrect. Lizards are reptiles — cold-blooded and lay eggs.</span>
      </qti-feedback-inline>
    </qti-simple-choice>
    <qti-simple-choice identifier="C">
      <p class="choice_paragraph">Trout</p>
      <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="C" show-hide="show">
        <span>This answer is incorrect. Trout are fish, not mammals.</span>
      </qti-feedback-inline>
    </qti-simple-choice>
    <qti-simple-choice identifier="D">
      <p class="choice_paragraph">Eagle</p>
      <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="D" show-hide="show">
        <span>This answer is incorrect. Eagles are birds, not mammals.</span>
      </qti-feedback-inline>
    </qti-simple-choice>
  </qti-choice-interaction>
</qti-item-body>
```

Combined with the response-processing in the canonical pattern above, this gives you:
- A student picks (say) `B`
- Response-processing sets `FEEDBACK-INLINE = B`
- The renderer scans every `<qti-feedback-inline>` in the item, shows only the one whose `identifier` matches `B` (the one inside the `B` choice)
- Everything else stays hidden

#### Implementation rules (updated 2026-04-07)
- **Exactly one `<qti-feedback-inline>` per choice, as a direct child of `<qti-simple-choice>`.** No sibling-placement, no shared blocks.
- **`identifier` attribute on the feedback element MUST match its parent choice identifier** (`A`, `B`, `C`, `D`). Mismatches silently render nothing.
- **`outcome-identifier="FEEDBACK-INLINE"`** on every feedback element (spelled with a hyphen, not underscore).
- **Use `<span>` inside `<qti-feedback-inline>`.** For additional formatting, use other inline elements: `<strong>`, `<em>`, `<a>`, `<code>`. No block elements.
- **Choice text goes in `<p class="choice_paragraph">`** (or bare text if you must, but the `p.choice_paragraph` wrapper matches production convention and gives the renderer typography hooks).
- **Choice text must contain ONLY the option text.** No parentheses with "correct because...", no explanatory prefixes, no "(A)" labels — the renderer adds labels automatically.
- Outcome declarations: `FEEDBACK-INLINE` + `MAXSCORE` + `SCORE`. NOT `FEEDBACK` — that outcome is not used in this pattern (earlier versions of this skill were wrong).
- Response processing: `<qti-set-outcome-value identifier="FEEDBACK-INLINE"><qti-variable identifier="RESPONSE"/></qti-set-outcome-value>` — this direct assignment is what wires the chosen identifier into the gating outcome. No JSON `inlineFeedback` block.

#### POST format note (verified 2026-04-07)
- **You MUST POST as XML for per-option inline feedback.** The JSON payload shape does not let you place `<qti-feedback-inline>` as a child of `<qti-simple-choice>` — there is no JSON field for per-choice feedback content. JSON POST of a choice template generates a flat structure with no inline feedback at all.
- The typed `feedbackInline` array on the GET response stays `[]` even after a successful XML POST — the API does not reverse-parse XML feedback into typed fields. The renderer reads from `rawXml`, so this is fine. Confirm success by grepping `rawXml` for `qti-feedback-inline` and checking it's inside `qti-simple-choice` (not a sibling).

### Modal Feedback (item-wide, not per-option)
- For a single explanation shown after answering (one for correct, one for incorrect), use `qti-modal-feedback` blocks in the item body XML
- Modal feedback identifiers must match `correctResponseIdentifier` / `incorrectResponseIdentifier`
- If both inline (per-option) and modal (correct/incorrect) feedback are needed, use BOTH — they don't conflict
- `metadata.explanation` is teacher-view only, NOT rendered to students

### Identifier Format
- Use `s4-` prefix followed by a UUID or timestamp-based ID
- Must be unique across the entire course

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Item saves but shows no answer key | `correctResponse.value` is a string, not array | Wrap in list: `["A"]` |
| Item saves, GET returns value as bare string | Sent `correctResponse.value` as string `"A"` instead of `["A"]` | API silently accepts strings but GET returns bare string (not array) -- grading may fail. ALWAYS use array format. |
| Stem renders blank | Invalid XHTML (unclosed tags, bare `&`) | Run through XHTML sanitizer |
| Table not visible | `<table>` nested inside `<p>` | Close `</p>` before `<table>` |
| No feedback after answering | Missing modal feedback blocks | Add `qti-modal-feedback` with correct identifiers |
| Explanations leak into option text / show before answering | Per-choice explanations were embedded in `qti-simple-choice` content | Move each explanation to a `<qti-feedback-inline>` element nested inside its `<qti-simple-choice>` — POST as XML |
| Inline feedback never displays despite correct outcome declarations | `<qti-feedback-inline>` placed as a sibling of `qti-choice-interaction` instead of as a child of each `qti-simple-choice` | Move each feedback-inline INSIDE its corresponding `<qti-simple-choice>` — see canonical pattern above |
| XHTML parse error on feedback content | `<p>` or other block element inside `<qti-feedback-inline>` | Replace block-level children with `<span>` (feedback-inline is an inline element) |
| Inline feedback wired but shows for every choice regardless of selection | `identifier` attribute on feedback element doesn't match its choice identifier, OR response-processing doesn't set `FEEDBACK-INLINE = RESPONSE` | Verify every feedback element has `identifier="<matching-choice>"`; verify `<qti-set-outcome-value identifier="FEEDBACK-INLINE"><qti-variable identifier="RESPONSE"/></qti-set-outcome-value>` is in response-processing |
| 500 "FEEDBACK is not a declared outcome" | Copied an old template that declared a `FEEDBACK` outcome alongside `FEEDBACK-INLINE` | Drop the `FEEDBACK` outcome — the canonical pattern uses only `FEEDBACK-INLINE`, `MAXSCORE`, `SCORE` |
| `feedbackInline` array empty on GET after XML POST | API doesn't reverse-parse XML feedback into typed fields (verified 2026-04-07) | Not a bug — the renderer reads from rawXml. Confirm by grepping rawXml for `qti-feedback-inline` inside `qti-simple-choice` |
| Styling lost on platform | CSS in `<style>` block | Convert all to inline `style` attributes |
| Options show HTML tags | Choice content has unescaped HTML | Ensure valid XHTML in choice content |

## Batch Creation Pattern

```python
import hashlib, json, time

def create_mcq(session, qti_base, item_data):
    payload = build_mcq_payload(item_data)  # construct from template above
    resp = session.post(f"{qti_base}/assessment-items", json=payload)
    resp.raise_for_status()
    return resp.json()["identifier"]

# Checkpoint after each item for resume-on-failure
for i, item in enumerate(items):
    if item["identifier"] in completed:
        continue
    item_id = create_mcq(session, QTI_BASE, item)
    completed[item_id] = True
    save_checkpoint(completed)
    time.sleep(0.1)  # rate limiting
```
