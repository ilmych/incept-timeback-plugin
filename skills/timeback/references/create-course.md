# Create Course Structure

Covers the full hierarchy: Course > Components (units/lessons) > Resources > Component-Resource links.

## Course Payload

```python
{
    "course": {
        "sourcedId": course_id,
        "status": "active",           # REQUIRED. Must be lowercase "active" (not "Active")
        "title": title,               # REQUIRED (can be empty string, but don't)
        "courseCode": course_id,       # Optional
        "grades": ["10", "11", "12"], # Optional. Strings recommended; integers also accepted
        "subjects": ["Science"],       # Optional. OneRoster enum: Reading, Language, Vocabulary, Social Studies, Writing, Science, FastMath, Math, None, Other
        "subjectCodes": [],            # Optional
        "org": {"sourcedId": "346488d3-efb9-4f56-95ea-f4a441de2370"},  # REQUIRED. Must be valid org ID (invalid = 404)
        "metadata": {                  # Optional (API auto-adds AlphaLearn key)
            "publishStatus": "testing", # Any string accepted (testing/published/draft/custom)
            "goals": {"dailyXp": 25, "dailyLessons": 1, "dailyAccuracy": 80, "dailyActiveMinutes": 25, "dailyMasteredUnits": 2},
            "quiz": {"value": 0, "multipliers": [{"end": 79, "start": 0, "xpMultiplier": 0}, {"end": 99, "start": 80, "xpMultiplier": 1}, {"end": 100, "start": 100, "xpMultiplier": 1.25}], "attemptMultipliers": [{"attempt": 1, "xpMultiplier": 1}]},
        },
    }
}
```

### Required Fields (empirically verified 2026-04-02)
- `sourcedId` — can be omitted (API auto-generates), but always provide for idempotency
- `status` — REQUIRED, must be lowercase `"active"` or `"tobedeleted"`
- `title` — REQUIRED (empty string accepted but not recommended)
- `org.sourcedId` — REQUIRED, must be valid org ID (invalid returns 404, not 422)

### Optional Fields
- `courseCode`, `grades`, `subjects`, `subjectCodes`, `metadata` — all optional
- `grades` — strings recommended but integers also work (earlier 400 error was from incomplete payloads, not integer type)
- `metadata` — API auto-injects `AlphaLearn: {DailyXPGoal: 25}` and `goals` defaults even if omitted

### Behavioral Notes
- PUT returns **201** (not 200) — non-standard REST but correct for this API
- PUT is partial-merge for metadata (custom fields survive) but see Critical Rule 3 in SKILL.md
- DELETE returns 204, but GET after DELETE returns 200 with `status: "tobedeleted"` (soft delete)
- Cannot re-create with same sourcedId after deletion — returns 404 with "already exists" message
- Wrong org ID returns 404 (not 422) with generic error
- Special chars (Unicode, HTML entities, emoji) in title are preserved as-is
- 500-char titles accepted; 300-char sourcedIds accepted

## Component Payload

```python
{
    "courseComponent": {
        "sourcedId": component_id,
        "status": "active",
        "title": title,
        "description": description,
        "sortOrder": sort_order,  # integer >= 1
        "course": {"sourcedId": course_id},
        "parent": {"sourcedId": parent_id},           # null for top-level units
        "courseComponent": {"sourcedId": parent_id},   # null for top-level units
        "metadata": {}
    }
}
```

### Critical Rules (empirically verified 2026-04-02)
- Setting `"parent"` automatically populates `"courseComponent"` on the server side. Setting only `"courseComponent"` does NOT set `"parent"`. Best practice: always set BOTH.
- `sortOrder` accepts any integer including 0 and negative values. API does NOT enforce >= 1. However, use >= 1 in practice for predictable UI ordering.
- `sortOrder` is optional — components can be created without it (but ordering becomes unpredictable).
- Duplicate `sortOrder` values within the same parent are accepted (no uniqueness enforcement).
- **Nesting depth**: API accepts 5+ levels of nesting (verified: unit > topic > subtopic > sub-sub > sub-sub-sub). However, UI rendering beyond 2 levels is untested — stick to 2 levels (unit > topic) for production.
- For top-level units: set both `parent` and `courseComponent` to `null` (not omitted).
- `status` is REQUIRED for components (422 without it).
- `course` reference is REQUIRED (422 without it).
- `title` can be empty string (accepted but not recommended).
- Deleting a parent does NOT cascade-delete children — children become orphaned. Always delete children first.
- Component metadata supports nested objects and custom fields.

