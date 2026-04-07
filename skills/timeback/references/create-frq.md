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

> **READ THIS FIRST.** FRQs with auto-grading have FOUR required components, all of which must be present in the actual `rawXml` body — NOT just in JSON-typed metadata fields. Getting any of these wrong leaves the item silently broken: it will accept POSTs (200/201) but never grade student responses.
>
> 1. **Six outcome declarations** with the exact types/cardinalities listed below (the most-bitten gotcha — `API_RESPONSE` is `cardinality="record"`, NOT `single`/`string`; `FEEDBACK_VISIBILITY` is `base-type="identifier"`, NOT `boolean`)
> 2. **One `<qti-rubric-block use="ext:criteria" view="scorer">` element wrapped in `<qti-content-body>`, INSIDE `<qti-item-body>`** — NOT just in `metadata.rubric`
> 3. **A `<qti-custom-operator class="com.alpha-1edtech.ExternalApiScore" definition="...URL...">` INSIDE a multi-step `<qti-response-processing>` pipeline** — NOT just in `responseProcessing.customOperator` JSON field
> 4. **A `<qti-feedback-block outcome-identifier="FEEDBACK_VISIBILITY" identifier="VISIBLE">` containing `<qti-printed-variable identifier="GENERATED_FEEDBACK">`** — without this, the AI-generated feedback never reaches the student even if grading succeeds
>
> **You MUST POST FRQs with auto-grading as XML.** JSON POST silently drops the rubric-block, the custom-operator, the feedback-block, and the printed-variable from the rawXml body. See "JSON POST trap" below.
>
> **The canonical reference is `s4-u1-frq-01`** (verified 2026-04-07 after PUT). When in doubt, GET that item and copy its `rawXml` shape.

### Canonical Full XML Pattern

