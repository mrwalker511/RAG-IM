# Prompt Standards Guide

The cheapest high-quality prompt is specific.

## Rules

1. Name the file or module when you know it.
2. State the expected behavior, not just the symptom.
3. Give the exact error text when debugging.
4. Say what must not change.
5. Split unrelated tasks into separate requests.
6. For doc work, name the exact `.md` files to update.

## Good Examples

### Bug fix

```text
Bug in `api/middleware.py`: project-scoped key can list all projects.
Expected: `GET /projects` should require the bootstrap key.
Do not change project-route auth.
```

### Test gap

```text
Add coverage in `tests/api/test_projects_api.py` for `/handbook/README.md`.
Expected: 200 without auth and rendered HTML content.
```

### Documentation

```text
Update `README.md`, `testing.md`, and `STATUS.md` for the current deploy flow.
Keep `testing.md` short.
```

## Avoid

- “Analyze the whole project and tell me what is missing.”
- “Fix the tests” without naming the failing suite.
- “Update the docs” without naming the docs or the behavior that changed.

## Review Requests

If you want a review, say what to review for:

```text
Review `api/main.py` for auth exposure and broken public routes.
Findings only.
```