## Resource Payload

```python
{
    "resource": {
        "sourcedId": resource_id,
        "status": "active",
        "title": title,
        "importance": "primary",
        "vendorResourceId": test_or_stimulus_id,
        "vendorId": "alpha-incept",
        "applicationId": "incept",
        "url": f"{QTI_BASE}/assessment-tests/{test_id}",  # for QTI resources
        "metadata": {
            "lessonType": lesson_type,  # must match component-resource metadata
        }
    }
}
```

### Critical Rules (empirically verified 2026-04-02)
- Resources endpoint has **trailing slash**: `/ims/oneroster/resources/v1p2/resources/` — without trailing slash returns 422
- **WARNING (2026-04-02)**: Resources API returns HTTP 500 when `lessonType` is included in metadata. This appears to be a server-side bug. Resources without lessonType in metadata create successfully. Workaround: create resource without lessonType, or retry if the issue is intermittent.
- `lessonType` should match in BOTH resource metadata AND component-resource metadata (when working).
- Valid lessonTypes: `quiz`, `exercise`, `article`, `alpha-read-article`, `powerpath-100`, `unit-test`
- `vendorId`: `"alpha-incept"`, `applicationId`: `"incept"`
- Required fields: `sourcedId`, `status`, plus at least `vendorResourceId`+`vendorId`+`applicationId` (minimal with just sourcedId+status returns 422)
- `status` is NOT required for resources (works without it)
- `importance` valid values: `"primary"`, `"secondary"` (others return 422)
- `metadata`, `url`, `importance` are optional
- DELETE returns 404 for resources (not 204 like courses/components) — may need GET verification

## Component-Resource Link

```python
{
    "componentResource": {
        "sourcedId": link_id,
        "status": "active",
        "title": title,
        "sortOrder": sort_order,
        "resource": {"sourcedId": resource_id},
        "courseComponent": {"sourcedId": component_id},
        "metadata": {
            "lessonType": lesson_type,  # MUST match resource's lessonType
        }
    }
}
```

### Critical Rules
- Links a resource to a component at a specific sort position.
- `sortOrder` convention: article(1) > practice(2) > review(3) > quiz(4) > mastery(5)
- Never create ComponentResource as sibling of CourseComponent -- it won't show in recommendations.

## Assessment Bank Pattern (for quiz variants)

Create individual sub-resources for each variant, then a parent bank resource:

```python
bank_resource["metadata"]["resources"] = [sub_resource_id_1, sub_resource_id_2, ...]
```

Link ONLY the bank to the component. Individual sub-resources should NOT be linked directly.

## Component-Resource Link Notes (empirically verified 2026-04-02)

- `lessonType` in link metadata works (unlike resource metadata which triggers 500s)
- Custom metadata fields are stored and returned (nested objects work)
- `sortOrder` is optional; duplicate values allowed
- `status` is REQUIRED (422 without it)
- `title` appears required in combination with sortOrder (minimal without title returns 422)
- Links to non-existent resources return 500 (not 404)
- Links to non-existent components return 404
- DELETE returns 204 but GET still returns with `status: "tobedeleted"` (soft delete)
- Duplicate sourcedId returns 500 (not 409) — different from courses which return 404

## Deletion / Replacement (empirically verified 2026-04-02)

Recommended: delete in reverse order for clean state:
1. Component-Resource links
2. Resources
3. Components (children first, then parents)
4. Course

However, the API does NOT enforce deletion order:
- Deleting a course does NOT cascade to components, resources, or links (they become orphaned)
- Deleting a parent component does NOT cascade to children
- Deleting a resource does NOT cascade to its links
- All entities can be deleted independently

**The `tobedeleted` PUT step is OPTIONAL.** Direct DELETE works without it.

DELETE behavior:
- Returns 204 on success
- Entities are soft-deleted: GET after DELETE returns 200 with `status: "tobedeleted"`
- Cannot re-create with the same sourcedId after deletion (returns 404 with "already exists")
- Double DELETE returns 204 (idempotent)
