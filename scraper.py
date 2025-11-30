"""Main scraper for North American Forts website."""

import argparse
import json
import time
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import REQUEST_DELAY, REQUEST_TIMEOUT, USER_AGENT, DATA_DIR
from db import (
    get_connection, init_db, insert_fort, insert_period, log_scrape,
    get_scrape_status, get_stats, get_forts_to_geocode, update_geocoding,
    get_geocoding_stats
)
from discover_urls import discover_all_us_pages, get_session
from parser import parse_page, entry_to_dict


def scrape_page(session: requests.Session, url: str) -> tuple:
    """
    Fetch and return page HTML.
    Returns (html, error_message).
    """
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text, None
    except requests.RequestException as e:
        return None, str(e)


def scrape_single_page(session: requests.Session, page_info: dict, conn, force: bool = False) -> int:
    """
    Scrape a single state page and save to database.
    Returns number of forts found.
    """
    url = page_info["url"]
    state_code = page_info["state_code"]
    state_name = page_info["state_name"]
    section = page_info["section"]

    # Check if already scraped (unless forcing)
    if not force:
        status = get_scrape_status(conn, url)
        if status and status["status"] == "success":
            print(f"  Skipping {url} (already scraped, {status['forts_found']} forts)")
            return 0

    print(f"  Scraping {page_info['filename']} ({state_name})...")

    html, error = scrape_page(session, url)
    if error:
        print(f"    ERROR: {error}")
        log_scrape(conn, url, "error", 0, error)
        conn.commit()
        return 0

    # Parse the page
    entries = parse_page(html, url)
    print(f"    Found {len(entries)} fort entries")

    # Save to database
    for entry in entries:
        fort_data = entry_to_dict(entry, state_code, state_name, url, section)
        periods = fort_data.pop("periods", [])

        fort_id = insert_fort(conn, fort_data)

        # Insert periods
        for period in periods:
            insert_period(conn, fort_id, period)

    log_scrape(conn, url, "success", len(entries))
    conn.commit()

    return len(entries)


def scrape_all(force: bool = False, limit: int = None):
    """
    Scrape all discovered US state pages.

    Args:
        force: Re-scrape pages even if already done
        limit: Maximum number of pages to scrape (for testing)
    """
    print("=" * 60)
    print("North American Forts Scraper")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    # Initialize database
    init_db()
    conn = get_connection()

    # Discover all pages
    print("\nDiscovering state pages...")
    pages = discover_all_us_pages()
    print(f"Found {len(pages)} total pages to scrape")

    # Save discovered URLs
    with open(f"{DATA_DIR}/discovered_urls.json", "w") as f:
        json.dump(pages, f, indent=2)

    if limit:
        pages = pages[:limit]
        print(f"Limiting to {limit} pages for testing")

    # Scrape each page
    session = get_session()
    total_forts = 0
    pages_scraped = 0
    errors = 0

    print("\nScraping pages...")
    print("-" * 60)

    for i, page_info in enumerate(pages, 1):
        print(f"[{i}/{len(pages)}] ", end="")

        try:
            forts_found = scrape_single_page(session, page_info, conn, force)
            if forts_found > 0:
                total_forts += forts_found
                pages_scraped += 1
        except Exception as e:
            print(f"    EXCEPTION: {e}")
            errors += 1

        # Respectful delay between requests
        if i < len(pages):
            time.sleep(REQUEST_DELAY)

    conn.close()

    # Summary
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)
    print(f"Pages processed: {len(pages)}")
    print(f"Pages with new data: {pages_scraped}")
    print(f"Errors: {errors}")
    print(f"Total forts found: {total_forts}")
    print(f"Finished: {datetime.now().isoformat()}")

    # Show database stats
    conn = get_connection()
    stats = get_stats(conn)
    conn.close()

    print("\nDatabase Statistics:")
    print(f"  Total forts in DB: {stats['total_forts']}")
    print(f"  Total periods: {stats['total_periods']}")
    print(f"  Pages scraped: {stats['pages_scraped']}")

    if stats["forts_by_state"]:
        print("\nForts by state (top 10):")
        for state, count in list(stats["forts_by_state"].items())[:10]:
            print(f"  {state}: {count}")


def test_single_page(url: str):
    """Test parsing on a single page without saving to database."""
    print(f"Testing parser on: {url}")

    session = get_session()
    html, error = scrape_page(session, url)

    if error:
        print(f"Error fetching page: {error}")
        return

    entries = parse_page(html, url)
    print(f"\nFound {len(entries)} entries:\n")

    for i, entry in enumerate(entries[:10], 1):  # Show first 10
        print(f"{i}. {entry.name_primary}")
        print(f"   Dates: {entry.dates_raw}")
        print(f"   Location: {entry.location_text}")
        print(f"   Periods: {entry.periods}")
        print(f"   Nationalities: {entry.nationalities}")
        print(f"   Type: {entry.description_raw[:100]}..." if entry.description_raw else "   Type: (no description)")
        print()

    if len(entries) > 10:
        print(f"... and {len(entries) - 10} more entries")


