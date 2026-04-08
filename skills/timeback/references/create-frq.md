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

## External Grader Setup (CRITICAL for Auto-Grading) — verified 2026-04-08

> **READ THIS FIRST.** FRQs with auto-grading have FOUR required components, all of which must be present in the actual `rawXml` body — NOT just in JSON-typed metadata fields. Getting any of these wrong leaves the item silently broken: it will accept POSTs (200/201) but never grade student responses.
>
> 1. **Six outcome declarations** with the exact types/cardinalities listed below (the most-bitten gotcha — `API_RESPONSE` is `cardinality="record"`, NOT `single`/`string`; `FEEDBACK_VISIBILITY` is `base-type="identifier"`, NOT `boolean`; `MAXSCORE` is **NOT used** — the platform tracks max score elsewhere; a **vestigial `FEEDBACK` outcome** must be declared even though nothing reads/writes it)
> 2. **One `<qti-rubric-block use="ext:criteria" view="scorer">` element PER criterion** (NOT one mega-block with all criteria), each wrapping plain text in `<qti-content-body>`, all placed at the top of `<qti-item-body>` — NOT just in `metadata.rubric`
> 3. **A `<qti-custom-operator class="com.alpha-1edtech.ExternalApiScore" definition="...URL..." />` SELF-CLOSING (no `<qti-variable>` child)** inside a 5-step `<qti-response-processing>` pipeline — NOT just in `responseProcessing.customOperator` JSON field. The grader implicitly reads `RESPONSE`.
> 4. **A `<qti-feedback-block outcome-identifier="FEEDBACK_VISIBILITY" identifier="VISIBLE">` containing `<qti-printed-variable identifier="GENERATED_FEEDBACK">`** — without this, the AI-generated feedback never reaches the student even if grading succeeds
>
> **You MUST POST FRQs with auto-grading as XML.** JSON POST silently drops the rubric-blocks, the custom-operator, the feedback-block, and the printed-variable from the rawXml body. See "JSON POST trap" below.
>
> **The canonical reference is `qti-item-4d365abb-7916-41a9-85d4-08ed7d3dd718`** (verified 2026-04-08 after the FRQ + grader fix shipped). When in doubt, GET that item and copy its `rawXml` shape. The previous reference (`s4-u1-frq-01`) used a now-superseded grader URL and a single-rubric-block layout — DO NOT copy from it.

### Canonical Full XML Pattern

