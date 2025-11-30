"""Database operations for the forts scraper."""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

from config import DB_PATH, PROJECT_DIR


def get_connection() -> sqlite3.Connection:
    """Get a database connection, creating the database if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database with the schema."""
    conn = get_connection()
    schema_path = os.path.join(PROJECT_DIR, "schema.sql")
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def insert_fort(conn: sqlite3.Connection, fort_data: dict) -> int:
    """Insert a fort and return its ID. Updates if already exists."""
    cursor = conn.cursor()

    # Check if fort already exists
    cursor.execute(
        """
        SELECT fort_id FROM forts
        WHERE name_primary = ? AND state_territory = ? AND source_url = ?
        """,
        (fort_data["name_primary"], fort_data["state_territory"], fort_data["source_url"]),
    )
    existing = cursor.fetchone()

    if existing:
        # Update existing fort
        fort_id = existing["fort_id"]
        cursor.execute(
            """
            UPDATE forts SET
                alt_names = ?,
                state_full_name = ?,
                location_text = ?,
                fort_type = ?,
                nationality = ?,
                dates_raw = ?,
                earliest_year = ?,
                latest_year = ?,
                source_section = ?,
                description_raw = ?,
                entry_raw = ?,
                other_attributes = ?,
                scraped_at = ?
            WHERE fort_id = ?
            """,
            (
                fort_data.get("alt_names"),
                fort_data.get("state_full_name"),
                fort_data.get("location_text"),
                fort_data.get("fort_type"),
                fort_data.get("nationality"),
                fort_data.get("dates_raw"),
                fort_data.get("earliest_year"),
                fort_data.get("latest_year"),
                fort_data.get("source_section"),
                fort_data.get("description_raw"),
                fort_data.get("entry_raw"),
                json.dumps(fort_data.get("other_attributes")) if fort_data.get("other_attributes") else None,
                datetime.now().isoformat(),
                fort_id,
            ),
        )
        # Clear old periods before re-inserting
        cursor.execute("DELETE FROM fort_periods WHERE fort_id = ?", (fort_id,))
    else:
        # Insert new fort
        cursor.execute(
            """
            INSERT INTO forts (
                name_primary, alt_names, state_territory, state_full_name,
                location_text, fort_type, nationality, dates_raw,
                earliest_year, latest_year, source_url, source_section,
                description_raw, entry_raw, other_attributes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fort_data["name_primary"],
                fort_data.get("alt_names"),
                fort_data["state_territory"],
                fort_data.get("state_full_name"),
                fort_data.get("location_text"),
                fort_data.get("fort_type"),
                fort_data.get("nationality"),
                fort_data.get("dates_raw"),
                fort_data.get("earliest_year"),
                fort_data.get("latest_year"),
                fort_data["source_url"],
                fort_data.get("source_section"),
                fort_data.get("description_raw"),
                fort_data.get("entry_raw"),
                json.dumps(fort_data.get("other_attributes")) if fort_data.get("other_attributes") else None,
            ),
        )
        fort_id = cursor.lastrowid

    return fort_id


def insert_period(conn: sqlite3.Connection, fort_id: int, period_data: dict) -> int:
    """Insert a fort period and return its ID."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO fort_periods (fort_id, start_year, end_year, period_type, period_notes, period_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            fort_id,
            period_data.get("start_year"),
            period_data.get("end_year"),
            period_data.get("period_type"),
            period_data.get("period_notes"),
            period_data.get("period_order", 0),
        ),
    )
    return cursor.lastrowid


def insert_alt_name(conn: sqlite3.Connection, fort_id: int, name_data: dict) -> int:
    """Insert an alternate name for a fort."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO fort_names (fort_id, name, year_from, year_to, named_for, is_primary)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            fort_id,
            name_data["name"],
            name_data.get("year_from"),
            name_data.get("year_to"),
            name_data.get("named_for"),
            name_data.get("is_primary", False),
        ),
    )
    return cursor.lastrowid


def log_scrape(conn: sqlite3.Connection, url: str, status: str, forts_found: int = 0, error_message: str = None):
    """Log a scraping attempt."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO scrape_log (url, status, forts_found, error_message, scraped_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (url, status, forts_found, error_message, datetime.now().isoformat()),
    )


def get_scrape_status(conn: sqlite3.Connection, url: str) -> Optional[dict]:
    """Get the scrape status for a URL."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scrape_log WHERE url = ?", (url,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_stats(conn: sqlite3.Connection) -> dict:
    """Get database statistics."""
    cursor = conn.cursor()
    stats = {}

    cursor.execute("SELECT COUNT(*) as count FROM forts")
    stats["total_forts"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM fort_periods")
    stats["total_periods"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM scrape_log WHERE status = 'success'")
    stats["pages_scraped"] = cursor.fetchone()["count"]

    cursor.execute(
        "SELECT state_territory, COUNT(*) as count FROM forts GROUP BY state_territory ORDER BY count DESC"
    )
    stats["forts_by_state"] = {row["state_territory"]: row["count"] for row in cursor.fetchall()}

    return stats


def get_forts_to_geocode(conn: sqlite3.Connection, limit: Optional[int] = None) -> list:
    """Get forts that haven't been geocoded yet."""
    cursor = conn.cursor()
    query = """
        SELECT fort_id, location_text, state_full_name
        FROM forts
        WHERE geocode_confidence IS NULL
        AND location_text IS NOT NULL
        AND location_text != ''
    """
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]


def update_geocoding(
    conn: sqlite3.Connection,
    fort_id: int,
    lat: Optional[float],
    lon: Optional[float],
    confidence: str,
    source: str,
    query: str
):
    """Update a fort's geocoding information."""
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE forts SET
            lat = ?,
            lon = ?,
            geocode_confidence = ?,
            geocode_source = ?,
            geocode_query = ?,
            geocoded_at = ?
        WHERE fort_id = ?
        """,
        (lat, lon, confidence, source, query, datetime.now().isoformat(), fort_id),
    )


def get_geocoding_stats(conn: sqlite3.Connection) -> dict:
    """Get geocoding statistics."""
    cursor = conn.cursor()
    stats = {}

    cursor.execute("SELECT COUNT(*) as count FROM forts")
    stats["total_forts"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM forts WHERE geocode_confidence IS NOT NULL")
    stats["geocoded"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM forts WHERE geocode_confidence IS NULL AND location_text IS NOT NULL AND location_text != ''")
    stats["pending"] = cursor.fetchone()["count"]

    cursor.execute(
        "SELECT geocode_confidence, COUNT(*) as count FROM forts WHERE geocode_confidence IS NOT NULL GROUP BY geocode_confidence"
    )
    stats["by_confidence"] = {row["geocode_confidence"]: row["count"] for row in cursor.fetchall()}

    return stats


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
