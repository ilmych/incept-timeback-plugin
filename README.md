# Timeback Plugin for Claude Code

Platform reference for creating, updating, and publishing educational content on Timeback. Prevents the XML, QTI, and rendering bugs that have cost days of debugging across AP course builds.

**Self-improving**: A nightly agent runs regression tests against the live APIs and updates documentation automatically.

## Install

```bash
claude plugin add /path/to/timeback-plugin
```

Or if hosted on GitHub:
```bash
claude plugin add github:your-org/timeback-plugin
```

## What You Get

### Skill: `/timeback`
Loads the full Timeback platform reference. Invoke it before writing ANY code that touches the Timeback API.

Covers:
- QTI item creation (MCQ, FRQ, match, hotspot, gap-match, inline-choice, etc.)
- Course structure (OneRoster courses, components, resources, links)
- HTML sanitization for XHTML compliance
- Update patterns (GET-modify-PUT)
- Error diagnosis
- Math/formula notation
- S3 uploads
- Push pipeline ordering
- **Admin dashboard read API** at `alpha.timeback.com` — student activity, goals, mastery, placements, roster (complementary to the QTI authoring side; useful for round-trip verification of pushed content). See [`skills/timeback/references/admin-dashboard-read-api.md`](skills/timeback/references/admin-dashboard-read-api.md).

### Agent: `skill-tester`
Autonomous agent that:
- Scans production repos for today's pipeline errors
- Reproduces errors with minimal API test cases
- Runs regression tests against known gotchas (45+ tests)
- Updates skill files when API behavior changes
- Generates nightly reports

### Hook: Timeback Code Detection
Automatically reminds you to load `/timeback` when you write code that touches Timeback API endpoints. Prevents the #1 cause of bugs: writing API code without loading the gotcha reference.

## Prerequisites

Environment variables (for API testing agent):
```bash
export TIMEBACK_CLIENT_ID="your-client-id"
export TIMEBACK_CLIENT_SECRET="your-client-secret"
```

Python packages (for test infrastructure):
```bash
pip install requests
```

## For Non-Technical Users

You don't need to understand the API. Just:
1. Install the plugin
2. When Claude Code is helping you with Timeback content, it will automatically have the right knowledge
3. If you see a reminder to load `/timeback`, type `/timeback` and press enter

## Nightly Self-Improvement

The `skill-tester` agent can be scheduled to run nightly:
```bash
claude schedule create --name "timeback-nightly" --cron "0 2 * * *" --prompt "Run the skill-tester agent: scan production repos for today's errors, run regression tests, update skill files, commit changes."
```

Reports are saved to `reports/nightly/YYYY-MM-DD.md`.

## Structure

```
timeback-plugin/
├── .claude-plugin/plugin.json    # Plugin manifest
├── skills/timeback/
│   ├── SKILL.md                  # Main skill (auto-loads on /timeback)
│   ├── references/               # 13 detailed reference files
│   └── scripts/sanitize_html.py  # XHTML sanitizer utility
├── agents/skill-tester.md        # Nightly regression agent
├── hooks/hooks.json              # API code detection hook
└── scripts/skill-tester/         # Python test infrastructure
    ├── auth.py                   # OAuth2 authentication
    └── api_client.py             # API wrapper with retry + logging
```

## Contributing

When you find a new gotcha:
1. Update the relevant file in `skills/timeback/references/`
2. Add a verification date: `(verified YYYY-MM-DD)`
3. Commit with message: `fix(skill): [what you found]`

The nightly agent will verify your addition in its next run.