This is the verified-working pattern from `s4-u1-frq-01`. Treat it as the template — adapt the prompt, rubric criteria, and grader URL, but keep the structure.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item
    xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqtiasi_v3p0 https://purl.imsglobal.org/spec/qti/v3p0/schema/xsd/imsqti_asiv3p0_v1p0.xsd"
    identifier="s4-..." title="..." adaptive="false" time-dependent="false">

  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="string">
    <qti-correct-response>
      <qti-value />
    </qti-correct-response>
  </qti-response-declaration>

  <!-- API_RESPONSE is cardinality="record". The outer base-type="string" is a
       Mongoose validator workaround required for POST (see "POST vs PUT validator
       gotcha" below) — the actual field types live on the qti-value children. -->
  <qti-outcome-declaration identifier="API_RESPONSE" cardinality="record" base-type="string">
    <qti-default-value>
      <qti-value base-type="string" field-identifier="FEEDBACK" />
      <qti-value base-type="string" field-identifier="feedback" />
      <qti-value base-type="float" field-identifier="SCORE">0</qti-value>
    </qti-default-value>
  </qti-outcome-declaration>

  <!-- FEEDBACK_VISIBILITY is base-type="identifier", NOT boolean -->
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
      <qti-prompt><p>...prompt HTML here, sanitized to XHTML...</p></qti-prompt>
    </qti-extended-text-interaction>

    <!-- Renders the AI-generated feedback to the student after submission.
         Without this block, grading happens but the student sees nothing. -->
    <qti-feedback-block outcome-identifier="FEEDBACK_VISIBILITY" identifier="VISIBLE">
      <qti-content-body>
        <div style="white-space: pre-line;">
          <qti-printed-variable identifier="GENERATED_FEEDBACK" class="qti-html-printed-variable" />
        </div>
      </qti-content-body>
    </qti-feedback-block>

    <!-- The rubric the grader actually consumes. Use ext:criteria + view=scorer.
         Wrap content in <qti-content-body>. -->
    <qti-rubric-block use="ext:criteria" view="scorer">
      <qti-content-body>
        <h1>Rubric (N points)</h1>
        <h2>Part A (X points) - ...</h2>
        <p>1. [Part (a)] Criterion text...</p>
        <p>2. [Part (a)] Criterion text...</p>
        <h2>Part B (Y points) - ...</h2>
        <p>3. [Part (b)] Criterion text...</p>
        <!-- ... -->
      </qti-content-body>
    </qti-rubric-block>
  </qti-item-body>

  <qti-response-processing>
    <!-- Step 1: Call the external grader. Result is a record-typed value
         with field-identifiers SCORE, feedback, FEEDBACK. -->
    <qti-set-outcome-value identifier="API_RESPONSE">
      <qti-custom-operator class="com.alpha-1edtech.ExternalApiScore" definition="https://YOUR-GRADER-HOST/path">
        <qti-variable identifier="RESPONSE" />
      </qti-custom-operator>
    </qti-set-outcome-value>

    <!-- Step 2: Extract the score from API_RESPONSE.SCORE -->
    <qti-set-outcome-value identifier="SCORE">
      <qti-field-value field-identifier="SCORE">
        <qti-variable identifier="API_RESPONSE" />
      </qti-field-value>
    </qti-set-outcome-value>

    <!-- Step 3: Extract feedback. Try lowercase "feedback" first... -->
    <qti-set-outcome-value identifier="GENERATED_FEEDBACK">
      <qti-field-value field-identifier="feedback">
        <qti-variable identifier="API_RESPONSE" />
      </qti-field-value>
    </qti-set-outcome-value>

    <!-- ...then fall back to uppercase "FEEDBACK" if lowercase was null. -->
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

    <!-- Step 4: Reveal the feedback block. -->
    <qti-set-outcome-value identifier="FEEDBACK_VISIBILITY">
      <qti-base-value base-type="identifier">VISIBLE</qti-base-value>
    </qti-set-outcome-value>

    <!-- Step 5: If the student submitted nothing, hard-code score 0
         and still show the feedback area. -->
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
</qti-assessment-item>
```

### Outcome Declarations — exact shapes

The biggest source of bugs is using the wrong cardinality/base-type. The corrections below override what older docs and earlier versions of this skill said.

| Identifier | Cardinality | Base type | Notes |
|---|---|---|---|
| `API_RESPONSE` | **`record`** | **`string`** for POST (validator quirk — see below) | Holds the structured grader response. Field-identifiers: `SCORE` (float), `feedback` (string, lowercase), `FEEDBACK` (string, uppercase fallback). Provide a `<qti-default-value>` with all three fields. |
| `FEEDBACK_VISIBILITY` | `single` | **`identifier`** | NOT `boolean`. Set to `VISIBLE` to show the feedback block. |
| `GENERATED_FEEDBACK` | `single` | `string` | The actual feedback text shown to the student. Populated by the response-processing pipeline from `API_RESPONSE`. |
| `MAXSCORE` | `single` | `float` | Default `1`. Sets the upper bound. |
| `SCORE` | `single` | `float` (with `normal-maximum="1"`) | Default `0`. Populated from `API_RESPONSE.SCORE`. |
| `RESPONSE` (response-declaration, not outcome) | `single` | `string` | Plain text student answer. Use `<qti-correct-response><qti-value /></qti-correct-response>` (self-closing empty value). |

> The previous skill version listed `FEEDBACK` (identifier), `GRADING_RESPONSE` (string), and `FEEDBACK_VISIBILITY` as `boolean`. Those were wrong. The canonical pattern uses `GENERATED_FEEDBACK` instead of `FEEDBACK`/`GRADING_RESPONSE` and `FEEDBACK_VISIBILITY` is an `identifier` flipped to `VISIBLE`.

#### POST vs PUT validator gotcha for record-typed outcomes (verified 2026-04-07)

The Mongoose schema on the QTI API requires `baseType` on EVERY outcome declaration, even though the QTI 3.0 spec says record-typed outcomes don't have one (their types live on the `<qti-value>` children inside `<qti-default-value>`).

**POST `/assessment-items` (strict)**: REQUIRES `base-type="<enum>"` on the API_RESPONSE outcome-decl. Empty string and missing both fail with:
```
QTIAssessmentItem validation failed: outcomeDeclarations.0.baseType: Path `baseType` is required.
```
And `base-type="record"` fails with:
```
`record` is not a valid enum value for path `baseType`.
```
Workaround: set `base-type="string"` (or any other valid enum value — `float`, `identifier`, etc.). The actual record fields are governed by the `<qti-value>` children's `field-identifier` + `base-type` attributes inside `<qti-default-value>`, so the outer `base-type` is structurally meaningless on a record-typed outcome — but the validator wants it anyway.

**PUT `/assessment-items/{id}` (lenient)**: Accepts the rawXml without `base-type` on record-typed outcomes and silently coerces the stored `baseType` to `""`. This is why `s4-u1-frq-01` (updated via PUT) has `cardinality="record"` with no `base-type` attribute in its rawXml, while items created via POST will have `base-type="string"`.

**Implication**: When building items via POST, ALWAYS include `base-type="string"` on `API_RESPONSE`. When migrating existing items via GET-modify-PUT, you can leave it absent if the source XML doesn't have it, but adding it explicitly is safer and round-trips identically.

### Why each piece exists

- **`API_RESPONSE` (record)** — The custom-operator returns structured data with multiple fields, not a single string. Marking it `record` lets `<qti-field-value>` extract specific fields.
- **`feedback` (lowercase) + `FEEDBACK` (uppercase) fallback** — Different grader implementations return the feedback under different keys. The pipeline tries lowercase first, falls back to uppercase if null. Defensive coding for grader-side schema drift.
- **`FEEDBACK_VISIBILITY` as identifier** — A boolean would force binary visible/hidden. Identifier lets you add states (e.g. `PARTIAL`, `HIDDEN`) later without breaking the gating mechanism.
- **`<qti-feedback-block>` + `<qti-printed-variable>`** — This is the only mechanism that renders dynamic grader output to the student. Without it, the `GENERATED_FEEDBACK` outcome holds the text but nothing displays it.
- **The two `<qti-response-condition>` blocks** — First handles the lowercase/uppercase fallback for feedback extraction. Second handles the empty-submission edge case. Both are required: omit either and you get silent partial-failure modes.

### Rubric Block — exact shape

```xml
<qti-rubric-block use="ext:criteria" view="scorer">
  <qti-content-body>
    <!-- HTML rubric content here — h1/h2/p are fine, must be valid XHTML -->
  </qti-content-body>
</qti-rubric-block>
```

Rules:
- `use="ext:criteria"` is REQUIRED (this attribute tells the grader to consume this block as scoring criteria, not display content)
- `view="scorer"` keeps the rubric hidden from students; the grader still receives it
- The content MUST be wrapped in `<qti-content-body>` — bare HTML at the rubric-block level is silently dropped
- A SINGLE `<qti-rubric-block>` containing all criteria as `<p>` items inside `<qti-content-body>` is the standard pattern. (Older docs that suggested one rubric-block per criterion with `data-part` divs were wrong.)
- `metadata.rubric` is NOT a substitute. Storing rubric markup there leaves it invisible to the grader. Use it only as a redundant backup.

### Grader URL Rules — CRITICAL (verified 2026-04-07)

- **NEVER invent or guess a grader URL.** ALWAYS get it from the user before creating any FRQ with auto-grading. The URL is course-specific and must be supplied at task time.
- **Watch for double-protocol typos.** The original `s4-u1-frq-01` pasted with `https://https://coreapi.inceptstore.com/...` — a copy-paste artifact. Always grep the XML for `https://https://` and `http://http://` before POST/PUT.
- The XML POST/PUT endpoint validates `definition` against an internal **allowlist** (`validateCustomOperatorUrls` in the QTI XML processor). URLs not on the allowlist return:
  ```
  500 Internal Server Error
  Custom operator "com.alpha-1edtech.ExternalApiScore" definition URL hostname is not in the approved grader allowlist: "<hostname>"
  ```
- If the user's grader URL fails the allowlist check, **STOP** and ask the user to coordinate with the platform team to add it. Do NOT fall back to JSON POST as a workaround — that's the trap below.
- The URL must start with `http://` or `https://` (exactly once).

#### Known allowlist status (verified 2026-04-07)

| Hostname | Allowlist status | Notes |
|---|---|---|
| `coreapi.inceptstore.com` | ✓ ALLOWED | Confirmed via XML POST 201. Path used: `/api/cs-autograder/score`. Used by `s4-u1-frq-01`. |
| `cs-autograder.onrender.com` | ✗ REJECTED | 500 from allowlist validator. Was on `s4-u1-frq-01` for a while via JSON POST trap (which bypasses validation but doesn't propagate to rawXml — the item never actually graded). |

### JSON POST trap — DO NOT use JSON POST for graded FRQs

The JSON `/assessment-items` controller does NOT enforce the grader allowlist, so a JSON POST with a `responseProcessing.customOperator` field returns 201 and looks like it worked. **It did not work.** When you GET the item back:

| Source | rubric-block in rawXml? | custom-operator in rawXml? | feedback-block in rawXml? |
|--------|---|---|---|
| JSON POST with `metadata.rubric` + `responseProcessing.customOperator` | **NO** | **NO** (rawXml has placeholder `<qti-response-processing template=".../custom.xml"/>`) | **NO** |
| XML POST/PUT with full canonical body | YES | YES (URL must be allowlisted) | YES |

The JSON-typed `responseProcessing.customOperator` field is preserved on the GET response, but the **renderer and grader read from `rawXml`** — so a JSON-posted FRQ with custom grading is silently inert: prompt renders, students can submit, but no scoring happens AND no feedback displays.

### Updating an existing graded FRQ — GET-modify-PUT

For an existing item that needs to be migrated to the canonical pattern (e.g. it was JSON-POSTed and is now broken):

```python
# 1. GET to capture current metadata (PUT is full-replace, so we must preserve it)
g = client.get_item(item_id)
current_metadata = g["data"].get("metadata", {})

# 2. Build the new XML (full canonical pattern, with corrected grader URL)
new_xml = build_canonical_frq_xml(prompt=..., rubric_html=..., grader_url=...)

# 3. Sanity-check for the double-https typo BEFORE validating
assert "https://https://" not in new_xml, "double-protocol typo"
assert "http://http://" not in new_xml, "double-protocol typo"

# 4. Validate parses
import xml.etree.ElementTree as ET
ET.fromstring(new_xml)

# 5. PUT with metadata preserved
result = client.update_item(item_id, new_xml, metadata=current_metadata)

# 6. Verify ALL of these post-PUT:
g2 = client.get_item(item_id)
raw = g2["data"].get("rawXml", "")
assert "qti-rubric-block" in raw
assert 'use="ext:criteria"' in raw
assert 'view="scorer"' in raw
assert "qti-content-body" in raw
assert "qti-custom-operator" in raw
assert "ExternalApiScore" in raw
assert grader_url in raw  # exact URL, no double-https
assert "qti-feedback-block" in raw
assert "qti-printed-variable" in raw
assert "GENERATED_FEEDBACK" in raw
assert 'cardinality="record"' in raw  # API_RESPONSE
assert 'base-type="identifier"' in raw  # FEEDBACK_VISIBILITY
```

### The Only Path That Works (verified 2026-04-07)

1. Get the grader URL from the user (and grep for `https://https://` typos)
2. Build the full canonical QTI XML using the template above (6 outcome decls + rubric-block in `<qti-content-body>` + feedback-block + printed-variable + multi-step response-processing pipeline)
3. Validate the XML with `ET.fromstring()` before posting
4. POST as `{"format": "xml", "xml": full_xml}` to `/assessment-items` (or PUT for updates, with metadata preserved)
5. If 500 with allowlist error → ask user to allowlist the URL with the platform team. Do not retry with the same URL.
6. After 201/200, GET the item back and run the assertions in the GET-modify-PUT block above. If any assertion fails, the item is broken — investigate, don't ship.

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
| Score always 0 | Missing rubric-block with `use="ext:criteria"` OR rubric content not wrapped in `<qti-content-body>` | Use the canonical rubric pattern (single block, `use="ext:criteria"`, `view="scorer"`, content inside `<qti-content-body>`) |
| Grader returns score but student sees nothing | Missing `<qti-feedback-block>` + `<qti-printed-variable>` for `GENERATED_FEEDBACK` | Add the canonical feedback-block — `GENERATED_FEEDBACK` outcome alone is not enough |
| Grader timeout | Rubric too complex / grader overloaded | Simplify rubric, check grader health |
| Student sees raw HTML | Prompt XHTML invalid | Sanitize prompt HTML |
| No feedback after submit | Missing `FEEDBACK_VISIBILITY` outcome OR pipeline never sets it to `VISIBLE` | Use the canonical 5-step response-processing pipeline; ensure `FEEDBACK_VISIBILITY` is `base-type="identifier"` not `boolean` |
| 500 "URL hostname is not in the approved grader allowlist" but URL looks fine | Double-protocol typo (`https://https://`) — the validator parses the second `https` as the hostname | Grep for `https://https://` and `http://http://` before posting |
| `API_RESPONSE` field extraction silently returns null | `API_RESPONSE` declared as `cardinality="single"` `base-type="string"` instead of `cardinality="record"` | Use `cardinality="record"` with a `<qti-default-value>` listing the field-identifiers; `<qti-field-value>` only works on records |

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
