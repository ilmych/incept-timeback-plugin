# Read PowerPath (Placement + Subject Progress)

**Base:** `https://api.alpha-1edtech.ai` · **Auth:** see `auth-cognito.md` · **Verified 2026-04-23**

PowerPath handles placement (MAP RIT / level) and per-course progress (XP earned out of attainable, lessons completed, enrollment flags). These are the "how far through each course is this student" and "what level should they be placed at" numbers.

## Endpoints Covered

| Purpose | Method | Path |
|---|---|---|
| Placement (MAP RIT score, placement level) | GET | `/powerpath/placement/{studentId}` |
| Per-course subject progress | GET | `/powerpath/placement/getSubjectProgress?student={id}&subject={s}` |

## 1. Placement

```python
r = requests.get(
    f"{BASE_URL}/powerpath/placement/{sourced_id}",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
placement = r.json()
```

### Response shape (trimmed)

```json
{
  "studentId": "stu-...",
  "placements": [
    {
      "subject": "math",
      "ritScore": 218,
      "placementLevel": 5.2,
      "lastAssessedAt": "2026-04-15T10:30:00Z"
    }
  ]
}
```

Drives "which grade level should this student start at" for each subject.

## 2. Subject Progress

The core "how far along in every course" endpoint. One call = one student × one subject × every course in that subject's catalog.

```python
r = requests.get(
    f"{BASE_URL}/powerpath/placement/getSubjectProgress",
    headers={"Authorization": f"Bearer {token}"},
    params={
        "student": sourced_id,    # NOTE: param is "student" (not "studentId")
        "subject": "math",        # lowercase
    },
    timeout=45,
)
progress = r.json().get("progress", [])
```

### Params

- `student` — student sourcedId. **Different param name than EduBridge** (which uses `studentId`). Getting this wrong returns an empty `progress` array, not an error — silent failure.
- `subject` — lowercase string. Valid: `math`, `reading`, `language`, `science`, `writing`, `vocabulary`, `social studies`.

### Response shape (trimmed)

```json
{
  "studentId": "stu-...",
  "subject": "math",
  "progress": [
    {
      "courseId": "crs-...",
      "courseName": "Math G5",
      "totalAttainableXp": 48000,
      "totalXpEarned": 12400,
      "completedLessons": 18,
      "totalLessons": 72,
      "inEnrolled": true,
      "hasUsedTestOut": false,
      "completionPercent": 25.8
    }
  ]
}
```

### Filtering to meaningful courses (important)

**The catalog contains ~2000 courses per subject.** Most are test/demo/deprecated and return zero XP for every student. Filter down to the ones that matter:

```python
meaningful = [
    p for p in progress
    if p.get("inEnrolled") or (p.get("totalXpEarned") or 0) > 0
]
```

This reduces a 2000-item response to typically 3–10 courses per student per subject. Anything not currently enrolled AND with zero earned XP is noise.

### Verified behavior: zero-XP returns for non-enrolled courses

If a student has never touched a course, `totalXpEarned == 0` and `completedLessons == 0` — both fields are present, not null. Don't treat their presence as signal. The filter above is the right read.

### `inEnrolled` vs OneRoster enrollment

`inEnrolled` here is PowerPath's view, not OneRoster's. Occasionally they drift: OneRoster shows a student enrolled in a class tied to a course PowerPath says they're not `inEnrolled` in (or vice versa). Treat PowerPath `inEnrolled` as authoritative for "is the student actively working in this course."

## Bulk Pull Pattern

7 subjects × 40 students = 280 calls. Parallelize per student, serialize across students (to stay under 10 concurrent):

```python
SUBJECTS = ["math", "reading", "language", "science", "writing", "vocabulary", "social studies"]
sem = asyncio.Semaphore(10)

async def pull_one_student(client, cache, sid):
    tasks = [get_subject_progress(client, cache, sem, sid, s) for s in SUBJECTS]
    return await asyncio.gather(*tasks)
```

40 students completes in ~2 minutes end-to-end.

## Common Failures

| Symptom | Cause | Fix |
|---|---|---|
| `progress` array is empty despite known enrollment | Query param was `studentId=` instead of `student=` | Param name is `student` for this endpoint only — PowerPath and EduBridge disagree |
| 404 on placement | Student has no placement record yet | Not an error for your code; treat as "no placement data" and continue |
| 2000 courses returned per call | No filter applied | Apply the `inEnrolled or totalXpEarned > 0` filter shown above |
| `totalXpEarned: 0` for a course you expected data on | Student is not (and has never been) enrolled in that course | Expected behavior — filter drops it |
| `hasUsedTestOut: true` on a 0-XP course | Student tested out without completing lessons | Expected — `hasUsedTestOut` is the "skipped via placement test" flag, orthogonal to XP |
| Progress numbers disagree with EduBridge weekly facts | Different aggregation windows: PowerPath is lifetime, EduBridge weekly facts are windowed | Use PowerPath for "current state," EduBridge for "what happened this week" — they are not interchangeable |
| 429 when pulling all subjects for all students at once | Over the concurrency ceiling | Cap at `asyncio.Semaphore(10)` |
