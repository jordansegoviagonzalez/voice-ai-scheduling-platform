# Security Checklist

## Purpose

This checklist defines the pre-push and pre-review security rules for the AI medical scheduling platform.

The goal is to prevent secrets, personal information, patient data, private notes, screenshots, or local-only files from being committed or pushed to GitHub.

Security is especially important in Phase 3 because the platform is becoming multi-organization. A mistake could expose one organization’s data to another organization or expose private project details in the repository.

## Never Commit

Do not commit:

- `.env` files.
- API keys.
- Tokens.
- Passwords.
- Private keys.
- Real patient data.
- Real personal email addresses.
- Private screenshots.
- Local machine paths.
- Demo-prep notes.
- Codex or Gemini scratch notes.
- Files inside `docs/agent-notes/`.
- `docs/codex.md` or `docs/codex*.md`.
- Database dumps.
- Production logs.
- Temporary runtime files.
- Build/cache folders unless intentionally required.

Use placeholders in documentation and examples.

Safe examples:

```text
ADMIN_EMAIL=admin@example.com
DATABASE_URL=postgresql://user:password@localhost:5432/app
OPENAI_API_KEY=<set-in-environment>
VOGENT_WEBHOOK_SECRET=<set-in-environment>
```

Do not use real credentials, real emails, real phone numbers, or real patient details in committed files.

## Git Identity

Git commit metadata should use a privacy-safe identity.

Recommended:

- Use a GitHub noreply email for commit author and committer metadata.
- Enable GitHub email privacy settings.
- Enable protection that blocks command-line pushes exposing a personal email.

Do not use a real personal email address in commits if the repository may be public or reviewed externally.

Before pushing, inspect recent commit metadata:

```bash
git log -3 --pretty=fuller
```

If a real personal email appears in recent commit metadata, fix it before pushing.

## Environment Variables

Configuration secrets must come from environment variables or secret managers, not committed files.

Allowed in the repo:

- `.env.example`
- placeholder values
- documented variable names
- safe local setup examples

Not allowed in the repo:

- real `.env`
- production secrets
- local private credentials
- copied API keys
- webhook secrets
- database passwords
- SSH keys
- cloud credentials

Before committing, check:

```bash
git status --short --branch --untracked-files=all
git ls-files | grep -E "\.env$|\.pem$|\.key$|id_rsa|id_ed25519" || true
```

## Patient Data

Do not commit real patient data.

This includes:

- names
- phone numbers
- email addresses
- dates of birth
- appointment details
- transcripts
- call recordings
- medical issues
- insurance details
- internal patient IDs from a real system

Use synthetic demo patients only.

Safe examples should clearly look fake, such as:

- `Olivia Carter`
- `Alex Morgan`
- `patient@example.com`
- `555-0100`

Do not use real people, real contact information, or real medical history in docs, tests, scripts, screenshots, or seed data.

## Screenshots and Local Files

Do not commit private screenshots or local-only reference images.

Before pushing, check for private screenshots and local image references:

```bash
git ls-files | grep -Ei "screenshot|screen shot|dashboard-reference|private|local" || true
rg -n --glob '!docs/agent-notes/**' --glob '!docs/codex.md' "dashboard-reference\.png|private screenshot|local screenshot" . || true
```

If a screenshot is needed for documentation, it should be scrubbed, reviewer-safe, and contain no real patient data, private URLs, personal email addresses, local machine paths, or credentials.

## Agent Notes

Agent notes are local-only.

These must remain ignored and untracked:

```text
docs/agent-notes/
docs/codex.md
docs/codex*.md
```

Use `docs/agent-notes/` only for private Codex/Gemini prompts, scratch notes, and local run reports.

Do not place reviewer-facing documentation inside `docs/agent-notes/`.

Reviewer-facing docs belong directly in `docs/`.

## Pre-Push Checks

Before pushing to GitHub, run:

```bash
git status --short --branch --untracked-files=all
git diff --check
git diff --stat
git diff --cached --stat
git log -3 --pretty=fuller
git check-ignore -v docs/codex.md || true
git check-ignore -v docs/agent-notes/ || true
git ls-files | grep -E "docs/agent-notes|docs/codex" || true
```

Check for personal email domains:

```bash
rg -n --glob '!docs/codex.md' --glob '!docs/codex*.md' --glob '!docs/agent-notes/**' "@gmail\.com|@yahoo\.com|@hotmail\.com|@outlook\.com|@icloud\.com" . || true
```

Check for secret-like values:

```bash
rg -n --glob '!docs/codex.md' --glob '!docs/codex*.md' --glob '!docs/agent-notes/**' "api_key|apikey|secret|token|password|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|sk-|ghp_|gho_|ghs_" . || true
```

Check for private screenshots or local references:

```bash
rg -n --glob '!docs/codex.md' --glob '!docs/codex*.md' --glob '!docs/agent-notes/**' "dashboard-reference\.png|private screenshot|local screenshot|/Users/" . || true
```

Any hits must be reviewed before pushing. Generic documentation references to words like `token`, `password`, or `secret` are acceptable only when they are placeholders or checklist language, not real values.

## Reviewer-Safe Documentation

Reviewer-safe documentation should explain the system clearly without exposing private implementation notes.

Documentation may include:

- architecture decisions
- API behavior
- setup steps
- test plans
- placeholder configuration
- synthetic demo data
- security rules
- workflow expectations

Documentation must not include:

- private prompt history
- local Codex/Gemini reports
- real credentials
- real personal emails
- real patient data
- private screenshots
- local machine paths
- unredacted production values

## Multi-Organization Security

Phase 3 must prevent cross-organization data leakage.

Security rules:

- Every organization-owned record must be scoped by organization.
- Explicit organization routes must not silently fall back to the default organization.
- Public chat links must resolve organization context before intake.
- Voice workflows must resolve organization context before lookup, routing, or booking.
- Routing must never return doctors, locations, slots, or appointments from another organization.
- Booking must reject cross-organization mismatches.
- Dashboard views must clearly scope or label organization-owned data.
- Audit records should store the organization context used for each decision.

The main security question for every Phase 3 change is:

`Can this workflow accidentally read, return, modify, or book data from another organization?`

If the answer is yes or unclear, the change is not ready.

## Final Rule

Do not push until:

- Git status is understood.
- The target branch is confirmed.
- Recent commit metadata uses privacy-safe identity.
- Ignored local-only files are not tracked.
- No real personal emails are present.
- No secrets are present.
- No private screenshots are present.
- Relevant tests pass.
- The final diff is reviewed.