# Claude Code Project Context

## Project Overview

This is a web scraper for extracting structured data about North American military forts from northamericanforts.com. The goal is to create a comprehensive dataset of US forts with location data, dates, and historical information.

## Current Status

**Part 1 (Complete):** Scraping
- Successfully scraped 4,005 forts from 181 pages
- Data stored in SQLite database (`data/forts.db`)
- Exported to CSV (`data/forts.csv`, `data/fort_periods.csv`)

**Part 2 (In Progress):** Geocoding
- Using Google Geocoding API for accuracy
- Handles "near X" patterns (marked as approximate confidence)
- Confidence levels: exact, locality, approximate, county, state, failed
- ~80 seconds to geocode all 4,005 forts with Google API

## Key Files

- `scraper.py` - Main CLI entry point
- `parser.py` - HTML parsing logic (uses regex on raw HTML to find fort entries)
- `geocoder.py` - Geocoding logic (Google Geocoding API)
- `db.py` - Database operations
- `schema.sql` - SQLite schema definition
- `config.py` - Configuration constants

## Database Schema

The main tables are:
- `forts` - Core fort data (name, location_text, dates_raw, description_raw, etc.)
- `fort_periods` - Multiple date ranges per fort
- `fort_names` - Alternate name history
- `fort_events` - Historical events

Geocoding columns in `forts` table:
- `lat` - Latitude
- `lon` - Longitude
- `geocode_confidence` - exact, locality, approximate, county, state, failed
- `geocode_source` - google, nominatim, manual
- `geocode_query` - The query string used for geocoding
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

# Geocoding commands
python scraper.py --geocode --api-key YOUR_KEY    # Geocode all pending forts
python scraper.py --geocode --geocode-limit 100   # Test with 100 forts
python scraper.py --geocode-stats                 # Show geocoding progress

# Or use environment variable for API key
export GOOGLE_GEOCODING_API_KEY=your_key
python scraper.py --geocode
```
