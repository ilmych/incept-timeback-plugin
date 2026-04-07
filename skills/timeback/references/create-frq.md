# Create FRQ (Extended-Text) Items

## Known-Good Payload (Basic)

```python
{
    "identifier": "...",
    "title": "...",
    "type": "extended-text",
    "interaction": {
        "type": "extended-text",
        "responseIdentifier": "RESPONSE",
        "questionStructure": {"prompt": "<p>HTML prompt</p>"},
    },
    "responseDeclarations": [{
        "identifier": "RESPONSE",
        "cardinality": "single",
        "baseType": "string",
    }],
    "outcomeDeclarations": [
        {"identifier": "SCORE", "cardinality": "single", "baseType": "float"},
        {"identifier": "FEEDBACK", "cardinality": "single", "baseType": "identifier"},
    ],
    "responseProcessing": {"templateType": "match_correct"},
    "metadata": {"modelAnswer": "...", "rubric": "..."},
}
```

## Endpoint

```
POST {QTI_BASE}/assessment-items
```

## Hard Rules

### Type and Base Type
- Root `type` AND `interaction.type` MUST both be `"extended-text"` -- mismatch is silently accepted (API stores whatever root `type` says) but may break downstream rendering/grading
- `interaction.type` is **REQUIRED** -- omitting it causes 500 error (`Unsupported interaction type: undefined`)
- `baseType` SHOULD be `"string"` for FRQ. `"identifier"` is silently accepted but may cause grading issues.
- `prompt` in `questionStructure` can be empty string (API accepts it) but SHOULD be non-empty for usability

### Stimulus References
- If `stimulus.identifier` is provided, the stimulus MUST already exist in the API -- nonexistent stimulus IDs return 400 (`"Stimulus(s) not found"`)
- Create stimulus BEFORE creating the item that references it

### Student Input
- Students can only type plain text -- no formatting toolbar, no equation editor
- Do NOT write prompts that expect formatted equations, diagrams, or rich text input
- If a question needs graphing/drawing, use a composite item with PCI (not plain extended-text)

### Model Answer and Rubric
- Model answer goes in `metadata.modelAnswer`
- Rubric HTML goes in `metadata.rubric`
- Neither field is rendered to students by default -- they are for grader/teacher view

## External Grader Setup (CRITICAL for Auto-Grading) — verified 2026-04-07

> **READ THIS FIRST.** FRQs with auto-grading have THREE required components, all of which must be present in the actual `rawXml` body — NOT just in JSON-typed metadata fields. Getting any of these wrong leaves the item silently broken: it will accept POSTs (200/201) but never grade student responses.
>
> 1. Five outcome declarations (SCORE, FEEDBACK, API_RESPONSE, GRADING_RESPONSE, FEEDBACK_VISIBILITY)
> 2. **One or more `<qti-rubric-block>` elements INSIDE `<qti-item-body>`** — NOT just in `metadata.rubric`
> 3. **A `<qti-custom-operator class="com.alpha-1edtech.ExternalApiScore" definition="...URL...">` INSIDE `<qti-response-processing>`** — NOT just in `responseProcessing.customOperator` JSON field
>
> **You MUST POST FRQs with auto-grading as XML.** JSON POST silently drops both the rubric-block and the custom-operator from the rawXml body. See "JSON POST trap" below.

### Required Outcome Declarations (5 total)

All five MUST be present. Missing any one breaks grading or feedback display.

```python
"outcomeDeclarations": [
    {"identifier": "SCORE", "cardinality": "single", "baseType": "float"},
    {"identifier": "FEEDBACK", "cardinality": "single", "baseType": "identifier"},
    {"identifier": "API_RESPONSE", "cardinality": "single", "baseType": "string"},
    {"identifier": "GRADING_RESPONSE", "cardinality": "single", "baseType": "string"},
    {"identifier": "FEEDBACK_VISIBILITY", "cardinality": "single", "baseType": "boolean"},
]
```

In XML:
```xml
<qti-outcome-declaration identifier="SCORE" base-type="float" cardinality="single"/>
<qti-outcome-declaration identifier="FEEDBACK" base-type="identifier" cardinality="single"/>
<qti-outcome-declaration identifier="API_RESPONSE" base-type="string" cardinality="single"/>
<qti-outcome-declaration identifier="GRADING_RESPONSE" base-type="string" cardinality="single"/>
<qti-outcome-declaration identifier="FEEDBACK_VISIBILITY" base-type="boolean" cardinality="single"/>
```

### qti-rubric-block — NEVER OMIT

The rubric block lives **inside `<qti-item-body>`**. This is what the grader actually consumes. One `<qti-rubric-block>` per scoring criterion is the standard pattern.

```xml
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
```

Rules:
- `view="scorer"` keeps the rubric hidden from students; the grader still receives it
- One `<qti-rubric-block>` per criterion is preferred (easier for the grader to enumerate parts) but a single block with multiple `<div data-part="...">` children also works
- The `data-part` attribute identifies which part of a multi-part question the criterion applies to (free-form string — `a`, `b`, `c` is the convention)
- `metadata.rubric` is NOT a substitute. Storing rubric markup there leaves it invisible to the grader. Use it only as a redundant backup, never as the primary location.

### Custom Operator — External Grader Wiring

Lives **inside `<qti-response-processing>`**, wrapped in a `<qti-response-condition>`.

