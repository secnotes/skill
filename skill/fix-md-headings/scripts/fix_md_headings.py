#!/usr/bin/env python3
"""
Fix Markdown heading levels using PDF bookmarks.

Headings not matched to PDF bookmarks are converted to plain text.
Some patterns are converted to bold, others to plain text.

Usage:
    python fix_md_headings.py <pdf_path> <md_path> [output_md]
"""

import json
import re
import os
import sys

# Special section titles that should be kept as headings even without bookmark match
# Only includes sections that are commonly found in NIST documents
SPECIAL_SECTIONS = {
    'ACKNOWLEDGEMENTS': 1,
    'ACKNOWLEDGMENTS': 1,
    'ABSTRACT': 1,
    'KEYWORDS': 1,
    'AUTHORITY': 1,
    'EXECUTIVE SUMMARY': 1,
    'INTRODUCTION': 1,
    'PREFACE': 1,
    'FOREWORD': 1,
    'TABLE OF CONTENTS': 1,
    'ERRATA': 1,
    'REFERENCES': 1,
    'GLOSSARY': 1,
    'INDEX': 1,
    'CONCLUSION': 1,
}

# Appendices that should have only ONE heading level (the main appendix title)
# All sub-headings in these appendices should be converted to plain text or bold
# D = Abbreviations/Acronyms list, E = Glossary, F = Change Log
SINGLE_HEADING_APPENDICES = ['D', 'E', 'F']

# Patterns that should be converted to plain text (not bold)
# These are typically body content that MinerU incorrectly marked as headings
PLAIN_TEXT_PATTERNS = [
    r'^Implement\s+',           # "Implement the security..."
    r'^Discussion:',            # "Discussion: ..."
    r'^Control:',               # "Control: ..."
    r'^Control Enhancements:',  # "Control Enhancements: ..."
    r'^Related Controls:',      # "Related Controls: ..."
    r'^Supplemental Guidance:', # "Supplemental Guidance: ..."
    r'^Priority and Baseline:', # "Priority and Baseline: ..."
    r'^Withdrawn:',             # "Withdrawn: ..."
    r'^Note:',                  # "Note: ..."
    r'^Example:',               # "Example: ..."
    r'^References:',            # "References: ..."
    r'^\d+\.\s+\[',             # "1. [text]" - list items
    r'^[a-z]\)\s+',             # "a) text", "b) text" - list items
    r'^\[[A-Z]+\]:',            # "[FISMA]: ..." - reference links
]

def extract_bookmarks(pdf_path):
    """Extract bookmarks from PDF using pdfminer"""
    try:
        from pdfminer.pdfparser import PDFParser
        from pdfminer.pdfdocument import PDFDocument
    except ImportError:
        print("Error: pdfminer.six not installed. Run: pip install pdfminer.six")
        sys.exit(1)
    
    bookmarks = []
    try:
        with open(pdf_path, 'rb') as f:
            parser = PDFParser(f)
            doc = PDFDocument(parser)
            try:
                outlines = doc.get_outlines()
                for level, title, dest, a, se in outlines:
                    if title:
                        bookmarks.append({
                            'level': level,
                            'title': title.strip(),
                        })
            except Exception as e:
                print(f"Warning: Could not extract outlines: {e}")
    except Exception as e:
        print(f"Error reading PDF: {e}")
        sys.exit(1)
    
    return bookmarks

def normalize_title(title):
    """Normalize title for matching"""
    if not title:
        return ''
    normalized = ' '.join(title.split())
    normalized = re.sub(r'\s+\d+F\s*', '', normalized)
    normalized = normalized.rstrip('.')
    return normalized.strip()

def is_plain_text_pattern(heading_text):
    """Check if heading matches a pattern that should be plain text (not bold)"""
    text = heading_text.strip()
    for pattern in PLAIN_TEXT_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    return False

def is_special_section(heading_text):
    """Check if heading is a special section that should be kept"""
    text_upper = heading_text.strip().upper()
    if text_upper in SPECIAL_SECTIONS:
        return True, SPECIAL_SECTIONS[text_upper]
    for special_title, level in SPECIAL_SECTIONS.items():
        if text_upper.startswith(special_title + ' ') or text_upper.startswith(special_title + '.'):
            return True, level
    return False, None

