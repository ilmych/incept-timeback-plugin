# Read QTI (Test Content Extraction)

**Base:** `https://qti.alpha-1edtech.ai` · **Auth:** see `auth-cognito.md` · **Verified 2026-04-23**

The QTI API exposes test metadata and every question (prompt, choices, correct answer, standards) for any assessment. Same Cognito token as the creation endpoints (confirmed 2026-04-23). Useful for auditing existing tests, extracting rubrics, or building tooling around bad-question analysis — without scraping a student-facing UI.

## Endpoints Covered

| Purpose | Method | Path |
|---|---|---|
| Get test metadata (title, subject, grade, question count) | GET | `/api/assessment-tests/{timebackId}` |
| Get every question in a test (prompts, choices, answers, standards) | GET | `/api/assessment-tests/{timebackId}/questions` |

These are the read counterparts to the write endpoints documented in `create-test.md`.

## 1. Test Metadata

```python
r = requests.get(
    f"{QTI_BASE}/api/assessment-tests/{timeback_id}",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
test = r.json()
```

### Response shape (trimmed)

```json
{
  "timeback_id": "_test-1527999c-...",
  "name": "Alpha Standardized Language G5.17",
  "subject": "Language",
  "grade": "5",
  "metadata": {
    "questionCount": 20,
    "createdAt": "2024-09-12T14:22:00Z",
    "sourceName": "Alpha Standardized",
    "questionTypes": ["choice", "extended-text"]
  }
}
```

## 2. Questions

```python
r = requests.get(
    f"{QTI_BASE}/api/assessment-tests/{timeback_id}/questions",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
questions = r.json().get("questions", [])
```

### Response shape (trimmed)

```json
{
  "questions": [
    {
      "question": {
        "identifier": "s4-...",
        "type": "choice",
        "rawXml": "<qti-assessment-item ...>...</qti-assessment-item>",
        "responseDeclarations": [
          { "identifier": "RESPONSE",
            "correctResponse": { "value": ["B"] } }
        ],
        "metadata": {
          "alignment": [
            {
              "curriculum": "CCSS",
              "domains": [
                { "name": "Reading: Literature",
                  "standards": ["RL.5.1", "RL.5.2"] }
              ]
            }
          ]
        }
      }
    }
  ]
}
```

The `rawXml` field contains the full item XML (same format as what you POST in `create-mcq.md`, `create-frq.md`, etc). The typed fields (`responseDeclarations`, `metadata`) are the API's parsed view — they can be empty even when the XML contains data (same gotcha as `feedbackInline` noted in `create-mcq.md`). **Treat `rawXml` as the source of truth.**

## Parsing rawXml

Regex works for simple structure (prompt + choices + correct answer):

```python
import re

def strip_xml(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()

def parse_question(q: dict, idx: int) -> dict:
    qdata = q.get("question", {})
    raw = qdata.get("rawXml", "")

    pm = re.search(r"<qti-prompt>(.*?)</qti-prompt>", raw, re.DOTALL)
    prompt = strip_xml(pm.group(1)) if pm else ""

    choices = []
    for m in re.finditer(
        r'<qti-simple-choice[^>]*identifier="([^"]+)"[^>]*>(.*?)</qti-simple-choice>',
        raw, re.DOTALL,
    ):
        choices.append({"id": m.group(1), "text": strip_xml(m.group(2))})

    correct_ids = []
    for rd in qdata.get("responseDeclarations", []):
        v = rd.get("correctResponse", {}).get("value") or []
        correct_ids.extend(v if isinstance(v, list) else [v])

    return {
        "q_num": idx,
        "identifier": qdata.get("identifier"),
        "type": qdata.get("type"),
        "prompt": prompt,
        "choices": choices,
        "correct_ids": correct_ids,
        "correct_text": next((c["text"] for c in choices if c["id"] in correct_ids), ""),
    }
```

For complex types (match, hotspot, PCI) regex is insufficient — use `xml.etree.ElementTree` with the QTI namespace.

## Resolving a Test Name to a `timebackId`

The QTI API keys on `timebackId` (e.g. `_test-1527999c-ef9a-...`), not on human names. Maintain a local inventory or pull the full test list first. For Alpha, the platform exposes an inventory endpoint (internal) that maps `{ name, subject, grade, timebackId }`.

## Bulk Extraction Pattern

For auditing an entire question bank:

```python
# 1. Get inventory (subject/grade → timebackId list)
# 2. For each test, call both endpoints in sequence
# 3. Save raw + parsed JSON + optional human-readable Markdown
for item in inventory:
    tbid = item["timebackId"]
    test = fetch_test(token, tbid)
    questions = fetch_questions(token, tbid)
    parsed = [parse_question(q, i+1) for i, q in enumerate(questions.get("questions", []))]
    save(item, test, questions, parsed)
```

Rate-limit to 1 request per ~100ms when pulling hundreds of tests (semaphore(10) is fine for a few dozen, but 1000+ tests benefits from a small per-call `time.sleep(0.1)`).

## Use Case: Bad-Question Audit

With per-student assessmentResults (OneRoster) + question text (QTI), you can identify which specific questions are failing most students:

1. Pull assessmentResults per student (see `read-oneroster.md`)
2. Correlate `assessmentLineItem.sourcedId` → test `timebackId` via line-item metadata
3. Pull questions for each test from QTI
4. Compute per-question fail rate: `1 - (n_correct / n_attempts)`
5. Flag questions with ≥70% fail rate across ≥5 students

This was the workflow that identified 12 bad-question tests at BTX in April 2026.

## Common Failures

| Symptom | Cause | Fix |
|---|---|---|
| 401 on QTI, 200 on main API | You used a different token | Same Cognito token works for both — use one `TokenCache` across both hosts |
| `questions` array empty for a known test | Test exists but has no items yet (scaffold) | Not an error; skip and log |
| `rawXml` has data but typed fields are empty | API doesn't reverse-parse complex QTI into typed fields | Parse `rawXml` directly; don't rely on typed fields (see `create-mcq.md` note about `feedbackInline`) |
| Regex matches fail on a question | Nested tags or namespaced element | Fall back to `xml.etree.ElementTree` with QTI namespace |
| Standards list empty on all questions | Older test predates the metadata schema | Not a bug — not all tests have `metadata.alignment` populated |
| Rate-limited during bulk pull | Firing 1000+ calls without throttle | Add `time.sleep(0.1)` between calls or keep semaphore at 10 |
