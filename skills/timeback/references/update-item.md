# Update Existing Items

## The #1 Rule: PUT is Full Replace

Omit `stimulus` -- link removed. Omit `metadata` -- cleared. Omit `responseProcessing` -- grader lost.

Every PUT must include the complete item. There is no PATCH endpoint.

## Update Pattern (Recommended)

```python
# 1. GET the item
resp = session.get(f"{QTI_BASE}/assessment-items/{item_id}")
item = resp.json()
raw_xml = item["rawXml"]  # Note: camelCase in GET response

# 2. Modify the specific section in raw_xml
# (use xml.etree.ElementTree or regex for targeted changes)
import xml.etree.ElementTree as ET
root = ET.fromstring(raw_xml)
# ... make changes to root ...
modified_xml = ET.tostring(root, encoding="unicode")

# 3. Validate before sending
ET.fromstring(modified_xml)  # will raise if invalid XML

# 4. PUT back the complete XML
resp = session.put(
    f"{QTI_BASE}/assessment-items/{item_id}",
    json={
        "format": "xml",
        "xml": modified_xml,
        "metadata": item.get("metadata", {}),
    },
)
resp.raise_for_status()
```

## Hard Rules

### Format Mismatch Between GET and PUT
- GET returns a nested JSON structure with `rawXml` (camelCase)
- PUT expects flat JSON with `xml` (lowercase) when using XML format
- These formats DO NOT match -- you cannot round-trip GET response directly to PUT

### PUT Payload Format
```python
{
    "format": "xml",
    "xml": raw_xml_string,      # lowercase "xml"
    "metadata": {...},           # must include or it's cleared
}
```

### Never Reconstruct XML From Scratch
- You will lose: rubrics, response processing rules, grader URLs, feedback blocks, custom operators
- Always start from the existing `rawXml` and make targeted edits

### Always Validate Before PUT
```python
ET.fromstring(modified_xml)  # catches malformed XML before it hits the API
```

## Alternative: DELETE + POST (More Reliable for Complex Changes)

**Forbidden in prod**: DELETE on a live `/assessment-items/{id}` or `/stimuli/{id}` opens a window where the entity is gone before the replacement POST lands. If POST fails (409 race, 500, auth expiry), students see 404s. NEVER use DELETE+POST as an automatic escalation when PUT fails on prod — surface the error to the user instead. DELETE+POST is for dev/test environments explicitly isolated from prod, OR for prod only with explicit user confirmation. Cross-reference: SKILL.md CRITICAL RULE 3 (final paragraph).

When modifying response processing, grader config, or interaction structure, DELETE + POST is safer than XML surgery:

```python
# 1. GET full item
resp = session.get(f"{QTI_BASE}/assessment-items/{item_id}")
item = resp.json()

# 2. DELETE
session.delete(f"{QTI_BASE}/assessment-items/{item_id}")
# No delay needed -- immediate POST after DELETE works (verified 2026-04-02, no 409 race)

# 3. Rebuild and POST
new_payload = rebuild_item_payload(item, changes)
resp = session.post(f"{QTI_BASE}/assessment-items", json=new_payload)
resp.raise_for_status()
```

Use this when: changing item type, restructuring interactions, swapping grader URLs, or any change that touches multiple XML sections simultaneously.

## Updating Stimuli

Stimulus PUT uses a DIFFERENT shape than item PUT. Items use `{"format": "xml", "xml": ...}`. Stimuli use:

```
PUT {QTI_BASE}/stimuli/{id}
```

```python
{
    "identifier": stimulus_id,
    "title": title,
    "content": updated_html,  # must be valid XHTML — inner of <qti-stimulus-body>, not full rawXml
    "metadata": {...},          # preserve from GET
}
```

