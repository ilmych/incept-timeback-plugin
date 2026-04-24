# Read OneRoster (Rostering + Gradebook)

**Base:** `https://api.alpha-1edtech.ai` · **Auth:** see `auth-cognito.md` · **Verified 2026-04-23**

OneRoster is the IMS-standard roster/gradebook API. The Timeback platform exposes it at `/ims/oneroster/rostering/v1p2/...` and `/ims/oneroster/gradebook/v1p2/...`. Everything here is read-only (GET).

## Endpoints Covered

| Purpose | Method | Path |
|---|---|---|
| List academic sessions (terms, calendar) | GET | `/ims/oneroster/rostering/v1p2/academicSessions/` |
| List a student's classes (enrollments) | GET | `/ims/oneroster/rostering/v1p2/students/{sourcedId}/classes` |
| List assessment results for a student | GET | `/ims/oneroster/gradebook/v1p2/assessmentResults/` (with filter) |
| Get a single assessment line item | GET | `/ims/oneroster/gradebook/v1p2/assessmentLineItems/{sourcedId}` |

Note the **trailing slashes** on the collection endpoints — omitting them returns 404 (same gotcha as the resource POST endpoint in `common-errors.md`).

## 1. Academic Sessions

Returns terms, grading periods, and the full school calendar. Use to determine whether an enrollment is currently active (a class tied to a term that has already ended should be filtered out).

```python
r = requests.get(
    f"{BASE_URL}/ims/oneroster/rostering/v1p2/academicSessions/",
    headers={"Authorization": f"Bearer {token}"},
    params={"limit": 200, "offset": 0},
    timeout=30,
)
sessions = r.json()["academicSessions"]
```

Response shape (trimmed):

```json
{
  "academicSessions": [
    {
      "sourcedId": "ses-...",
      "status": "active",
      "title": "Fall 2025",
      "type": "term",
      "startDate": "2025-08-13",
      "endDate":   "2025-12-19",
      "schoolYear": "2026"
    }
  ],
  "totalCount": 47
}
```

### Filtering to "currently active"

```python
from datetime import date
today = date.today()

def is_term_current(session: dict) -> bool:
    if session.get("status") != "active":
        return False
    sd = date.fromisoformat(session["startDate"][:10]) if session.get("startDate") else None
    ed = date.fromisoformat(session["endDate"][:10])   if session.get("endDate")   else None
    if sd and today < sd: return False
    if ed and today > ed: return False
    return True
```

## 2. Student Classes (Enrollments)

```python
r = requests.get(
    f"{BASE_URL}/ims/oneroster/rostering/v1p2/students/{sourced_id}/classes",
    headers={"Authorization": f"Bearer {token}"},
    params={"limit": 500},
    timeout=30,
)
classes = r.json().get("classes", [])
```

Each class contains a `terms` array linking to `academicSessions.sourcedId`. Cross-reference against the sessions pull to filter to currently-active enrollments (a student's `/classes` list returns both past AND current by default).

**Gotcha (verified 2026-04-23):** the endpoint returns completed / withdrawn enrollments alongside active ones with no `status` distinction on the class itself — only the linked term's date range tells you. The enrollment record itself may say `status: "active"` even when its term ended 6 months ago.

## 3. Assessment Results

This is the "every test this student has taken" endpoint. Filter syntax here is non-obvious:

```python
r = requests.get(
    f"{BASE_URL}/ims/oneroster/gradebook/v1p2/assessmentResults/",
    headers={"Authorization": f"Bearer {token}"},
    params={
        "filter": f"student.sourcedId='{sourced_id}'",   # NOT student='...'
        "limit": 1000,
        "offset": 0,
    },
    timeout=60,
)
results = r.json().get("assessmentResults", [])
```

### Pagination

Results often exceed the page limit (single students can have 500+ results). Loop until the running offset meets `totalCount`:

```python
all_results, offset = [], 0
while True:
    r = requests.get(..., params={..., "limit": 1000, "offset": offset}, timeout=60)
    batch = r.json().get("assessmentResults", [])
    all_results.extend(batch)
    total = r.json().get("totalCount", 0)
    offset += len(batch)
    if offset >= total or not batch:
        break
```

### Response shape (trimmed)

```json
{
  "assessmentResults": [
    {
      "sourcedId": "ar-...",
      "status": "active",
      "score": 0.75,
      "scoreStatus": "fully graded",
      "scoreDate": "2026-04-18T14:22:00Z",
      "assessmentLineItem": { "sourcedId": "ali-..." },
      "student": { "sourcedId": "stu-..." },
      "metadata": { "totalQuestions": 20, "correctAnswers": 15 }
    }
  ],
  "totalCount": 512
}
```

**`assessmentLineItem.sourcedId` is a reference, not a payload.** To get the test name/subject/grade-level, call endpoint 4 below.

## 4. Assessment Line Item (single)

```python
r = requests.get(
    f"{BASE_URL}/ims/oneroster/gradebook/v1p2/assessmentLineItems/{ali_sourced_id}",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
line_item = r.json().get("assessmentLineItem", {})
title   = line_item.get("title")
subject = line_item.get("metadata", {}).get("subject")
```

Cache these — they change rarely, but every result references one. For a 40-student roster you typically see ~800 unique line items.

## Common Failures

| Symptom | Cause | Fix |
|---|---|---|
| 404 on `/academicSessions` | Missing trailing slash | Path must end with `/` |
| Results come back empty despite known attempts | Filter syntax was `student='...'` | Must be `student.sourcedId='...'` — dotted path |
| Partial pagination silently accepted as "done" | No `totalCount` check | Loop until `offset >= totalCount`, not until the page is short — the API will occasionally return a short page mid-dataset |
| All classes returned, not just active ones | `/students/{sid}/classes` includes past enrollments | Cross-reference `class.terms[].sourcedId` against active academic sessions |
| Slow bulk pulls (>5 min for 40 students) | Serial per-student requests | Use `httpx.AsyncClient` + `asyncio.Semaphore(10)` — 10 is the observed safe concurrency ceiling |
| 429 bursts mid-pull | Concurrency above 10 | Drop semaphore to 10; add the retry pattern from `auth-cognito.md` |

## Full Example

See `scripts/read-examples/pull_student_weekly.py` for a working end-to-end pull that combines all four endpoints.
