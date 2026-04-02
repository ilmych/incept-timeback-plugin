# Math and Chemical Formula Notation in QTI

## What Works

| Method | Use Case | Reliability |
|--------|----------|-------------|
| MathML | Fractions, integrals, complex expressions | Native renderer support |
| Unicode sub/superscripts | Chemical formulas, simple exponents | Universally reliable |
| `<sub>`/`<sup>` HTML tags | Stimuli and item prompts | Works in all contexts |
| Inline SVG | Complex diagrams, labeled graphs | Works in stimuli |

## What Does NOT Work

- **LaTeX** (`$\frac{1}{2}$`) -- renders as raw text
- **MathJax** -- not loaded by platform
- **JavaScript in stimuli** -- stripped by sanitizer

## MathML

Namespace: `http://www.w3.org/1998/Math/MathML`

```xml
<math xmlns="http://www.w3.org/1998/Math/MathML">
  <mfrac><mn>1</mn><mn>2</mn></mfrac>
</math>
```

Key elements: `<mfrac>`, `<msqrt>`, `<msub>`, `<msup>`, `<msubsup>`, `<mrow>`, `<mi>`, `<mn>`, `<mo>`

## Unicode Chemical Formula Conversion

```python
SUBSCRIPT_MAP = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")
SUPERSCRIPT_MAP = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")

def to_subscript(text: str) -> str:
    return text.translate(SUBSCRIPT_MAP)

def to_superscript(text: str) -> str:
    return text.translate(SUPERSCRIPT_MAP)
```

### Common Conversions

| Raw | Correct | Method |
|-----|---------|--------|
| `CO2` | CO₂ | `"CO" + to_subscript("2")` |
| `H2O` | H₂O | `"H" + to_subscript("2") + "O"` |
| `Al2O3` | Al₂O₃ | Subscript digits after element symbols |
| `Ca2+` | Ca²⁺ | Superscript for charges |
| `Fe3+` | Fe³⁺ | Superscript for charges |
| `SO4^2-` | SO₄²⁻ | Subscript for count, superscript for charge |

## Known Garbled Patterns (from PDF Extraction)

Space-separated atoms: `"C 2H 5 OH"` should be `"C₂H₅OH"`

MathType noise (from Word/PDF):
```python
import re
text = re.sub(r'MathType@MTEF@[^\s<]{10,}', '', text)
```

## Encoding Corruption Fix

These mojibake patterns appear when UTF-8 is read as Latin-1:

| Garbled | Correct | Unicode |
|---------|---------|---------|
| `Ã—` | x (multiply) | U+00D7 |
| `Ï€` | pi | U+03C0 |
| `â‰ˆ` | approximately | U+2248 |
| `Ã¸` | o-slash | U+00F8 |
| `â†'` | right arrow | U+2192 |
| `Î"` | Delta | U+0394 |

Fix:
```python
def fix_mojibake(text: str) -> str:
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text
```

## SVG Math Gotchas

1. **Bare `&`** in SVG text or attributes -- must be `&amp;`
2. **HTML entities** -- convert to Unicode (`&Delta;` to the actual character)
3. **Always validate** before embedding:

```python
from xml.etree import ElementTree as ET

def validate_svg(svg_text: str) -> bool:
    try:
        ET.fromstring(svg_text)
        return True
    except ET.ParseError as e:
        print(f"Invalid SVG: {e}")
        return False
```

4. **SVG answer labels** -- LLMs sometimes label graph points with actual answers. Use neutral markers (A, B, C) or geometric shapes, never answer values.

## MathML to Unicode Fallback

When MathML is overkill (simple formulas), convert `<msub>`/`<msup>` to Unicode:

```python
import re

def mathml_sub_to_unicode(mathml: str) -> str:
    """Convert simple MathML subscripts to Unicode."""
    pattern = r'<msub>\s*<mi>(\w+)</mi>\s*<mn>(\d+)</mn>\s*</msub>'
    def replace(m):
        return m.group(1) + m.group(2).translate(SUBSCRIPT_MAP)
    return re.sub(pattern, replace, mathml)
```

## Equilibrium and Reaction Arrows

| Symbol | Unicode | Use |
|--------|---------|-----|
| Right arrow | U+2192 | Irreversible reaction |
| Equilibrium | U+21CC | Reversible reaction |
| Delta (heat) | U+0394 | Above arrow for heating |
| Degree | U+00B0 | Temperature units |