This is the verified-working pattern from `qti-item-4d365abb-7916-41a9-85d4-08ed7d3dd718` (confirmed by GET 2026-04-08, after the grader fix). Treat it as the template — adapt the prompt, rubric criteria, and grader URL, but keep the structure exactly. Order of children inside `<qti-item-body>` matters: rubric-blocks → interaction → feedback-block.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item
    xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqtiasi_v3p0 https://purl.imsglobal.org/spec/qti/v3p0/schema/xsd/imsqti_asiv3p0_v1p0.xsd"
    identifier="qti-item-..." title="..." adaptive="false" time-dependent="false">

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

  <!-- SCORE MUST include BOTH normal-minimum="0" AND normal-maximum="1.0".
       NO MAXSCORE outcome — the platform tracks max score elsewhere. -->
  <qti-outcome-declaration identifier="SCORE" cardinality="single" base-type="float" normal-maximum="1.0" normal-minimum="0">
    <qti-default-value><qti-value>0</qti-value></qti-default-value>
  </qti-outcome-declaration>

  <!-- Vestigial FEEDBACK outcome the platform expects. Never written or read by
       the response-processing pipeline below — keep with empty default value.
       Omitting this is silently accepted but may break downstream consumers. -->
  <qti-outcome-declaration identifier="FEEDBACK" base-type="string" cardinality="single">
    <qti-default-value><qti-value /></qti-default-value>
  </qti-outcome-declaration>

  <qti-item-body>
    <!-- Rubric criteria: ONE qti-rubric-block PER criterion (not one mega-block).
         Plain text inside qti-content-body — no h1/h2/p wrapping needed.
         These are placed FIRST inside qti-item-body, before the interaction. -->
    <qti-rubric-block use="ext:criteria" view="scorer">
      <qti-content-body>[Part A] Criterion 1 text...</qti-content-body>
    </qti-rubric-block>
    <qti-rubric-block use="ext:criteria" view="scorer">
      <qti-content-body>[Part A] Criterion 2 text...</qti-content-body>
    </qti-rubric-block>
    <qti-rubric-block use="ext:criteria" view="scorer">
      <qti-content-body>[Part B] Criterion 3 text...</qti-content-body>
    </qti-rubric-block>
    <!-- ...one block per rubric criterion... -->

    <!-- expected-lines sizes the textarea; required="true" prevents empty submits
         at the UI layer (which is why the old null-RESPONSE branch is gone). -->
    <qti-extended-text-interaction response-identifier="RESPONSE" expected-lines="15" required="true">
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
  </qti-item-body>

  <qti-response-processing>
    <!-- Step 1: Call the external grader. The custom-operator is SELF-CLOSING
         with NO qti-variable child — the grader implicitly reads RESPONSE.
         Result is a record-typed value with fields SCORE, feedback, FEEDBACK. -->
    <qti-set-outcome-value identifier="API_RESPONSE">
      <qti-custom-operator class="com.alpha-1edtech.ExternalApiScore" definition="https://YOUR-GRADER-HOST/path" />
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
    <!-- NOTE: There is NO null-RESPONSE branch in the gold standard.
         required="true" on the interaction prevents empty submissions, so the
         defensive condition is unnecessary. Adding it is silently accepted but
         is not part of the canonical pattern. -->
    <qti-set-outcome-value identifier="FEEDBACK_VISIBILITY">
      <qti-base-value base-type="identifier">VISIBLE</qti-base-value>
    </qti-set-outcome-value>
  </qti-response-processing>
</qti-assessment-item>
```

### Outcome Declarations — exact shapes

The biggest source of bugs is using the wrong cardinality/base-type. The table below matches the gold-standard `qti-item-4d365abb-7916-41a9-85d4-08ed7d3dd718`.

| Identifier | Cardinality | Base type | Notes |
|---|---|---|---|
| `API_RESPONSE` | **`record`** | **`string`** for POST (validator quirk — see below) | Holds the structured grader response. Field-identifiers: `SCORE` (float), `feedback` (string, lowercase), `FEEDBACK` (string, uppercase fallback). Provide a `<qti-default-value>` with all three fields. |
| `FEEDBACK_VISIBILITY` | `single` | **`identifier`** | NOT `boolean`. Set to `VISIBLE` to show the feedback block. |
| `GENERATED_FEEDBACK` | `single` | `string` | The actual feedback text shown to the student. Populated by the response-processing pipeline from `API_RESPONSE`. |
| `SCORE` | `single` | `float` with **BOTH** `normal-maximum="1.0"` **AND** `normal-minimum="0"` | Default `0`. Populated from `API_RESPONSE.SCORE`. **No `MAXSCORE` outcome — the platform tracks max score elsewhere.** |
| `FEEDBACK` | `single` | `string` | **Vestigial** — the platform expects this declaration to be present even though nothing in the canonical pipeline reads or writes it. Provide an empty default: `<qti-default-value><qti-value /></qti-default-value>`. Omitting it is silently accepted but may break downstream consumers. |
| `RESPONSE` (response-declaration, not outcome) | `single` | `string` | Plain text student answer. Use `<qti-correct-response><qti-value /></qti-correct-response>` (self-closing empty value). |

> Earlier skill versions listed `MAXSCORE` and omitted `FEEDBACK`. That was wrong. Updated 2026-04-08 from the gold-standard `qti-item-4d365abb-7916-41a9-85d4-08ed7d3dd718` after the FRQ + grader fix shipped. Earlier-still versions also listed `FEEDBACK` as identifier, `GRADING_RESPONSE` as string, and `FEEDBACK_VISIBILITY` as boolean — also wrong.

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
- **Vestigial `FEEDBACK` outcome (string)** — Not the same as `GENERATED_FEEDBACK`. Nothing in the canonical pipeline reads or writes it, but the platform expects the declaration to be present. Treat it as a required schema artifact, not as a place to put real data. Always include with an empty default value.
- **No `MAXSCORE` outcome** — Older patterns declared `MAXSCORE` to set the upper bound. The current platform tracks the max score on `SCORE` itself via `normal-maximum`, so a separate outcome is redundant. `SCORE` MUST have BOTH `normal-minimum="0"` and `normal-maximum="1.0"` — omitting either was the old failure mode.
- **`<qti-feedback-block>` + `<qti-printed-variable>`** — This is the only mechanism that renders dynamic grader output to the student. Without it, the `GENERATED_FEEDBACK` outcome holds the text but nothing displays it.
- **Self-closing `<qti-custom-operator>` (no `<qti-variable>` child)** — The grader implementation reads `RESPONSE` implicitly. Adding an explicit `<qti-variable identifier="RESPONSE" />` child is silently accepted by the validator but is not part of the canonical shape and may confuse future readers about the data flow.
- **Single `<qti-response-condition>` (lowercase/uppercase fallback only)** — There is NO defensive null-RESPONSE branch. `required="true"` on the extended-text-interaction prevents empty submissions at the UI layer, so a hard-coded `SCORE = 0` fallback is unnecessary. Adding one is silently accepted but is not canonical.

### Rubric Blocks — exact shape (verified 2026-04-08)

```xml
<qti-rubric-block use="ext:criteria" view="scorer">
  <qti-content-body>[Part A] Criterion 1 plain text...</qti-content-body>
