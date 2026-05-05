# Admin Dashboard Read API (`alpha.timeback.com`)

This reference covers the **read-side** of the Timeback platform — the admin/teacher dashboard at `https://alpha.timeback.com` that surfaces student activity, goals, mastery, placements, and roster data. **Complementary to the QTI content-authoring API** (`qti.alpha-1edtech.ai`) covered in the rest of this skill.

When to load: building dashboards, extracting student data for analytics, automating coaching workflows, debugging "why does the UI show X but our API call returns Y", or pulling roster/activity to feed AI-coaching systems.

> Source: full network sweep + JS-bundle scan against the production dashboard. 141 server-function endpoints discovered, 35+ verified live with body shape + sample response. All examples below use placeholder IDs (`<UUID>`, `<email>`, `<class_sourcedId>`); substitute real values from your own session.

## Architecture in 30 seconds

| Layer | URL |
|---|---|
| Frontend | `https://alpha.timeback.com` (TanStack Start SPA) |
| Server functions | `https://alpha.timeback.com/_serverFn/<handler>?createServerFn` (POST `{data,context}`) |
| REST endpoints | `https://alpha.timeback.com/api/...` (e.g. `/api/parent/children`) |
| Underlying data | OneRoster v1p2 at `https://api.alpha-1edtech.ai/ims/oneroster/rostering/v1p2/` (CORS-blocked from page; usable server-side) |
| Assessments | `https://alphatest.alpha.school/assignment/<id>` (separate auth) |

**Auth**: Clerk session cookie (HttpOnly). No client-credentials/Cognito flow — that's the QTI side. For dashboard reads you must use a logged-in user's session.

**Routes that exist** (all 7 confirmed; everything else 404s):
```
/app
/app/learning-metrics
/app/xp-stats
/app/xp/manual
/app/teacher/tests
/app/placements
/app/goal-tracking
```

**Response envelope (POST)**: `{result: {...}, error: {"$undefined":0}, context: {}}` — `$undefined` is TanStack Start's serialization of JS `undefined`.

## CRITICAL GOTCHA — ID field name varies wildly across endpoints

Same student UUID is named differently per endpoint. There is no consistent convention. Use this table:

| Endpoint | ID field name |
|---|---|
| `getActivityMetrics`, `listSubjectGoals`, `getStudentSubjectGoalsBatch`, `getStudentProgressionBatch (studentIds[])`, `getStudentPlacementData`, `getStudentPlacementTestHistory`, `getStudentXPFromEdubridge`, `fetchCourseProgress` | `studentId` (UUID) |
| `getCurrentLevel`, `getAllPlacementTests`, `getManualXPEvents` | `student` (UUID, bare) |
| `getDailyXPEvents`, `getStudentFlowTime` | `userId` (UUID) + plain `date` |
| `course-progress.fetchUser` | `id` (UUID) |
| `getUserPendingMasteryAssessments`, `getUserCompletedMasteryAssessments`, `getUserEnrollmentsUnfiltered`, `getUserEnrollments`, `getTimeSaved`, `getUserMetrics` (+ `weekDate` + `timezone`), `getUserCourseRecommendations` | `onerosterUserId` (lowercase r) |
| `getUserStreak`, `getUserWeekStreak`, `getUserSessionXP`, `getUserYearXP`, `getUserLeagueMembership`, `getUserWeeklyXP` | `oneRosterUserId` (CamelCase R!) |
| `getStudentXPTransactions`, `getStudentXPFromEdubridge` | `studentEmail` + `date` |
| `getEnrollmentsForMultipleStudents`, `getAssignedTestsBatch`, `getEnrollmentFacts` | `studentSourcedIds[]` (batch) |
| `getEnrollmentAnalyticsBatch` | `enrollmentIds[]` |
| `getClassStudentsV2` | `classId` (string-shaped sourcedId) |
| `getTeacherClasses` / `getStudentsByTeacher` | `teacherId` / `teacherUserId` |

**Date format depends on field name:**
- `startDate` / `endDate` → ISO datetime: `2026-04-01T00:00:00.000Z` (must include time + Z; plain `YYYY-MM-DD` fails Zod)
- `date` / `weekDate` → plain `YYYY-MM-DD`

**Subject enum (8 subjects)**: `Reading | Language | Vocabulary | Social Studies | Writing | Science | FastMath | Math`

