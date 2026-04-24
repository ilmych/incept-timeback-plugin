# Read EduBridge Analytics

**Base:** `https://api.alpha-1edtech.ai` · **Auth:** see `auth-cognito.md` · **Verified 2026-04-23**

EduBridge is Timeback's analytics layer. Three endpoints cover the student-level data that feeds most dashboards: weekly XP/mastery facts, daily activity breakdown, and the highest-grade-mastered snapshot.

## Endpoints Covered

| Purpose | Method | Path |
|---|---|---|
| Weekly XP + mastery facts (primary pipeline source of truth) | GET | `/edubridge/analytics/facts/weekly` |
| Daily activity (XP per day, per subject/app) | GET | `/edubridge/analytics/activity` |
| Highest grade mastered per subject (snapshot) | GET | `/edubridge/analytics/highestGradeMastered/{studentId}/{subject}` |

## 1. Weekly Facts

The authoritative weekly XP/mastery rollup. One call = one student × one week × all subjects.

```python
r = requests.get(
    f"{BASE_URL}/edubridge/analytics/facts/weekly",
    headers={"Authorization": f"Bearer {token}"},
    params={
        "studentId": sourced_id,
        "weekDate": "2026-04-19",            # ISO date; the Sunday of the week
        "timezone": "America/Chicago",       # required to align week boundaries
    },
    timeout=30,
)
```

### Params

- `studentId` — OneRoster `sourcedId` (NOT a display name)
- `weekDate` — any ISO date within the week; the API normalizes to the containing Sun→Sat window
- `timezone` — IANA tz string. Omit or pass wrong tz and weeks straddle boundaries; all BTX pulls use `America/Chicago` (verified 2026-04-23)

### Response shape (trimmed)

```json
{
  "studentId": "stu-...",
  "weekStart": "2026-04-13",
  "weekEnd":   "2026-04-19",
  "subjects": [
    {
      "subject": "Math",
      "xpEarned": 4250,
      "lessonsCompleted": 8,
      "masteryGained": 0.12,
      "minutesActive": 142
    }
  ],
  "total": { "xpEarned": 18420, "minutesActive": 612 }
}
```

### Bulk-pulling a year of weekly facts

For a 40-week academic year × N students, fire one call per (student, week). Async + semaphore(10) completes 40 students × 40 weeks (1,600 calls) in ~90 seconds.

```python
from datetime import date, timedelta

WEEKS = []
d = date(2025, 8, 10)                        # Sunday before first day of school
while d <= date(2026, 6, 5):
    WEEKS.append(d.isoformat())
    d += timedelta(days=7)

# Fan out in parallel per student
tasks = [fetch_weekly_facts(client, cache, sem, sid, w) for w in WEEKS]
```

## 2. Daily Activity

Per-day breakdown. One call covers a date range — prefer a single range call over per-day loops (1 call vs 300 per student).

```python
r = requests.get(
    f"{BASE_URL}/edubridge/analytics/activity",
    headers={"Authorization": f"Bearer {token}"},
    params={
        "studentId": sourced_id,
        "startDate": "2025-08-10T00:00:00Z",
        "endDate":   "2026-06-05T23:59:59Z",
        "timezone":  "America/Chicago",
    },
    timeout=90,       # wider window = slower response; give it 90s
)
```

### Response shape (trimmed)

```json
{
  "studentId": "stu-...",
  "days": [
    {
      "date": "2026-04-19",
      "totalXp": 4250,
      "minutesActive": 142,
      "bySubject": {
        "Math":    { "xp": 1800, "minutes": 54 },
        "Reading": { "xp": 2450, "minutes": 88 }
      },
      "byApp": {
        "IXL":          { "xp": 2100, "minutes": 60 },
        "Lexia":        { "xp": 1800, "minutes": 44 }
      }
    }
  ]
}
```

## 3. Highest Grade Mastered

Snapshot of the highest grade level a student has mastered per subject. Drives placement, promotion, and the "on/above/below grade" UI chips.

```python
r = requests.get(
    f"{BASE_URL}/edubridge/analytics/highestGradeMastered/{sourced_id}/{subject}",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
grades = r.json().get("grades", {})
```

### Path params

- `{sourced_id}` — student OneRoster ID
- `{subject}` — **lowercase** subject name. Valid: `math`, `reading`, `language`, `science`, `writing`, `vocabulary`, `social studies`. (Note: PowerPath uses the same lowercase convention — see `read-powerpath.md`.)

Spaces in the subject (e.g. `social studies`) are URL-encoded automatically by `requests`/`httpx`. No manual quoting needed.

### Response shape

```json
{
  "studentId": "stu-...",
  "subject": "math",
  "grades": {
    "ritGrade":         4.8,
    "edulasticGrade":   5.0,
    "placementGrade":   4.5,
    "testOutGrade":     5.0,
    "highestGradeOverall": 5.0
  }
}
```

Treat `highestGradeOverall` as the canonical "what grade is this student at" — it's the max across all signal sources.

## Common Failures

| Symptom | Cause | Fix |
|---|---|---|
| `weekStart` differs from the date you sent | `weekDate` lands mid-week, API normalized to the Sunday | Not a bug — always key results by `weekStart` from the response, not by the param you sent |
| Week spans two calendar dates unexpectedly | `timezone` param omitted | Always pass `timezone=America/Chicago` (or correct IANA tz for the campus) |
| `/activity` times out | Large date range + slow quarter | Bump timeout to 90s; do NOT split into per-day calls (that makes it slower and hits 429) |
| `highestGradeMastered` returns 404 | Subject spelled with capital letter | Use lowercase: `math`, not `Math` |
| `grades` object empty | Student has no data in that subject (never enrolled / never tested) | Treat `{}` as "no signal" not as an error |
| Mixed-case subject mismatch between endpoints | Weekly facts returns `"Math"`, PowerPath expects `"math"` | Normalize to lowercase at the caller boundary; see `read-powerpath.md` |
