# Create Match, DnD, and Other Complex Interaction Types

All types on this page MUST use XML POST. The API's JSON-to-XML converter silently drops child elements for these types. Items return 200 OK but render broken/empty in the student UI. This is the single most expensive gotcha in the project.

## Endpoint

```
POST {QTI_BASE}/assessment-items
```

XML POST format: `{"format": "xml", "xml": "<qti-assessment-item ...>full XML</qti-assessment-item>"}`

## Namespace

MUST be: `http://www.imsglobal.org/xsd/imsqtiasi_v3p0` (NOT `imsqti_v3p0` -- missing `asi` causes 500 error). Omitting the namespace entirely also causes 500 error (XML parser cannot extract identifier/title without it).

---

## Match Interaction (Classify / Sort / DnD)

The most common complex type. Students drag items into categories.

### Known-Good XML Template

Extracted from `tools/lesson_assembler/fix_scenario_items.py` (production, 11 scenario items).

```xml
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0"
  identifier="{ITEM_ID}" title="{TITLE}" adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="multiple" base-type="directedPair">
    <qti-correct-response>
      <qti-value>item1 category1</qti-value>
      <qti-value>item2 category2</qti-value>
      <qti-value>item3 category1</qti-value>
    </qti-correct-response>
  </qti-response-declaration>
  <qti-outcome-declaration identifier="SCORE" cardinality="single" base-type="float">
    <qti-default-value><qti-value>0</qti-value></qti-default-value>
  </qti-outcome-declaration>
  <qti-item-body>
    <p>Context paragraph here.</p>
    <p><strong>Classify each item into the correct category.</strong></p>
    <qti-match-interaction response-identifier="RESPONSE" shuffle="true" max-associations="{N_PAIRS}">
      <qti-simple-match-set>
        <!-- Source items (draggable) -->
        <qti-simple-associable-choice identifier="item1" match-max="1">GDP</qti-simple-associable-choice>
        <qti-simple-associable-choice identifier="item2" match-max="1">CPI</qti-simple-associable-choice>
        <qti-simple-associable-choice identifier="item3" match-max="1">Unemployment Rate</qti-simple-associable-choice>
      </qti-simple-match-set>
      <qti-simple-match-set>
        <!-- Target categories (drop zones) -->
        <qti-simple-associable-choice identifier="category1" match-max="{MAX_ITEMS}">Leading Indicator</qti-simple-associable-choice>
        <qti-simple-associable-choice identifier="category2" match-max="{MAX_ITEMS}">Lagging Indicator</qti-simple-associable-choice>
      </qti-simple-match-set>
    </qti-match-interaction>
  </qti-item-body>
  <qti-response-processing template="https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/match_correct"/>
</qti-assessment-item>
```

### Match Interaction Hard Rules

1. **JSON POST corrupts directedPair values**: `"i1 c1"` becomes `"i 1"` through the converter (empirically verified 2026-04-02). The JSON-to-XML converter splits on spaces in the pair value, mangling it. MUST use XML POST.

2. **`match-max=0` means "accept zero matches"**, NOT "unlimited". Set `match-max` on target categories to the actual number of items that can be dropped there (use total item count as safe maximum).

3. **Value format is plain text space-separated pair**: `<qti-value>source_id target_id</qti-value>`. Do NOT wrap in `<qti-directed-pair>` -- that element is non-standard and breaks scoring.

4. **`max-associations` on `qti-match-interaction`**: Set to the total number of correct pairs. Setting to `0` at the interaction level has ambiguous platform behavior -- prefer the actual count.

5. **Source item `match-max`**: How many categories each source maps to. Usually `1` (each item goes to one category). If an item can belong to multiple categories, increase accordingly. Compute from your correct_pairs data.

6. **Target category `match-max`**: How many items each category can accept. Set to `len(items)` to allow all items into any category.

### Match Interaction Python Builder

