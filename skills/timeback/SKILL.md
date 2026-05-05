---
name: timeback
description: >
  Timeback/QTI platform reference for creating, updating, and publishing educational content,
  AND for reading student/teacher/class/activity/goal data from the admin dashboard at
  alpha.timeback.com.
  MUST invoke when: (1) writing code that calls Timeback API endpoints (/assessment-items,
  /assessment-tests, /stimuli, /courses, /components, /resources), (2) generating QTI XML,
  (3) writing HTML that will be embedded in QTI items or stimuli, (4) uploading content to S3
  for Timeback, (5) building course push pipelines, (6) creating PCI interactive items,
  (7) debugging rendering failures in Timeback student UI, (8) working with MathML or chemical
  formulas in QTI, (9) reading student/teacher/class/activity/goal data from the admin
  dashboard at alpha.timeback.com (`_serverFn` endpoints, Clerk session auth — see
  references/admin-dashboard-read-api.md), (10) verifying pushed QTI content via
  fetchCourseSyllabus / getCourseComponents / getLessonDetails round-trips.
  Covers all gotchas discovered across 3 AP course builds, 60+ fix scripts, and a full
  network sweep of the production admin dashboard.
---

# Timeback Platform Reference

This skill prevents the XML/QTI/rendering bugs that have cost days of debugging across AP Bio, AP Chem, and AP Micro builds. Every rule here was extracted from real fix scripts and production failures.

## CRITICAL RULE 1: XML vs JSON POST

The API's JSON-to-XML converter is **lossy**. It silently drops child elements for complex types. Items return 200 OK but render broken/empty in the student UI.

**JSON POST safe for (4 types ONLY)**:
- `choice` (MCQ)
- `extended-text` (FRQ)
- `order` (sequencing)
- `text-entry` (fill-in-blank)

**XML POST required for EVERYTHING ELSE**: match, hottext, hotspot, select-point, graphic-gap-match, gap-match, inline-choice, slider, associate, PCI, feedback-block, template.

XML format: `{"format": "xml", "xml": "<qti-assessment-item xmlns=\"http://www.imsglobal.org/xsd/imsqtiasi_v3p0\" ...>full XML</qti-assessment-item>"}`

Namespace MUST be: `http://www.imsglobal.org/xsd/imsqtiasi_v3p0` (NOT `imsqti_v3p0`).

## CRITICAL RULE 2: HTML Sanitization

ALL HTML entering QTI payloads (item prompts, stimulus content, feedback) MUST be sanitized to valid XHTML. The Timeback API uses a SAX XML parser. Invalid HTML causes silent render failures.

Run `scripts/sanitize_html.py` or apply these rules:

```python
import re

def sanitize_html_for_xhtml(html: str) -> str:
    # 1. Self-close void elements: <br> → <br/>, <img ...> → <img .../>
    html = re.sub(r'<(br|hr|col|embed|input|link|meta|param|source|track|wbr)(\s[^>]*)?\s*(?<!/)\s*>', r'<\1\2/>', html)
    html = re.sub(r'<img((?:\s+[^>]*?)?)(?<!/)>', r'<img\1/>', html)
    # 2. Escape bare < not part of tags
    html = re.sub(r'<(?![a-zA-Z/!])', '&lt;', html)
    # 3. Escape bare & not part of entities
    html = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', html)
    # 4. Fix boolean attributes for XHTML
    for attr in ("allowfullscreen", "disabled", "checked", "selected", "readonly",
                 "required", "autofocus", "autoplay", "controls", "loop", "muted"):
        html = re.sub(rf'(<[^>]*\s){attr}(?=[\s/>])', rf'\1{attr}="{attr}"', html)
    return html
```

Additional HTML rules:
- **`<table>` inside `<p>` is the #1 rendering bug.** Split: `<p>text</p><table>...</table><p>more</p>`
- Platform strips `<style>` blocks — ALL CSS must be inline on elements
- Forbidden: `<center>`, `<font>`, nested `<p>`, `<p>` in modalFeedback
- HTML entities valid in HTML but NOT XML: use Unicode instead (`&mdash;` → `—`, `&rarr;` → `→`, `&Delta;` → `Δ`)
- Markdown pipe tables must be converted to `<table>` before push
- Always validate XML with `ET.fromstring()` before pushing

