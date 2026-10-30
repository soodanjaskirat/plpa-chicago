"""
Step 3: Download neighborhood (census tract) characteristics from the
American Community Survey (ACS) 5-year estimates for 2015-2019.

Why 2015-2019?
  - It describes neighborhoods BEFORE the law (2021) and before COVID-19 (2020).
  - It uses 2010 tract boundaries, matching our tract map.

Why "5-year"? The ACS surveys a sample of households. For small areas like tracts,
the Census Bureau pools 5 years of responses to get reliable estimates. Every
estimate still has a margin of error (MOE); we keep the MOE for median income.

You need a free Census API key: https://api.census.gov/data/key_signup.html
Save it in a file called .census_key in the project root, or set the
CENSUS_API_KEY environment variable.
"""

import sys
import pandas as pd
import requests

from config import RAW, ACS_URL, STATE_FIPS, COUNTY_FIPS, census_api_key

# Census variable codes -> readable names.
# Table B01003 = total population; B19013 = median household income;
# B03002 = race by Hispanic origin; B17001 = poverty status;
# B23025 = employment status; B25003 = owner vs renter households.
VARIABLES = {
    "B01003_001E": "pop_total",
    "B19013_001E": "median_hh_income",
    "B19013_001M": "median_hh_income_moe",
    "B03002_001E": "race_universe",
    "B03002_003E": "nh_white",
    "B03002_004E": "nh_black",
    "B03002_012E": "hispanic",
    "B17001_001E": "poverty_universe",
    "B17001_002E": "below_poverty",
    "B23025_003E": "civ_labor_force",
    "B23025_005E": "unemployed",
    "B25003_001E": "occupied_units",
    "B25003_003E": "renter_units",
}


def main():
    key = census_api_key()
    if not key:
        sys.exit("No Census API key found. Get one free at "
                 "https://api.census.gov/data/key_signup.html and save it in .census_key")

    params = {
        "get": ",".join(["NAME"] + list(VARIABLES)),
        "for": "tract:*",                                   # every tract...
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",   # ...in Cook County, Illinois
        "key": key,
    }
    response = requests.get(ACS_URL, params=params, timeout=300)
    response.raise_for_status()
    # A bad or not-yet-activated key is redirected to an "invalid_key" web page
    # instead of returning data.
    if "invalid_key" in response.url:
        sys.exit("The Census API rejected the key. Check .census_key, and make sure you "
                 "clicked the activation link in the Census email (it can take a few minutes).")
    rows = response.json()  # first row is the header, the rest are tracts

    acs = pd.DataFrame(rows[1:], columns=rows[0]).rename(columns=VARIABLES)
    acs.to_csv(RAW / "acs_2015_2019_cook_tracts.csv", index=False)
    print(f"Saved ACS data for {len(acs):,} Cook County tracts")


if __name__ == "__main__":
    main()
