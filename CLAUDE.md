# Claude Code Project Context

## Project Overview

This is a web scraper for extracting structured data about North American military forts from northamericanforts.com. The goal is to create a comprehensive dataset of US forts with location data, dates, and historical information.

## Current Status

**Part 1 (Complete):** Scraping
- Successfully scraped 4,005 forts from 181 pages
- Data stored in SQLite database (`data/forts.db`)
- Exported to CSV (`data/forts.csv`, `data/fort_periods.csv`)

**Part 2 (Next):** Geocoding
- Need to convert `location_text` field to lat/lon coordinates
- Plan to use Nominatim (OpenStreetMap) via geopy library
- Must handle rate limiting (1 request/second for Nominatim)
- Should store geocoding confidence levels

## Key Files

- `scraper.py` - Main CLI entry point
- `parser.py` - HTML parsing logic (uses regex on raw HTML to find fort entries)
- `db.py` - Database operations
- `schema.sql` - SQLite schema definition
- `config.py` - Configuration constants

## Database Schema

The main tables are:
- `forts` - Core fort data (name, location_text, dates_raw, description_raw, etc.)
- `fort_periods` - Multiple date ranges per fort
- `fort_names` - Alternate name history
- `fort_events` - Historical events

For geocoding, we need to add columns to `forts`:
- `lat` - Latitude
- `lon` - Longitude
- `geocode_confidence` - How confident the geocoding is (exact, locality, county, state)
- `geocode_source` - Which service was used
- `geocoded_at` - Timestamp

## HTML Parsing Pattern

The source website uses this structure for fort entries:
```html
<A NAME="anchor">Fort Name</A> <img src="flag.gif">
<I>(dates), Location</I>
Description text...
```

The parser in `parser.py` extracts this using regex patterns.

## Important Notes

1. **Rate Limiting**: Be respectful of the source website (1 second delay between requests)
2. **Data Preservation**: Always keep `entry_raw` and `description_raw` intact - never lose original text
3. **Multiple Periods**: Forts can have multiple active periods (e.g., "1775, 1811-1814, 1898-1899")
4. **Geocoding Strategy**: Use location_text + state for geocoding; fall back to county/state level if exact location fails

## Commands

```bash
# Activate venv
source venv/bin/activate

# Full scrape
python scraper.py

# Export CSV
python scraper.py --export

# Show stats
python scraper.py --stats
```
