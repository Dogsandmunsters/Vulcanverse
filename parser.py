#!/usr/bin/env python3
"""
Vulcanverse Gamebook Parser

Parses markdown manuscript files into structured section data for
graph-based analysis and validation.
"""

import re
import json
import sys
from pathlib import Path

# Book metadata
BOOKS = {
    "The_Houses_of_the_Dead.md": {"book_num": 1, "title": "The Houses of the Dead"},
    "The_Hammer_of_the_Sun.md": {"book_num": 2, "title": "The Hammer of the Sun"},
    "The_Wild_Woods.md": {"book_num": 3, "title": "The Wild Woods"},
    "The_Pillars_of_the_Sky.md": {"book_num": 4, "title": "The Pillars of the Sky"},
    "Workshop_of_the_Gods.md": {"book_num": 5, "title": "Workshop of the Gods"},
}

# --- Regex patterns ---

# Section header: #### 123
RE_SECTION_HEADER = re.compile(r'^####\s+(\d+)\s*$', re.MULTILINE)

# Navigation targets: goto [**123**](#_123) or ?[**123**](#_123) or [**123**](#_123)
# Also bare "turn to 123" without markdown link
RE_GOTO_LINK = re.compile(r'(?:goto|turn to|go to|\?)\s*\[\*\*(\d+)\*\*\]', re.IGNORECASE)
RE_GOTO_BARE = re.compile(r'(?:turn to|go to|goto)\s+(\d+)', re.IGNORECASE)
# Arrow navigation: ► 123 or ► [**123**]
RE_ARROW = re.compile(r'►\s*(?:\[\*\*)?(\d+)', re.IGNORECASE)

# Codeword operations
# Check: "if you have the codeword X" or "if you have the codeword X or Y"
RE_CW_CHECK = re.compile(
    r'if you have the codeword\s+\*\*_([^_*]+)_\*\*', re.IGNORECASE
)
RE_CW_CHECK_OR = re.compile(
    r'if you have the codewords?\s+\*\*_([^_*]+)_\*\*\s+or\s+\*\*_([^_*]+)_\*\*', re.IGNORECASE
)
# Check negative: "if you do not have the codeword X" / "if you don't have the codeword X"
RE_CW_CHECK_NEG = re.compile(
    r"if you (?:do not|don't|don't) have the codeword\s+\*\*_([^_*]+)_\*\*", re.IGNORECASE
)
# Acquire: "get the codeword X" / "gain the codeword X" / "you now have the codeword X"
RE_CW_ACQUIRE = re.compile(
    r'(?:get|gain|you now have) the codeword\s+\*\*_([^_*]+)_\*\*', re.IGNORECASE
)
# Lose: "lose the codeword X" / "delete the codeword X"
RE_CW_LOSE = re.compile(
    r'(?:lose|delete|cross off) the codewords?\s+\*\*_([^_*]+)_\*\*', re.IGNORECASE
)
# Lose multiple: "lose the codewords X and Y"
RE_CW_LOSE_MULTI = re.compile(
    r'lose the codewords?\s+\*\*_([^_*]+)_\*\*(?:\s+and\s+\*\*_([^_*]+)_\*\*)?', re.IGNORECASE
)

# Tickbox operations
RE_TICKBOX = re.compile(r'\[TICKBOX\]', re.IGNORECASE)
RE_TICK_THE_BOX = re.compile(r'(?:put a tick|tick)\s+(?:in\s+)?(?:the|one of the)\s+box', re.IGNORECASE)
RE_BOX_TICKED = re.compile(r'(?:if\s+(?:the\s+)?box\s+is\s+ticked|if\s+there\s+was\s+a\s+tick)', re.IGNORECASE)
RE_BOX_EMPTY = re.compile(r'(?:box\s+is\s+(?:empty|not\s+ticked)|box\s+is\s+unticked)', re.IGNORECASE)

# Current Location
RE_SET_CURRENT_LOC = re.compile(
    r'(?:write|note)\s+(?:the\s+number\s+)?\*\*(\d+)\*\*\s+(?:in\s+)?(?:the\s+)?(?:current\s+location|your\s+current\s+location)',
    re.IGNORECASE
)
RE_SET_CURRENT_LOC2 = re.compile(
    r'note\s+that\s+your\s+current\s+location\s+is\s+(?:\*\*)?(\d+)(?:\*\*)?',
    re.IGNORECASE
)
RE_GOTO_CURRENT_LOC = re.compile(
    r'turn to (?:the section number written in )?(?:the )?(?:your )?current location',
    re.IGNORECASE
)

# Stat rolls
RE_STAT_ROLL = re.compile(
    r'make\s+(?:a|an)\s+(strength|grace|charm|ingenuity)(?:\s+or\s+(?:a|an)\s+(strength|grace|charm|ingenuity))?\s+roll\s+at\s+difficulty\s+(\d+)',
    re.IGNORECASE
)