## CRITICAL RULE 3: PUT is Full Replace

PUT replaces the ENTIRE item. Omit `stimulus` → link removed. Omit `metadata` → cleared.

**Update pattern**: GET item → extract `rawXml` → modify specific section → PUT back complete XML with `{"format": "xml", "xml": modified_xml, "metadata": {...}}`

Never reconstruct XML from scratch — you'll lose rubrics, response processing, grader URLs, feedback blocks.

## Pre-Push Checklist

Before ANY push operation, verify:

- [ ] All HTML run through `sanitize_html_for_xhtml()`?
- [ ] No `<table>` inside `<p>` tags?
- [ ] All void elements self-closed (`<br/>`, `<img/>`, `<hr/>`)?
- [ ] Complex interaction types using XML POST (not JSON)?
- [ ] `correctResponse.value` is array of strings `["A"]`?
- [ ] **MCQ inline feedback: each `<qti-feedback-inline>` is a CHILD of its `<qti-simple-choice>` (not a sibling of `qti-choice-interaction`), contains `<span>` not `<p>`, and outcome decls are `FEEDBACK-INLINE` / `MAXSCORE` / `SCORE` (NOT `FEEDBACK`)?** (verified 2026-04-07 against WORH23-qti103821-q1119893-v1 — see create-mcq.md)
- [ ] **FRQ items have ALL FOUR in `rawXml` body** (verified 2026-04-08 against `qti-item-4d365abb-7916-41a9-85d4-08ed7d3dd718` canonical pattern — JSON POST silently drops all four — see create-frq.md):
  - 5 outcome declarations + 1 response-decl: `API_RESPONSE` (cardinality=**record**, base-type=**string** for POST validator), `FEEDBACK_VISIBILITY` (base-type=**identifier**, NOT boolean), `GENERATED_FEEDBACK` (string), `SCORE` (float, with **BOTH** `normal-minimum="0"` AND `normal-maximum="1.0"`), vestigial `FEEDBACK` (string, empty default — required even though nothing reads/writes it), and the `RESPONSE` response-declaration. **No `MAXSCORE`** — removed from the canonical pattern.
  - **One `<qti-rubric-block use="ext:criteria" view="scorer">` PER criterion** (NOT one mega-block), each with plain text inside `<qti-content-body>`, all placed at the top of `<qti-item-body>` BEFORE the interaction
  - `<qti-extended-text-interaction>` with **`expected-lines`** and **`required="true"`** attributes
  - **Self-closing `<qti-custom-operator class="...ExternalApiScore" definition="..." />`** (no `<qti-variable>` child — the grader implicitly reads `RESPONSE`) inside a 5-step `<qti-response-processing>` pipeline with a single lowercase/uppercase FEEDBACK fallback condition (NO defensive null-RESPONSE branch)
  - `<qti-feedback-block outcome-identifier="FEEDBACK_VISIBILITY" identifier="VISIBLE">` containing `<qti-printed-variable identifier="GENERATED_FEEDBACK">` (without this, grader output never reaches the student)
- [ ] **FRQ grader URL came from the user (never invented), uses the post-2026-04-08 path `https://coreapi.inceptstore.com/cs-autograder/score` (NO `/api/` prefix), survived XML POST allowlist validation, and contains no `https://https://` double-protocol typo?**
- [ ] PCI: typeIdentifier matches across XML + JS + module ID + S3 filename?
- [ ] PCI: S3 URL verified accessible?
- [ ] PCI: `getResponse()` returns plain string, not nested object?
- [ ] Stimuli linked with full API URL in href?
- [ ] `lessonType` set in component-resource metadata? (WARNING: lessonType in resource metadata causes 500 as of 2026-04-02)
- [ ] Parent components have `parent` field set? (`courseComponent` auto-fills from `parent`, but set both for safety)
- [ ] Validated with `ET.fromstring()` before push?
- [ ] No bare `&` or HTML entities in XML contexts?
- [ ] Checkpoint file initialized for resume-on-failure?

## Operation-Specific References

Load the appropriate reference when performing a specific operation:

