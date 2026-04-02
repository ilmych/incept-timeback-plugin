# Error Diagnosis Guide

## Rendering Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Item renders empty/broken in student UI | JSON POST for complex type | Re-push with XML POST (see `interaction-types.md`) |
| `<table>` not visible | Inside `<p>` tag, or missing inline CSS | Move table outside `<p>`, add `style="border: 1px solid #ccc"` etc. |
| No explanation shown after answering | Missing `qti-modal-feedback` blocks | Add FEEDBACK outcome declaration + modal-feedback element |
| Stimulus not displayed | Missing `stimulus-ref` or relative href | Use full API URL in href, verify stimulus exists |
| Pipe chars visible in content | Markdown table not converted to HTML | Convert all markdown tables to `<table>` elements |
| Chemical formula garbled | MathML stripped or PDF extraction artifact | Convert to Unicode subscripts (see `math-and-formulas.md`) |
| Feedback cut off mid-sentence | Undocumented char limit on inline feedback | Keep under ~1000 chars; use metadata for longer explanations |
| SVG shows answer labels | LLM labeled graph points with actual answers | Regenerate with neutral markers (A, B, C, dots) |
| Items showing "[Placeholder]" | PCI pushed with placeholder config | Regenerate with real content, re-push JS module |

## PCI-Specific Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| PCI shows blank | typeIdentifier mismatch or S3 403/404 | Verify 4-way ID match: item XML, module filename, S3 key, PCI config |
| PCI scores everything wrong | `getResponse()` returns object not string | Return plain `"correct"` or `"incorrect"` string |
| PCI loads but interaction broken | JS error in module | Check browser console; test module at S3 URL directly |
| PCI intermittently blank | S3 eventual consistency | Add 200ms delay after upload, verify with HEAD request |

## API Errors

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 500 error on PUT | `<table>` inside `<p>`, wrong namespace, or malformed XML | Fix XHTML nesting, verify namespace declarations |
| 409 on POST | Entity already exists | Treat as success; use GET to retrieve existing entity |
| 400/422 on course POST | Missing `status` field (most common) | Include `"status": "active"` — it is required |
| 500 on resource POST | `lessonType` in resource metadata | Known server bug (2026-04-02): avoid lessonType in resource metadata, or retry |
| 404 on resource POST | Missing trailing slash on URL | Endpoint is `/resources/` with trailing slash (without slash = 422) |
| 404 on course POST (with "already exists") | Re-creating soft-deleted entity | Soft-deleted entities block re-creation with same sourcedId |
| Data lost after PUT update | PUT does full replace, fields omitted | GET first, modify only needed fields in response, PUT complete payload |
| Boolean attr error in XML | `allowfullscreen` not XHTML compliant | Use `allowfullscreen="allowfullscreen"` |
| Bare `&` causes parse error | Not escaped in XML context | Use `&amp;` everywhere in XML/XHTML |

## Structural Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Quiz shows 3 links per topic instead of 1 | Individual variant links instead of assessment bank | Create bank parent resource with `metadata.resources: [ids]`, link only bank |
| Lessons appear empty | Component-resource links missing | Create links (step 9 in push pipeline) |
| Components orphaned (not visible) | Missing `parent` or `courseComponent` field | Both fields must be set to parent's sourcedId |
| FRQ not graded | Missing ExternalApiScore customOperator | Add grader URL + rubric block to response processing |
| Items in wrong order | sortOrder not set or duplicated | Ensure unique integer sortOrder >= 1 per sibling level |

## Debugging Checklist

When something doesn't render correctly:

1. **Check the API response** -- did the POST/PUT return 200/201?
2. **GET the entity back** -- compare what the API stored vs what you sent
3. **Check browser console** -- JS errors indicate PCI or renderer issues
4. **Check network tab** -- 404s on S3 URLs indicate missing assets
5. **Try XML format** -- if JSON POST, re-push with `{"format": "xml", "xml": rawXml}`
6. **Validate XHTML** -- parse with `xml.etree.ElementTree.fromstring()` before pushing
7. **Check encoding** -- ensure UTF-8 throughout, no mojibake (see `math-and-formulas.md`)

## Prevention Rules

1. Always validate XML before POST: `ET.fromstring(xml_string)`
2. Always use XML format for non-choice, non-text-entry types
3. Always GET before PUT (to avoid losing fields)
4. Always checkpoint after every successful POST (to enable resume)
5. Always verify S3 uploads before referencing in API payloads
6. Never put `<table>`, `<div>`, or block elements inside `<p>` tags
7. Never use bare `&` -- always `&amp;`
8. Never trust that `grades` accepts integers -- always use strings
