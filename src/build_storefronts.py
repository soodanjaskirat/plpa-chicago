"""
Step 4: Turn raw license records into a clean table of lender STOREFRONTS.

Key ideas (worth being able to explain):

* A "storefront" = one physical address with a given type of lender, across
  license renewals AND changes of owner. We first tried using the city's
  account number + site number, but when a chain re-registered its stores
  (Check 'n Go moved all its stores to a new company account in 2018) the same
  store looked like one store closing and a new one opening, and stores
  briefly licensed under two accounts were counted twice. Grouping by address
  fixes both problems. See addresses.py for how addresses are standardized.

* Matching lenders by account number, not by name. Matching on name text is error-prone:
  searching for "SPEEDY" also finds car washes. Instead, a person reviewed the
  candidate accounts once (see review_candidates.py) and recorded each lender's
  account number and category in data/reference/lender_entities.csv.

* Categories:
    high_cost   payday, auto-title, and high-APR installment lenders (the law's target)
    lower_cost  installment lenders charging about 36% APR or less (comparison group)
    pawn        pawnshops (a possible substitute that borrowers might turn to)
    uncertain   small-loan companies whose prices we could not verify (kept separate)

* A store is "active" on a date if it held a license covering that date.
  A license is a permission to operate, not proof the store was open; a store
  can close before its license expires. So our dates are approximate.

Outputs:
  data/clean/storefronts.csv            one row per storefront
  data/clean/storefront_year_panel.csv  one row per storefront per year (Jan 1)
"""

import time
import geopandas as gpd
import pandas as pd
import requests

from addresses import address_key
from config import (RAW, CLEAN, REFERENCE, PRE_DATE, LAW_DATE, POST_DATE,
                    PANEL_YEARS, GEOCODER_URL)

KEEP_CATEGORIES = ["high_cost", "lower_cost", "pawn", "uncertain"]


def load_licenses():
    """Read the raw license download and attach a lender category to each record."""
    lic = pd.read_csv(RAW / "licenses_lender_candidates.csv", dtype=str)
    entities = pd.read_csv(REFERENCE / "lender_entities.csv", dtype=str)

    lic = lic.merge(entities[["account_number", "category", "brand"]],
                    on="account_number", how="left")

    # Pawnshops are identified by license TYPE, not by name, so no list is needed.
    is_pawn_license = lic["license_description"] == "Pawnbroker"
    lic.loc[is_pawn_license, "category"] = "pawn"
    lic.loc[is_pawn_license, "brand"] = lic.loc[is_pawn_license, "doing_business_as_name"]
    # Pawn companies sometimes hold other license types too; for pawn we only
    # count the pawnbroker licenses themselves.
    lic = lic[~((lic["category"] == "pawn") & ~is_pawn_license)]

    lic = lic[lic["category"].isin(KEEP_CATEGORIES)].copy()
    return lic


def license_spells(lic):
    """Work out the start and end date each license record actually covered."""
    lic["start"] = pd.to_datetime(lic["license_start_date"], errors="coerce")
    lic["end"] = pd.to_datetime(lic["expiration_date"], errors="coerce")
    changed = pd.to_datetime(lic["license_status_change_date"], errors="coerce")

    # Status codes: AAI = issued, AAC = cancelled, REV = revoked.
    # If a license was cancelled or revoked early, it stopped counting on that date.
    stopped_early = lic["license_status"].isin(["AAC", "REV"]) & changed.notna() & (changed < lic["end"])
    lic.loc[stopped_early, "end"] = changed[stopped_early]
    lic["cancelled_early"] = stopped_early

    lic = lic.dropna(subset=["start", "end"]).copy()
    # Storefront ID = category + standardized address, e.g. "high_cost|5638 W FULLERTON".
    # If an address can't be standardized, fall back to the city's account-site number.
    location = lic["address"].map(address_key)
    location = location.fillna("acct " + lic["account_number"] + "-" + lic["site_number"])
    lic["storefront_id"] = lic["category"] + "|" + location
    return bridge_short_gaps(lic)


