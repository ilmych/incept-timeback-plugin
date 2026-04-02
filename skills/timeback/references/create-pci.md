# Create PCI (Portable Custom Interaction) Items

This is the hardest Timeback integration. It took 9 iterations across probe items to get working. Every gotcha below was discovered the hard way. 388 PCI items now run this pattern in production.

## Endpoint

```
POST {QTI_BASE}/assessment-items
```

XML POST required: `{"format": "xml", "xml": "<qti-assessment-item ...>full XML</qti-assessment-item>"}`

## Known-Good QTI XML Template

Extracted from `tools/pci_widgets_chem/generator.py` (production, 388 items).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<qti-assessment-item
    xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0"
    identifier="{ITEM_ID}"
    title="{ITEM_TITLE}"
    adaptive="false"
    time-dependent="false">

  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="identifier">
    <qti-correct-response>
      <qti-value>correct</qti-value>
    </qti-correct-response>
  </qti-response-declaration>

  <qti-outcome-declaration identifier="SCORE" cardinality="single" base-type="float">
    <qti-default-value>
      <qti-value>0</qti-value>
    </qti-default-value>
  </qti-outcome-declaration>

  <qti-item-body>
    <qti-portable-custom-interaction
        response-identifier="RESPONSE"
        custom-interaction-type-identifier="{MODULE_NAME}"
        module="{MODULE_NAME}"
        data-item-path-uri="{S3_BASE_URL}">

      <qti-interaction-modules>
        <qti-interaction-module
            id="{MODULE_NAME}"
            primary-path="{S3_BASE_URL}{COURSE_PREFIX}/{MODULE_NAME}.js"/>
      </qti-interaction-modules>

      <qti-interaction-markup>
        <div class="pci-container" data-pci-config='{ESCAPED_CONFIG_JSON}'></div>
      </qti-interaction-markup>

    </qti-portable-custom-interaction>
  </qti-item-body>

  <qti-response-processing
      template="https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/match_correct.xml"/>

</qti-assessment-item>
```

## Known-Good AMD JS Module Template (TAO/OAT Pattern)

All methods live DIRECTLY on the hook object. No separate instance.

```javascript
define(['qtiCustomInteractionContext'], function(ctx) {
    'use strict';

    var hook = {
        id: -1,

        getTypeIdentifier: function() { return 'MODULE_NAME'; },

        // Called by platform -- NOT getInstance
        initialize: function(id, dom, config) {
            this.id = id;
            this.dom = dom;
            // Read config from data attribute
            var configEl = dom.querySelector('[data-pci-config]');
            this.config = configEl ? JSON.parse(configEl.dataset.pciConfig) : {};
            // Build UI here using this.dom and this.config
            // ...
            ctx.notifyReady(this);
        },

        // Called by platform on submit
        // MUST return PLAIN STRING -- NOT {base: {identifier: "correct"}}
        getResponse: function() {
            return this.isCorrect ? "correct" : "incorrect";
        },

        setResponse: function(response) {},
        resetResponse: function() {},

        getSerializedState: function() { return JSON.stringify({}); },
        setSerializedState: function(state) {},

        destroy: function() {
            // Clean up DOM content
            while (this.dom.firstChild) { this.dom.removeChild(this.dom.firstChild); }
        },
    };

    ctx.register(hook);
});
```

## The 10 PCI Gotchas (each discovered the hard way)

1. **TAO/OAT API, NOT IMS PCI v1**: Methods live on the hook object directly. The IMS pattern (`getInstance()` returning a separate instance) causes `getResponse()` to fail -- the platform calls `hook.getResponse()` and cannot find it because the method was on the returned instance, not the hook. Probe items v2-v5 all failed this way.

2. **typeIdentifier MUST match in 4 places**: `custom-interaction-type-identifier` in XML, `module` attribute in XML, `qti-interaction-module` `id`, and `getTypeIdentifier()` return value in JS. Use a plain module name (e.g., `"prediction_U1_L01_0"`). URN prefixes (`urn:incept:pci:...`) cause lookup mismatch -- probe items v3-v5 broke on this.

3. **primary-path includes the full URL with `.js` extension**: Production code (388 items) uses the full URL including `.js`. The S3 URL in `primary-path` is the complete path: `https://ai-first-incept-media.s3.amazonaws.com/pci/apchem/moduleName.js`.

4. **getResponse() returns PLAIN STRINGS**: Platform `JSON.stringify()`s whatever you return. If you return `{base: {identifier: "correct"}}`, it becomes the STRING `'{"base":{"identifier":"correct"}}'` which does NOT match `"correct"` in match_correct. Return `"correct"` or `"incorrect"` directly.

5. **`<properties>` does NOT work**: Platform strips custom `<property>` keys. `config.properties` only contains `itemPathUri` (the S3 base URL from `data-item-path-uri`). Use `data-pci-config` attribute on a div inside `<qti-interaction-markup>` instead. Probe item `pci-config-probe-6f287228` confirmed this.

6. **PCI-side scoring is the ONLY working pattern**: Platform only supports `match_correct` string comparison. The PCI evaluates its own rubric and returns `"correct"` or `"incorrect"`. Use `base-type="identifier"` (or `"string"`) + `match_correct` template. The PCI owns the rubric; the platform just matches strings.

7. **Never omit qti-correct-response**: Platform warns `EMPTY_CORRECT_RESPONSE` and scores everything as incorrect.

