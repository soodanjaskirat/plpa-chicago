# Results (Phase 2)

All numbers come from `python src/run_all.py`. Full model printouts are in `model_details.txt`.

## Sub-question 1: Where were high-cost lenders before the law?

**Short answer: mostly where shops are. After accounting for that, there is a modest tilt toward neighborhoods with more Black residents. There is no relationship with income or with Latino share.**

Descriptive (`tract_comparison.csv`, `exposure_by_*.csv`), 67 high-cost storefronts on Jan 1, 2020:

| Tract group | Share of residents | Share of stores | Stores per 100k residents |
|---|---|---|---|
| Majority Black | 27% | 31% | 2.8 |
| Majority white | 33% | 34% | 2.5 |
| Majority Latino | 24% | 15% | 1.5 |
| No majority | 16% | 19% | 3.0 |
| Poorest fifth of tracts | 15% | 12% | 2.0 |
| Richest fifth of tracts | 21% | 28% | 3.2 (pulled up by 7 stores in one downtown tract) |

Tracts with a store had about 2.8 times as many licensed businesses as other tracts (153 vs 54).

Models (`model_location.csv`, Figure 6): 797 tracts. Standard errors are clustered by community area. Results are odds ratios or rate ratios; 1.00 means no relationship.

| Model | Income (+$10k) | % Black (+10 pts) | % Latino (+10 pts) |
|---|---|---|---|
| Any store, no controls (logit) | 1.08 [0.96–1.21] | 1.07 [0.95–1.21] | 1.06 [0.92–1.22] |
| Any store, + businesses (logit) | 1.01 [0.88–1.16] | **1.18 [1.04–1.34]** | 1.07 [0.92–1.25] |
| Number of stores (Poisson) | 0.95 [0.82–1.10] | 1.12 [0.97–1.29] | 1.03 [0.89–1.19] |
| Number of stores (neg. binomial) | 0.97 [0.83–1.12] | 1.13 [0.98–1.30] | 1.04 [0.89–1.22] |
| Any store, downtown excluded | 1.03 [0.89–1.18] | **1.20 [1.05–1.36]** | 1.09 [0.93–1.27] |
| Stores within 1 mile (Poisson) | 1.00 [0.94–1.05] | **1.11 [1.02–1.20]** | 1.06 [0.99–1.15] |

- Commercial activity is by far the strongest predictor. Each 1-unit increase in log businesses (about 2.7 times as many businesses) multiplies the odds of having a store by about 3.4.
- The predictors are not too correlated to separate (variance inflation factors 1.3–3.4).
- **How to read the % Black result:** among areas *equally commercial*, those with more Black residents were somewhat more likely to have a high-cost lender. Without that control, the relationship disappears, because majority-Black areas have fewer businesses overall. The effect is modest, and it falls short of statistical significance in the two count models. It should be reported as suggestive, not definitive.
- **Store location is not the same as who borrows.** Studies of payday *borrowers* (e.g. New America's analysis of IDFPR loan data) find borrowing concentrated in Black and Latino ZIP codes. People travel to stores, and online loans need no store, so the two findings don't contradict each other.

## Sub-question 2: Did lenders close after the law?

**Short answer: yes, almost all of them, within about a year and a half, while comparable storefronts did not.**

- High-cost storefronts licensed on Jan 1: 67 (2020), 65 (2021), 16 (2022), 1 (2023), 0 (2026). Pawnshops: 60 → 49 (2020–2024). All licensed storefront businesses citywide: 21,520 → 18,625.
- Of the 65 high-cost stores licensed on the day the law passed, **40 had licenses cancelled before they expired**. Every chain's last license ended within 1–17 months of the law, except one store, which ended 48 months later (`closures_by_brand.csv`).
- Yearly closure rates (`closure_rates.csv`): high-cost lenders went from 5.2% a year before the law to 77% after. Pawnshops went from 3.9% to 5.8%.
- **Difference-in-differences** (`model_closure.csv`): the law is associated with a **+70 percentage point** increase in the yearly chance a high-cost store closed, relative to pawnshops (95% CI 60–80). With separate year effects it is +69 points (57–81).
- **Parallel pre-trends check:** before the law, the gap between high-cost and pawnshop closure rates was not changing (−0.1 points per year, p = 0.83). That supports using pawnshops as the comparison.

**What this can and can't prove.** The timing, the size of the jump, the comparison group and the flat pre-trends make a strong case that the law caused the closures. Two threats remain:
1. Anything else that hit payday lenders, but not pawnshops, in 2021. National payday demand fell during COVID, for example. A comparison with payday stores in a state without a cap would address this.
2. A lapsed license is not proof of closure. See `data/README.md` for why we believe these closures are real.

## Sub-question 3: Did pawnshops fill the gap?

**Short answer: we can't tell from this data. The test is underpowered, not negative.**

- Only 9 pawnshops opened in Chicago from 2014 to 2026: 5 before the law and 4 after (`pawn_openings.csv`).
- Pawnshops within 1 mile of a payday store were not measurably more likely to survive after the law than those farther away. The difference-in-differences estimate is −1.8 points per year (95% CI −8.8 to +5.2; p = 0.61; `model_substitution.csv`).
- Substitution could also happen in ways licenses can't show: existing pawnshops making more loans, online lenders, family borrowing, or going without.

## Sub-question 3 (original version): CFPB complaints

Dropped in Phase 0. There are about 50–95 payday/personal-loan complaints a year across all Chicago-area ZIP codes, roughly one per ZIP code per year. That's too few to measure neighborhood change.

## Files
| File | Contents |
|---|---|
| `store_counts_by_year.csv` | Figure 4 data |
| `tract_comparison.csv`, `exposure_by_majority_group.csv`, `exposure_by_income_quintile.csv` | Sub-question 1 descriptives |
| `model_location.csv` | Sub-question 1 models (Figure 6) |
| `closure_rates.csv`, `model_closure.csv`, `closures_by_brand.csv` | Sub-question 2 |
| `pawn_openings.csv`, `pawn_closure_rates_by_proximity.csv`, `model_substitution.csv` | Sub-question 3 |
| `model_details.txt` | Full statistical output for every model |
