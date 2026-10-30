"""
Step 2: Download map boundary files from the Chicago Data Portal.

- Census tracts (2010 boundaries). We use 2010 tracts because our Census data
  (ACS 2015-2019) is published on 2010 tract boundaries. Mixing 2010 data with
  2020 boundaries would put numbers on the wrong shapes.
- Community areas: Chicago's 77 official neighborhoods, used for maps and labels.
"""

import requests

from config import RAW, TRACTS_2010_URL, COMMUNITY_AREAS_URL


def download(url, path):
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    path.write_bytes(response.content)
    print(f"Saved {path.name} ({len(response.content) / 1e6:.1f} MB)")


def main():
    download(TRACTS_2010_URL, RAW / "chicago_tracts_2010.geojson")
    download(COMMUNITY_AREAS_URL, RAW / "chicago_community_areas.geojson")


if __name__ == "__main__":
    main()
