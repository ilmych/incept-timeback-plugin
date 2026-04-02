# QTI Interaction Type Status Matrix

## Fully Working (API + Renderer)

| Type | JSON Safe | XML Required | Notes |
|------|-----------|-------------|-------|
| `choice` (MCQ) | Yes | Optional | Standard MCQ, 4 options |
| `extended-text` (FRQ) | Yes | Optional | Plain text response only |
| `match` | NO | Yes | JSON corrupts `directedPair` scoring |
| `order` | Yes | Optional | Sequencing / rank ordering |
| `text-entry` | Yes | Optional | Fill-in-blank (small response box) |
| `inline-choice` | NO | Yes | Dropdown in text |
| `hottext` | NO | Yes | Error spotting / select words |
| `hotspot` | NO | Yes | Click on image area |
| `select-point` | NO | Yes | Coordinate clicking |
| `graphic-gap-match` | NO | Yes | Drag labels onto graph (1 assoc at a time -- known bug) |
| `gap-match` | NO | Yes | Drag text into sentence blanks |
| `feedback-block` | NO | Yes | Post-response feedback |

### The JSON vs XML Rule

If a type says "NO" under JSON Safe, you MUST push it via XML (rawXml format). JSON POST will silently corrupt the scoring logic, and items will render but grade incorrectly.

```python
# For XML-required types:
payload = {
    "format": "xml",
    "xml": raw_xml_string,
    "metadata": { ... }
}
```

## API Accepts But Renderer Incomplete

These types can be created via API but have rendering issues in the student UI:

`slider`, `associate`, `graphic-order`, `graphic-associate`, `drawing`, `media`, `upload`, `template-processing`, `adaptive`

Do NOT use these for production content. Items will appear broken to students.

## PCI (Portable Custom Interactions)

For interaction types not natively supported, use PCI with custom JS modules:

- Requires S3-hosted JS module (see `s3-uploads.md`)
- typeIdentifier must match across: item XML, module filename, S3 key, and PCI config
- `getResponse()` must return a plain string (`"correct"` / `"incorrect"`), NOT an object

## HTML Rendering in Stimuli (Confirmed Working)

| Feature | Status | Notes |
|---------|--------|-------|
| Styled tables with inline CSS | Works | Must use inline `style=`, not `<style>` blocks |
| CSS flexbox | Works | Via inline styles |
| `<details>`/`<summary>` | Works | Collapsible sections |
| MathML | Works | With proper namespace |
| Inline SVG | Works | Validate XML first |
| `<iframe>` (YouTube) | Works | Use `allowfullscreen="allowfullscreen"` (XHTML) |
| `<sub>`/`<sup>` | Works | Chemical formulas, exponents |
| `<img>` with S3 src | Works | Full URL required |

## Does NOT Work in Stimuli

| Feature | What Happens |
|---------|-------------|
| JavaScript | Stripped by sanitizer |
| `<video>` tag | Not rendered |
| MathJax/LaTeX | Renders as raw text |
| `<style>` blocks | Stripped |
| Custom CSS classes | No stylesheet loaded, classes ignored |
| `<script>` tags | Stripped |

## Feedback Blocks

To show explanations after a student answers:

```xml
<qti-modal-feedback outcomeIdentifier="FEEDBACK" identifier="feedbackModal" showHide="show">
  <qti-content-body>
    <p>Explanation text here...</p>
  </qti-content-body>
</qti-modal-feedback>
```

Requirements:
- Outcome variable `FEEDBACK` must be declared in `outcomeDeclarations`
- Response processing must set FEEDBACK value
- Keep feedback under ~1000 chars (undocumented limit; longer text gets cut off)

## Interaction Selection Guide

| Need | Use | Why |
|------|-----|-----|
| Multiple choice | `choice` | Most reliable, JSON safe |
| Free response | `extended-text` | Simple, JSON safe |
| Matching/pairing | `match` | XML required but well-supported |
| Ordering/ranking | `order` | JSON safe |
| Fill in blank (word) | `text-entry` | JSON safe |
| Fill in blank (dropdown) | `inline-choice` | XML required |
| Select errors in text | `hottext` | XML required |
| Click on image | `hotspot` or `select-point` | XML required |
| Drag and drop | `gap-match` or `graphic-gap-match` | XML required |
| Complex interactive | PCI | Custom JS, most flexible |
