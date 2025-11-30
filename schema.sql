-- North American Forts Database Schema
-- Part 1: Scraping (no geocoding yet)

-- Core forts table: one row per unique fort/site
CREATE TABLE IF NOT EXISTS forts (
    fort_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Primary identification
    name_primary TEXT NOT NULL,
    alt_names TEXT,                    -- Pipe-separated list of alternate names

    -- Location (text-based for now, geocoding in Part 2)
    state_territory TEXT NOT NULL,     -- Two-letter code (e.g., CT, CO)
    state_full_name TEXT,              -- Full name (e.g., Connecticut, Colorado)
    location_text TEXT,                -- Verbatim location from source (e.g., "near Ovid")

    -- Classification
    fort_type TEXT,                    -- fort, battery, camp, stockade, trading post, etc.
    nationality TEXT,                  -- Derived from flag icons (US, British, French, Spanish, etc.)

    -- Raw date string (preserved exactly as scraped)
    dates_raw TEXT,                    -- Original date string, e.g., "(1775, 1811 - 1814, 1898 - 1899)"

    -- Derived earliest/latest (computed from fort_periods)
    earliest_year INTEGER,
    latest_year INTEGER,

    -- Source tracking
    source_url TEXT,                   -- Full URL of the page scraped
    source_section TEXT,               -- "East" or "West"

    -- Full original content (never lose information)
    description_raw TEXT,              -- Full description paragraph(s)
    entry_raw TEXT,                    -- Complete original entry text

    -- Flexible storage for unknown attributes
    other_attributes TEXT,             -- JSON object for key-value pairs we discover later

    -- Metadata
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure no duplicate entries from same source
    UNIQUE(name_primary, state_territory, source_url)
);

-- Fort active periods: multiple rows per fort for complex date ranges
CREATE TABLE IF NOT EXISTS fort_periods (
    period_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fort_id INTEGER NOT NULL,

    -- Date range (NULL means unknown)
    start_year INTEGER,
    end_year INTEGER,                  -- NULL if ongoing or unknown end

    -- Optional context
    period_type TEXT,                  -- established, reactivated, reconstructed, etc.
    period_notes TEXT,                 -- Any notes about this specific period

    -- Order within the fort's history (for display)
    period_order INTEGER DEFAULT 0,

    FOREIGN KEY (fort_id) REFERENCES forts(fort_id) ON DELETE CASCADE
);

-- Name history: tracks name changes over time
CREATE TABLE IF NOT EXISTS fort_names (
    name_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fort_id INTEGER NOT NULL,

    name TEXT NOT NULL,
    year_from INTEGER,                 -- When this name started (NULL if unknown)
    year_to INTEGER,                   -- When this name ended (NULL if still current)
    named_for TEXT,                    -- Person/thing it was named for (if mentioned)
    is_primary BOOLEAN DEFAULT 0,      -- Is this the primary/current name?

    FOREIGN KEY (fort_id) REFERENCES forts(fort_id) ON DELETE CASCADE
);

-- Events: significant events in the fort's history
CREATE TABLE IF NOT EXISTS fort_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fort_id INTEGER NOT NULL,

    year INTEGER,
    year_end INTEGER,                  -- For events spanning multiple years
    event_type TEXT,                   -- battle, siege, construction, destruction, etc.
    description TEXT,
    belligerents TEXT,                 -- Comma-separated if applicable

    FOREIGN KEY (fort_id) REFERENCES forts(fort_id) ON DELETE CASCADE
);

-- Scraping progress tracking
CREATE TABLE IF NOT EXISTS scrape_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    status TEXT DEFAULT 'pending',     -- pending, success, error
    forts_found INTEGER DEFAULT 0,
    error_message TEXT,
    scraped_at TIMESTAMP,
    html_hash TEXT                     -- To detect if page changed
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_forts_state ON forts(state_territory);
CREATE INDEX IF NOT EXISTS idx_forts_years ON forts(earliest_year, latest_year);
CREATE INDEX IF NOT EXISTS idx_periods_fort ON fort_periods(fort_id);
CREATE INDEX IF NOT EXISTS idx_names_fort ON fort_names(fort_id);
CREATE INDEX IF NOT EXISTS idx_events_fort ON fort_events(fort_id);
