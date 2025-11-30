"""Parser for extracting fort entries from HTML pages."""

import re
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
from dataclasses import dataclass, field

from config import FLAG_NATIONALITY


@dataclass
class FortEntry:
    """Represents a parsed fort entry."""

    name_primary: str
    dates_raw: str = ""
    location_text: str = ""
    description_raw: str = ""
    entry_raw: str = ""
    alt_names: List[str] = field(default_factory=list)
    nationalities: List[str] = field(default_factory=list)
    periods: List[dict] = field(default_factory=list)
    earliest_year: Optional[int] = None
    latest_year: Optional[int] = None


def extract_nationalities(html_fragment: str) -> List[str]:
    """Extract nationalities from flag image references in HTML."""
    nationalities = []
    # Match flag image patterns: britishflag.gif, usaflag1.gif, etc.
    flag_pattern = r"([a-z]+flag\d*)\.gif"
    for match in re.finditer(flag_pattern, html_fragment, re.IGNORECASE):
        flag_name = match.group(1).lower()
        nationality = FLAG_NATIONALITY.get(flag_name)
        if nationality and nationality not in nationalities:
            nationalities.append(nationality)
    return nationalities


def parse_date_ranges(dates_raw: str) -> Tuple[List[dict], Optional[int], Optional[int]]:
    """
    Parse date string into structured periods.

    Examples:
        "(1675)" -> [{"start": 1675, "end": 1675}]
        "(1864 - 1871)" -> [{"start": 1864, "end": 1871}]
        "(1775, 1811 - 1814, 1898 - 1899)" -> [{"start": 1775}, {"start": 1811, "end": 1814}, ...]
        "(1837 - 1845/1854)" -> [{"start": 1837, "end": 1845}, {"start": None, "end": 1854}] (ambiguous)

    Returns:
        (list of period dicts, earliest_year, latest_year)
    """
    periods = []
    all_years = []

    # Clean the string
    cleaned = dates_raw.strip("() ")
    if not cleaned:
        return [], None, None

    # Split by comma to get individual date entries
    parts = [p.strip() for p in cleaned.split(",")]

    for i, part in enumerate(parts):
        if not part:
            continue

        period = {"period_order": i}

        # Handle ranges with dash/en-dash: "1864 - 1871" or "1864-1871"
        range_match = re.match(r"(\d{4})\s*[-–]\s*(\d{4})", part)
        if range_match:
            start_year = int(range_match.group(1))
            end_year = int(range_match.group(2))
            period["start_year"] = start_year
            period["end_year"] = end_year
            all_years.extend([start_year, end_year])
            periods.append(period)
            continue

        # Handle "unknown" end: "1864 - unknown"
        unknown_end_match = re.match(r"(\d{4})\s*[-–]\s*unknown", part, re.IGNORECASE)
        if unknown_end_match:
            start_year = int(unknown_end_match.group(1))
            period["start_year"] = start_year
            period["end_year"] = None
            all_years.append(start_year)
            periods.append(period)
            continue

        # Handle ambiguous slash dates: "1845/1854" (could mean 1845 or 1854, or range)
        slash_match = re.match(r"(\d{4})/(\d{4})", part)
        if slash_match:
            # Treat as "possibly ended in either year" - store both
            year1 = int(slash_match.group(1))
            year2 = int(slash_match.group(2))
            period["start_year"] = None
            period["end_year"] = year2
            period["period_notes"] = f"Ambiguous: {year1}/{year2}"
            all_years.extend([year1, year2])
            periods.append(period)
            continue

        # Handle single year: "1675"
        single_match = re.match(r"(\d{4})", part)
        if single_match:
            year = int(single_match.group(1))
            period["start_year"] = year
            period["end_year"] = None  # Unknown end
            all_years.append(year)
            periods.append(period)
            continue

        # Handle "ca." or "c." dates: "ca. 1750"
        circa_match = re.match(r"c(?:a)?\.?\s*(\d{4})", part, re.IGNORECASE)
        if circa_match:
            year = int(circa_match.group(1))
            period["start_year"] = year
            period["period_notes"] = "Approximate date"
            all_years.append(year)
            periods.append(period)
            continue

        # Handle century references: "18th century"
        century_match = re.match(r"(\d+)(?:st|nd|rd|th)\s+century", part, re.IGNORECASE)
        if century_match:
            century = int(century_match.group(1))
            # 18th century = 1700s
            period["start_year"] = (century - 1) * 100
            period["end_year"] = century * 100 - 1
            period["period_notes"] = f"{century}th century"
            all_years.extend([period["start_year"], period["end_year"]])
            periods.append(period)
            continue

        # If we can't parse it, store the raw text as a note
        if part:
            period["period_notes"] = f"Unparsed: {part}"
            periods.append(period)

    earliest = min(all_years) if all_years else None
    latest = max(all_years) if all_years else None

    return periods, earliest, latest