</qti-rubric-block>
<qti-rubric-block use="ext:criteria" view="scorer">
  <qti-content-body>[Part A] Criterion 2 plain text...</qti-content-body>
</qti-rubric-block>
<qti-rubric-block use="ext:criteria" view="scorer">
  <qti-content-body>[Part B] Criterion 3 plain text...</qti-content-body>
</qti-rubric-block>
```

Rules:
- `use="ext:criteria"` is REQUIRED on every block (this attribute tells the grader to consume the block as scoring criteria, not display content)
- `view="scorer"` on every block keeps the rubric hidden from students; the grader still receives it
- The content MUST be wrapped in `<qti-content-body>` — bare text/HTML at the rubric-block level is silently dropped
- **One `<qti-rubric-block>` per criterion**, NOT one mega-block with all criteria. The grader concatenates all blocks in document order to build the criteria list. Older docs (and earlier versions of this skill) said to use a single block with `<h1>`/`<h2>`/`<p>` markup inside — that was wrong and is now superseded.
- Plain text inside `<qti-content-body>` is enough. No need for `<h1>`/`<h2>`/`<p>` wrappers — the grader doesn't render the rubric to students, so structure markup adds no value. Keeping it plain also avoids XHTML sanitization bugs.
- Place all rubric-blocks at the **top** of `<qti-item-body>`, BEFORE the `<qti-extended-text-interaction>`. The interaction and feedback-block come after.
- A `[Part A]` / `[Part B]` prefix in each block is the convention used by the gold-standard item to encode part-grouping in plain text (since there's no per-block part attribute).
- `metadata.rubric` is NOT a substitute. Storing rubric markup there leaves it invisible to the grader. Use it only as a redundant backup.

### Grader URL Rules — CRITICAL (verified 2026-04-08)

- **NEVER invent or guess a grader URL.** ALWAYS get it from the user before creating any FRQ with auto-grading. The URL is course-specific and must be supplied at task time.
- **Watch for double-protocol typos.** Earlier items pasted with `https://https://coreapi.inceptstore.com/...` — a copy-paste artifact. Always grep the XML for `https://https://` and `http://http://` before POST/PUT.
- The XML POST/PUT endpoint validates `definition` against an internal **allowlist** (`validateCustomOperatorUrls` in the QTI XML processor). URLs not on the allowlist return:
  ```
  500 Internal Server Error
  Custom operator "com.alpha-1edtech.ExternalApiScore" definition URL hostname is not in the approved grader allowlist: "<hostname>"
  ```