```python
QTI_NS = "http://www.imsglobal.org/xsd/imsqtiasi_v3p0"

def xml_escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))

def build_match_xml(
    identifier: str,
    title: str,
    prompt_html: str,
    items: list[dict],       # [{"id": "item1", "text": "GDP"}, ...]
    categories: list[dict],  # [{"id": "cat1", "text": "Leading"}, ...]
    correct_pairs: list[list[str]],  # [["item1", "cat1"], ["item2", "cat2"]]
) -> str:
    pair_values = "\n      ".join(
        f"<qti-value>{xml_escape(p[0])} {xml_escape(p[1])}</qti-value>"
        for p in correct_pairs
    )
    # Per-item match-max: how many categories each source maps to
    item_counts = {}
    for p in correct_pairs:
        item_counts[p[0]] = item_counts.get(p[0], 0) + 1

    source_choices = "\n        ".join(
        f'<qti-simple-associable-choice identifier="{xml_escape(i["id"])}" '
        f'match-max="{item_counts.get(i["id"], 1)}">'
        f'{xml_escape(i["text"])}</qti-simple-associable-choice>'
        for i in items
    )
    max_items = len(items)
    target_choices = "\n        ".join(
        f'<qti-simple-associable-choice identifier="{xml_escape(c["id"])}" '
        f'match-max="{max_items}">'
        f'{xml_escape(c["text"])}</qti-simple-associable-choice>'
        for c in categories
    )

    return f"""<qti-assessment-item xmlns="{QTI_NS}"
  identifier="{xml_escape(identifier)}" title="{xml_escape(title[:80])}"
  adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="multiple" base-type="directedPair">
    <qti-correct-response>
      {pair_values}
    </qti-correct-response>
  </qti-response-declaration>
  <qti-outcome-declaration identifier="SCORE" cardinality="single" base-type="float">
    <qti-default-value><qti-value>0</qti-value></qti-default-value>
  </qti-outcome-declaration>
  <qti-item-body>
    {prompt_html}
    <qti-match-interaction response-identifier="RESPONSE" shuffle="true"
        max-associations="{len(correct_pairs)}">
      <qti-simple-match-set>
        {source_choices}
      </qti-simple-match-set>
      <qti-simple-match-set>
        {target_choices}
      </qti-simple-match-set>
    </qti-match-interaction>
  </qti-item-body>
  <qti-response-processing
      template="https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/match_correct"/>
</qti-assessment-item>"""
```

### Parsing Match Items (for feedback/fix scripts)

```python
import re

def parse_correct_response(xml: str) -> list[tuple[str, str]]:
    """Extract directed pairs from qti-correct-response."""
    pairs = []
    for m in re.finditer(r"<qti-value>([^<]+)</qti-value>", xml):
        parts = m.group(1).strip().split(" ", 1)
        if len(parts) == 2:
            pairs.append((parts[0], parts[1]))
    return pairs

def parse_match_sets(xml: str) -> tuple[dict, dict]:
    """Parse source items and target categories from match-set blocks."""
    pattern = r'<qti-simple-associable-choice\s+identifier="(\w+)"\s+match-max="\d+">([^<]+)'
    matches = re.findall(pattern, xml)
    # First match-set = sources, second = targets
    # (Need context-aware parsing for production -- see fix_match_feedback.py)
    return matches
```

---

## Hotspot Interaction

Students click on an image region. JSON POST strips `<qti-hotspot-choice>` elements.

### Known-Good XML Template

Extracted from `tools/graph_builder_generator/push.py` (production, 18 items).

```xml
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0"
    identifier="{ITEM_ID}" title="{TITLE}" adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="identifier">
    <qti-correct-response><qti-value>{CORRECT_HOTSPOT_ID}</qti-value></qti-correct-response>
  </qti-response-declaration>
  <qti-outcome-declaration identifier="SCORE" cardinality="single" base-type="float">
    <qti-default-value><qti-value>0</qti-value></qti-default-value>
  </qti-outcome-declaration>
  <qti-item-body>
    <qti-hotspot-interaction response-identifier="RESPONSE" max-choices="1">
      <qti-prompt><p>Click on the equilibrium point.</p></qti-prompt>
      <object data="{IMAGE_DATA_URI}" type="image/svg+xml" width="400" height="300"/>
      <qti-hotspot-choice identifier="hs1" shape="circle" coords="220,160,25"/>
      <qti-hotspot-choice identifier="hs2" shape="circle" coords="100,200,25"/>
    </qti-hotspot-interaction>
  </qti-item-body>
  <qti-response-processing template="https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/match_correct"/>
</qti-assessment-item>
```

### Coords Format

| Shape | Format | Example | Notes |
|-------|--------|---------|-------|
| `circle` | `cx,cy,r` | `220,160,25` | 25px radius for graph points |
| `rect` | `x1,y1,x2,y2` | `195,135,245,185` | Top-left, bottom-right |
| `poly` | `x1,y1,x2,y2,...` | `100,100,200,100,150,200` | Vertices in order |

Tolerance guidance: 25px radius works for graph equilibrium points. For larger targets (curves, regions), use `rect` or larger radius.

### Coordinate Conversion (Percentage to Pixel)

For SVG graphs at 400x300:

```python
def pct_to_px(x_pct: float, y_pct: float, r_pct: float = 5.0,
              w: int = 400, h: int = 300) -> tuple[int, int, int]:
    return round(x_pct / 100 * w), round(y_pct / 100 * h), round(r_pct / 100 * min(w, h))
```

