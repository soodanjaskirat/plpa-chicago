"""
Phase 2, part 3: did pawnshops "fill the gap" left by payday lenders? (sub-question 3)

Idea: if former payday borrowers turned to pawnshops, pawnshops NEAR closed
payday stores should have done better after the law than pawnshops far away
(more customers -> fewer closures, maybe new openings).

Two checks:
  C1  New pawnshop openings before vs. after the law, and how many opened
      within 1 mile of a payday store that was open when the law passed.
  C2  Difference-in-differences on yearly pawnshop closures:
      (near - far) closure rate after the law, minus (near - far) before.
      A negative number would mean near pawnshops survived better = substitution.

HONEST WARNING: Chicago had only ~60 pawnshops and few openings or closures,
so these tests have very little statistical power. A "no effect" result here
means "we can't tell", not "there was no substitution". Substitution could
also happen in ways licenses can't show (existing pawnshops lending more,
online lenders, borrowing from family).
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from analysis_data import load_stores, load_panel, METRIC_CRS, ACCESS_RADIUS_M
from config import RESULTS, LAW_DATE


def pawn_proximity():
    """Distance from every pawnshop to the nearest payday store open on the law date."""
    stores = load_stores().to_crs(METRIC_CRS)
    payday_at_law = stores[(stores["category"] == "high_cost") & stores["active_law"]]
    pawn = stores[stores["category"] == "pawn"].copy()
    pawn["meters_to_payday"] = pawn.geometry.apply(lambda point: payday_at_law.distance(point).min())
    pawn["near_payday"] = (pawn["meters_to_payday"] <= ACCESS_RADIUS_M).astype(int)
    return pawn


def openings(pawn):
    """C1: pawnshop openings before and after the law."""
    law = pd.Timestamp(LAW_DATE)
    opened = pawn[pawn["first_licensed"] >= "2014-01-01"].copy()
    opened["period"] = np.where(opened["first_licensed"] < law, "2014 to law", "after law")
    table = opened.groupby("period").agg(openings=("near_payday", "size"),
                                         within_1mi_of_payday=("near_payday", "sum"))
    table.to_csv(RESULTS / "pawn_openings.csv")
    return table


def closure_did(pawn):
    """C2: did pawnshops near payday stores close less often after the law?"""
    panel = load_panel()
    panel = panel[panel["category"] == "pawn"].merge(
        pawn[["storefront_id", "near_payday"]], on="storefront_id", how="left")
    rates = (panel.assign(period=np.where(panel["post"] == 1, "after (2021-25)", "before (2014-20)"))
             .groupby(["near_payday", "period"])
             .agg(store_years=("exit", "size"), closures=("exit", "sum"), closure_rate=("exit", "mean")))
    rates.to_csv(RESULTS / "pawn_closure_rates_by_proximity.csv")

    fit = smf.ols("exit ~ near_payday * post", data=panel).fit(
        cov_type="cluster", cov_kwds={"groups": panel["storefront_id"]})
    lo, hi = fit.conf_int().loc["near_payday:post"]
    result = pd.DataFrame([{
        "model": "C2 Pawn closure DiD (near vs far from payday)",
        "estimate_pct_points": fit.params["near_payday:post"] * 100,
        "ci_low": lo * 100, "ci_high": hi * 100,
        "p_value": fit.pvalues["near_payday:post"], "n": int(fit.nobs),
    }])
    result.to_csv(RESULTS / "model_substitution.csv", index=False)
    return rates, result


def main():
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    pawn = pawn_proximity()
    print("== C1. Pawnshop openings ==")
    print(openings(pawn).to_string())
    rates, result = closure_did(pawn)
    print("\n== C2. Pawnshop yearly closure rates, near (1) vs far (0) from a payday store ==")
    print(rates.to_string())
    print("\n== C2. Difference-in-differences (percentage points; negative = near pawnshops survived better) ==")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