- If the user's grader URL fails the allowlist check, **STOP** and ask the user to coordinate with the platform team to add it. Do NOT fall back to JSON POST as a workaround — that's the trap below.
- The URL must start with `http://` or `https://` (exactly once).

#### Known allowlist status (verified 2026-04-08)

| Hostname + path | Allowlist status | Notes |
|---|---|---|
| `https://coreapi.inceptstore.com/cs-autograder/score` | ✓ ALLOWED & WORKING | Current canonical grader URL. Confirmed via XML POST 201 + live grading. Used by `qti-item-4d365abb-7916-41a9-85d4-08ed7d3dd718`. **Note: NO `/api/` prefix.** |
| `https://coreapi.inceptstore.com/api/cs-autograder/score` | ✗ SUPERSEDED | The hostname is on the allowlist but the `/api/` prefix returns 404 from the grader after the 2026-04-08 routing change. Earlier versions of this skill recommended this path — DO NOT use it. |
| `https://cs-autograder.onrender.com/...` | ✗ REJECTED | 500 from allowlist validator. Was on `s4-u1-frq-01` for a while via the JSON POST trap (which bypasses validation but doesn't propagate to rawXml — the item never actually graded). |

### JSON POST trap — DO NOT use JSON POST for graded FRQs

The JSON `/assessment-items` controller does NOT enforce the grader allowlist, so a JSON POST with a `responseProcessing.customOperator` field returns 201 and looks like it worked. **It did not work.** When you GET the item back:

| Source | rubric-block in rawXml? | custom-operator in rawXml? | feedback-block in rawXml? |
|--------|---|---|---|
| JSON POST with `metadata.rubric` + `responseProcessing.customOperator` | **NO** | **NO** (rawXml has placeholder `<qti-response-processing template=".../custom.xml"/>`) | **NO** |
| XML POST/PUT with full canonical body | YES (one block per criterion) | YES (URL must be allowlisted, self-closing element) | YES |

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

# Rubric: at least 1 block, all properly attributed
assert raw.count("<qti-rubric-block") >= 1
assert 'use="ext:criteria"' in raw
assert 'view="scorer"' in raw
assert "qti-content-body" in raw

# Custom operator: present, allowlisted URL, NO nested qti-variable child
assert "qti-custom-operator" in raw
assert "ExternalApiScore" in raw
assert grader_url in raw  # exact URL, no double-https
assert "/api/cs-autograder/score" not in raw  # superseded path
# The custom-operator MUST be self-closing in the canonical pattern. If it has
# a qti-variable child it will still validate but is not canonical.
import re
assert re.search(r'<qti-custom-operator[^/>]*/>', raw), "custom-operator must be self-closing"

# Feedback rendering
assert "qti-feedback-block" in raw
assert "qti-printed-variable" in raw
assert "GENERATED_FEEDBACK" in raw

# Outcome decls — exact shapes
assert 'cardinality="record"' in raw  # API_RESPONSE
assert 'base-type="identifier"' in raw  # FEEDBACK_VISIBILITY
assert 'normal-minimum="0"' in raw  # SCORE
assert 'normal-maximum="1.0"' in raw or 'normal-maximum="1"' in raw  # SCORE
assert 'identifier="FEEDBACK"' in raw  # vestigial FEEDBACK outcome
assert 'identifier="MAXSCORE"' not in raw  # MAXSCORE is REMOVED

# Interaction attributes
assert 'expected-lines=' in raw
assert 'required="true"' in raw

# Pipeline shape — single null-fallback condition (lowercase→uppercase),
# NO defensive null-RESPONSE branch
assert raw.count("<qti-response-condition") == 1
```

### The Only Path That Works (verified 2026-04-08)

1. Get the grader URL from the user (and grep for `https://https://` typos and stray `/api/` prefixes)
2. Build the full canonical QTI XML using the template above:
   - 5 outcome decls + RESPONSE response-decl: `API_RESPONSE` (record), `FEEDBACK_VISIBILITY` (identifier), `GENERATED_FEEDBACK` (string), `SCORE` (float, with BOTH `normal-minimum="0"` and `normal-maximum="1.0"`), and the vestigial `FEEDBACK` (string, empty default)
   - One `<qti-rubric-block>` per criterion at the top of `<qti-item-body>`
   - `<qti-extended-text-interaction>` with `expected-lines` and `required="true"`
   - `<qti-feedback-block>` with `<qti-printed-variable>`
   - 5-step response-processing pipeline with self-closing `<qti-custom-operator/>` and a single lowercase/uppercase FEEDBACK fallback condition
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
| Score always 0 | Missing rubric-block with `use="ext:criteria"` OR rubric content not wrapped in `<qti-content-body>` OR all criteria stuffed into one mega-block | Use the canonical pattern: ONE `<qti-rubric-block use="ext:criteria" view="scorer">` per criterion, plain text inside `<qti-content-body>` |
| Grader returns score but student sees nothing | Missing `<qti-feedback-block>` + `<qti-printed-variable>` for `GENERATED_FEEDBACK` | Add the canonical feedback-block — `GENERATED_FEEDBACK` outcome alone is not enough |
| Grader timeout | Rubric too complex / grader overloaded | Simplify rubric, check grader health |
| Student sees raw HTML | Prompt XHTML invalid | Sanitize prompt HTML |
| Grader returns 404 (route not found) for `coreapi.inceptstore.com` | Old `/api/cs-autograder/score` path used. After 2026-04-08 the prefix moved — the working path is `/cs-autograder/score` (no `/api/`) | Use `https://coreapi.inceptstore.com/cs-autograder/score` exactly |
| No feedback after submit | Missing `FEEDBACK_VISIBILITY` outcome OR pipeline never sets it to `VISIBLE` | Use the canonical 5-step response-processing pipeline; ensure `FEEDBACK_VISIBILITY` is `base-type="identifier"` not `boolean` |
| 500 "URL hostname is not in the approved grader allowlist" but URL looks fine | Double-protocol typo (`https://https://`) — the validator parses the second `https` as the hostname | Grep for `https://https://` and `http://http://` before posting |
| `API_RESPONSE` field extraction silently returns null | `API_RESPONSE` declared as `cardinality="single"` `base-type="string"` instead of `cardinality="record"` | Use `cardinality="record"` with a `<qti-default-value>` listing the field-identifiers; `<qti-field-value>` only works on records |
| Score never reaches `normal-maximum` even on perfect answers | `SCORE` outcome missing `normal-minimum="0"` (it must have BOTH `normal-minimum` and `normal-maximum`) | Add `normal-minimum="0"` to the `SCORE` outcome declaration |
| Item POSTs/PUTs OK but a downstream consumer 500s reading the item | Vestigial `FEEDBACK` outcome decl missing | Add `<qti-outcome-declaration identifier="FEEDBACK" base-type="string" cardinality="single"><qti-default-value><qti-value /></qti-default-value></qti-outcome-declaration>` even though nothing in the canonical pipeline reads or writes it |
| Empty textarea on render / student can submit empty answer | `expected-lines` and/or `required` missing on `<qti-extended-text-interaction>` | Add `expected-lines="15" required="true"` (the `required="true"` is what removed the need for the old null-RESPONSE branch in response-processing) |
| Custom-operator validates but pipeline output is empty | `<qti-custom-operator>` has a stale `<qti-variable>` child from an older pattern that confuses the grader | Make `<qti-custom-operator class="..." definition="..." />` self-closing — the grader implicitly reads `RESPONSE` |

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
