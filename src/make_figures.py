"""
Phase 2, part 4: publication figures (saved to figures/ as 300-dpi PNGs).

  fig1_map_income.png       Lender locations (2020) over tract median income
  fig2_map_race.png         Lender locations (2020) over % Black and % Latino
  fig3_model_estimates.png  Regression estimates with 95% confidence intervals
  fig4_map_before_after.png High-cost lenders and pawnshops, Jan 2020 vs Jan 2024
  fig5_trend_index.png      Store counts over time, indexed to 2020 = 100
  fig6_closure_rates.png    Yearly closure rates: high-cost lenders vs pawnshops

Design choices (so they can be explained):
  * Each kind of store keeps ONE color everywhere: high-cost = orange circle,
    pawnshop = blue square. Shape is a second cue, for colorblind readers and
    black-and-white printing.
  * Maps shade tracts with a single-hue scale (light = low, dark = high),
    in a few labeled classes, which are easier to read than a smooth gradient.
  * One y-axis per chart; light gridlines; direct labels instead of legends
    where possible.
"""

import matplotlib
matplotlib.use("Agg")  # draw to files, no window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import geopandas as gpd
from analysis_data import load_tracts, load_stores, load_panel
from config import FIGURES, RAW, RESULTS, CLEAN

# --- Colors (validated reference palette) ---
HIGH_COST = "#eb6834"   # orange
PAWN = "#2a78d6"        # blue
NEUTRAL = "#8a8984"     # gray, for the citywide background line
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
NO_DATA = "#f0efec"
BLUES = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # sequential ramp, 5 classes

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10.5,
    "axes.titleweight": "bold", "axes.edgecolor": INK_2, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300,
    "savefig.bbox": "tight", "figure.facecolor": "white",
})

LAW_YEAR = 2021 + 82 / 365  # March 23, 2021 as a decimal year


def base_map(ax, community_areas):
    ax.set_axis_off()
    community_areas.boundary.plot(ax=ax, color="white", linewidth=0.6, zorder=2)


def classed_choropleth(ax, tracts, column, bins, labels, title):
    """Shade tracts by class (bins) with the blue ramp; tracts with no data in light gray."""
    cmap = ListedColormap(BLUES[:len(labels)])
    norm = BoundaryNorm(bins, cmap.N)
    tracts[tracts[column].isna()].plot(ax=ax, color=NO_DATA, hatch="///", edgecolor="#d6d5cf", linewidth=0)
    tracts.dropna(subset=[column]).plot(ax=ax, column=column, cmap=cmap, norm=norm, linewidth=0)
    ax.set_title(title, loc="left")
    return [Patch(facecolor=BLUES[i], label=lab) for i, lab in enumerate(labels)]


def plot_stores(ax, stores, color, marker, size=26, label=None):
    stores.plot(ax=ax, color=color, marker=marker, markersize=size, edgecolor="white",
                linewidth=0.7, zorder=5, label=label)


def store_handle(color, marker, label):
    return Line2D([], [], color=color, marker=marker, linestyle="none", markersize=6.5,
                  markeredgecolor="white", label=label)


def fig1_income(tracts_all, community_areas, high_cost_pre):
    fig, ax = plt.subplots(figsize=(5.2, 6.6))
    tracts_all = tracts_all.copy()
    tracts_all["income_k"] = tracts_all["median_hh_income"] / 1000
    patches = classed_choropleth(
        ax, tracts_all, "income_k", [0, 30, 50, 75, 100, 300],
        ["Under $30k", "$30k–50k", "$50k–75k", "$75k–100k", "Over $100k"],
        "High-cost lenders in January 2020,\nby neighborhood median household income")
    base_map(ax, community_areas)
    plot_stores(ax, high_cost_pre, HIGH_COST, "o")
    handles = patches + [Patch(facecolor=NO_DATA, hatch="///", edgecolor="#d6d5cf", label="No estimate"),
                         store_handle(HIGH_COST, "o", f"High-cost lender ({len(high_cost_pre)})")]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8, title="Tract median income",
              title_fontsize=8, alignment="left")
    ax.annotate("Downtown (Loop):\n7 stores in one tract", xy=(447800, 4636600), xytext=(452500, 4643500),
                fontsize=7.5, color=INK_2, arrowprops=dict(arrowstyle="-", color=INK_2, lw=0.7))
    fig.text(0.02, 0.01, "Sources: City of Chicago business licenses; ACS 2015–2019 5-year estimates.",
             fontsize=7, color=INK_2)
    fig.savefig(FIGURES / "fig1_map_income.png")
    plt.close(fig)