def geocode_forts(api_key: str, limit: int = None, delay: float = 0.05):
    """
    Geocode forts that haven't been geocoded yet.

    Args:
        api_key: Google Geocoding API key
        limit: Maximum number of forts to process (None = all)
        delay: Delay between API calls in seconds
    """
    from geocoder import geocode_fort

    print("=" * 60)
    print("Fort Geocoding")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    conn = get_connection()

    # Get forts to geocode
    forts = get_forts_to_geocode(conn, limit)
    total = len(forts)

    if total == 0:
        print("\nNo forts pending geocoding.")
        conn.close()
        return

    print(f"\nForts to geocode: {total}")
    if limit:
        print(f"(Limited to {limit})")
    print("-" * 60)

    # Process each fort
    success_count = 0
    failed_count = 0
    start_time = time.time()

    for i, fort in enumerate(forts, 1):
        result = geocode_fort(
            fort["location_text"],
            fort["state_full_name"],
            api_key,
            delay=delay
        )

        # Update database
        update_geocoding(
            conn,
            fort["fort_id"],
            result.lat,
            result.lon,
            result.confidence,
            result.source,
            result.query
        )
        conn.commit()

        # Track stats
        if result.confidence != "failed":
            success_count += 1
        else:
            failed_count += 1

        # Progress output
        if i % 100 == 0 or i == total:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"  [{i}/{total}] {success_count} success, {failed_count} failed "
                  f"({rate:.1f}/sec, ETA: {eta:.0f}s)")

    conn.close()

    # Summary
    print("\n" + "=" * 60)
    print("GEOCODING COMPLETE")
    print("=" * 60)
    print(f"Processed: {total}")
    print(f"Success: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Duration: {time.time() - start_time:.1f}s")


def show_geocoding_stats():
    """Show geocoding progress statistics."""
    conn = get_connection()
    stats = get_geocoding_stats(conn)
    conn.close()

    print("=" * 60)
    print("Geocoding Statistics")
    print("=" * 60)
    print(f"Total forts:     {stats['total_forts']}")
    print(f"Geocoded:        {stats['geocoded']}")
    print(f"Pending:         {stats['pending']}")

    pct = (stats['geocoded'] / stats['total_forts'] * 100) if stats['total_forts'] > 0 else 0
    print(f"Progress:        {pct:.1f}%")

    if stats['by_confidence']:
        print("\nBy confidence level:")
        for level, count in sorted(stats['by_confidence'].items()):
            print(f"  {level}: {count}")


def export_csv():
    """Export database to CSV files."""
    import csv

    conn = get_connection()
    cursor = conn.cursor()

    # Export forts
    cursor.execute("SELECT * FROM forts ORDER BY state_territory, name_primary")
    rows = cursor.fetchall()

    if rows:
        columns = [description[0] for description in cursor.description]
        csv_path = f"{DATA_DIR}/forts.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        print(f"Exported {len(rows)} forts to {csv_path}")

    # Export periods
    cursor.execute(
        """
        SELECT p.*, f.name_primary, f.state_territory
        FROM fort_periods p
        JOIN forts f ON p.fort_id = f.fort_id
        ORDER BY f.state_territory, f.name_primary, p.period_order
    """
    )
    rows = cursor.fetchall()

    if rows:
        columns = [description[0] for description in cursor.description]
        csv_path = f"{DATA_DIR}/fort_periods.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        print(f"Exported {len(rows)} periods to {csv_path}")

    conn.close()


def main():
    import os
    from dotenv import load_dotenv

    # Load .env file if it exists
    load_dotenv()

    parser = argparse.ArgumentParser(description="Scrape fort data from northamericanforts.com")
    parser.add_argument("--force", action="store_true", help="Re-scrape pages even if already done")
    parser.add_argument("--limit", type=int, help="Maximum number of pages to scrape (for testing)")
    parser.add_argument("--test", type=str, help="Test parser on a single URL")
    parser.add_argument("--export", action="store_true", help="Export database to CSV")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--discover", action="store_true", help="Only discover URLs, don't scrape")

    # Geocoding options
    parser.add_argument("--geocode", action="store_true", help="Geocode forts using Google API")
    parser.add_argument("--geocode-stats", action="store_true", help="Show geocoding statistics")
    parser.add_argument("--geocode-limit", type=int, help="Limit number of forts to geocode")
    parser.add_argument("--api-key", type=str, help="Google Geocoding API key (or set GOOGLE_GEOCODING_API_KEY env var)")

    args = parser.parse_args()

    if args.test:
        test_single_page(args.test)
    elif args.export:
        export_csv()
    elif args.stats:
        init_db()
        conn = get_connection()
        stats = get_stats(conn)
        conn.close()
        print(json.dumps(stats, indent=2))
    elif args.discover:
        pages = discover_all_us_pages()
        print(json.dumps(pages, indent=2))
    elif args.geocode_stats:
        show_geocoding_stats()
    elif args.geocode:
        # Get API key from argument or environment
        api_key = args.api_key or os.environ.get("GOOGLE_GEOCODING_API_KEY")
        if not api_key:
            print("ERROR: Google API key required. Use --api-key or set GOOGLE_GEOCODING_API_KEY environment variable.")
            sys.exit(1)
        geocode_forts(api_key, limit=args.geocode_limit)
    else:
        scrape_all(force=args.force, limit=args.limit)


if __name__ == "__main__":
    main()
