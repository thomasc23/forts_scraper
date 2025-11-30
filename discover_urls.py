"""Discover all state page URLs from the site, including subdivisions."""

import re
import time
import requests
from bs4 import BeautifulSoup
from typing import Set
from urllib.parse import urljoin

from config import BASE_URL, US_SECTIONS, REQUEST_DELAY, REQUEST_TIMEOUT, USER_AGENT, STATE_NAMES


def get_session() -> requests.Session:
    """Create a requests session with appropriate headers."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def discover_state_pages(session: requests.Session, section: str) -> Set[str]:
    """
    Discover all state page URLs for a given section (East/West).
    Returns a set of full URLs.
    """
    section_url = f"{BASE_URL}/{section}/"
    print(f"Discovering pages in {section_url}...")

    try:
        response = session.get(section_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  Error fetching {section_url}: {e}")
        return set()

    soup = BeautifulSoup(response.text, "lxml")
    pages = set()

    # Find all links in the page
    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Match state page patterns - can be relative or absolute:
        # - Relative: ct.html, co.html
        # - Absolute: /East/ct.html, /West/co.html
        # - With number suffix: ak2.html, co3.html
        # - With region: ca-central.html, tx-south.html, ca-sfbay.html
        # - Compound: mosouth.html, kswest.html, ndwest.html

        # Check if it's a state page HTML file (either relative or in this section)
        state_pattern = r"^(?:/{section}/)?([a-z]{{2}}(?:-?[a-z0-9]*)?)\.html$".format(section=section)
        match = re.match(state_pattern, href, re.IGNORECASE)
        if match:
            full_url = urljoin(section_url, href)
            pages.add(full_url)

    print(f"  Found {len(pages)} pages in {section}")
    return pages


def discover_all_us_pages() -> list:
    """
    Discover all US state pages from East and West sections.
    Returns a list of dicts with url and section info.
    """
    session = get_session()
    all_pages = []

    for section in US_SECTIONS:
        pages = discover_state_pages(session, section)
        for url in sorted(pages):
            # Extract state code from URL
            filename = url.split("/")[-1].replace(".html", "")
            # Get base state code (e.g., "ca" from "ca-central" or "co2")
            base_state = re.match(r"^([a-z]{2})", filename).group(1) if re.match(r"^([a-z]{2})", filename) else filename

            all_pages.append(
                {
                    "url": url,
                    "section": section,
                    "filename": filename,
                    "state_code": base_state,
                    "state_name": STATE_NAMES.get(base_state, base_state.upper()),
                }
            )

        time.sleep(REQUEST_DELAY)

    return all_pages


def print_discovered_pages(pages: list):
    """Print a summary of discovered pages."""
    print(f"\n{'=' * 60}")
    print(f"Total pages discovered: {len(pages)}")
    print(f"{'=' * 60}\n")

    for section in US_SECTIONS:
        section_pages = [p for p in pages if p["section"] == section]
        print(f"\n{section} ({len(section_pages)} pages):")
        print("-" * 40)
        for page in section_pages:
            print(f"  {page['filename']:20} -> {page['state_name']}")


if __name__ == "__main__":
    pages = discover_all_us_pages()
    print_discovered_pages(pages)

    # Save to file for reference
    import json

    with open("data/discovered_urls.json", "w") as f:
        json.dump(pages, f, indent=2)
    print(f"\nSaved to data/discovered_urls.json")