def bridge_short_gaps(spells, max_gap_days=365):
    """Treat short gaps between licenses at the same storefront as continuous.

    Example: Check 'n Go's old company license ran out in Dec 2017 and the new
    company's license started in Sept 2018, at the same addresses. The stores
    almost certainly stayed open; the gap is paperwork. We add a "bridge" record
    covering any gap shorter than one year BETWEEN two licenses. We never extend
    the LAST license, so this can't hide a real closure."""
    spells = spells.sort_values(["storefront_id", "start"])
    previous_end = spells.groupby("storefront_id")["end"].shift()  # end of the license before this one
    gap_days = (spells["start"] - previous_end).dt.days
    # A normal renewal leaves a 1-day "gap" (one license ends on the 15th, the next
    # starts on the 16th) - that's not a real gap. Real gaps are 2+ days.
    needs_bridge = gap_days.between(2, max_gap_days)

    bridges = spells[needs_bridge].copy()
    bridges["end"] = bridges["start"]
    bridges["start"] = previous_end[needs_bridge]
    bridges["cancelled_early"] = False
    bridges["license_status"] = "BRIDGE"  # marks records we created, not the city
    print(f"Bridged {len(bridges)} gaps of under {max_gap_days} days between licenses")
    return pd.concat([spells, bridges], ignore_index=True)


def how_license_ended(spells):
    """For each storefront, describe its LAST license period:
    'still_active'    - covers today
    'cancelled_early' - the business cancelled (or the city revoked) it before it expired.
                        A strong sign the store actually shut down on about that date.
    'expired'         - it simply ran out and was not renewed (closure date less certain)."""
    last = spells.sort_values("end").groupby("storefront_id").tail(1).set_index("storefront_id")
    ended = pd.Series("expired", index=last.index)
    ended[last["cancelled_early"]] = "cancelled_early"
    ended[last["end"] >= pd.Timestamp.today().normalize()] = "still_active"
    return ended


def active_on(spells, date):
    """Return the set of storefront_ids that held a license on a given date."""
    date = pd.Timestamp(date)
    covering = spells[(spells["start"] <= date) & (spells["end"] >= date)]
    return set(covering["storefront_id"])


def geocode(address, zip_code):
    """Look up coordinates for one address with the free Census Geocoder."""
    one_line = f"{address}, Chicago, IL {zip_code or ''}".strip()
    params = {"address": one_line, "benchmark": "Public_AR_Current", "format": "json"}
    try:
        matches = requests.get(GEOCODER_URL, params=params, timeout=60).json()["result"]["addressMatches"]
    except Exception:
        return None, None
    if not matches:
        return None, None
    coords = matches[0]["coordinates"]
    return coords["y"], coords["x"]  # y = latitude, x = longitude


def fill_missing_coordinates(stores):
    """Geocode the storefronts the city left without coordinates.

    Results are saved in data/raw/geocode_cache.csv so we only ask the
    geocoder once per address, and the result is the same on every rebuild."""
    cache_path = RAW / "geocode_cache.csv"
    cache = (pd.read_csv(cache_path, dtype={"address": str, "zip_code": str})
             if cache_path.exists() else pd.DataFrame(columns=["address", "zip_code", "lat", "lon"]))
    # Blank ZIP codes are stored as "" (not missing) so addresses can be matched to the cache.
    cache["zip_code"] = cache["zip_code"].fillna("")
    stores["zip_code"] = stores["zip_code"].fillna("")

    missing = stores["latitude"].isna()
    new_rows = []
    for _, row in stores[missing].iterrows():
        hit = cache[(cache["address"] == row["address"]) & (cache["zip_code"] == row["zip_code"])]
        if hit.empty:
            lat, lon = geocode(row["address"], row["zip_code"])
            new_rows.append({"address": row["address"], "zip_code": row["zip_code"], "lat": lat, "lon": lon})
            time.sleep(0.5)  # be polite to a free public service
    if new_rows:
        cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
        cache.to_csv(cache_path, index=False)

    stores = stores.merge(cache, on=["address", "zip_code"], how="left")
    stores["geocoded_by"] = "city"
    use_cache = stores["latitude"].isna() & stores["lat"].notna()
    stores.loc[use_cache, "latitude"] = stores.loc[use_cache, "lat"]
    stores.loc[use_cache, "longitude"] = stores.loc[use_cache, "lon"]
    stores.loc[use_cache, "geocoded_by"] = "census_geocoder"
    stores.loc[stores["latitude"].isna(), "geocoded_by"] = "failed"
    return stores.drop(columns=["lat", "lon"])


