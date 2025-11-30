# North American Forts Scraper

A Python scraper that extracts structured data about historical US military forts from [northamericanforts.com](https://www.northamericanforts.com/).

## Overview

This project scrapes fort data from the American Forts Network website and creates a structured SQLite database with:

- **4,005 forts** across all US states and territories
- **4,299 time periods** (forts with multiple active periods are properly tracked)
- Full original text preserved for each entry
- Nationality detection from flag images (US, British, French, Spanish, Dutch, Confederate, etc.)
- Fort type classification (fort, camp, blockhouse, stockade, trading post, battery, etc.)

## Data Schema

### Core Tables

**forts** - One row per fort/site:
- `fort_id` - Primary key
- `name_primary` - Fort name
- `alt_names` - Pipe-separated alternate names
- `state_territory` - Two-letter state code
- `location_text` - Verbatim location from source
- `fort_type` - Classification (fort, camp, battery, etc.)
- `nationality` - Controlling nation(s)
- `dates_raw` - Original date string
- `earliest_year`, `latest_year` - Derived from periods
- `description_raw` - Full description text
- `entry_raw` - Complete original entry

**fort_periods** - Multiple rows per fort for complex date ranges:
- `fort_id` - Foreign key to forts
- `start_year`, `end_year` - Date range
- `period_order` - Sequence within fort's history

### Additional Tables
- `fort_names` - Name change history
- `fort_events` - Historical events
- `scrape_log` - Scraping progress tracking

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Run full scrape (181 pages, ~3-4 minutes)
python scraper.py

# Test on a single page
python scraper.py --test "https://www.northamericanforts.com/East/ct.html"

# Limit pages for testing
python scraper.py --limit 10

# Re-scrape everything (ignore cache)
python scraper.py --force

# Export to CSV
python scraper.py --export

# Show statistics
python scraper.py --stats

# Discover URLs only
python scraper.py --discover
```

## Output Files

After running the scraper:

- `data/forts.db` - SQLite database
- `data/forts.csv` - Main fort data (4,005 rows)
- `data/fort_periods.csv` - Time periods (4,299 rows)
- `data/discovered_urls.json` - All scraped URLs

## Project Structure

```
forts_scraper/
├── config.py           # Configuration (delays, state names, flag mappings)
├── db.py               # Database operations
├── discover_urls.py    # URL discovery for all state pages
├── parser.py           # HTML parsing and data extraction
├── schema.sql          # SQLite database schema
├── scraper.py          # Main scraper CLI
├── requirements.txt    # Python dependencies
└── data/
    ├── forts.db
    ├── forts.csv
    └── fort_periods.csv
```

## Data Source

Data is scraped from [North American Forts](https://www.northamericanforts.com/), maintained by the American Forts Network. Please credit them if you use this data.

## Next Steps

- [ ] Part 2: Geocoding - Convert location text to lat/lon coordinates
- [ ] Data validation and cleanup
- [ ] Add Canadian and Latin American forts

## License

This scraper code is provided as-is for educational and research purposes. The underlying fort data is curated by the American Forts Network.