# Dice rolls (non-attribute)
RE_DICE_ROLL = re.compile(r'roll\s+(?:two\s+dice|a\s+die|one\s+die|2d6|1d6)', re.IGNORECASE)

# Title operations
RE_TITLE_GAIN = re.compile(r'(?:gain|you now have|get|receive|earn)\s+the\s+title\s+\*\*([^*]+)\*\*', re.IGNORECASE)
RE_TITLE_CHECK = re.compile(r'if\s+you\s+have\s+the\s+title\s+\*\*([^*]+)\*\*', re.IGNORECASE)

# Item checks
RE_ITEM_CHECK = re.compile(r'if\s+you\s+have\s+(?:a|an|the|some)?\s*\*\*([^*]+)\*\*', re.IGNORECASE)

# Glory
RE_GLORY_GAIN = re.compile(r'(?:get|gain|add)\s+\+?(\d+)\s+glory', re.IGNORECASE)
RE_GLORY_LOSE = re.compile(r'(?:lose|subtract|deduct)\s+(\d+)\s+glory', re.IGNORECASE)
RE_GLORY_CHECK = re.compile(r'if\s+(?:you have|your)\s+(?:glory|Glory)\s+(?:is\s+)?(?:at least\s+)?(\d+)', re.IGNORECASE)

# Wound
RE_WOUND_TICK = re.compile(r'tick\s+(?:the|your)\s+wound\s+box', re.IGNORECASE)

# Scar
RE_SCAR = re.compile(r'(?:gain|get|add)\s+(?:a\s+)?(?:\+?(\d+)\s+)?scars?', re.IGNORECASE)

# Money
RE_MONEY_GAIN = re.compile(r'(?:gain|get|receive|find|take)\s+(\d+)\s+pyr', re.IGNORECASE)
RE_MONEY_LOSE = re.compile(r'(?:lose|pay|spend|costs?)\s+(\d+)\s+pyr', re.IGNORECASE)

# Attribute changes
RE_ATTR_CHANGE = re.compile(
    r'(?:add|gain|get)\s+\+?(\d+)\s+(?:to\s+(?:your\s+)?)?(strength|grace|charm|ingenuity)',
    re.IGNORECASE
)


def split_into_sections(text, book_num):
    """Split a markdown file into individual numbered sections."""
    sections = {}
    # Find all section headers and their positions
    headers = list(RE_SECTION_HEADER.finditer(text))

    for i, match in enumerate(headers):
        section_num = int(match.group(1))
        start = match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        sections[section_num] = body

    return sections


def extract_all_codewords(text):
    """Extract all codeword names mentioned in bold-italic format."""
    return re.findall(r'\*\*_([^_*]+)_\*\*', text)


