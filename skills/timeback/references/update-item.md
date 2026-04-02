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

```
PUT {QTI_BASE}/stimuli/{id}
```

```python
{
    "identifier": stimulus_id,
    "title": title,
    "content": updated_html,  # must be valid XHTML
}
```

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

## Field Name Reference

| Context | Field Name | Notes |
|---------|-----------|-------|
| GET response | `rawXml` | camelCase |
| PUT payload | `xml` | lowercase |
| GET response | `metadata` | nested object |
| PUT payload | `metadata` | same structure, must include |
| GET stimulus ref | `stimulusRef` | can be object or list |
| PUT item with stimulus | `stimulus.identifier` | must include or link breaks |
