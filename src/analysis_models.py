"""
Phase 2, part 2: regression models.

MODEL SET A - Where were high-cost lenders located before the law? (sub-question 1)
  Unit: census tract (797 tracts where people live).
  A1  Logistic regression: does the tract have at least one store? (yes/no)
      - no controls, then with the commercial-activity control.
      Logistic regression is the standard model for a yes/no outcome; its results
      are "odds ratios": 1.20 means 20% higher odds, 0.80 means 20% lower odds.
  A2  Poisson regression: HOW MANY stores does the tract have? (0, 1, 2, ...)
      Poisson is the standard model for counts. Results are "incidence rate
      ratios" (IRR): 1.20 = 20% more stores expected. Our counts are more
      spread out than a textbook Poisson expects ("overdispersion": variance
      0.15 vs mean 0.08), so we use robust standard errors, and check the
      answer with a negative binomial model, which allows extra spread.
  A3  Robustness: drop downtown (the Loop), and measure access as stores
      within 1 mile instead of inside the tract.

  Standard errors are "clustered" by community area: neighboring tracts are
  similar, so treating all 797 as fully independent would overstate certainty.

MODEL SET B - Did high-cost stores close faster than pawnshops after the law? (sub-question 2)
  Unit: store-year. For each store open on Jan 1, did it close during the year?
  Difference-in-differences: (high-cost closure rate after - before) minus
  (pawnshop closure rate after - before). Pawnshops are the comparison group:
  similar fringe-finance storefronts, same neighborhoods, same COVID years,
  but (according to news reports, to verify) exempt from the 36% cap.
  We use a "linear probability model" (ordinary regression on a 0/1 outcome)
  so the result reads directly as percentage points.

Results go to results/; full model printouts to results/model_details.txt.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor

from analysis_data import load_tracts, load_panel, LOOP_COMMUNITY_AREA
from config import RESULTS

DEMOGRAPHICS = "income_10k + black_10pp + latino_10pp"
LABELS = {
    "income_10k": "Median income (+$10k)",
    "black_10pp": "% Black (+10 pts)",
    "latino_10pp": "% Latino (+10 pts)",
    "log_businesses": "Businesses in tract (log)",
    "log_businesses_1mi": "Businesses within 1 mi (log)",
}


def tidy(result, model_name, exponentiate=True):
    """Turn a fitted model into a small table: estimate, 95% CI, p-value."""
    ci = result.conf_int()
    table = pd.DataFrame({
        "model": model_name,
        "term": result.params.index,
        "estimate": result.params.values,
        "ci_low": ci[0].values,
        "ci_high": ci[1].values,
        "p_value": result.pvalues.values,
        "n": int(result.nobs),
    })
    if exponentiate:  # odds ratios / rate ratios are exp(coefficient)
        table[["estimate", "ci_low", "ci_high"]] = np.exp(table[["estimate", "ci_low", "ci_high"]])
    table = table[table["term"] != "Intercept"]
    table["term"] = table["term"].map(LABELS).fillna(table["term"])
    return table


def location_models(tracts, details):
    """Model set A."""
    cluster = {"groups": tracts["community_area"]}
    no_loop = tracts[tracts["community_area"] != LOOP_COMMUNITY_AREA]
    specs = [
        # (name, formula, family, data)
        ("A1a Logit, no controls", f"any_high_cost_pre ~ {DEMOGRAPHICS}", "logit", tracts),
        ("A1b Logit + businesses", f"any_high_cost_pre ~ {DEMOGRAPHICS} + log_businesses", "logit", tracts),
        ("A2a Poisson count + businesses", f"n_high_cost_pre ~ {DEMOGRAPHICS} + log_businesses", "poisson", tracts),
        ("A2b Neg. binomial count + businesses", f"n_high_cost_pre ~ {DEMOGRAPHICS} + log_businesses", "negbin", tracts),
        ("A3a Logit, Loop excluded", f"any_high_cost_pre ~ {DEMOGRAPHICS} + log_businesses", "logit", no_loop),
        ("A3b Poisson, stores within 1 mile", f"high_cost_within_1mi ~ {DEMOGRAPHICS} + log_businesses_1mi", "poisson", tracts),
    ]
    tables = []
    for name, formula, family, data in specs:
        groups = {"groups": data["community_area"]}
        if family == "logit":
            fit = smf.logit(formula, data=data).fit(disp=False, cov_type="cluster", cov_kwds=groups)
        elif family == "poisson":
            fit = smf.glm(formula, data=data, family=sm.families.Poisson()).fit(cov_type="cluster", cov_kwds=groups)
        else:
            fit = smf.negativebinomial(formula, data=data).fit(disp=False, maxiter=200, cov_type="cluster", cov_kwds=groups)
        details.append(f"\n\n===== {name} =====\n{fit.summary()}")
        table = tidy(fit, name)
        tables.append(table[table["term"] != "alpha"])  # alpha = NB dispersion, not a predictor
    out = pd.concat(tables)
    out.to_csv(RESULTS / "model_location.csv", index=False)

    # Multicollinearity check: are the predictors too correlated to separate?
    # VIF above ~5 would be a warning sign.
    X = sm.add_constant(tracts[["income_10k", "black_10pp", "latino_10pp", "log_businesses"]])
    vif = pd.Series([variance_inflation_factor(X.values, i) for i in range(1, X.shape[1])],
                    index=X.columns[1:], name="VIF")
    details.append(f"\n\n===== Variance inflation factors =====\n{vif.round(2).to_string()}")
    return out, vif


def closure_models(panel, details):
    """Model set B: difference-in-differences on yearly closure rates."""
    rates = (panel.assign(period=np.where(panel["post"] == 1, "after (2021-25)", "before (2014-20)"))
             .groupby(["category", "period"])
             .agg(store_years=("exit", "size"), closures=("exit", "sum"), closure_rate=("exit", "mean")))
    rates.to_csv(RESULTS / "closure_rates.csv")

    cluster = {"groups": panel["storefront_id"]}
    # B1: the classic 2x2 difference-in-differences.
    b1 = smf.ols("exit ~ high_cost * post", data=panel).fit(cov_type="cluster", cov_kwds=cluster)
    # B2: same, but with a separate baseline for every year (absorbs COVID, economy-wide shocks).
    b2 = smf.ols("exit ~ high_cost + high_cost:post + C(year)", data=panel).fit(cov_type="cluster", cov_kwds=cluster)
    # B3: pre-trend check, before the law only: were high-cost closures already
    # rising faster than pawnshop closures? (parallel-trends assumption)
    pre = panel[panel["post"] == 0]
    b3 = smf.ols("exit ~ high_cost * year", data=pre).fit(cov_type="cluster", cov_kwds={"groups": pre["storefront_id"]})

    for name, fit in [("B1 DiD 2x2", b1), ("B2 DiD with year effects", b2), ("B3 Pre-law trend check", b3)]:
        details.append(f"\n\n===== {name} =====\n{fit.summary()}")
    keep = {"B1 DiD 2x2": (b1, "high_cost:post"),
            "B2 DiD with year effects": (b2, "high_cost:post"),
            "B3 Pre-law trend difference (per year)": (b3, "high_cost:year")}
    rows = []
    for name, (fit, term) in keep.items():
        lo, hi = fit.conf_int().loc[term]
        rows.append({"model": name, "term": term, "estimate_pct_points": fit.params[term] * 100,
                     "ci_low": lo * 100, "ci_high": hi * 100, "p_value": fit.pvalues[term], "n": int(fit.nobs)})
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "model_closure.csv", index=False)
    return rates, out


def main():
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    details = []

    tracts = load_tracts()
    loc, vif = location_models(tracts, details)
    print("== A. Where were high-cost lenders? (odds ratios / rate ratios, 95% CI) ==")
    print(loc[["model", "term", "estimate", "ci_low", "ci_high", "p_value", "n"]].to_string(index=False))
    print("\nVariance inflation factors (above ~5 = worry):")
    print(vif.round(2).to_string())

    panel = load_panel()
    rates, did = closure_models(panel, details)
    print("\n== B. Yearly closure rates ==")
    print(rates.to_string())
    print("\n== B. Difference-in-differences (percentage points) ==")
    print(did.to_string(index=False))

    (RESULTS / "model_details.txt").write_text("\n".join(details))


if __name__ == "__main__":
    main()
