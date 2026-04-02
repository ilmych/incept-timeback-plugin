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

## External Grader Setup (CRITICAL for Auto-Grading)

When FRQs need automated scoring, the payload is significantly more complex:

### Required Outcome Declarations (5 total)

```python
"outcomeDeclarations": [
    {"identifier": "SCORE", "cardinality": "single", "baseType": "float"},
    {"identifier": "FEEDBACK", "cardinality": "single", "baseType": "identifier"},
    {"identifier": "API_RESPONSE", "cardinality": "single", "baseType": "string"},
    {"identifier": "GRADING_RESPONSE", "cardinality": "single", "baseType": "string"},
    {"identifier": "FEEDBACK_VISIBILITY", "cardinality": "single", "baseType": "boolean"},
]
```

### Response Processing with External Grader

```python
"responseProcessing": {
    "templateType": "custom",
    "customOperator": {
        "class": "com.alpha-1edtech.ExternalApiScore",
        "definition": "https://grader.example.com/grade"
    }
}
```

### Rubric Block for Grader

```python
"rubricBlock": {
    "view": "scorer",
    "content": '<div data-part="a">Criterion A: ...</div><div data-part="b">Criterion B: ...</div>'
}
```

### Grader URL Rules
- `grader_url` must start with `http://` or `https://`
- The grader receives the student response + rubric and returns a score + feedback
- If grader URL is missing or malformed, the item silently fails to grade

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
| Score always 0 | Missing rubricBlock with data-part divs | Add rubric block with `view="scorer"` |
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