def fig2_race(tracts_all, community_areas, high_cost_pre):
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 5.6))
    fig.subplots_adjust(left=0, right=1, wspace=0.02, top=0.86, bottom=0.08)
    bins = [0, 0.10, 0.25, 0.50, 0.75, 1.0001]
    labels = ["Under 10%", "10–25%", "25–50%", "50–75%", "Over 75%"]
    for ax, column, name in [(axes[0], "pct_black", "Black residents"),
                             (axes[1], "pct_hispanic", "Latino residents")]:
        patches = classed_choropleth(ax, tracts_all, column, bins, labels, f"Share of {name}")
        base_map(ax, community_areas)
        plot_stores(ax, high_cost_pre, HIGH_COST, "o", size=20)
    handles = patches + [store_handle(HIGH_COST, "o", f"High-cost lender, Jan 2020 ({len(high_cost_pre)})")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=8,
               bbox_to_anchor=(0.5, -0.04), title="Share of tract residents", title_fontsize=8)
    fig.suptitle("High-cost lenders in January 2020, by neighborhood racial and ethnic composition",
                 x=0.02, ha="left", fontweight="bold", fontsize=10.5)
    fig.text(0.02, -0.09, "Sources: City of Chicago business licenses; ACS 2015–2019 5-year estimates.",
             fontsize=7, color=INK_2)
    fig.savefig(FIGURES / "fig2_map_race.png")
    plt.close(fig)


def fig4_before_after(tracts_all, community_areas, stores):
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 5.6))
    fig.subplots_adjust(left=0, right=1, wspace=0.02, top=0.86, bottom=0.02)
    for ax, flag, title in [(axes[0], "active_pre", "January 2020 (before the law)"),
                            (axes[1], "active_post", "January 2024 (after the law)")]:
        tracts_all.plot(ax=ax, color=NO_DATA, edgecolor="white", linewidth=0.2)
        base_map(ax, community_areas)
        community_areas.boundary.plot(ax=ax, color="#d6d5cf", linewidth=0.5, zorder=2)
        hc = stores[(stores["category"] == "high_cost") & stores[flag]]
        pawn = stores[(stores["category"] == "pawn") & stores[flag]]
        plot_stores(ax, pawn, PAWN, "s", size=18)
        plot_stores(ax, hc, HIGH_COST, "o", size=22)
        ax.set_title(title, loc="left")
        ax.legend(handles=[store_handle(HIGH_COST, "o", f"High-cost lenders: {len(hc)}"),
                           store_handle(PAWN, "s", f"Pawnshops: {len(pawn)}")],
                  loc="lower left", frameon=False, fontsize=8.5)
    fig.suptitle("Storefront high-cost lenders nearly vanished after the 36% APR cap; pawnshops mostly remained",
                 x=0.02, ha="left", fontweight="bold", fontsize=10.5)
    fig.text(0.02, -0.01, "Locations licensed by the City of Chicago on each date. "
             "Pawnshops were exempted from the cap (2021 court injunction; Public Act 103-0585, 2024).",
             fontsize=7, color=INK_2)
    fig.savefig(FIGURES / "fig4_map_before_after.png")
    plt.close(fig)


def fig5_trend():
    counts = pd.read_csv(RESULTS / "store_counts_by_year.csv").set_index("year")
    index = counts / counts.loc[2020] * 100
    fig, ax = plt.subplots(figsize=(6.8, 3.9))
    series = [("high_cost", "High-cost lenders", HIGH_COST, "o"),
              ("pawn", "Pawnshops", PAWN, "s"),
              ("limited_license_locations", "All licensed storefront businesses", NEUTRAL, None)]
    for col, label, color, marker in series:
        ax.plot(index.index, index[col], color=color, linewidth=2, marker=marker, markersize=5,
                markeredgecolor="white", markeredgewidth=0.6)
        last = index[col].iloc[-1] + {"high_cost": 0, "pawn": -8, "limited_license_locations": 8}[col]
        ax.text(index.index[-1] + 0.25, last, f"{label}\n({int(counts[col].iloc[-1]):,} in 2026)",
                color=INK, fontsize=8, va="center")
    ax.axvline(LAW_YEAR, color=INK_2, linestyle="--", linewidth=1)
    ax.text(LAW_YEAR + 0.1, 150, "Law takes effect\n(March 2021)", fontsize=8, color=INK_2, va="top")
    ax.axhline(100, color=GRID, linewidth=1, zorder=0)
    ax.set_ylim(-5, 155)
    ax.set_xlim(2013.6, 2026.4)
    ax.set_xticks(range(2014, 2027, 2))
    ax.set_ylabel("Count on January 1 (2020 = 100)")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_title("High-cost lenders fell from 65 to 1 within two years; other businesses declined slowly",
                 loc="left")
    fig.text(0.01, -0.03, "Source: City of Chicago business licenses (storefronts licensed on January 1 of each year).",
             fontsize=7, color=INK_2)
    fig.savefig(FIGURES / "fig5_trend_index.png")
    plt.close(fig)