### SVG Alignment Rule

Visual marker positions in SVG MUST derive FROM the QTI hotspot coord declarations, not independently. If your SVG shows a circle at (220,160) but the hotspot coords say (200,140), students will click the visual marker and miss the hotspot.

---

## Graphic Gap-Match (Drag Labels onto Image)

Students drag text labels onto image regions. JSON POST strips `<qti-gap-text>` elements.

### Known-Good XML Template

Extracted from `tools/graph_builder_generator/push.py` (production, 21 items).

```xml
<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqtiasi_v3p0"
    identifier="{ITEM_ID}" title="{TITLE}" adaptive="false" time-dependent="false">
  <qti-response-declaration identifier="RESPONSE" cardinality="multiple" base-type="directedPair">
    <qti-correct-response>
      <qti-value>label1 hs1</qti-value>
      <qti-value>label2 hs2</qti-value>
    </qti-correct-response>
  </qti-response-declaration>
  <qti-outcome-declaration identifier="SCORE" cardinality="single" base-type="float">
    <qti-default-value><qti-value>0</qti-value></qti-default-value>
  </qti-outcome-declaration>
  <qti-item-body>
    <qti-graphic-gap-match-interaction response-identifier="RESPONSE">
      <qti-prompt><p>Drag each label to the correct position on the graph.</p></qti-prompt>
      <object data="{IMAGE_DATA_URI}" type="image/svg+xml" width="400" height="300"/>
      <qti-gap-text identifier="label1" match-max="1">Supply Curve</qti-gap-text>
      <qti-gap-text identifier="label2" match-max="1">Demand Curve</qti-gap-text>
      <qti-gap-text identifier="distractor1" match-max="1">Money Supply</qti-gap-text>
      <qti-associable-hotspot identifier="hs1" shape="circle" coords="220,160,25" match-max="1"/>
      <qti-associable-hotspot identifier="hs2" shape="circle" coords="300,100,25" match-max="1"/>
    </qti-graphic-gap-match-interaction>
  </qti-item-body>
  <qti-response-processing template="https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/match_correct"/>
</qti-assessment-item>
```

### Graphic Gap-Match Rules

- Correct response: `<qti-value>gap_text_id hotspot_id</qti-value>` (space-separated)
- Distractor `qti-gap-text` elements have no corresponding hotspot -- they exist to make the drag pool harder
- `match-max="1"` on both gap-text and hotspot means each label placed once, each hotspot accepts one label
- **Known platform limitation**: only 1 association at a time works reliably in some platform versions

### Drop Zone Visual Indicators

For SVG-based images, add dashed-circle indicators at hotspot coordinates so students can see where to drop. See `tools/graph_builder_generator/fix_dropzones.py` for the production pattern: parse hotspot coords, remove existing indicators, add standardized dashed circles, re-encode SVG.

### Python Builder for Graphic Gap-Match

```python
def build_gap_match_xml(
    identifier: str, title: str, instructions: str,
    image_data_uri: str,
    gaps: list[dict],         # [{"id": "label1", "label": "Supply Curve",
                              #   "target_x_pct": 55.0, "target_y_pct": 53.3}]
    distractors: list[str],   # ["Money Supply", "Aggregate Demand"]
) -> str:
    correct_pairs = []
    gap_text_elements = []
    hotspot_elements = []

    for idx, gap in enumerate(gaps):
        hs_id = f"hs{idx + 1}"
        correct_pairs.append(
            f"      <qti-value>{xml_escape(gap['id'])} {xml_escape(hs_id)}</qti-value>")
        gap_text_elements.append(
            f'      <qti-gap-text identifier="{xml_escape(gap["id"])}" '
            f'match-max="1">{xml_escape(gap["label"])}</qti-gap-text>')
        x_px, y_px, r_px = pct_to_px(gap["target_x_pct"], gap["target_y_pct"], 5)
        hotspot_elements.append(
            f'      <qti-associable-hotspot identifier="{xml_escape(hs_id)}" '
            f'shape="circle" coords="{x_px},{y_px},{r_px}" match-max="1"/>')

    for d_idx, label in enumerate(distractors):
        gap_text_elements.append(
            f'      <qti-gap-text identifier="distractor_{d_idx + 1}" '
            f'match-max="1">{xml_escape(label)}</qti-gap-text>')

    # ... assemble into full XML (same pattern as match interaction above)
```

---

## Hottext Interaction

Students select words/phrases in a passage. JSON POST strips `<qti-hottext>` elements entirely.