def assign_tracts(stores):
    """Find which census tract (2010 boundaries) each storefront sits in.

    This is a "spatial join": we turn each store's latitude/longitude into a
    point and ask which tract polygon contains it."""
    tracts = gpd.read_file(RAW / "chicago_tracts_2010.geojson")[["geoid10", "commarea", "geometry"]]
    points = gpd.GeoDataFrame(
        stores,
        geometry=gpd.points_from_xy(stores["longitude"].astype(float), stores["latitude"].astype(float)),
        crs="EPSG:4326",  # EPSG:4326 = ordinary latitude/longitude
    )
    joined = gpd.sjoin(points, tracts.to_crs("EPSG:4326"), how="left", predicate="within")
    joined = joined.rename(columns={"geoid10": "tract_geoid", "commarea": "community_area"})
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"]))


def main():
    spells = license_spells(load_licenses())

    # One row per storefront, using its most recent license record for name/address/coordinates.
    latest = spells.sort_values("start").groupby("storefront_id").tail(1)
    stores = latest[["storefront_id", "category", "brand",
                     "legal_name", "doing_business_as_name", "address", "zip_code",
                     "latitude", "longitude"]].copy()
    # Every city account that ever held a license at this storefront (shows ownership changes).
    accounts = spells.groupby("storefront_id")["account_number"].agg(lambda s: ";".join(sorted(set(s))))
    stores["accounts"] = stores["storefront_id"].map(accounts)
    # Use the most recent record that HAS coordinates, if the latest one doesn't.
    with_coords = spells.dropna(subset=["latitude"]).sort_values("start").groupby("storefront_id").tail(1)
    coord_lookup = with_coords.set_index("storefront_id")[["latitude", "longitude"]]
    stores = stores.drop(columns=["latitude", "longitude"]).join(coord_lookup, on="storefront_id")

    span = spells.groupby("storefront_id").agg(first_licensed=("start", "min"),
                                               last_licensed=("end", "max"))
    stores = stores.join(span, on="storefront_id")
    stores["license_ended"] = stores["storefront_id"].map(how_license_ended(spells))

    # Snapshot flags: was the store licensed before the law, at the law date, and after?
    for label, date in [("active_pre", PRE_DATE), ("active_law", LAW_DATE), ("active_post", POST_DATE)]:
        stores[label] = stores["storefront_id"].isin(active_on(spells, date))

    # Keep only storefronts that existed at some point in our study window.
    window_start = pd.Timestamp(f"{PANEL_YEARS[0]}-01-01")
    stores = stores[stores["last_licensed"] >= window_start]

    stores = fill_missing_coordinates(stores)
    stores = assign_tracts(stores)
    stores.to_csv(CLEAN / "storefronts.csv", index=False)

    # Long "panel": storefront x year, active on Jan 1 of that year.
    panel = []
    for year in PANEL_YEARS:
        active = active_on(spells, f"{year}-01-01")
        panel.append(pd.DataFrame({"storefront_id": stores["storefront_id"],
                                   "category": stores["category"],
                                   "year": year,
                                   "active": stores["storefront_id"].isin(active)}))
    pd.concat(panel).to_csv(CLEAN / "storefront_year_panel.csv", index=False)

    print("Storefronts by category (licensed on the 'before' and 'after' dates):")
    print(stores.groupby("category")[["active_pre", "active_law", "active_post"]].sum())
    print(f"Geocoding: {stores['geocoded_by'].value_counts().to_dict()}")
    print(f"Not inside a Chicago tract: {stores['tract_geoid'].isna().sum()}")


if __name__ == "__main__":
    main()
