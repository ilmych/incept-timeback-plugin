# Create MCQ (Choice) Items

## Known-Good Payload

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
        {"identifier": "FEEDBACK", "cardinality": "single", "baseType": "identifier"},
        {"identifier": "FEEDBACK-INLINE", "cardinality": "single", "baseType": "identifier"},
    ],
    "responseProcessing": {
        "templateType": "match_correct",
        "responseDeclarationIdentifier": "RESPONSE",
        "outcomeIdentifier": "FEEDBACK",
        "correctResponseIdentifier": "CORRECT",
        "incorrectResponseIdentifier": "INCORRECT",
        "inlineFeedback": {
            "outcomeIdentifier": "FEEDBACK-INLINE",
            "variableIdentifier": "RESPONSE",
        },
    },
    "metadata": {},
}
```

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

### Feedback / Explanations (CRITICAL — verified 2026-04-07)

**HARD RULE: per-option explanations MUST live in `<qti-feedback-inline>` blocks. They MUST NOT be embedded in choice text.**

**WRONG** — explanation glued onto the option text:
```xml
<qti-simple-choice identifier="A">Dogs are mammals. (Correct because dogs are warm-blooded vertebrates.)</qti-simple-choice>
<qti-simple-choice identifier="B">Lizards are mammals. (Wrong — lizards are reptiles.)</qti-simple-choice>
```
This shows the explanation BEFORE the student answers, defeats the assessment, and renders as garbled option text.

**RIGHT** — option text is the option, explanation is in a separate feedback-inline block keyed by identifier:
```xml
<qti-item-body>
  <qti-choice-interaction response-identifier="RESPONSE" max-choices="1" shuffle="false">
    <qti-prompt><p>Which of these is a mammal?</p></qti-prompt>
    <qti-simple-choice identifier="A">Dog</qti-simple-choice>
    <qti-simple-choice identifier="B">Lizard</qti-simple-choice>
    <qti-simple-choice identifier="C">Trout</qti-simple-choice>
    <qti-simple-choice identifier="D">Eagle</qti-simple-choice>
  </qti-choice-interaction>
  <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="A" show-hide="show">
    <p>Correct — dogs are warm-blooded vertebrates that nurse their young.</p>
  </qti-feedback-inline>
  <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="B" show-hide="show">
    <p>Lizards are reptiles, not mammals — they're cold-blooded and lay eggs.</p>
  </qti-feedback-inline>
  <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="C" show-hide="show">
    <p>Trout are fish, not mammals.</p>
  </qti-feedback-inline>
  <qti-feedback-inline outcome-identifier="FEEDBACK-INLINE" identifier="D" show-hide="show">
    <p>Eagles are birds, not mammals.</p>
  </qti-feedback-inline>
</qti-item-body>
```

#### Why this matters
- Inline feedback only renders AFTER the student picks an answer, gated by which choice they selected
- The `outcome-identifier="FEEDBACK-INLINE"` + `identifier="A|B|C|D"` pair tells the renderer which feedback block to show
- Without this structure, the student either sees nothing after answering, or sees ALL explanations regardless of choice, or sees explanations leaked into the option text

#### Implementation rules
- Inline feedback requires BOTH `FEEDBACK` and `FEEDBACK-INLINE` outcome declarations (see Known-Good Payload above)
- The `responseProcessing.inlineFeedback` block (in the JSON template) wires `RESPONSE` → `FEEDBACK-INLINE` so the chosen identifier becomes the value used to gate display
- Use one `<qti-feedback-inline>` per choice. Identifier on the feedback element must match the choice identifier exactly (`A`, `B`, `C`, `D`)
- Choice `content` must contain ONLY the option text (no parentheses with "correct because...", no inline explanations, no "right answer:" prefix)
- For block-level feedback (multi-paragraph, with images/tables), use `<qti-feedback-block>` instead — same identifier-keying rules apply

#### POST format note (verified 2026-04-07)
- The JSON `inlineFeedback` field is **not auto-populated** when you POST XML — XML posts succeed (201) and the rawXml round-trips correctly, but the typed `feedbackInline` array on the GET response stays `[]`. The renderer reads from rawXml, so this is fine.
- If you POST as JSON with the standard MCQ template, the API will generate the feedback wiring automatically — but ONLY if the feedback content is supplied via the typed structure. There is no JSON field for "explanation per choice" — for per-option feedback you MUST POST as XML.

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
| Explanations leak into option text / show before answering | Per-choice explanations were embedded in `qti-simple-choice` content | Move each explanation to its own `<qti-feedback-inline>` block keyed by choice identifier — POST as XML |
| Inline feedback never displays | Missing `FEEDBACK-INLINE` outcome declaration OR missing `responseProcessing.inlineFeedback` wiring | Use the Known-Good Payload above; ensure both outcome decls + the inlineFeedback wiring are present |
| `feedbackInline` array empty on GET after XML POST | API doesn't reverse-parse XML feedback into typed fields (verified 2026-04-07) | Not a bug — the renderer reads from rawXml. Confirm by grepping rawXml for `qti-feedback-inline` |
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
