"""Configuration for the forts scraper."""

import os

# Paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "forts.db")

# Scraping settings
BASE_URL = "https://www.northamericanforts.com"
REQUEST_DELAY = 1.0  # Seconds between requests (be respectful)
REQUEST_TIMEOUT = 30  # Seconds
USER_AGENT = "FortsScraper/1.0 (Educational research project; contact: your-email@example.com)"

# US sections to scrape (Part 1 - US only)
US_SECTIONS = ["East", "West"]

# State codes and full names
STATE_NAMES = {
    # Eastern states
    "al": "Alabama",
    "ct": "Connecticut",
    "dc": "District of Columbia",
    "de": "Delaware",
    "fl": "Florida",
    "ga": "Georgia",
    "il": "Illinois",
    "in": "Indiana",
    "ky": "Kentucky",
    "la": "Louisiana",
    "ma": "Massachusetts",
    "md": "Maryland",
    "me": "Maine",
    "mi": "Michigan",
    "ms": "Mississippi",
    "nc": "North Carolina",
    "nh": "New Hampshire",
    "nj": "New Jersey",
    "ny": "New York",
    "oh": "Ohio",
    "pa": "Pennsylvania",
    "pr": "Puerto Rico",
    "ri": "Rhode Island",
    "sc": "South Carolina",
    "tn": "Tennessee",
    "va": "Virginia",
    "vt": "Vermont",
    "wi": "Wisconsin",
    "wv": "West Virginia",
    # Western states
    "ak": "Alaska",
    "ar": "Arkansas",
    "as": "American Samoa",
    "az": "Arizona",
    "ca": "California",
    "co": "Colorado",
    "gu": "Guam",
    "hi": "Hawaii",
    "ia": "Iowa",
    "id": "Idaho",
    "ks": "Kansas",
    "mn": "Minnesota",
    "mo": "Missouri",
    "mt": "Montana",
    "nd": "North Dakota",
    "ne": "Nebraska",
    "nm": "New Mexico",
    "nv": "Nevada",
    "ok": "Oklahoma",
    "or": "Oregon",
    "sd": "South Dakota",
    "tx": "Texas",
    "ut": "Utah",
    "wa": "Washington",
    "wy": "Wyoming",
}

# Flag image to nationality mapping
FLAG_NATIONALITY = {
    "usaflag": "United States",
    "usaflag1": "United States (Colonial/Revolutionary)",
    "britishflag": "Great Britain",
    "frenchflag": "France",
    "spanishflag": "Spain",
    "mexicanflag": "Mexico",
    "confederateflag": "Confederate States",
    "russianflag": "Russia",
    "dutchflag": "Netherlands",
    "swedishflag": "Sweden",
}