def is_valid_pattern_heading(heading_text):
    """
    Check if heading matches a valid pattern that should be kept.
    Returns (is_valid, level) tuple.
    
    Valid patterns:
    - Chapter titles: CHAPTER ONE, CHAPTER 1
    - Numbered sections: 1.1, 2.3.1 (NOT (1), (10), etc.)
    - Control codes: AC-1, AU-2, SA-8
    """
    text = heading_text.strip()
    text_upper = text.upper()
    
    # Chapter patterns = level 1
    if re.match(r'^CHAPTER\s+(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|\d+)', text_upper):
        return True, 1
    
    if re.match(r'^PART\s+(ONE|TWO|THREE|FOUR|FIVE|\d+)', text_upper):
        return True, 1
    
    # Numbered sections: 1.1, 2.3.1, etc. (NOT (1), (10), etc.)
    # Must start with digit, not parenthesis
    num_match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?\s+', text)
    if num_match:
        parts = [p for p in num_match.groups() if p]
        return True, min(len(parts) + 1, 5)
    
    # Control codes: AC-1, AU-2, SA-8, etc. = level 3
    if re.match(r'^[A-Z]{2}-\d+', text):
        return True, 3
    
    # Section keywords = level 2 (must be main content, not just contained)
    section_keywords_exact = [
        'PURPOSE AND APPLICABILITY',
        'PURPOSE',
        'TARGET AUDIENCE',
        'ORGANIZATION OF THIS PUBLICATION',
        'ORGANIZATION OF THIS',
        'RISK MANAGEMENT',
        'REQUIREMENTS AND CONTROLS',
        'CONTROL STRUCTURE AND ORGANIZATION',
        'CONTROL IMPLEMENTATION APPROACHES',
        'TRUSTWORTHINESS AND ASSURANCE',
        'EVIDENCE OF CONTROL IMPLEMENTATION',
    ]
    
    for kw in section_keywords_exact:
        if text_upper.startswith(kw) or text_upper == kw:
            return True, 2
    
    for kw in section_keywords_exact:
        if kw in text_upper and len(kw) > len(text_upper) * 0.7:
            return True, 2
    
    return False, None

def determine_heading_level(heading_text, prev_level=1):
    """
    Determine heading level from text patterns.
    Returns None if should be plain text.
    """
    text = heading_text.strip()
    text_upper = text.upper()
    
    # Check special sections first
    is_special, level = is_special_section(text)
    if is_special:
        return level
    
    # Check valid patterns
    is_valid, level = is_valid_pattern_heading(text)
    if is_valid:
        return level
    
    return None

def build_bookmark_map(bookmarks):
    """Build mapping of normalized titles to bookmark levels"""
    bookmark_map = {}
    for bm in bookmarks:
        normalized = normalize_title(bm['title']).lower()
        if normalized and len(normalized) > 3:
            if normalized not in bookmark_map or bm['level'] < bookmark_map[normalized]:
                bookmark_map[normalized] = bm['level']
    return bookmark_map

def match_heading_to_bookmark(heading_text, bookmark_map):
    """
    Try to match heading to a bookmark.
    Priority: exact match > startswith match > contains match > word overlap
    
    Returns matched level or None.
    """
    normalized_heading = normalize_title(heading_text).lower()
    
    # Priority 1: Exact match
    if normalized_heading in bookmark_map:
        return bookmark_map[normalized_heading]
    
    # Priority 2: Heading starts with bookmark title
    for bm_title, bm_level in bookmark_map.items():
        if normalized_heading.startswith(bm_title + ' ') or normalized_heading.startswith(bm_title):
            return bm_level
    
    # Priority 3: Bookmark title starts with heading
    for bm_title, bm_level in bookmark_map.items():
        if bm_title.startswith(normalized_heading + ' ') or bm_title.startswith(normalized_heading):
            return bm_level
    
    # Priority 4: Substring match
    for bm_title, bm_level in bookmark_map.items():
        if bm_title in normalized_heading or normalized_heading in bm_title:
            return bm_level
    
    # Priority 5: Word overlap (strict - require 80% overlap)
    if len(normalized_heading) > 10:
        heading_words = set(normalized_heading.split())
        for bm_title, bm_level in bookmark_map.items():
            if len(bm_title) <= 10:
                continue
            bookmark_words = set(bm_title.split())
            overlap = len(heading_words & bookmark_words)
            if overlap >= len(heading_words) * 0.8:
                return bm_level
    
    return None