**Apps seen in data**: `Incept` (Math), `MobyMax` (multi), `Alpha Read` (Reading), `VocabLoco` (Vocabulary, course `primaryApp`), `AlphaTest` (assessment `toolProvider`).

## Verified endpoints by category

### A. Activity / XP (the dashboard's spine)

#### `getActivityMetrics` ⭐
```
POST /_serverFn/src_features_learning-metrics_actions_getActivityMetrics_ts--getActivityMetrics_createServerFn_handler?createServerFn
{"data":{"studentId":"<UUID>","startDate":"2026-04-01T00:00:00.000Z","endDate":"2026-04-30T23:59:59.999Z"},"context":{}}
```
Returns `facts[YYYY-MM-DD][Subject]` with `{activityMetrics:{xpEarned,totalQuestions,correctQuestions,masteredUnits}, timeSpentMetrics:{activeSeconds,inactiveSeconds,wasteSeconds}, apps:[]}`. Powers heatmaps and daily cards.

#### `getDailyXPEvents` ⭐
```
POST /_serverFn/src_features_learning-metrics_actions_getDailyXPEvents_ts--getDailyXPEvents_createServerFn_handler?createServerFn
{"data":{"userId":"<UUID>","date":"2026-04-30"},"context":{}}
```
Returns lesson-level XP events for a single day. Each event: `{id, xpChange, description, timestamp, courseId, courseName, lessonId, lessonName, subject, app, className, classId}`. Lesson IDs encode unit/skill structure: `unit_<id>:prereq_quiz:1:skl_<id>`.

#### `getStudentXPTransactions` ⭐
```
POST /_serverFn/src_features_learning-metrics_actions_getStudentXPTransactions_ts--getStudentXPTransactions_createServerFn_handler?createServerFn
{"data":{"studentEmail":"<email>","date":"2026-04-30"},"context":{}}
```
**Per-quiz-attempt** detail with timestamps + accuracy. Returns `transactions[]` each `{id, eventId, caliperXP, lessonId, courseId, subject, appName, activityName:"Quiz", courseName, eventTime, attemptNumber, generatedItems:[{type,value}], extensions:{incept_fail_out_lesson:false}, accuracy, isRetry, previousAttempt}`. Note: when the source app is **Incept**, `extensions.incept_fail_out_lesson` flags whether the student failed out — directly relevant to QTI authoring (lesson difficulty calibration).

#### `getUserMetrics`
```
POST /_serverFn/src_features_learning-metrics_actions_getUserMetrics_ts--getUserMetrics_createServerFn_handler?createServerFn
{"data":{"onerosterUserId":"<UUID>","weekDate":"2026-04-30","timezone":"America/Chicago"},"context":{}}
```
Week-grain comprehensive activity facts. Each fact tags `{userId, email, userGrade, userFamilyName, userGivenName, subject, app, courseId, courseName, campusId, campusName, enrollmentId, activityId, activityName, datetime}`.

#### `getStudentFlowTime`
```
POST /_serverFn/src_features_flow_actions_getStudentFlowTime_ts--getStudentFlowTime_createServerFn_handler?createServerFn
{"data":{"userId":"<UUID>","date":"2026-04-30"},"context":{}}
```
Returns `{minutesToday: int, minutesWeek: int}`.