def extract_alt_names(description: str) -> List[str]:
    """Extract alternate names from bold text in description."""
    alt_names = []

    # Pattern for bold text that looks like fort names
    # Common patterns: "first known as **Fort X**" or "also called **Camp Y**"
    patterns = [
        r"(?:first |originally |also |formerly |later |previously )?(?:known|called|named|designated) as \*\*([^*]+)\*\*",
        r"(?:renamed|changed to) \*\*([^*]+)\*\*",
        r"\*\*([^*]+)\*\*",  # Any bold text (fallback)
    ]

    for pattern in patterns[:-1]:  # Use specific patterns first
        for match in re.finditer(pattern, description, re.IGNORECASE):
            name = match.group(1).strip()
            if name and name not in alt_names:
                # Filter out non-name bold text
                if not any(x in name.lower() for x in ["the ", "a ", "an ", "this ", "that "]):
                    alt_names.append(name)

    return alt_names


def detect_fort_type(name: str, description: str) -> Optional[str]:
    """Detect the type of fortification from name and description."""
    text = (name + " " + description).lower()

    type_keywords = [
        ("battery", ["battery", "batteries"]),
        ("redoubt", ["redoubt"]),
        ("blockhouse", ["blockhouse", "block house", "block-house"]),
        ("stockade", ["stockade", "palisade"]),
        ("camp", ["camp "]),  # Space to avoid "campaign"
        ("cantonment", ["cantonment"]),
        ("barracks", ["barracks"]),
        ("arsenal", ["arsenal"]),
        ("trading post", ["trading post", "fur trading", "trading house"]),
        ("garrison", ["garrison house", "garrison"]),
        ("powder house", ["powder house", "magazine"]),
        ("fort", ["fort "]),  # Space to be more specific
    ]

    for fort_type, keywords in type_keywords:
        for keyword in keywords:
            if keyword in text:
                return fort_type

    return "fort"  # Default


def parse_fort_entry(entry_text: str, entry_html: str = "") -> Optional[FortEntry]:
    """
    Parse a single fort entry.

    Expected format:
        Fort Name (dates), Location - Description...

    Or with line breaks:
        Fort Name
        (dates), Location
        Description...
    """
    if not entry_text.strip():
        return None

    # Clean up the text
    text = entry_text.strip()
    text = re.sub(r"\s+", " ", text)  # Normalize whitespace

    # Try to match the standard pattern:
    # Name (dates), Location - Description
    # or: Name (dates), Location Description (no dash)

    # Pattern 1: Name (dates), Location - Description
    pattern1 = r"^(.+?)\s*\(([^)]+)\)\s*,\s*([^–-]+?)(?:\s*[-–]\s*(.*))?$"

    # Pattern 2: Name (dates), Location (no description separator)
    pattern2 = r"^(.+?)\s*\(([^)]+)\)\s*,\s*(.+)$"

    # Pattern 3: Just Name (dates) with description after
    pattern3 = r"^(.+?)\s*\(([^)]+)\)\s*(.*)$"

    match = re.match(pattern1, text, re.DOTALL)
    if match:
        name_raw = match.group(1).strip()
        dates_raw = match.group(2).strip()
        location_raw = match.group(3).strip()
        description_raw = match.group(4).strip() if match.group(4) else ""
    else:
        match = re.match(pattern2, text, re.DOTALL)
        if match:
            name_raw = match.group(1).strip()
            dates_raw = match.group(2).strip()
            # Location and description are merged - try to separate
            rest = match.group(3).strip()
            # First sentence is usually location context
            sentences = re.split(r"(?<=[.!?])\s+", rest, maxsplit=1)
            location_raw = sentences[0] if sentences else rest
            description_raw = sentences[1] if len(sentences) > 1 else ""
        else:
            match = re.match(pattern3, text, re.DOTALL)
            if match:
                name_raw = match.group(1).strip()
                dates_raw = match.group(2).strip()
                description_raw = match.group(3).strip()
                location_raw = ""
            else:
                # Can't parse - store everything as raw
                return FortEntry(
                    name_primary=text[:100],  # Use first 100 chars as name
                    entry_raw=text,
                    description_raw=text,
                )

    # Clean up name (remove any remaining flag references, asterisks, etc.)
    name_clean = re.sub(r"\s*\[.*?\]\s*", "", name_raw)  # Remove [brackets]
    name_clean = re.sub(r"\s*\*+\s*", "", name_clean)  # Remove asterisks
    name_clean = name_clean.strip()

    # Parse dates
    periods, earliest, latest = parse_date_ranges(dates_raw)

    # Extract nationalities from HTML
    nationalities = extract_nationalities(entry_html) if entry_html else []

    # Extract alternate names
    alt_names = extract_alt_names(description_raw)

    # Detect fort type
    fort_type = detect_fort_type(name_clean, description_raw)

    entry = FortEntry(
        name_primary=name_clean,
        dates_raw=f"({dates_raw})",
        location_text=location_raw,
        description_raw=description_raw,
        entry_raw=text,
        alt_names=alt_names,
        nationalities=nationalities,
        periods=periods,
        earliest_year=earliest,
        latest_year=latest,
    )

    return entry