| Operation | Reference | When to Load |
|-----------|-----------|-------------|
| Create MCQ | [references/create-mcq.md](references/create-mcq.md) | Creating choice/MCQ items |
| Create FRQ | [references/create-frq.md](references/create-frq.md) | Creating extended-text/FRQ items, setting up graders |
| Create Stimulus | [references/create-stimulus.md](references/create-stimulus.md) | Creating articles, reading passages |
| Create PCI | [references/create-pci.md](references/create-pci.md) | Creating interactive items (MANDATORY — hardest integration) |
| Create Test | [references/create-test.md](references/create-test.md) | Creating assessment tests from item refs |
| Create Course | [references/create-course.md](references/create-course.md) | Building course structure (course/components/resources/links) |
| Update Item | [references/update-item.md](references/update-item.md) | Modifying existing items (GET/PUT gotchas) |
| Create Match/DnD | [references/create-match.md](references/create-match.md) | Creating match, hottext, hotspot, gap-match, graphic-gap-match |
| Push Pipeline | [references/push-pipeline.md](references/push-pipeline.md) | Building full course push pipelines |
| S3 Uploads | [references/s3-uploads.md](references/s3-uploads.md) | Uploading images, videos, PCI JS modules |
| Math/Formulas | [references/math-and-formulas.md](references/math-and-formulas.md) | MathML, chemical formulas, Unicode subscripts |
| Interaction Types | [references/interaction-types.md](references/interaction-types.md) | Checking what QTI types work on Timeback |
| Error Diagnosis | [references/common-errors.md](references/common-errors.md) | Debugging rendering or push failures |
| Admin Dashboard Read API | [references/admin-dashboard-read-api.md](references/admin-dashboard-read-api.md) | Reading student/teacher/class/activity/goals/mastery from `alpha.timeback.com` (complementary to QTI authoring; useful for round-trip verification of pushed content) |

## API Quick Reference

**Base URLs**:
- QTI API: `https://qti.alpha-1edtech.ai/api`
- OneRoster API: `https://api.alpha-1edtech.ai`
- Admin Dashboard (read): `https://alpha.timeback.com` (Clerk session auth — see [admin-dashboard-read-api.md](references/admin-dashboard-read-api.md))

**Auth**: OAuth 2.0 client_credentials via AWS Cognito. Token expires 3600s. Env vars: `TIMEBACK_CLIENT_ID`, `TIMEBACK_CLIENT_SECRET`.

**Token URL**: `https://prod-beyond-timeback-api-2-idp.auth.us-east-1.amazoncognito.com/oauth2/token`

**Auth pattern** (credentials go in POST body, NOT HTTP Basic Auth):
```python
resp = requests.post(TOKEN_URL, data={
    "grant_type": "client_credentials",
    "client_id": os.environ["TIMEBACK_CLIENT_ID"],
    "client_secret": os.environ["TIMEBACK_CLIENT_SECRET"],
}, headers={"Content-Type": "application/x-www-form-urlencoded"})
token = resp.json()["access_token"]
```

**Key endpoints**:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/assessment-items` | Create item (JSON or XML) |
| PUT | `/assessment-items/{id}` | Update item (full replace) |
| GET | `/assessment-items/{id}` | Fetch item (`rawXml` field) |
| POST | `/assessment-tests` | Create test |
| POST/PUT | `/stimuli` or `/stimuli/{id}` | Create/update stimulus |
| POST | `/ims/oneroster/rostering/v1p2/courses` | Create course |
| POST | `/ims/oneroster/rostering/v1p2/courses/components` | Create component |
| POST | `/ims/oneroster/resources/v1p2/resources/` | Create resource (trailing slash!) |
| POST | `/ims/oneroster/rostering/v1p2/courses/component-resources` | Link component to resource |

**HTTP 409** = already exists = treat as success (idempotent).

**Retry**: 3 attempts, backoff [5, 15, 30]s, retry on [429, 500, 502, 503, 504].

**List/Search endpoints** (verified 2026-04-02):
- `GET /assessment-items` — returns paginated object `{total: N, data: [...]}`, NOT a raw array. Supports `limit`, `page`, `type` params. Warning: `type` filter can timeout on large datasets.
- `GET /stimuli` — same paginated format. Supports `limit`, `page`, `sort`, `order`.
- `GET /assessment-tests` — same paginated format.
