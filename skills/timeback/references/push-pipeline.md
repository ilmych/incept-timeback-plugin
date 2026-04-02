# Full Course Push Pipeline

## Strict Creation Order

```
1. S3 uploads (images, videos, PCI JS modules) -- BEFORE any API calls
2. Course (POST /courses)
3. Components: Units (parent=null)
4. Components: Lessons/Topics (parent=unit)
5. QTI Items (POST /assessment-items)
6. QTI Tests (POST /assessment-tests) -- groups item IDs
7. Stimuli (POST /stimuli) -- HTML content blocks
8. Resources (POST /resources/) -- wraps tests/stimuli
9. Component-Resource Links (POST /component-resources) -- ties resources to lessons
```

Items must exist before tests. Tests must exist before resources. Components must exist before links.

## Checkpointing (MANDATORY)

Save after EVERY entity creation, not after batches:

```python
state["units"][str(unum)] = comp_id
with open(CHECKPOINT_FILE, "w") as f:
    json.dump(state, f, indent=2)
```

Check before creating: if entity exists in checkpoint, skip.

```python
if str(unum) in state.get("units", {}):
    comp_id = state["units"][str(unum)]
    print(f"  Skipping unit {unum} (exists: {comp_id})")
    continue
```

Resume pattern: load checkpoint at start, skip all completed entities, continue from first missing.

## Retry and Idempotency

- HTTP 409 = already exists = treat as success, extract ID from response if possible.
- Retry config: 3 attempts, backoff `[5, 15, 30]`s, retry on `[429, 500, 502, 503, 504]`.
- Rate limiting: 0.05s between items, 0.1s between components, 0.3s between delete+create.

```python
for attempt in range(3):
    try:
        resp = session.post(url, json=payload, timeout=30)
        if resp.status_code == 409:
            return {"success": True, "already_existed": True}
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except (HTTPError, Timeout, ConnectionError) as e:
        if attempt < 2 and getattr(e.response, 'status_code', 0) in [429, 500, 502, 503, 504]:
            time.sleep([5, 15, 30][attempt])
            continue
        raise
```

## ID Generation

Use timestamp-based deterministic IDs for resume:

```python
TS = datetime.now().strftime("%Y%m%d-%H%M")
course_id = f"{prefix}-{TS}"
unit_id = f"{prefix}-{TS}-unit-{num}"
topic_id = f"{prefix}-{TS}-unit-{unum}-topic-{tnum}"
resource_id = f"{prefix}-{TS}-res-{lesson_type}-{unum}-{tnum}"
link_id = f"{prefix}-{TS}-link-{lesson_type}-{unum}-{tnum}"
```

## Parallel Upload Pattern

For items (the bulk of the work), use parallel POST with rate limiting:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=5) as pool:
    futures = {}
    for item in items:
        time.sleep(0.05)  # rate limit
        f = pool.submit(post_item, item)
        futures[f] = item["sourcedId"]
    for f in as_completed(futures):
        result = f.result()
        state["items"][futures[f]] = result
        save_checkpoint(state)
```

## Validation After Push

After all entities created, verify the chain:

1. GET course -- confirm exists and active
2. GET components with `?filter=course.sourcedId='{course_id}'` -- confirm count matches
3. Spot-check 3-5 resources -- confirm lessonType and vendorResourceId correct
4. Open student UI and verify at least one lesson renders

## Common Pipeline Failures

| Failure | Cause | Fix |
|---------|-------|-----|
| Components exist but lessons empty | Missing component-resource links | Create links in step 9 |
| Tests 404 in student UI | Resource URL wrong or test not created | Verify test exists, check URL format |
| Duplicate items on retry | No idempotency check | Always check checkpoint before POST |
| Partial push, can't resume | No checkpoint file | Always checkpoint after every entity |
| Items created but test empty | Item IDs not in test payload | Verify item creation succeeded before building test |