```xml
<qti-item-body>
  <qti-hottext-interaction response-identifier="RESPONSE" max-choices="2">
    <qti-prompt><p>Select the two incorrect claims.</p></qti-prompt>
    <p>The market reaches <qti-hottext identifier="ht1">surplus</qti-hottext> when
    quantity supplied exceeds <qti-hottext identifier="ht2">quantity demanded</qti-hottext>
    at a price <qti-hottext identifier="ht3">below</qti-hottext> equilibrium.</p>
  </qti-hottext-interaction>
</qti-item-body>
```

Response declaration: `cardinality="multiple"` with `base-type="identifier"`.

---

## Gap-Match (Drag Text into Sentence Blanks)

Students drag text labels into blanks within sentences. JSON POST strips `<qti-gap-text>` elements.

```xml
<qti-item-body>
  <qti-gap-match-interaction response-identifier="RESPONSE">
    <qti-gap-text identifier="gt1" match-max="1">elastic</qti-gap-text>
    <qti-gap-text identifier="gt2" match-max="1">inelastic</qti-gap-text>
    <qti-gap-text identifier="gt3" match-max="1">unit elastic</qti-gap-text>
    <p>When the percentage change in quantity demanded is greater than the
    percentage change in price, demand is <qti-gap identifier="G1"/>.</p>
  </qti-gap-match-interaction>
</qti-item-body>
```

Correct response: `<qti-value>gt1 G1</qti-value>` (gap-text-id gap-id pair).
Response declaration: `cardinality="multiple"`, `base-type="directedPair"`.

---

## Inline-Choice (Dropdown in Text)

Dropdown-in-text interaction. JSON POST strips inline choice elements.

```xml
<qti-item-body>
  <p>An increase in supply causes equilibrium price to
    <qti-inline-choice-interaction response-identifier="RESPONSE" shuffle="false">
      <qti-inline-choice identifier="ic1">increase</qti-inline-choice>
      <qti-inline-choice identifier="ic2">decrease</qti-inline-choice>
      <qti-inline-choice identifier="ic3">stay the same</qti-inline-choice>
    </qti-inline-choice-interaction>.</p>
</qti-item-body>
```

Response declaration: `cardinality="single"`, `base-type="identifier"`.

---

## Select-Point (Coordinate Clicking on Image)

Students click a coordinate on an image. JSON POST strips `<qti-area-mapping>`.

```xml
<qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="point">
  <qti-correct-response>
    <qti-value>220 160</qti-value>
  </qti-correct-response>
  <qti-area-mapping default-value="0">
    <qti-area-map-entry shape="circle" coords="220,160,25" mapped-value="1"/>
  </qti-area-mapping>
</qti-response-declaration>
```

Use `map_response_point.xml` response processing template (NOT `match_correct` -- that requires exact pixel match which is impossible for humans).

Note: point format is `"x y"` space-separated string in XML, `[x, y]` array in JS PCI responses.

---

## Common Failures Across All Complex Types

| Symptom | Cause | Fix |
|---------|-------|-----|
| Item saves (200 OK) but renders empty | Used JSON POST instead of XML POST | Re-push with `{"format": "xml", "xml": ...}` |
| 500 error on POST | Wrong namespace (`imsqti_v3p0` not `imsqtiasi_v3p0`) | Fix namespace string |
| Match scoring always 0 | `<qti-directed-pair>` wrapper around values | Use plain text: `<qti-value>src tgt</qti-value>` |
| Match accepts zero drops | `match-max="0"` on categories | Set to actual item count |
| Hotspot clicks wrong area | SVG visual markers don't match QTI coords | Derive markers from coords |
| Gap-match only scores 1 pair | Platform graphic-gap-match limitation | Design around 1-association constraint |
| Dropdown not visible | JSON POST stripped inline-choice elements | Re-push with XML POST |
| DnD accepts no items in category | `max-associations="0"` | Set to total pair count |

## Batch Push Pattern

```python
import time

def push_complex_item(session, qti_base, xml: str) -> str:
    """Push an item that requires XML POST."""
    payload = {"format": "xml", "xml": xml}
    resp = session.post(f"{qti_base}/assessment-items", json=payload)
    if resp.status_code == 409:  # Already exists -- idempotent
        return identifier
    resp.raise_for_status()
    return resp.json()["identifier"]

# Checkpoint after each item
for item in items:
    if item["id"] in completed:
        continue
    xml = build_match_xml(item)  # or build_hotspot_xml, etc.
    item_id = push_complex_item(session, QTI_BASE, xml)
    completed[item["id"]] = item_id
    save_checkpoint(completed)
    time.sleep(0.1)
```
