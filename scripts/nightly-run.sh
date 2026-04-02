#!/bin/bash
# Nightly Timeback Skill Self-Improvement
# Called by launchd at 2am local time.
# Runs Claude Code headlessly to: scan production errors, run regression tests, update skills, push.

set -euo pipefail

PLUGIN_DIR="/Volumes/T7 Shield/my scripts/projects/ap-courses/timeback-plugin"
LOG_DIR="$PLUGIN_DIR/reports/nightly"
DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/${DATE}.log"

mkdir -p "$LOG_DIR"

echo "=== Nightly skill test run: $DATE ===" | tee "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"

# Check T7 Shield is mounted
if [ ! -d "/Volumes/T7 Shield" ]; then
    echo "ERROR: T7 Shield not mounted. Aborting." | tee -a "$LOG_FILE"
    exit 1
fi

# Check API credentials
if [ -z "${TIMEBACK_CLIENT_ID:-}" ] || [ -z "${TIMEBACK_CLIENT_SECRET:-}" ]; then
    # Try loading from .env if not in environment
    ENV_FILE="$PLUGIN_DIR/.env"
    if [ -f "$ENV_FILE" ]; then
        export $(grep -v '^#' "$ENV_FILE" | xargs)
    else
        echo "ERROR: TIMEBACK_CLIENT_ID/SECRET not set and no .env found." | tee -a "$LOG_FILE"
        exit 1
    fi
fi

# Auto-discover production repos — scan ALL repos under ap-courses that touch Timeback
export AP_COURSES_ROOT="/Volumes/T7 Shield/my scripts/projects/ap-courses"

# Find repos that contain Timeback API references (auto-discovers new repos)
TIMEBACK_REPOS=$(grep -rl "alpha-1edtech\|qti\.alpha\|assessment-items\|oneroster" "$AP_COURSES_ROOT"/*/tools/ "$AP_COURSES_ROOT"/*/scripts/ 2>/dev/null | sed 's|/tools/.*||;s|/scripts/.*||' | sort -u | tr '\n' ',' | sed 's/,$//')
echo "Discovered Timeback repos: $TIMEBACK_REPOS" | tee -a "$LOG_FILE"

# Run Claude Code headlessly with the skill-tester prompt
PROMPT="You are the skill-tester agent. Run the nightly self-improvement cycle:

1. SCAN PRODUCTION ERRORS: Auto-discovered repos that use Timeback APIs:
   ${TIMEBACK_REPOS}
   Scan ALL of these repos for files modified today containing error patterns (status 4xx/5xx, traceback, failed).
   Also scan any repo under $AP_COURSES_ROOT that has recent .log or .jsonl files.
   For each new error: check if it's documented in the skill files. If not, flag it.

2. RUN REGRESSION TESTS: Use the test infrastructure at $PLUGIN_DIR/scripts/skill-tester/.
   Run the QTI regression suite (15 tests) and OneRoster regression suite (10 tests).
   Compare results to documented behavior.

3. UPDATE SKILLS: For any changed behavior or new production errors:
   - Edit the relevant file in $PLUGIN_DIR/skills/timeback/ or references/
   - Add verification date
   - Log the change

4. WRITE REPORT: Save to $PLUGIN_DIR/reports/nightly/${DATE}.md with:
   - Production errors found (new vs known)
   - Regression test results (pass/changed/fail)
   - Skill updates made

5. COMMIT AND PUSH if any skill files changed:
   cd '$PLUGIN_DIR'
   git add skills/ reports/
   git commit -m 'nightly: skill updates from ${DATE}'
   git push origin main

Be concise. Run tests, update docs, commit. No interactive questions."

echo "Running Claude Code..." | tee -a "$LOG_FILE"
claude --print --dangerously-skip-permissions -p "$PROMPT" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
echo "Finished: $(date), exit code: $EXIT_CODE" | tee -a "$LOG_FILE"

exit $EXIT_CODE
