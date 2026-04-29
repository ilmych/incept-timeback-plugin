# Create Stimulus (Article/Passage)

## Endpoint

```
POST {QTI_BASE}/stimuli
```

**NOT** `/assessment-stimuli` -- that is a legacy endpoint.

## Known-Good Payload

```python
{
    "identifier": "s4-stim-xxxxxxxxxxxx",
    "title": "Passage Title",
    "content": "<p>sanitized XHTML content here</p>"
}
```

## Hard Rules

### Content Format
- Content field accepts HTML but is **parsed as XML** -- MUST be valid XHTML
- Run `sanitize_html_for_xhtml()` on ALL content before posting
- Common XHTML violations that cause 400 errors:
  - Bare `&` (must be `&amp;`)
  - Unclosed `<br>`, `<img>`, `<hr>` (must be `<br/>`, `<img/>`, `<hr/>`)
  - Unquoted attributes
  - `<style>` blocks (stripped by platform -- use inline styles)

### Linking Stimuli to Items
- Stimulus href in item must be full API URL: `https://qti.alpha-1edtech.ai/api/stimuli/{id}`
- When PUTting an item that has a stimulus, include `"stimulus": {"identifier": "..."}` or the link is SILENTLY REMOVED
- This is the #1 cause of "my passage disappeared" bugs

### GET Response Quirk
- Stimulus ref in GET response can be a single object OR a list
- Always normalize to list before iterating:
```python
refs = item.get("stimulusRef", [])
if isinstance(refs, dict):
    refs = [refs]
```

### Two Endpoints for Legacy Stimuli
- Primary: `/stimuli/{id}`
- Legacy: `/assessment-stimuli/{id}`
- On 404 from primary, try legacy endpoint before giving up
```python
resp = session.get(f"{QTI_BASE}/stimuli/{stim_id}")
if resp.status_code == 404:
    resp = session.get(f"{QTI_BASE}/assessment-stimuli/{stim_id}")
```

### Content Type Variants

| Use Case | lessonType | subType |
|----------|-----------|---------|
| Article / reading passage | `alpha-read-article` | `qti-stimulus` |
| Video resource | n/a (type is `video`) | `alpha-read-article` |
| Embedded passage for items | n/a | n/a (linked via stimulus ref) |

### Rendering Behavior
- Embedded passages should be separate stimulus objects, not crammed into `<qti-prompt>`
- QTI viewer renders stimulus in a dedicated reading pane (split view)
- Long articles: platform handles scrolling, no need for manual pagination

### Images in Stimuli (verified 2026-04-04)
- **Do NOT embed base64 images** — stimuli with base64 content grow to 50-150KB and cause 500 errors in the alpharead app
- Upload images to S3 (`ai-first-incept-media` bucket) and reference via `<img src="https://..." alt="..."/>`
- Self-close the img tag for XHTML compatibility: `<img src="..." alt="..."/>`

## Update (PUT)

```
PUT {QTI_BASE}/stimuli/{id}
```

```python
{
    "identifier": "s4-stim-xxxxxxxxxxxx",
    "title": "Updated Title",
    "content": "<p>updated sanitized XHTML</p>"
}
```

Same format as POST. Full replace -- omitted fields are cleared.

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| 400 on POST | Invalid XHTML in content | Sanitize with `sanitize_html_for_xhtml()` |
| Passage disappears after item update | PUT item without `stimulus` field | Always include stimulus ref in item PUT |
| 404 on GET | Stimulus on legacy endpoint | Try `/assessment-stimuli/{id}` fallback |
| Content renders with raw tags | Bare `&`, unclosed tags | Full XHTML sanitization pass |
| Images broken in passage | Relative image URLs | Use absolute URLs with full https:// path |

## Batch Pattern

```python
def create_stimulus(session, qti_base, title, html_content):
    clean = sanitize_html_for_xhtml(html_content)
    identifier = f"s4-stim-{uuid4().hex[:12]}"
    payload = {
        "identifier": identifier,
        "title": title,
        "content": clean,
    }
    resp = session.post(f"{qti_base}/stimuli", json=payload)
    resp.raise_for_status()
    return resp.json()["identifier"]
```

## Linking Stimulus to Item After Creation

```python
# When creating or updating an item with a stimulus reference:
item_payload["stimulus"] = {"identifier": stimulus_id}
# The platform resolves the identifier to the full href internally
```