The `content` field is HTML (the inner of `<qti-stimulus-body>`, not the full rawXml). If you accidentally PUT a stimulus with `{"format": "xml", "xml": ...}`, the API returns **500** with `DocumentNotFoundError ... on model QTIStimulus` — the Mongo ObjectId lookup fails because the request didn't include the right fields. The fix is to use the HTML `content` shape above, NOT to escalate to DELETE+POST. (See SKILL.md CRITICAL RULE 3 for the prod-DELETE prohibition.)

Same full-replace semantics. Omit `content` and it's cleared.

## Updating Tests

```
PUT {QTI_BASE}/assessment-tests/{id}
Content-Type: application/xml
```

Body is raw XML string -- NOT JSON. Different from item and stimulus updates.

## Batch Update Pattern

```python
import json

CHECKPOINT_FILE = "update_checkpoint.json"

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"completed": [], "failed": []}

def save_checkpoint(state):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f, indent=2)

state = load_checkpoint()

for item_id in item_ids:
    if item_id in state["completed"]:
        continue
    try:
        update_item(session, QTI_BASE, item_id, changes)
        state["completed"].append(item_id)
    except Exception as e:
        state["failed"].append({"id": item_id, "error": str(e)})
    save_checkpoint(state)  # after EVERY item
```

## CRITICAL: XML PUT Can Silently Fail to Update Rendered State

The API has two internal representations: `rawXml` (the stored XML string) and a **typed object model** (parsed fields like `interaction.shuffle`, `interaction.choices[]`). When you PUT with `format: "xml"`, `rawXml` is updated but the **typed model may not be re-parsed**. The renderer reads some properties (notably `shuffle`) from the typed model, not from rawXml.

**Consequence**: XML PUT returns 200, GET shows correct `rawXml` with `shuffle="true"`, but the student UI still shows fixed order because the typed `interaction.shuffle` field was never updated. This caused 12,000+ items to appear fixed after a "successful" batch update in April 2026.

**Safe approach for simple property changes** (shuffle, maxChoices, etc.):
- Use **JSON PUT** with the typed fields, not XML PUT
- Or use **DELETE + POST** with the correct XML (POST forces full parsing)

**XML PUT is safe for**: content changes (prompt text, feedback text, stimulus references) — anything in the XML body that the renderer reads directly from rawXml.

**XML PUT is NOT reliable for**: interaction configuration properties (`shuffle`, `maxChoices`, `orientation`, choice ordering) that the typed model caches separately.

**Always round-trip verify**: After any batch update, GET a sample of items and check BOTH `rawXml` AND the typed fields (e.g., `interaction.shuffle`) to confirm they match.

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Stimulus link gone after update | PUT omitted `stimulus` field | Always include stimulus ref |
| Metadata cleared | PUT omitted `metadata` | Always include metadata from GET |
| Grader stopped working | PUT omitted `responseProcessing` | Include full response processing |
| 400 on PUT | Malformed XML | Validate with `ET.fromstring()` first |
| ~~409 Conflict~~ | ~~DELETE + immediate POST race~~ | No delay needed (verified 2026-04-02: immediate POST after DELETE succeeds) |
| Wrong field name | Used `rawXml` in PUT (should be `xml`) | Use lowercase `xml` in PUT payload |
| Lost feedback blocks | Reconstructed XML from scratch | Always edit existing XML, never rebuild |
| **Shuffle/config unchanged after PUT** | **XML PUT didn't update typed model** | **Use JSON PUT or DELETE+POST for interaction config changes** |
| **Answer positions shifted to A-bias** | **XML PUT triggered internal normalization** | **Verify answer distribution after batch updates, not just success count** |

## Field Name Reference

| Context | Field Name | Notes |
|---------|-----------|-------|
| GET response | `rawXml` | camelCase |
| PUT payload | `xml` | lowercase |
| GET response | `metadata` | nested object |
| PUT payload | `metadata` | same structure, must include |
| GET stimulus ref | `stimulusRef` | can be object or list |
| PUT item with stimulus | `stimulus.identifier` | must include or link breaks |
