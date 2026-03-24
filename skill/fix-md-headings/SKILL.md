---
name: fix-md-headings
description: Fix Markdown heading levels using PDF bookmarks. Use when: (1) MinerU or other OCR tools output all headings as level 1, (2) need to restore proper heading hierarchy in converted documents, (3) batch-fix multiple Markdown files, (4) working with NIST or technical documentation converted from PDF, (5) user asks to fix/correct/restore Markdown heading levels based on PDF bookmarks/outlines/table of contents, (6) user mentions PDF outline/bookmark/directory and Markdown heading hierarchy. Headings without bookmark match are converted to plain text.
---

# Fix Markdown Headings Skill

Restore proper heading hierarchy in Markdown files using PDF bookmarks as reference.

## Installation

This skill requires Python and pdfminer.six:

```bash
pip install pdfminer.six
```

## What This Skill Does

When converting PDFs to Markdown (especially with tools like MinerU), all headings often become level 1 (`#`). This skill:

1. **Extracts bookmarks** from the source PDF
2. **Matches headings** to PDF bookmarks
3. **Fixes heading levels** based on bookmark hierarchy
4. **Converts unmatched headings** to plain text or bold

### Special Sections

The following sections are always kept as headings, even without bookmark match:

- Acknowledgements / Acknowledgments
- Abstract
- Keywords
- Authority
- Executive Summary
- Introduction
- Preface / Foreword
- Table of Contents
- Errata
- References
- Glossary
- Index
- Conclusion

### Single-Heading Appendices

The following appendices should have **only one heading** (the main appendix title). All sub-headings in these appendices are converted to bold text or plain text:

- **Appendix D**: List of Abbreviations and Acronyms (abbreviation entries → bold)
- **Appendix E**: Glossary (term definitions → bold)
- **Appendix F**: Change Log (numbered list items → plain text)

### Pattern Recognition

The skill also recognizes these patterns as valid headings:

| Pattern | Example | Level |
|---------|---------|-------|
| Chapters | `CHAPTER ONE`, `CHAPTER 1` | 1 |
| Numbered sections | `1.1`, `2.3.1` | 2-4 |
| Control codes | `AC-1`, `AU-2` | 3 |

### Plain Text Patterns

The following patterns are converted to plain text (not bold):

| Pattern | Example |
|---------|---------|
| `Implement...` | `Implement the security...` |
| `Discussion:` | `Discussion: The principle...` |
| `Control:` | `Control: Enforce approved...` |
| `Control Enhancements:` | `Control Enhancements:...` |
| `Related Controls:` | `Related Controls: AC-3...` |
| `Withdrawn:` | `Withdrawn: Incorporated...` |
| `Note:` / `Example:` | `Note: This control...` |
| List items | `a) text`, `1. [text]` |

## Usage

### Basic Usage

```bash
py fix_md_headings.py <pdf_path> <md_path> [output_md]
```

### Examples

```bash
# Fix a single file
py fix_md_headings.py document.pdf document.md document_fixed.md

# Output to default location (adds _fixed suffix)
py fix_md_headings.py document.pdf document.md

# Batch fix multiple files
for $f in Get-ChildItem *.md {
    $pdf = $f.Name -replace '\.md$', '.pdf'
    py fix_md_headings.py $pdf $f.Name
}
```

## Script Location

```
skills/fix-md-headings/scripts/fix_md_headings.py
```

## How It Works

### Step 1: Extract PDF Bookmarks

```python
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument

with open(pdf_path, 'rb') as f:
    parser = PDFParser(f)
    doc = PDFDocument(parser)
    outlines = doc.get_outlines()
    # Returns: [(level, title, dest, a, se), ...]
```

### Step 2: Build Bookmark Map

Creates a mapping of normalized bookmark titles to their levels for fast matching.

### Step 3: Process Each Heading

For each Markdown heading:

1. **Check plain text patterns** - `Implement...`, `Discussion:`, etc. → plain text
2. **Try bookmark match** - Compare heading text with bookmark titles
3. **Check special sections** - Keep Acknowledgements, Abstract, etc.
4. **Check patterns** - Recognize chapter numbers, section numbers, control codes
5. **Decide**:
   - Plain text pattern → Remove `#`, keep as plain text
   - Bookmark match → Keep as heading with proper level
   - Special section → Keep as heading
   - Valid pattern → Keep as heading with pattern-based level
   - No match → Convert to **bold text**

### Step 4: Output Fixed Markdown

Writes corrected Markdown with proper heading hierarchy.

## Output Statistics

After running, the script reports:

```
Done!
  Total headings: 602
  Kept as headings: 389
  Converted to bold: 51
  Converted to plain: 162
  Level distribution: {1: 28, 2: 35, 3: 326}
```

## Example: Before and After

### Before (MinerU output)

```markdown
# AC-1 POLICY AND PROCEDURES
# Implement the security...
# Discussion: This control...
# Control: Enforce approved...
# (10) SECURITY AND PRIVACY...
```

### After (Fixed)

```markdown
### AC-1 POLICY AND PROCEDURES
Implement the security...
Discussion: This control...
Control: Enforce approved...
**(10) SECURITY AND PRIVACY...**
```

Note: 
- `Implement...`, `Discussion:`, `Control:` are converted to plain text
- `(10) SECURITY...` is converted to bold (not in PDF bookmarks)

## Troubleshooting

### Issue: Too many headings converted to text

Check if the PDF has bookmarks:
```bash
# Extract and review bookmarks
py extract_bookmarks.py document.pdf bookmarks.json
```

If PDF has no bookmarks, the script relies on pattern recognition only.

### Issue: Special section not recognized

Add it to the `SPECIAL_SECTIONS` dictionary in the script:
```python
SPECIAL_SECTIONS = {
    'YOUR_SECTION': 1,  # Add here
    'ACKNOWLEDGEMENTS': 1,
    ...
}
```

### Issue: Encoding errors

Ensure files are UTF-8 encoded:
```bash
Get-Content input.md -Encoding Default | Set-Content output.md -Encoding UTF8
```

## Limitations

- Requires PDF with embedded bookmarks for best results
- Pattern-based detection may not work for all document styles
- Very long heading texts may not match bookmarks exactly
- Non-English documents may need pattern adjustments
- Does not add headings that don't exist in the original Markdown or PDF

## Best Practices

1. **Always backup** original Markdown before fixing
2. **Review statistics** after fixing to ensure changes were made
3. **Spot-check** sections to verify correctness
4. **Use with PDF bookmarks** when available for best accuracy
5. **Don't expect perfect results** - some manual review may be needed

## Related Tools

- **MinerU** - PDF to Markdown conversion
- **pdfplumber** - PDF text extraction
- **markitdown** - Microsoft's PDF to Markdown tool
- **pandoc** - Document format conversion
