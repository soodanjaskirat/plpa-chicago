"""
Shared settings for the whole project: folder paths, key dates, and data source URLs.

Every other script imports from here, so if you want to change a date or a path,
change it once in this file and everything else follows.
"""

from pathlib import Path
import os

# ---------------------------------------------------------------------------
# Folder layout
# ---------------------------------------------------------------------------
# Path(__file__) is this file (src/config.py). .parents[1] goes up one folder
# to the project root, so the code works no matter where you run it from.
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"            # downloaded files, never edited by hand
CLEAN = ROOT / "data" / "clean"        # files our scripts produce
REFERENCE = ROOT / "data" / "reference"  # small hand-built lookup tables
FIGURES = ROOT / "figures"
RESULTS = ROOT / "results"             # tables of numbers produced by the analysis

for folder in (RAW, CLEAN, REFERENCE, FIGURES, RESULTS):
    folder.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Key dates
# ---------------------------------------------------------------------------
# The Predatory Loan Prevention Act was signed and took effect on March 23, 2021.
LAW_DATE = "2021-03-23"

# "Before" snapshot: Jan 1, 2020 is before both the law and COVID-19 closures.
PRE_DATE = "2020-01-01"

# "After" snapshot: Chicago business licenses last 2 years. A license bought just
# before the law could still be "active" until early 2023 even if the store closed.
# Jan 1, 2024 is safely past that, so a store still licensed then renewed AFTER the law.
POST_DATE = "2024-01-01"

# Yearly snapshots (Jan 1 of each year) used to draw trend lines.
PANEL_YEARS = list(range(2014, 2027))

# Date used to measure how "commercial" each neighborhood is (all licensed businesses).
COMMERCIAL_DATE = "2019-07-01"

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
# City of Chicago "Business Licenses" dataset on the Chicago Data Portal (Socrata).
LICENSES_URL = "https://data.cityofchicago.org/resource/r5kz-chrr.json"

# Boundary files (GeoJSON exports from the Chicago Data Portal).
TRACTS_2010_URL = "https://data.cityofchicago.org/api/geospatial/74p9-q2aq?method=export&format=GeoJSON"
COMMUNITY_AREAS_URL = "https://data.cityofchicago.org/api/geospatial/igwz-8jzy?method=export&format=GeoJSON"

# Census Bureau American Community Survey, 5-year estimates for 2015-2019.
ACS_YEAR = 2019
ACS_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
STATE_FIPS, COUNTY_FIPS = "17", "031"  # Illinois, Cook County

# Census Geocoder (free, no key) - only used for the few licenses missing coordinates.
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def census_api_key():
    """Return the Census API key from the CENSUS_API_KEY environment variable
    or from a file named .census_key in the project root (which git ignores)."""
    key = os.environ.get("CENSUS_API_KEY")
    key_file = ROOT / ".census_key"
    if not key and key_file.exists():
        key = key_file.read_text().strip()
    return key
