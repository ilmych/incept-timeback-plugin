---
name: timeback
description: >
  Timeback/QTI platform reference for creating, updating, and publishing educational content.
  MUST invoke when: (1) writing code that calls Timeback API endpoints (/assessment-items,
  /assessment-tests, /stimuli, /courses, /components, /resources), (2) generating QTI XML,
  (3) writing HTML that will be embedded in QTI items or stimuli, (4) uploading content to S3
  for Timeback, (5) building course push pipelines, (6) creating PCI interactive items,
  (7) debugging rendering failures in Timeback student UI, (8) working with MathML or chemical
  formulas in QTI. Covers all gotchas discovered across 3 AP course builds and 60+ fix scripts.
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
- **NEVER reference local filesystem paths in QTI content.** Every `<img src="...">`, `<source src="...">`, video/audio URL, or embedded asset MUST point to an `https://` URL (typically `https://ai-first-incept-media.s3.amazonaws.com/...`). If an image/asset exists only on disk (`/Users/...`, `/Volumes/...`, relative paths like `images/foo.png`), upload to S3 FIRST via `references/s3-uploads.md`, THEN embed the S3 URL. Local paths render as broken thumbnails or 404s in the student UI. This check applies to stimuli, items, feedback, rubric blocks — anywhere HTML is embedded.
- **`<table>` inside `<p>` is the #1 rendering bug.** Split: `<p>text</p><table>...</table><p>more</p>`
- Platform strips `<style>` blocks — ALL CSS must be inline on elements
- Forbidden: `<center>`, `<font>`, nested `<p>`, `<p>` in modalFeedback
- HTML entities valid in HTML but NOT XML: use Unicode instead (`&mdash;` → `—`, `&rarr;` → `→`, `&Delta;` → `Δ`)
- Markdown pipe tables must be converted to `<table>` before push
- Always validate XML with `ET.fromstring()` before pushing

## CRITICAL RULE 3: Updates Use PUT — POST Creates or 409s

For existing items: use PUT, not POST. POSTing to `/assessment-items` with an ID that already exists returns `409 Conflict` and the update never lands — but a naive caller may log "200 OK or 409 for already-existing" as success and not realize the update silently failed.

PUT replaces the ENTIRE item. Omit `stimulus` → link removed. Omit `metadata` → cleared.

**Update pattern (items)**: GET item → extract `rawXml` → modify specific section → PUT back complete XML with `{"format": "xml", "xml": modified_xml, "metadata": {...}}`

**Update pattern (stimuli) — DIFFERENT SHAPE**: Stimulus PUT does **NOT** accept `{"format": "xml", "xml": ...}` — that shape is items-only and will return 500 (Mongo ObjectId lookup fails with `DocumentNotFoundError ... on model QTIStimulus`). Stimulus PUT expects:
```python
PUT /stimuli/{id}
{
    "identifier": "<same id>",
    "title": "<title from GET>",
    "content": "<full HTML body — inner of <qti-stimulus-body>, not full rawXml>",
    "metadata": {...},  # preserve from GET
}
```
The `content` field is HTML (XHTML-sanitized), not XML. If stimulus PUT returns 500 with "No document found for query... on model QTIStimulus", the fix is the HTML `content` shape above — NOT DELETE escalation. (Verified 2026-04-23 after a near-miss on a prod stimulus.)

Never reconstruct XML from scratch — you'll lose rubrics, response processing, grader URLs, feedback blocks.

**After any PUT, verify round-trip**: GET the item back and confirm the field you changed is reflected. HTTP 200 on PUT does NOT guarantee the change landed — the API can 200 while silently dropping fields or writing to a different layer than the one the renderer reads. If PUTs return 200 but content visibly didn't change, the escalation (not the default) is DELETE+POST — used in `ap-test-scrapper` after observing this failure mode in production.

**DELETE+POST is FORBIDDEN on prod stimuli/items without explicit user confirmation.** DELETE opens a data-loss window: if the subsequent POST fails (409, 500, auth expiry, network blip), the entity is gone from prod and students see 404s. When PUT fails with 4xx/5xx on a prod entity: (1) first try the correct payload shape (HTML `content` for stimuli, not XML), (2) if still failing, STOP and surface the error to the user — do NOT auto-escalate to DELETE. The only exception: dev/test environments explicitly isolated from prod. "Escalation" in the skill means "user-approved last resort," not "automatic next step." (Added 2026-04-23 after Claude was about to DELETE a live stimulus.)

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
- [ ] `lessonType` set in BOTH resource metadata AND component-resource link metadata?
- [ ] **For quiz/test resources: URL in `metadata.url` (not top-level)?** Top-level `url` field is silently dropped by the OneRoster API. `powerpath-100` resources don't need this — the platform constructs their URL from `vendorResourceId`. (verified 2026-04-12)
- [ ] Parent components have BOTH `parent` AND `courseComponent` fields set? Both must point to the same parent id. Setting only one may work in the API but the admin panel may not render the hierarchy correctly.
- [ ] **3-level hierarchy (unit > section > lesson)**: if components were originally created without a parent and later re-parented via PUT, the admin panel tree view may show stale grouping due to caching. The API data will be correct (verify via individual GET). Syllabus endpoint reflects correct structure immediately. Admin panel cache clears on hard-refresh or within minutes. (verified 2026-04-12)
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
| Auth (Cognito OAuth2) | [references/auth-cognito.md](references/auth-cognito.md) | Token exchange, caching, retry/backoff for ANY read-side call |
| Read OneRoster | [references/read-oneroster.md](references/read-oneroster.md) | Pulling academic sessions, enrollments, assessmentResults, lineItems |
| Read EduBridge | [references/read-edubridge.md](references/read-edubridge.md) | Pulling weekly facts, daily activity, highestGradeMastered |
| Read PowerPath | [references/read-powerpath.md](references/read-powerpath.md) | Pulling placement, per-course subject progress |
| Read QTI | [references/read-qti.md](references/read-qti.md) | Extracting test metadata + questions (prompt/choices/answers/standards) |

See also `scripts/read-examples/pull_student_weekly.py` for a working end-to-end read pattern combining all four read-side APIs.

## API Quick Reference

**Base URLs**:
- QTI API: `https://qti.alpha-1edtech.ai/api`
- OneRoster API: `https://api.alpha-1edtech.ai`

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
