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

### Feedback / Explanations
- Inline feedback requires BOTH `FEEDBACK` and `FEEDBACK-INLINE` outcome declarations
- Explanation text goes in `metadata.explanation` (no dedicated feedback body field yet)
- For modal feedback (explanation shown after answering), add `qti-modal-feedback` blocks in the item body XML -- if omitted, students see nothing after answering
- Modal feedback identifiers must match `correctResponseIdentifier` / `incorrectResponseIdentifier`

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