8. **S3 hosting requirements**: `ContentType: "application/javascript"` (NOT `text/javascript`). CORS: `GET`/`HEAD` from `*` origins (RequireJS fetches cross-origin). `CacheControl: "no-cache, no-store, must-revalidate"` during dev (S3 caches aggressively; a previous broken module may persist). Verify URL is accessible after upload.

9. **Config passing via data attribute**: HTML-escape the JSON for the `data-pci-config` attribute. The JS reads it with `JSON.parse(dom.querySelector('[data-pci-config]').dataset.pciConfig)`. Escape `&`, `<`, `>`, and `'` (since attribute is single-quoted in the XML).

10. **Point format mismatch**: `[x, y]` array in JS `getResponse()` but `"x y"` space-separated string in XML `qti-correct-response`. Only relevant for point-type interactions (not string/identifier scoring).

## Config Escaping (Python)

```python
import json

def escape_for_xml_attr(json_str: str) -> str:
    """Escape JSON string for single-quoted HTML attribute in XML."""
    return (
        json_str
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&#39;")
    )

config_json = json.dumps(params, ensure_ascii=False)
config_escaped = escape_for_xml_attr(config_json)
# Use in XML: data-pci-config='{config_escaped}'
```

## S3 Upload for PCI Modules

```python
import boto3, time, requests

s3 = boto3.client("s3")
s3.put_object(
    Bucket="ai-first-incept-media",
    Key=f"pci/{course_prefix}/{module_name}.js",
    Body=js_content.encode("utf-8"),
    ContentType="application/javascript",
    CacheControl="no-cache, no-store, must-revalidate",  # During dev
)
# Verify accessibility (S3 eventual consistency)
time.sleep(0.2)
url = f"https://ai-first-incept-media.s3.amazonaws.com/pci/{course_prefix}/{module_name}.js"
resp = requests.head(url, timeout=10)
assert resp.status_code == 200, f"S3 upload not accessible: {url}"
```

## Module ID Generation

Must be RequireJS-safe (alphanumeric + underscore only).

```python
import re

def make_module_id(lesson_key: str, widget_type: str, index: int) -> str:
    clean_key = re.sub(r"[^a-zA-Z0-9]", "_", lesson_key)
    return f"{widget_type}_{clean_key}_{index}"
```

## Composite FRQ with PCI Parts

Single `qti-assessment-item` with multiple interactions. Each gets its own response declaration with a unique identifier.

```xml
<qti-response-declaration identifier="RESPONSE_A" cardinality="single" base-type="string">
  <!-- text answer -->
</qti-response-declaration>
<qti-response-declaration identifier="RESPONSE_B" cardinality="single" base-type="identifier">
  <qti-correct-response><qti-value>correct</qti-value></qti-correct-response>
</qti-response-declaration>

<qti-item-body>
  <qti-extended-text-interaction response-identifier="RESPONSE_A" .../>
  <qti-portable-custom-interaction response-identifier="RESPONSE_B" ...>
    <!-- PCI for graph drawing -->
  </qti-portable-custom-interaction>
</qti-item-body>
```

## Response Format Reference

| base-type | getResponse() returns | correct-response in XML |
|-----------|----------------------|------------------------|
| `identifier` | `"correct"` (plain string) | `<qti-value>correct</qti-value>` |
| `string` | `"correct"` (plain string) | `<qti-value>correct</qti-value>` |
| `point` | `{base: {point: [x, y]}}` | `<qti-value>220 160</qti-value>` |

For identifier/string scoring: PCI evaluates its own rubric and returns `"correct"`/`"incorrect"`.

For point scoring: use `map_response_point.xml` template with `qti-area-mapping` (NOT `match_correct`).

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Module loads, graph renders, but Score: 0 | `getResponse()` returns `{base:{identifier:"correct"}}` | Return plain string `"correct"` |
| Module never loads, blank item | typeIdentifier mismatch between XML and JS | Make all 4 places match exactly |
| "EMPTY_CORRECT_RESPONSE" warning | Missing `qti-correct-response` element | Add it with `<qti-value>correct</qti-value>` |
| Config is empty in JS | Used `<properties>` instead of `data-pci-config` | Move config to data attribute |
| Old broken module cached | S3 `CacheControl` too aggressive | Set `no-cache` and upload fresh |
| Module 404 | Wrong S3 path or content type | Verify URL with `requests.head()` |
| `getResponse` not found | Used IMS `getInstance()` pattern | Move all methods onto hook object directly |

## Batch Creation Pattern

```python
import hashlib, json, time

def push_pci_item(session, qti_base, xml: str) -> str:
    payload = {"format": "xml", "xml": xml}
    resp = session.post(f"{qti_base}/assessment-items", json=payload)
    resp.raise_for_status()
    return resp.json()["identifier"]

# Checkpoint after each item for resume-on-failure
for i, item in enumerate(items):
    if item["module_id"] in completed:
        continue
    # 1. Upload JS to S3
    upload_to_s3(item["module_id"], item["js_source"])
    # 2. Generate QTI XML
    xml = generate_qti_xml(item)
    # 3. Push to API
    item_id = push_pci_item(session, QTI_BASE, xml)
    completed[item["module_id"]] = item_id
    save_checkpoint(completed)
    time.sleep(0.1)  # rate limiting
```