def parse_section(section_num, text, book_num):
    """Parse a single section and extract all structured data."""
    result = {
        "section": section_num,
        "book": book_num,
        "outgoing_refs": [],
        "codeword_ops": [],
        "tickbox_ops": [],
        "current_location": {"sets": None, "uses_current_loc": False},
        "stat_rolls": [],
        "dice_rolls": False,
        "title_ops": [],
        "item_checks": [],
        "glory_ops": [],
        "wound": False,
        "scar": False,
        "money_ops": [],
        "attr_changes": [],
        "raw_text": text[:300],
    }

    # --- Outgoing references ---
    refs = set()
    for m in RE_GOTO_LINK.finditer(text):
        refs.add(int(m.group(1)))
    for m in RE_GOTO_BARE.finditer(text):
        refs.add(int(m.group(1)))
    for m in RE_ARROW.finditer(text):
        refs.add(int(m.group(1)))
    result["outgoing_refs"] = sorted(refs)

    # --- Codeword operations ---
    cw_ops = []
    for m in RE_CW_ACQUIRE.finditer(text):
        cw_ops.append({"op": "acquire", "codeword": m.group(1).strip().rstrip('.')})
    for m in RE_CW_LOSE.finditer(text):
        cw_ops.append({"op": "lose", "codeword": m.group(1).strip().rstrip('.')})
    # Also catch second codeword in "lose X and Y" patterns
    for m in RE_CW_LOSE_MULTI.finditer(text):
        if m.group(2):
            cw_ops.append({"op": "lose", "codeword": m.group(2).strip().rstrip('.')})
    for m in RE_CW_CHECK.finditer(text):
        cw_name = m.group(1).strip().rstrip('.')
        cw_ops.append({"op": "check", "codeword": cw_name})
    # Handle "codeword X or Y" patterns
    for m in RE_CW_CHECK_OR.finditer(text):
        cw_ops.append({"op": "check", "codeword": m.group(2).strip().rstrip('.')})
    for m in RE_CW_CHECK_NEG.finditer(text):
        cw_name = m.group(1).strip().rstrip('.')
        cw_ops.append({"op": "check_not", "codeword": cw_name})
    # Deduplicate
    seen = set()
    deduped = []
    for op in cw_ops:
        key = (op["op"], op["codeword"])
        if key not in seen:
            seen.add(key)
            deduped.append(op)
    result["codeword_ops"] = deduped

    # --- Tickbox operations ---
    tickbox_count = len(RE_TICKBOX.findall(text))
    if tickbox_count > 0:
        result["tickbox_ops"].append({"op": "has_tickbox", "count": tickbox_count})
    if RE_TICK_THE_BOX.search(text):
        result["tickbox_ops"].append({"op": "tick"})
    if RE_BOX_TICKED.search(text):
        result["tickbox_ops"].append({"op": "check_ticked"})
    if RE_BOX_EMPTY.search(text):
        result["tickbox_ops"].append({"op": "check_empty"})

    # --- Current Location ---
    m = RE_SET_CURRENT_LOC.search(text) or RE_SET_CURRENT_LOC2.search(text)
    if m:
        result["current_location"]["sets"] = int(m.group(1))
    if RE_GOTO_CURRENT_LOC.search(text):
        result["current_location"]["uses_current_loc"] = True

    # --- Stat rolls ---
    for m in RE_STAT_ROLL.finditer(text):
        roll = {"attribute": m.group(1).capitalize(), "difficulty": int(m.group(3))}
        if m.group(2):
            roll["or_attribute"] = m.group(2).capitalize()
        result["stat_rolls"].append(roll)

    # --- Dice rolls ---
    if RE_DICE_ROLL.search(text):
        result["dice_rolls"] = True

    # --- Title operations ---
    for m in RE_TITLE_GAIN.finditer(text):
        result["title_ops"].append({"op": "gain", "title": m.group(1).strip()})
    for m in RE_TITLE_CHECK.finditer(text):
        result["title_ops"].append({"op": "check", "title": m.group(1).strip()})

    # --- Glory ---
    for m in RE_GLORY_GAIN.finditer(text):
        result["glory_ops"].append({"op": "gain", "amount": int(m.group(1))})
    for m in RE_GLORY_LOSE.finditer(text):
        result["glory_ops"].append({"op": "lose", "amount": int(m.group(1))})
    for m in RE_GLORY_CHECK.finditer(text):
        result["glory_ops"].append({"op": "check", "amount": int(m.group(1))})

    # --- Wound ---
    if RE_WOUND_TICK.search(text):
        result["wound"] = True

    # --- Scar ---
    if RE_SCAR.search(text):
        result["scar"] = True

    # --- Money ---
    for m in RE_MONEY_GAIN.finditer(text):
        result["money_ops"].append({"op": "gain", "amount": int(m.group(1))})
    for m in RE_MONEY_LOSE.finditer(text):
        result["money_ops"].append({"op": "lose", "amount": int(m.group(1))})

    # --- Attribute changes ---
    for m in RE_ATTR_CHANGE.finditer(text):
        result["attr_changes"].append({
            "attribute": m.group(2).capitalize(),
            "change": int(m.group(1))
        })

    return result


def parse_book(filepath, limit=None):
    """Parse an entire book file. If limit is set, only parse that many sections."""
    path = Path(filepath)
    filename = path.name
    meta = BOOKS.get(filename, {"book_num": 0, "title": filename})
    book_num = meta["book_num"]

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    raw_sections = split_into_sections(text, book_num)

    parsed = {}
    count = 0
    for sec_num in sorted(raw_sections.keys()):
        parsed[sec_num] = parse_section(sec_num, raw_sections[sec_num], book_num)
        count += 1
        if limit and count >= limit:
            break

    return parsed


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Parse Vulcanverse gamebook sections")
    ap.add_argument("file", help="Path to markdown source file")
    ap.add_argument("--limit", type=int, default=None, help="Max sections to parse")
    ap.add_argument("--output", default=None, help="Output JSON file")
    ap.add_argument("--show", type=int, nargs="*", default=None,
                    help="Section numbers to display (if omitted, shows first 5)")
    args = ap.parse_args()

    parsed = parse_book(args.file, limit=args.limit)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(parsed, f, indent=2)
        print(f"Wrote {len(parsed)} sections to {args.output}")

    # Display selected sections
    show_nums = args.show
    if show_nums is None:
        show_nums = sorted(parsed.keys())[:5]

    for num in show_nums:
        if num in parsed:
            print(json.dumps(parsed[num], indent=2))
            print("---")
        else:
            print(f"Section {num} not found in parsed data")


if __name__ == "__main__":
    main()