def parse_page(html: str, url: str) -> List[FortEntry]:
    """
    Parse an entire page of fort entries.

    The site uses a consistent HTML structure:
    <A NAME="anchor">Fort Name</A> <img src="flag.gif">
    <I>(dates), Location</I>
    Description text...

    We use regex on raw HTML to extract these patterns reliably.
    """
    entries = []

    # Primary pattern for entries with NAME anchors (most common)
    # Matches: <A NAME="x">Name</A> [flags] <I>(dates), Location</I> description
    pattern = (
        r'<A\s+NAME="([^"]+)"[^>]*>([^<]+)</A>\s*'  # Anchor with name
        r'((?:<img[^>]*>\s*)*)'  # Zero or more flag images
        r'(?:<BR>\s*)?(?:</FONT>)?\s*'  # Optional BR and closing FONT
        r'<I>([^<]*)</I>\s*'  # Italicized date/location
        r'(?:<BR>)?\s*'  # Optional BR
        r'(.*?)'  # Description (non-greedy)
        r'(?=</P>|<P>|<A\s+NAME=|<HR|<FONT\s+SIZE|$)'  # Stop at next entry or section
    )

    matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)

    for match in matches:
        anchor_name, fort_name, flags_html, date_loc, description_html = match

        # Clean fort name
        fort_name = fort_name.strip()
        if not fort_name:
            continue

        # Extract nationalities from flag images
        nationalities = extract_nationalities(flags_html)

        # Parse date and location from italicized text
        # Format: "(dates), Location" or just "(dates)"
        date_loc = date_loc.strip()
        dates_raw = ""
        location_text = ""

        date_loc_match = re.match(r'\(([^)]+)\)\s*,?\s*(.*)', date_loc)
        if date_loc_match:
            dates_raw = date_loc_match.group(1).strip()
            location_text = date_loc_match.group(2).strip()
        else:
            # Try to extract just dates
            date_only_match = re.match(r'\(([^)]+)\)', date_loc)
            if date_only_match:
                dates_raw = date_only_match.group(1).strip()

        # Clean description - remove HTML tags
        description_clean = re.sub(r'<[^>]+>', ' ', description_html)
        description_clean = re.sub(r'\s+', ' ', description_clean).strip()

        # Parse date ranges
        periods, earliest, latest = parse_date_ranges(dates_raw)

        # Extract alternate names from description (bold text patterns)
        alt_names = extract_alt_names_from_html(description_html)

        # Build the raw entry text for preservation
        entry_raw = f"{fort_name} ({dates_raw}), {location_text} - {description_clean}"

        entry = FortEntry(
            name_primary=fort_name,
            dates_raw=f"({dates_raw})" if dates_raw else "",
            location_text=location_text,
            description_raw=description_clean,
            entry_raw=entry_raw,
            alt_names=alt_names,
            nationalities=nationalities,
            periods=periods,
            earliest_year=earliest,
            latest_year=latest,
        )
        entries.append(entry)

    # If primary pattern didn't find anything, try fallback patterns
    if not entries:
        entries = parse_page_fallback(html, url)

    return entries