def fix_headings(md_content, bookmarks):
    """
    Fix heading levels.
    - Matched headings: keep with proper level
    - Unmatched headings that look like body text: convert to plain text
    - Other unmatched headings: convert to **bold text**
    - Headings in Table of Contents without bookmark match: convert to **bold text**
    - Headings in single-heading appendices (D, E, F): convert to plain text or bold
    """
    lines = md_content.split('\n')
    fixed_lines = []
    stats = {
        'total_headings': 0,
        'kept_as_heading': 0,
        'converted_to_bold': 0,
        'converted_to_plain': 0,
        'level_distribution': {}
    }
    
    bookmark_map = build_bookmark_map(bookmarks) if bookmarks else {}
    prev_level = 1
    in_table_of_contents = False
    in_single_heading_appendix = False
    current_appendix = None
    
    for line in lines:
        # Detect if we're entering Table of Contents section
        if re.match(r'^#+\s*(TABLE\s+OF\s+CONTENTS|CONTENTS|TOC)\s*$', line, re.IGNORECASE):
            in_table_of_contents = True
            fixed_lines.append(line)
            continue
        
        # Detect if we're entering a single-heading appendix (D, E, F)
        appendix_match = re.match(r'^#+\s*APPENDIX\s+([D-F])\.[\s.]+', line, re.IGNORECASE)
        if appendix_match:
            current_appendix = appendix_match.group(1).upper()
            if current_appendix in SINGLE_HEADING_APPENDICES:
                in_single_heading_appendix = True
            fixed_lines.append(line)
            continue
        
        # Detect if we're entering a different appendix (A, B, C, etc.) - exit single-heading mode
        other_appendix_match = re.match(r'^#+\s*APPENDIX\s+([A-CG-Z])\.[\s.]+', line, re.IGNORECASE)
        if other_appendix_match:
            in_single_heading_appendix = False
            current_appendix = None
        
        # Detect if we're exiting Table of Contents (when we hit a main chapter)
        if in_table_of_contents:
            chapter_match = re.match(r'^#+\s*(CHAPTER\s+(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|\d+)|PART\s+(ONE|TWO|THREE|FOUR|FIVE|\d+)|REFERENCES|APPENDIX\s+[A-Z])\s*$', line, re.IGNORECASE)
            if chapter_match:
                in_table_of_contents = False
        match = re.match(r'^(#+)\s+(.+)$', line)
        if match:
            stats['total_headings'] += 1
            heading_text = match.group(2).strip()
            
            # Special handling for single-heading appendices (D, E, F)
            # In these appendices, only the main appendix title should be a heading
            # All sub-headings should be converted to plain text or bold
            if in_single_heading_appendix:
                # Check if it's a plain text pattern (e.g., term definitions in glossary)
                if is_plain_text_pattern(heading_text):
                    fixed_lines.append(heading_text)
                    stats['converted_to_plain'] += 1
                else:
                    # Convert to bold (for terms, abbreviations, etc.)
                    fixed_lines.append(f"**{heading_text}**")
                    stats['converted_to_bold'] += 1
                continue
            
            # Check if it's a plain text pattern first
            if is_plain_text_pattern(heading_text):
                fixed_lines.append(heading_text)
                stats['converted_to_plain'] += 1
                continue
            
            # Try bookmark match first
            matched_level = match_heading_to_bookmark(heading_text, bookmark_map)
            
            # Special handling for Table of Contents:
            # If in TOC and no bookmark match, convert to bold (not heading)
            if in_table_of_contents and matched_level is None:
                fixed_lines.append(f"**{heading_text}**")
                stats['converted_to_bold'] += 1
                continue
            
            # If no bookmark match, check pattern-based rules
            if matched_level is None:
                matched_level = determine_heading_level(heading_text, prev_level)
            
            if matched_level is not None:
                # Keep as heading with proper level
                new_level = matched_level
                if new_level > prev_level + 1:
                    new_level = prev_level + 1
                
                new_hashes = '#' * new_level
                fixed_lines.append(f"{new_hashes} {heading_text}")
                stats['kept_as_heading'] += 1
                stats['level_distribution'][new_level] = stats['level_distribution'].get(new_level, 0) + 1
                prev_level = new_level
            else:
                # No match - convert to **bold text**
                fixed_lines.append(f"**{heading_text}**")
                stats['converted_to_bold'] += 1
        else:
            fixed_lines.append(line)
    
    return '\n'.join(fixed_lines), stats

def main():
    if len(sys.argv) < 3:
        print("Usage: python fix_md_headings.py <pdf_path> <md_path> [output_md]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    md_path = sys.argv[2]
    output_md = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not output_md:
        base, ext = os.path.splitext(md_path)
        output_md = f"{base}_fixed{ext}"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)
    
    if not os.path.exists(md_path):
        print(f"Error: Markdown not found: {md_path}")
        sys.exit(1)
    
    print(f"Extracting bookmarks from: {pdf_path}")
    bookmarks = extract_bookmarks(pdf_path)
    print(f"Found {len(bookmarks)} bookmarks")
    
    print(f"Reading Markdown from: {md_path}")
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
    except UnicodeDecodeError:
        with open(md_path, 'r', encoding='gbk') as f:
            md_content = f.read()
    
    print("Fixing heading levels...")
    fixed_content, stats = fix_headings(md_content, bookmarks)
    
    print(f"Writing to: {output_md}")
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"\nDone!")
    print(f"  Total headings: {stats['total_headings']}")
    print(f"  Kept as headings: {stats['kept_as_heading']}")
    print(f"  Converted to bold: {stats['converted_to_bold']}")
    print(f"  Converted to plain: {stats['converted_to_plain']}")
    if stats['level_distribution']:
        print(f"  Level distribution: {stats['level_distribution']}")

if __name__ == "__main__":
    main()
