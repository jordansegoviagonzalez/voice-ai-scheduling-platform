# Development Workflow

## Purpose

This document defines the recommended development workflow for the AI medical scheduling platform.

The goal is to keep changes small, testable, secure, and aligned with the existing architecture while Phase 3 adds multi-organization support.

This document is for local development and implementation workflow. Production deployment details belong in `docs/DEPLOYMENT.md`.

## Before Making Changes

Before starting any change:

1. Check the current Git state.
2. Confirm the active branch.
3. Review the relevant documentation.
4. Identify the smallest safe implementation slice.
5. Avoid mixing unrelated changes in the same commit.

Useful checks:

```bash
git status --short --branch --untracked-files=all
git branch -vv
git log --oneline --decorate -n 10
```

Do not start implementation if the working tree contains unrelated changes that could be accidentally committed.

## Local Development

The project uses a Flask backend, PostgreSQL database, SQLAlchemy/Alembic migrations, React + Vite + TypeScript frontend, Docker workflow, and Nginx/HTTPS deployment path.

Local work should generally follow this order:

1. Confirm the app starts locally.
2. Confirm the backend health endpoint works.
3. Confirm the frontend can reach the backend.
4. Make one scoped change.
5. Run focused tests.
6. Run broader checks before committing.

Avoid changing backend, frontend, docs, and deployment configuration all in the same step unless the change clearly requires it.

## Migration Workflow

Database changes should be handled through Alembic migrations.

For schema work:

1. Update the model.
2. Add or revise the migration.
3. Verify the migration path.
4. Verify the downgrade path when practical.
5. Test against a fresh database path when possible.
6. Confirm existing seeded/demo data still works safely.

For Phase 3 multi-organization work, migrations must preserve legacy single-organization behavior while adding explicit organization ownership.

The default organization may be used for migration safety and legacy compatibility, but explicit organization routes must not silently fall back to it.

## API Workflow

Backend API changes should be implemented before GUI changes when the feature needs both programmatic and admin interface support.

Recommended order:

1. Add or update service-layer behavior.
2. Add or update database queries with organization scope.
3. Add or update API routes.
4. Add request validation.
5. Add response serialization.
6. Add tests for success and failure paths.
7. Update documentation after behavior is stable.

For Phase 3, organization context must be resolved before routing, booking, chat, voice, or dashboard workflows touch organization-owned records.

## GUI Workflow

The frontend should call backend APIs instead of duplicating business logic.

The GUI should not independently decide:

- routing eligibility
- doctor matching
- slot validity
- booking confirmation
- organization ownership
- cross-organization access rules

For admin organization management, the GUI should use the same backend APIs that programmatic clients use.

Recommended GUI order:

1. Add API client methods.
2. Add TypeScript types.
3. Add the page or component.
4. Add loading and error states.
5. Add simple form validation.
6. Confirm the backend remains the source of truth.

## Testing Workflow

Run focused tests after each small change.

For backend changes, test:

- model behavior
- migration behavior
- service-layer behavior
- route validation
- routing decisions
- booking safety
- chat session behavior
- voice endpoint behavior when applicable

For frontend changes, test:

- API client behavior
- page rendering
- loading states
- error states
- form submission
- user flows

For Phase 3 multi-organization work, tests should prove:

- at least two organizations can exist
- a new organization can be recognized by slug
- doctors are scoped by organization
- locations are scoped by organization
- slots are scoped by organization
- chat sessions are scoped by organization
- calls are scoped by organization
- routing never returns another organization’s resources
- booking rejects cross-organization mismatches

## Documentation Workflow

Documentation should be updated when behavior, architecture, setup, or verification expectations change.

Use each document for its intended purpose:

- `docs/MULTI_ORG_PLAN.md` owns the Phase 3 implementation plan.
- `docs/ORG_CONTEXT_CONTRACT.md` owns organization recognition and scoping rules.
- `docs/SECURITY_CHECKLIST.md` owns pre-push and pre-review safety checks.
- `docs/DEVELOPMENT_WORKFLOW.md` owns local development workflow.
- `docs/DEPLOYMENT.md` owns production deployment and runtime operations.
- `docs/API.md` owns API behavior.
- `docs/ROUTING_RULES.md` owns scheduling and routing behavior.
- `docs/TEST_PLAN.md` owns test scenarios and verification strategy.
- `docs/ARCHITECTURE.md` owns the stable system architecture.

Private notes, prompts, scratch reports, and local-only planning should stay out of committed documentation.

## Commit Hygiene

Commits should be small, clear, and reviewable.

Before committing:

1. Check the working tree.
2. Review the diff.
3. Confirm no private files are staged.
4. Confirm no secrets or personal data are included.
5. Run relevant tests.
6. Use a clear commit message.

Useful checks:

```bash
git status --short --branch --untracked-files=all
git diff --check
git diff --stat
git diff --cached --stat
```

Do not commit:

- `.env` files
- secrets
- tokens
- passwords
- API keys
- real patient data
- real personal emails
- private screenshots
- local machine paths
- private Codex or Gemini notes
- files inside `docs/agent-notes/`

Git commit metadata should use a privacy-safe identity, such as a GitHub noreply email, instead of a real personal email.

## Phase 3 Verification Loop

For each Phase 3 implementation slice, follow this loop:

1. Define the organization-scoped behavior.
2. Update the schema or service layer if needed.
3. Add or update API behavior.
4. Add focused tests.
5. Verify no cross-organization leakage.
6. Update documentation.
7. Review security before committing.

The most important Phase 3 verification question is:

`Can this workflow accidentally read, return, modify, or book data from another organization?`

If the answer is yes or unclear, the change is not ready.

## Pre-Push Review

Before pushing to GitHub:

1. Confirm the branch target.
2. Confirm the latest commits use privacy-safe Git metadata.
3. Confirm ignored local-only files are not tracked.
4. Confirm no private screenshots or personal emails are included.
5. Run relevant tests.
6. Review the final diff.

Suggested checks:

```bash
git status --short --branch --untracked-files=all
git log -3 --pretty=fuller
git ls-files | grep -E "docs/agent-notes|docs/codex" || true
git check-ignore -v docs/codex.md || true
git check-ignore -v docs/agent-notes/ || true
rg -n --glob '!docs/codex.md' --glob '!docs/agent-notes/**' "@gmail\.com|@yahoo\.com|@hotmail\.com|@outlook\.com|@icloud\.com" . || true
rg -n --glob '!docs/codex.md' --glob '!docs/agent-notes/**' "dashboard-reference\.png" . || true
```

Do not push until the working tree, commit metadata, tests, and security checks are clean.