def extract_alt_names_from_html(html: str) -> List[str]:
    """Extract alternate names from bold tags in HTML description."""
    alt_names = []

    # Look for bold text that appears to be fort names
    # Pattern: <b>Name</b> or <B>Name</B> or <strong>Name</strong>
    bold_pattern = r'<(?:b|strong)>([^<]+)</(?:b|strong)>'

    for match in re.finditer(bold_pattern, html, re.IGNORECASE):
        name = match.group(1).strip()
        # Filter out non-name text (too short, contains certain words, etc.)
        if name and len(name) > 3 and name not in alt_names:
            # Check if it looks like a fort name (contains Fort, Camp, Post, etc. or starts with capital)
            if re.match(r'^[A-Z]', name) and not any(x in name.lower() for x in ['the ', 'click', 'here', 'see ']):
                alt_names.append(name)

    return alt_names


def parse_page_fallback(html: str, url: str) -> List[FortEntry]:
    """
    Fallback parser for pages with different structure.
    Uses BeautifulSoup for more flexible parsing.
    """
    entries = []
    soup = BeautifulSoup(html, "lxml")

    # Try to find text that matches fort entry pattern
    body = soup.find("body")
    if not body:
        return entries

    text = body.get_text(separator="\n")

    # Look for patterns like "Fort Name (year" at the start of lines
    # This catches entries that might not have the anchor structure
    entry_pattern = r'^([A-Z][^(]+?)\s*\((\d{4}[^)]*)\)\s*,?\s*([^\n]*?)(?:\n|$)(.*?)(?=^[A-Z][^(]+?\s*\(\d{4}|\Z)'

    for match in re.finditer(entry_pattern, text, re.MULTILINE | re.DOTALL):
        fort_name = match.group(1).strip()
        dates_raw = match.group(2).strip()
        location_text = match.group(3).strip()
        description = match.group(4).strip()

        if not fort_name:
            continue

        # Clean up description
        description_clean = re.sub(r'\s+', ' ', description)

        # Parse date ranges
        periods, earliest, latest = parse_date_ranges(dates_raw)

        # Try to find flags in original HTML near this entry
        nationalities = []
        if fort_name in html:
            idx = html.find(fort_name)
            context = html[max(0, idx - 100):idx + 100]
            nationalities = extract_nationalities(context)

        entry = FortEntry(
            name_primary=fort_name,
            dates_raw=f"({dates_raw})" if dates_raw else "",
            location_text=location_text,
            description_raw=description_clean[:1000],  # Limit length
            entry_raw=f"{fort_name} ({dates_raw}), {location_text} - {description_clean[:500]}",
            alt_names=[],
            nationalities=nationalities,
            periods=periods,
            earliest_year=earliest,
            latest_year=latest,
        )
        entries.append(entry)

    return entries


def entry_to_dict(entry: FortEntry, state_code: str, state_name: str, source_url: str, section: str) -> dict:
    """Convert a FortEntry to a dict suitable for database insertion."""
    return {
        "name_primary": entry.name_primary,
        "alt_names": "|".join(entry.alt_names) if entry.alt_names else None,
        "state_territory": state_code.upper(),
        "state_full_name": state_name,
        "location_text": entry.location_text or None,
        "fort_type": detect_fort_type(entry.name_primary, entry.description_raw),
        "nationality": "|".join(entry.nationalities) if entry.nationalities else None,
        "dates_raw": entry.dates_raw or None,
        "earliest_year": entry.earliest_year,
        "latest_year": entry.latest_year,
        "source_url": source_url,
        "source_section": section,
        "description_raw": entry.description_raw or None,
        "entry_raw": entry.entry_raw or None,
        "periods": entry.periods,  # Will be inserted separately
    }