```xml
<qti-response-processing>
  <qti-response-condition>
    <qti-response-if>
      <qti-custom-operator class="com.alpha-1edtech.ExternalApiScore" definition="{GRADER_URL}">
        <qti-variable identifier="RESPONSE"/>
      </qti-custom-operator>
      <qti-set-outcome-value identifier="SCORE">
        <qti-base-value base-type="float">1</qti-base-value>
      </qti-set-outcome-value>
    </qti-response-if>
  </qti-response-condition>
</qti-response-processing>
```

### Grader URL Rules — CRITICAL (verified 2026-04-07)

- **NEVER invent or guess a grader URL.** ALWAYS get it from the user before creating any FRQ with auto-grading. The URL is course-specific and must be supplied at task time.
- The XML POST endpoint validates `definition` against an internal **allowlist** (`validateCustomOperatorUrls` in the QTI XML processor). URLs not on the allowlist return:
  ```
  500 Internal Server Error
  Custom operator "com.alpha-1edtech.ExternalApiScore" definition URL hostname is not in the approved grader allowlist: "<hostname>"
  ```
- If the user's grader URL fails the allowlist check, **STOP** and ask the user to coordinate with the platform team to add it. Do NOT fall back to JSON POST as a workaround — that's the trap below.
- The URL must start with `http://` or `https://`
- Reference URL the user has used previously (allowlist status: pending — verify before use): `https://cs-autograder.onrender.com/cs-autograder/score`

### JSON POST trap — DO NOT use JSON POST for graded FRQs

The JSON `/assessment-items` controller does NOT enforce the grader allowlist, so a JSON POST with a `responseProcessing.customOperator` field returns 201 and looks like it worked. **It did not work.** When you GET the item back:

| Source | Has rubric-block in rawXml? | Has custom-operator in rawXml? |
|--------|------------------------------|---------------------------------|
| JSON POST with `metadata.rubric` + `responseProcessing.customOperator` | **NO** | **NO** (rawXml has placeholder `<qti-response-processing template=".../custom.xml"/>`) |
| XML POST with `<qti-rubric-block>` + `<qti-custom-operator>` in body | YES | YES (URL must be allowlisted) |

The JSON-typed `responseProcessing.customOperator` field is preserved on the GET response, but the **renderer and grader read from `rawXml`** — so a JSON-posted FRQ with custom grading is silently inert: prompt renders, students can submit, but no scoring happens.

The reference item `s4-u1-frq-01` is in this exact broken state: customOperator in JSON field, missing from rawXml, AND missing the rubric-block entirely. Treat it as an example of "how it looks when the rules in this file are violated," not as a working template.

### The Only Path That Works (verified 2026-04-07)

1. Get the grader URL from the user
2. Build the full QTI XML with: 5 outcome declarations + `<qti-rubric-block>` element(s) inside `<qti-item-body>` + `<qti-custom-operator>` inside `<qti-response-processing>`
3. Validate the XML with `ET.fromstring()` before posting
4. POST as `{"format": "xml", "xml": full_xml}` to `/assessment-items`
5. If 500 with allowlist error → ask user to allowlist the URL with the platform team. Do not retry.
6. After 201, GET the item back and assert: `"qti-rubric-block" in rawXml` AND `"ExternalApiScore" in rawXml` AND `grader_url in rawXml`. If any assertion fails, the item is broken — investigate, don't ship.

## Multi-Part FRQs

- Platform does NOT support per-part scoring natively
- External grader returns a single aggregate score
- For composite FRQ (text + graph parts): use multiple interactions in one item body, each with own `RESPONSE_{LABEL}`

```python
# Composite example: text response + graph interaction
"interactions": [
    {"type": "extended-text", "responseIdentifier": "RESPONSE_TEXT", ...},
    {"type": "custom", "responseIdentifier": "RESPONSE_GRAPH", ...},
]
```

## FRQ as Read-Only Display

For showing FRQs without student interaction (review mode):
- Use `lessonType: "powerpath-100"`
- Wrap rubric in `<details><summary>Show Rubric</summary>...</details>`

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Item never gets graded | Missing customOperator or bad grader URL | Add external grader config with valid URL |
| Item POSTed via JSON, returns 201, never grades | JSON POST drops `<qti-custom-operator>` from rawXml even though `responseProcessing.customOperator` field is preserved | POST as XML with full body. Verify with `"ExternalApiScore" in rawXml` after GET |
| Item POSTed via JSON, rubric metadata set but grader sees no rubric | `metadata.rubric` is not propagated into `<qti-item-body>` as `<qti-rubric-block>` | POST as XML with `<qti-rubric-block>` inside `<qti-item-body>` |
| XML POST returns 500 "URL hostname is not in the approved grader allowlist" | Grader hostname not on platform allowlist | Ask user to coordinate with platform team to allowlist the host. Do NOT fall back to JSON POST. |
| Score always 0 | Missing rubric-block with `data-part` divs | Add rubric block with `view="scorer"` and per-part divs |
| Grader timeout | Rubric too complex / grader overloaded | Simplify rubric, check grader health |
| Student sees raw HTML | Prompt XHTML invalid | Sanitize prompt HTML |
| No feedback after submit | Missing FEEDBACK_VISIBILITY outcome | Add all 5 outcome declarations |

## Batch Creation Pattern

```python
def create_frq(session, qti_base, frq_data, grader_url=None):
    payload = build_frq_payload(frq_data)
    if grader_url:
        payload = add_external_grader(payload, grader_url)
    resp = session.post(f"{qti_base}/assessment-items", json=payload)
    resp.raise_for_status()
    return resp.json()["identifier"]

# Always checkpoint
for frq in frqs:
    if frq["identifier"] in done:
        continue
    create_frq(session, QTI_BASE, frq, GRADER_URL)
    done[frq["identifier"]] = True
    save_checkpoint(done)
```