def fig6_closure_rates():
    panel = load_panel()
    rates = panel.groupby(["category", "year"]).agg(at_risk=("exit", "size"), rate=("exit", "mean")).reset_index()
    rates = rates[rates["at_risk"] >= 5]  # too few stores to compute a meaningful rate
    fig, ax = plt.subplots(figsize=(6.8, 3.9))
    for category, label, color, marker in [("high_cost", "High-cost lenders", HIGH_COST, "o"),
                                           ("pawn", "Pawnshops", PAWN, "s")]:
        r = rates[rates["category"] == category]
        ax.plot(r["year"] + 0.5, r["rate"] * 100, color=color, linewidth=2, marker=marker, markersize=6,
                markeredgecolor="white", markeredgewidth=0.6, label=label)
    ax.axvline(LAW_YEAR, color=INK_2, linestyle="--", linewidth=1)
    ax.text(LAW_YEAR + 0.1, 98, "Law takes effect", fontsize=8, color=INK_2, va="top")
    ax.set_ylim(0, 100)
    ax.set_xticks([y + 0.5 for y in range(2014, 2026, 2)])
    ax.set_xticklabels([f"{y}–{str(y + 1)[2:]}" for y in range(2014, 2026, 2)])
    ax.set_ylabel("Share of open stores that closed\nduring the year (%)")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.legend(frameon=False, loc="center left")
    ax.set_title("Before the law, both store types closed at about 4–5% a year; after it, high-cost lenders closed en masse",
                 loc="left", fontsize=9.5)
    fig.text(0.01, -0.03, "Each point covers Jan 1 of one year to Jan 1 of the next. Years with fewer than "
             "5 open stores are not shown (high-cost lenders after 2022).", fontsize=7, color=INK_2)
    fig.savefig(FIGURES / "fig6_closure_rates.png")
    plt.close(fig)


def fig3_model_estimates():
    models = pd.read_csv(RESULTS / "model_location.csv")
    terms = ["Median income (+$10k)", "% Black (+10 pts)", "% Latino (+10 pts)"]
    order = ["A1a Logit, no controls", "A1b Logit + businesses", "A2a Poisson count + businesses",
             "A2b Neg. binomial count + businesses", "A3a Logit, Loop excluded", "A3b Poisson, stores within 1 mile"]
    short = ["Any store (no controls)", "Any store", "Number of stores", "Number of stores (neg. binomial)",
             "Any store, excluding downtown", "Stores within 1 mile"]
    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.6), sharey=True)
    fig.subplots_adjust(top=0.8, wspace=0.12)
    y = np.arange(len(order))[::-1]
    for ax, term in zip(axes, terms):
        d = models[models["term"] == term].set_index("model").loc[order]
        ax.hlines(y, d["ci_low"], d["ci_high"], color=INK_2, linewidth=1.6)
        ax.plot(d["estimate"], y, "o", color=INK, markersize=6)
        ax.axvline(1, color=INK_2, linestyle="--", linewidth=0.9)
        ax.set_xticks([0.8, 1.0, 1.2, 1.4])
        ax.set_xlim(0.78, 1.45)
        ax.set_title(term, loc="left", fontsize=9.5)
        ax.grid(axis="x", color=GRID, linewidth=0.6)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(short)
    axes[1].set_xlabel("Odds ratio or rate ratio (1 = no relationship), with 95% confidence interval")
    fig.suptitle("Income and % Latino show no clear link to lender presence;\n% Black shows a modest positive link "
                 "once commercial activity is held constant", x=0.01, y=0.99, ha="left", fontweight="bold", fontsize=9.5)
    fig.text(0.01, -0.06, "All models except the first control for the number of licensed businesses. "
             "Standard errors clustered by community area. N = 797 tracts (792 excluding downtown).",
             fontsize=7, color=INK_2)
    fig.savefig(FIGURES / "fig3_model_estimates.png")
    plt.close(fig)


def main():
    # Draw maps in a projection measured in meters (UTM 16N) so shapes are not stretched.
    tracts_all = gpd.read_file(CLEAN / "tracts_analysis.geojson").to_crs("EPSG:26916")
    community_areas = gpd.read_file(RAW / "chicago_community_areas.geojson").to_crs(tracts_all.crs)
    stores = load_stores().to_crs(tracts_all.crs)
    high_cost_pre = stores[(stores["category"] == "high_cost") & stores["active_pre"]]

    fig1_income(tracts_all, community_areas, high_cost_pre)
    fig2_race(tracts_all, community_areas, high_cost_pre)
    fig3_model_estimates()
    fig4_before_after(tracts_all, community_areas, stores)
    fig5_trend()
    fig6_closure_rates()
    print("Saved figures:", ", ".join(sorted(p.name for p in FIGURES.glob("*.png"))))


if __name__ == "__main__":
    main()
