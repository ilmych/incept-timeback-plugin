# Create Assessment Test

## Endpoint

```
POST {QTI_BASE}/assessment-tests
```

## Known-Good Payload

```python
{
    "identifier": "test-id",
    "title": "Test Title",
    "qti-test-part": [{
        "identifier": "test_part",
        "navigationMode": "linear",
        "submissionMode": "individual",
        "qti-assessment-section": [{
            "identifier": "test_section",
            "title": "Section Title",
            "visible": True,
            "required": True,
            "fixed": False,
            "sequence": 1,
            "qti-assessment-item-ref": [
                {"identifier": "item-id", "href": "item-id.xml"}
            ],
        }],
    }],
    "qti-outcome-declaration": [
        {"identifier": "SCORE", "cardinality": "single", "baseType": "float"}
    ],
}
```

## Hard Rules

### Item References
- `href` SHOULD be `"{identifier}.xml"` -- but missing `.xml` suffix is also accepted (verified 2026-04-02). Use `.xml` suffix by convention.
- **Items do NOT need to exist before test creation** -- the API does NOT validate item existence at test creation time (verified 2026-04-02, returns 201 even with nonexistent item refs). However, such tests will fail at runtime when items can't be loaded.
- Item identifiers must be non-empty and non-duplicate within the test

### Structure Requirements
- `qti-outcome-declaration` with `SCORE` is required
- `qti-test-part` must have at least one entry
- Each test part must have at least one `qti-assessment-section`
- Each section must have at least one `qti-assessment-item-ref`

### Navigation and Submission Modes
- `navigationMode`: `"linear"` (forward only) or `"nonlinear"` (jump between items)
- `submissionMode`: `"individual"` (submit per item) or `"simultaneous"` (submit all at end)
- Most common for quizzes: `linear` + `individual`

### Stimulus References in Tests
- Stimulus refs go in `qti-assessment-section`, NOT in individual items within the test
- If an item references a stimulus, the stimulus must also exist in the API

### Section Sequencing
- `sequence` field controls item ordering within a section
- `fixed: False` allows platform to shuffle items (if randomization is enabled)
- `fixed: True` locks item order

## Assessment Bank (Quiz Variants)

For creating item banks that generate quiz variants:

```python
# 1. Create sub-resources (individual items)
# 2. Create bank parent with resources array in metadata
bank_payload = {
    "identifier": "bank-id",
    "title": "Item Bank: Topic X",
    "metadata": {
        "resources": [
            {"identifier": "item-1", "type": "assessment-item"},
            {"identifier": "item-2", "type": "assessment-item"},
            # ... pool of items
        ],
        "selectionCount": 10,  # how many to pick per quiz
    },
}
```

## Update (PUT)

For test XML updates:
```
PUT {QTI_BASE}/assessment-tests/{id}
Content-Type: application/xml
Body: raw XML string
```

Note the different content type -- test PUT expects raw XML, not JSON.

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Items not loading at runtime | Item refs point to nonexistent items | API does NOT validate refs at creation -- always create items first |
| ~~400 on POST~~ | ~~href missing `.xml` suffix~~ | Both `id.xml` and bare `id` work (verified 2026-04-02) |
| Items not showing | Duplicate identifiers in refs | Ensure all item identifiers are unique |
| Score always 0 | Missing SCORE outcome declaration | Add `qti-outcome-declaration` with SCORE |
| Wrong item order | `fixed: False` with no sequence | Set `fixed: True` or explicit `sequence` values |
| Stimulus not rendering | Stimulus ref on item instead of section | Move stimulus ref to `qti-assessment-section` level |

## Build Pattern

```python
def create_test(session, qti_base, test_id, title, item_ids):
    """Create a test from a list of existing item identifiers."""
    item_refs = [
        {"identifier": iid, "href": f"{iid}.xml"}
        for iid in item_ids
    ]
    payload = {
        "identifier": test_id,
        "title": title,
        "qti-test-part": [{
            "identifier": f"{test_id}_part",
            "navigationMode": "linear",
            "submissionMode": "individual",
            "qti-assessment-section": [{
                "identifier": f"{test_id}_section",
                "title": title,
                "visible": True,
                "required": True,
                "fixed": True,
                "sequence": 1,
                "qti-assessment-item-ref": item_refs,
            }],
        }],
        "qti-outcome-declaration": [
            {"identifier": "SCORE", "cardinality": "single", "baseType": "float"}
        ],
    }
    resp = session.post(f"{qti_base}/assessment-tests", json=payload)
    resp.raise_for_status()
    return resp.json()["identifier"]
```

## Multi-Section Test

```python
# For tests with multiple sections (e.g., MCQ section + FRQ section):
"qti-assessment-section": [
    {
        "identifier": "mcq_section",
        "title": "Multiple Choice",
        "sequence": 1,
        "qti-assessment-item-ref": mcq_refs,
        # ... other fields
    },
    {
        "identifier": "frq_section",
        "title": "Free Response",
        "sequence": 2,
        "qti-assessment-item-ref": frq_refs,
        # ... other fields
    },
]
```