#### `getManualXPEvents` ⭐
```
POST /_serverFn/src_features_manual-xp_actions_getManualXPEvents_ts--getManualXPEvents_createServerFn_handler?createServerFn
{"data":{"student":"<UUID>"},"context":{}}
```
Returns the **network-wide** manual XP ledger (the `student` param doesn't filter — admin sees all). Each event: `{id, student:"<email>", studentEmail, date, subject, xp:<signed int>, reason}`. Includes coaching attribution and behaviour deductions in the `reason` text field.

### B. XP totals / streaks

| Endpoint | Body | Returns |
|---|---|---|
| `getUserSessionXP` | `{oneRosterUserId}` | `{sessionXP: float}` |
| `getUserYearXP` | `{oneRosterUserId}` | `{yearXP: float}` |
| `getUserStreak` | `{oneRosterUserId}` | `{streak: int}` |
| `getUserWeekStreak` | `{oneRosterUserId}` | `{weekStreak: int}` |
| `getTimeSaved` | `{onerosterUserId}` | `{totalHoursSaved, totalDaysSaved, schoolDaysElapsed, calculation:{...}}` |

### C. Goals

#### `listSubjectGoals` ⭐
```
POST /_serverFn/src_features_goals_actions_goals-rest-api_ts--listSubjectGoals_createServerFn_handler?createServerFn
{"data":{"studentId":"<UUID>"},"context":{}}
```
Per-subject goal data. Each item:
```json
{
  "subject": "FastMath",
  "baseline": {"goalId","dailyTargetXP","defaultDailyTargetXP","startDate","updatedAt"},
  "goal": null,
  "execution": null,
  "computed": {
    "xp": null,
    "pace": {"requiredDailyXP","effectiveDailyXP","schoolDaysRemaining"},
    "projection": {
      "currentGrade": "<grade>",
      "daysToNextGrade": <int>,
      "gradeTimeline": [{"grade":"<next>","courseIds":[...],"status":"future","totalXP":<int>,"earnedXP":<int>,"remainingXP":<int>,"daysToComplete":<int>,"projectedDate":"<ISO>"}]
    }
  }
}
```
The `gradeTimeline.projectedDate` is the platform's pace-based projection of when the student will complete the next grade in this subject.

#### `getStudentSubjectGoalsBatch`
```
{"data":{"studentIds":["<UUID>",...]},"context":{}}
```
Returns `[{studentId, subjectGoals:{FastMath,Language,Math,Reading,Science,Vocabulary,Writing}, dailyTotal}]`.

#### `getPercentiles` ⭐ — **MAP Growth scores**
```
{"data":{"studentId":"<UUID>"},"context":{}}
```
Returns `data:[{subject, percentile, ritScore, assessmentDate, season}]` — NWEA RIT + percentile per subject.

### D. Assessments / mastery

#### `getUserPendingMasteryAssessments`
```
POST /_serverFn/src_features_assessment-results_actions_getUserPendingMasteryAssessments_ts--getUserPendingMasteryAssessments_createServerFn_handler?createServerFn
{"data":{"onerosterUserId":"<UUID>"},"context":{}}
```
Each result: `{sourcedId, status, metadata:{xp, origin:"progression", subject, testLink:"https://alphatest.alpha.school/assignment/<id>", testName, testType:"end of course", assignedAt, assignmentId, numericGrade, studentEmail, toolProvider:"AlphaTest"}, assessmentLineItem:{sourcedId}, student:{sourcedId}, score, scoreStatus:"not submitted", learningObjectiveSet:[]}`.

#### `getUserCompletedMasteryAssessments`
Same path, function-name swapped to `--getUserCompletedMasteryAssessments_createServerFn_handler`. Adds `metadata:{totalQuestions, correctQuestions, gapAnalysisReportId, assessmentType:"MANUAL", masteryTrackProcessed}, score:<float>, scorePercentile, scoreStatus:"fully graded", learningObjectiveSet:[{source, learningObjectiveResults:[{learningObjectiveId, score, textScore}]}]`.

⚠ `gapAnalysisReportId` is a UUID but `getGapAnalysisReport` is **not** in `alpha.timeback.com` bundles — likely served by `alphatest.alpha.school` (separate auth).

#### `getStudentPlacementTestHistory`
```
{"data":{"studentId":"<UUID>","subject":"Math"},"context":{}}
```

#### `getAssignedTestsBatch`
```
{"data":{"studentSourcedIds":["<UUID>",...]},"context":{}}
```

### E. Placements

| Endpoint | Body | Returns |
|---|---|---|
| `getStudentPlacementData` | `{studentId}` | `{<Subject>: {results:[{status:"SKIP"\|"NOT_STARTED"\|...,testId,title,subject,grade,source:"PLACEMENT"}]}}` per subject |
| `getCurrentLevel` | `{student, subject}` | `{gradeLevel, onboarded, availableTests}` |
| `getAllPlacementTests` | `{student, subject}` | `{placementTests:[{component_resources:{...}, resources:{...}}]}` |

Path prefix for all three: `/_serverFn/src_features_placements_versions_legacy_api_client_ts--<fn>_createServerFn_handler?createServerFn`. There's also a non-legacy `src_features_placements_api_client_ts` with `getNextPlacementTest` and `getSubjectProgress`.

### F. Roster / class

#### `getClassStudentsV2` ⭐
```
POST /_serverFn/src_features_teacher_actions_getClassStudentsV2_ts--getClassStudentsV2_createServerFn_handler?createServerFn
{"data":{"classId":"<class_sourcedId>"},"context":{}}
```
Field name is `classId` even though the value is the OneRoster sourcedId. Returns `enrollments[]` (teachers + students) with **goal targets per enrollment**:
```json
{
  "sourcedId":"enroll_<role>_<UUID>_<epochMs>",
  "metadata":{
    "goals":{"dailyXp":<int>,"dailyLessons":<int>,"dailyActiveMinutes":<int>,"dailyAccuracy":<int>,"dailyMasteredUnits":<int>},
    "AlphaLearn":{"DailyXPGoal":<int>}
  },
  "role":"student","beginDate","endDate",
  "user":{"href":"https://api.alpha-1edtech.ai/.../users/<UUID>","sourcedId","name"},
  "class":{"href",sourcedId},"school":{href,sourcedId,name},"course":{href,sourcedId,name}
}
```

#### `getEnrollmentsForMultipleStudents`
```
GET /_serverFn/src_features_teacher_actions_getEnrollmentsForMultipleStudents_ts--getEnrollmentsForMultipleStudents_createServerFn_handler?payload={"data":{"studentSourcedIds":[...]},"context":{}}&createServerFn
```

#### `getStudentProgressionBatch`
```
{"data":{"studentIds":["<UUID>",...]},"context":{}}
```
Returns `{[studentId]:{science:{id,status,timestamp_started,message}, writing:{...}, math:{...}, reading:{...}}}`. Statuses include `test_assignment_completed`, `course_assignment_completed`.

#### `getTeacherClasses`
```
{"data":{"teacherId":"<UUID>"},"context":{}}
```
Returns `{classes:[{sourcedId, title, classCode, school:{sourcedId,name}, classType:"homeroom", grades, subjects}]}`.

#### `getStudentsByTeacher`
```
POST /_serverFn/src_features_session-snapshot_actions_getStudentsByTeacher_ts--getStudentsByTeacher_createServerFn_handler?createServerFn
{"data":{"teacherUserId":"<UUID>"},"context":{}}
```
Returns rich student records with `{id, name, email, level, orgs, primaryOrg:{href,sourcedId,name}, hasSessionSnapshot}`.

#### `getCourses` / `getAcademicSessions`
Both take empty `{data:{}}`. Returns network-wide `courses[]` and `sessions[]` (terms).

### G. Profile / progression

| Endpoint | Body | Notes |
|---|---|---|
| `getUserProfile` (GET) | `{userId}` (URL-encoded payload) | Full OneRoster user with `metadata.dob/Campus/alphaLevel/onboarding{<Subject>}/progression{<subject>}` |
| `course-progress.fetchUser` | `{id}` (note: `id`, not `userId`) | Roles, primary org, parent links — exposes OneRoster API URL pattern |
| `getOneRosterUser` (auth) | `{userId}` | OneRoster user via auth feature |
| `getLinkedParents` | shape unverified | |

### H. Course / curriculum structure (overlap with QTI side)

#### `fetchCourseSyllabus`
```
{"data":{"courseId":"<UUID>"},"context":{}}
```
Returns `syllabus.course:{sourcedId, metadata:{goals, metrics:{totalXp,totalGrades,totalLessons}, AlphaLearn, courseType:"base", primaryApp, contactEmail, publishStatus}, title, grades, subjects, subjectCodes, org, resources}`. **Maps directly to QTI-side `/courses/{id}` via `sourcedId`.** Useful for read-back verification after creating courses with the QTI API.

#### `getCourseComponents`
```
{"data":{"courseId":"<UUID>"},"context":{}}
```
Returns `courseComponents:[{sourcedId, course:{sourcedId}, courseComponent:{sourcedId}, parent:{sourcedId}, title, sortOrder, prerequisites, prerequisiteCriteria, unlockDate}]`. **Same shape the QTI-side `/courses/components` POST consumes for creating** — useful for round-trip validation.

#### `getLessonDetails` / `getLessonType`
```
{"data":{"lessonId":"<id>"},"context":{}}
```
`getLessonDetails` returns `{id, title, lessonType:"quiz", enableTTS, timeLimitSeconds, lessonStyle, desmosCalculator, courseId, courseName, qtiRenderer, maxAttempts}` — the runtime config the student app uses to render a QTI lesson. Useful for verifying QTI items render with the expected lesson-level settings. `getLessonType` returns just the type string.

#### `fetchCourseProgress`
```
{"data":{"studentId":"<UUID>","courseId":"<UUID>"},"context":{}}
```
Returns per-student per-course `{lineItems:[]}` — completion line items (OneRoster gradebook).

### I. Auth / impersonation

| Endpoint | Method | Notes |
|---|---|---|
| `refreshSession` | POST | Auto-fired periodically |
| `getImpersonatedUserId` / `getImpersonatedUserRole` | GET | Current impersonated context |
| `setImpersonatedUserId` | POST | **WRITE** — switches the dashboard's view |

### J. REST endpoints (non-serverFn)

- `GET /api/parent/children` → `{success:true, data:[{sourcedId, givenName, familyName, email, grade, school:{sourcedId,name}}]}`

## Recipes

### "Did the student hit goal today?"
1. `listSubjectGoals(studentId)` → `baseline.dailyTargetXP` per subject
2. `getActivityMetrics(studentId, today, today)` → `facts[today][subject].activityMetrics.xpEarned`
3. Compare. (For class-wide: single `getStudentSubjectGoalsBatch(studentIds[])` call.)

### "Drill into one student's day"
1. `getDailyXPEvents(userId, date)` → lesson-level XP events with course/lesson IDs
2. `getStudentXPTransactions(studentEmail, date)` → per-attempt question counts + accuracy
3. Join on `eventTime`/`timestamp` for play-by-play

### "Curriculum progress through course"
1. `getUserEnrollmentsUnfiltered(onerosterUserId)` → list courses
2. `fetchCourseSyllabus(courseId)` → scope and sequence
3. `fetchCourseProgress(studentId, courseId)` → completion lineItems
4. (deeper) `getCourseComponents(courseId)` for unit/lesson tree

### "MAP scores + projected next grade"
1. `getPercentiles(studentId)` → RIT + percentile per subject
2. `listSubjectGoals(studentId)` → `computed.projection.gradeTimeline` (next grade + projectedDate)

### "Coaching attribution from manual XP log"
1. `getManualXPEvents(student)` → all manual XP events network-wide (the `student` arg doesn't actually filter)
2. Filter client-side by `studentEmail`
3. Surface `reason` text as coaching log entries

### "Multi-campus rollout"
1. `getAllOrgsMap()` → every school
2. `getSchoolClasses(schoolSourcedId)` per school
3. `getClassStudentsV2(classId)` per class
4. Per-student pulls in parallel (5-10 concurrent per school is safe)

### "Round-trip QTI authoring → dashboard verification"
After pushing a course/component/item via the QTI API:
1. `fetchCourseSyllabus(courseId)` → confirm `metadata.publishStatus`, `goals`, `subjects`, `primaryApp` match what was POSTed
2. `getCourseComponents(courseId)` → verify the unit/lesson tree's `sortOrder` and `prerequisites` survived the push
3. `getLessonDetails(lessonId)` → check `lessonType`, `timeLimitSeconds`, `maxAttempts` reflect the QTI item's metadata

## Auth strategy

The Clerk session cookie is HttpOnly. Two viable paths:

**Cookie copy (headless):** sign into alpha.timeback.com → DevTools Network → copy the `Cookie` header → save to a file → pass to a Python script. Cookies expire in hours/days, so refresh daily.

**Browser relay (zero token wrangling):** keep a long-lived Chrome window open and run all fetches inside the page context. Trade-off: needs Chrome running.

Long term, prefer migrating to the OneRoster bearer flow (`api.alpha-1edtech.ai`) used by the QTI side of the platform — avoids Clerk session expiry entirely.

## Throughput

The server tolerates significant fan-out. /app/xp-stats fires 30+ parallel `getActivityMetrics` calls without 429s. For automated extraction, throttle to **5–10 in-flight per server** to stay safe. No 429/Retry-After observed during the discovery sweep.

For 13 students × 30-day window across all endpoints: ~1000 calls, ~50 MB raw JSON.

## Schema-validation feedback loop (Zod)

Every dashboard endpoint is Zod-validated. On a wrong-shape request you get a 500 with the **expected field name + type** in the error body — use that to discover correct shapes:
```
{"$error":{"message":"[\n  {\n    \"code\": \"invalid_type\",\n    \"expected\": \"string\",\n    \"received\": \"undefined\",\n    \"path\": [\"studentId\"],\n    \"message\": \"Required\"\n  }\n]\""}}
```
The Zod errors also reveal enum constraints — e.g. the 8-subject enum was confirmed via a `getAllPlacementTests` Zod error.

## Known gaps

| Gap | Why we don't have it | How to close |
|---|---|---|
| Gap-analysis report content | `gapAnalysisReportId` returned, no `getGapAnalysisReport` serverFn in bundles | Open a test link at `alphatest.alpha.school` and capture the network call |
| Per-question text + student answers | Counts only via `generatedItems`. QTI item bodies likely via `fetchQti` (course-progress) | Probe with `{lessonId, attemptId}`; or capture during a quiz |
| MAP detail beyond percentile/RIT | Sub-strand scores not proxied | NWEA admin (separate auth) |
| Standards/TEKS mapping per question | `learningObjectiveId` field exists but empty in samples | Test with a more advanced student or different test type |
| Attendance | No dedicated endpoint | Derive proxy: `activeSeconds > 0` from `getActivityMetrics`; or pull from school SIS |
| Lead-Guide multi-class roster | `fetchLeadGuideRoster` exists, returned no data with empty body | Login as actual lead guide and capture |
| Live class-mode session activity | `flow.allocateRecordingChannel` etc. — likely real-time only | Watch network during a live class |
| OneRoster API direct from page | CORS-blocked from `alpha.timeback.com` context | Use a server-side caller with right token (probably the QTI Cognito token works) |

## Full discovered endpoint list (141)

Bundle-scan extracted all `_createServerFn_handler` references across 193 loaded JS chunks. ✅ = verified live during the discovery sweep. (WRITE) = mutation, treat with care.

### `_actions` (top-level) — 8
- `decryptCredential`
- `getImpersonatedUserId` ✅
- `getImpersonatedUserRole` ✅
- `getOneRosterUser`
- `getUserEnrollments`
- `refreshSession`
- `setImpersonatedUserId` (WRITE)
- `updateUser` (WRITE)

### `admin` — 4
- `getAllOrgsMap`
- `getOrganizationDetails`
- `searchOrganizations`
- `searchUsers`

### `alpha-di-video` — 1
- `completeInteractiveVideo` (WRITE)

### `assessment-results` — 2
- `getUserCompletedMasteryAssessments` ✅
- `getUserPendingMasteryAssessments` ✅

### `course-builder` — 1
- `fetchCourseSyllabus` ✅

### `course-progress` — 4
- `fetchCourseProgress` ✅
- `fetchQti`
- `fetchUser` ✅
- `fetchUsers`

### `courses-explorer` — 3
- `createCourseEnrollment` (WRITE)
- `getEnrollmentAnalyticsBatch` ✅
- `unenrollFromCourseAction` (WRITE)

### `courses-list` — 1
- `getCourses`

### `emporium` — 1
- `getEmporiumSidebarConfig`

### `flow` — 4
- `allocateRecordingChannel` (WRITE)
- `getPendingIncidentsCount`
- `getStudentFlowTime` ✅
- `releaseRecordingChannel` (WRITE)

### `goals` — 14
- `createCourseGoalProduct` (WRITE)
- `createSubjectGoal` (WRITE)
- `deleteCourseGoalProduct` (WRITE)
- `deleteSubjectGoal` (WRITE)
- `getGoalDailyActivity`
- `getPercentiles` ✅
- `getStudentSubjectGoalsBatch` ✅
- `listCourseGoals`
- `listSubjectGoals` ✅
- `previewCourseGoalProduct`
- `previewSubjectGoal`
- `updateCourseGoalProduct` (WRITE)
- `updateSubjectGoal` (WRITE)
- `updateSubjectMinimum` (WRITE)

### `lead-guide` — 1
- `fetchLeadGuideRoster`

### `leaderboards` — 11
- `getAllLeagues` ✅
- `getLeagueDivisionLeaderboard`
- `getLeaguePageData`
- `getLeagueWeekStatus`
- `getMostRecentWeekRecap`
- `getUserLeagueHistory`
- `getUserLeagueMembership`
- `getUserWeeklyXP`
- `markWeekRecapViewed` (WRITE)
- `placeUserInInitialLeague` (WRITE)
- `updateLeagueXP` (WRITE)

### `learning-metrics` — 5
- `getActivityMetrics` ✅ ⭐
- `getDailyXPEvents` ✅ ⭐
- `getStudentXPFromEdubridge`
- `getStudentXPTransactions` ✅ ⭐
- `getUserMetrics` ✅

### `manage-courses` — 1
- `getCourseComponents` ✅

### `manage-enrollments` — 1
- `getEnrollments`

### `manual-xp` (verified despite not appearing in the bundle scan — bundle wasn't loaded at scan time)
- `getManualXPEvents` ✅

### `onboarding` — 4
- `finalizeUserOnboarding` (WRITE)
- `getOrCreateUserDemographics`
- `getSchools`
- `getSchoolsPaginated`

### `organizations` — 4
- `createOrganization` (WRITE)
- `deleteOrganization` (WRITE)
- `getOrganization` ✅
- `updateOrganization` (WRITE)

### `parent` — 2
- `getParentChildren`
- `getStudentPlacementTestHistory` ✅

### `placements` — 9 (split between `versions/legacy/api_client` and `api_client`)
- `getAllPlacementTests` ✅ (legacy verified)
- `getCurrentLevel` ✅ (legacy verified)
- `getNextPlacementTest`
- `getPlacementTestsAdmin`
- `getStudentPlacementData` ✅
- `getSubjectProgress`

### `powerpath-quiz` — 13
- `createNewAttempt` (WRITE)
- `finalStudentAssessmentResponse` (WRITE)
- `getAssessmentProgress`
- `getAttempts`
- `getLessonDetails` ✅
- `getLessonType` ✅
- `getNextQuestion`
- `importExternalTestAssignmentResults` (WRITE)
- `makeExternalTestAssignment` (WRITE)
- `resetAttempt` (WRITE)
- `startTestOut` (WRITE)
- `testOut` (WRITE)
- `updateStudentQuestionResponse` (WRITE)

### `profile` — 2
- `getLinkedParents`
- `getUserProfile` ✅ (path: `src_features_profile_api_profile_ts--getUserProfile_createServerFn_handler`)

### `progression` — 3
- `dismissBanner` (WRITE)
- `dismissBannersBatch` (WRITE)
- `getDismissedBanners`

### `pulse-surveys` — 7
- `closeSurvey` (WRITE)
- `createSurvey` (WRITE)
- `getActiveSurveys` ✅
- `getSurveyResults`
- `listSurveys` ✅
- `resolveEmailsToStudents`
- `submitResponse` (WRITE)

### `qti` — 1
- `getAzureSpeechToken`

### `recommendations` — 18
- `assignTestOut` (WRITE)
- `completeStimulus` (WRITE)
- `completeTextFile` (WRITE)
- `completeVideo` (WRITE)
- `generateWelcomeMessage` (WRITE)
- `getAssignedTests`
- `getBatchEnrollmentStatus`
- `getEnrollmentAnalytics`
- `getEnrollmentFacts`
- `getTimeSaved` ✅
- `getUserCourseRecommendations`
- `getUserEnrollments` ✅
- `getUserRecommendationsBatch`
- `getUserSessionXP` ✅
- `getUserStreak` ✅
- `getUserWeekStreak` ✅
- `getUserYearXP` ✅
- `resetLessonPlan` (WRITE)

### `session-snapshot` — 2
- `getGuidesByOrganization`
- `getStudentsByTeacher` ✅

### `teacher` — 15
- `checkTestOutEligibility`
- `createClassWithRoster` (WRITE)
- `getAcademicSessions` ✅
- `getAssignedTestsBatch` ✅
- `getClassStudentsV2` ✅ ⭐
- `getCourses` ✅
- `getEnrollmentsForMultipleStudents` ✅
- `getSchoolClasses`
- `getSchoolInfo`
- `getStudentProgressionBatch` ✅
- `getStudentsForSchool`
- `getTeacherClasses` ✅
- `getUserOrganizations`
- `joinClass` (WRITE)
- `requestTestForStudent` (WRITE)
