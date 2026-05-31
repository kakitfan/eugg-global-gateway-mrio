"""Supplementary figures for Chapter 4 (EUGG).

Function names are aligned with the chapter figure number they produce:

  fig_4_01_pop_invest_income          - §4.1.2 Population/investment/footprint shares
  fig_4_02_carbon_output_asymmetry    - §4.1.3 Carbon-output asymmetry
  fig_4_06_incgroup_gini              - §4.2.3 Income-group gradient in Gini response
  fig_4_07_region_performance         - §4.2.3 Regional Gini performance
  fig_4_08_recipients_vs_nonrec       - §4.2.3 Recipients vs non-recipients
  fig_4_09_recipient_grid             - §4.2.3 Country-level grid for 37 recipients
  fig_4_10_baseline_pyramid           - §4.3.1 Baseline carbon-footprint pyramid
  fig_4_11_incgroup_theil_change      - §4.3.1 Mean within-country Theil change by income group
  fig_4_12_winscore_by_income         - §4.3.3 Multi-dimensional Win Scores
  fig_4_13_investment_vs_theil        - §4.3.3 Investment size vs within-country Theil change

Reads results/Data/EUGG_Results.xlsx exclusively and writes
PDF + PNG to results/Figures/.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
EXCEL_PATH = HERE / "results" / "Data" / "EUGG_Results.xlsx"
OUT_DIRS = [
    HERE / "results" / "Figures",
]

# --------------------------------------------------------------------------- #
# Global style
# --------------------------------------------------------------------------- #
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

COLOR_EU = "#1F497D"      # thesis heading blue
COLOR_ROW = "#C0504D"     # warm red
COLOR_RECIP = "#9E3E3A"
COLOR_NONRECIP = "#4F6D8C"
COLOR_POS = "#C0504D"
COLOR_NEG = "#4F81BD"
COLOR_GRID = "#DDDDDD"


def _save(fig: plt.Figure, stem: str) -> None:
    for d in OUT_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        fig.savefig(d / f"{stem}.pdf", bbox_inches="tight")
        fig.savefig(d / f"{stem}.png", bbox_inches="tight", dpi=300)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Figure 4.2 - Carbon-output asymmetry (§4.1.3)
# --------------------------------------------------------------------------- #
def fig_4_02_carbon_output_asymmetry() -> None:
    """EU vs recipients share of induced GDP and CO2; plus EV-ratio.

    Note: the original three-bar panel (Investment / GDP / CO2) was
    revised because the Investment bar is fixed at 0% EU / 100% non-EU
    by construction and conveys no information. Panel (a) now shows
    only the two informative shares; the 0% direct-investment baseline
    is documented in the caption and as an annotation on the panel.
    """
    df_g = pd.read_excel(EXCEL_PATH, sheet_name="1_Global")
    r = df_g.iloc[0]
    total_gdp = r["GDP_Billion"]
    total_co2 = r["CO2_Mt"]
    eu_va = r["EU_SpilloverVA_MEUR"] / 1000.0   # -> B EUR
    eu_co2 = r["EU_SpilloverCO2_Mt"]

    # Panel (a): two shares (GDP, CO2). Investment is fixed at 0% EU / 100% non-EU.
    categories = ["Induced GDP", r"Induced CO$_2$"]
    eu_share = np.array([eu_va / total_gdp, eu_co2 / total_co2]) * 100
    row_share = 100 - eu_share

    # Panel (b): EV-ratio (tCO2 per k EUR)
    ev_eu = eu_co2 * 1e6 / (eu_va * 1e9 / 1000)         # Mt / (BEUR*1e6 kEUR) -> tCO2/kEUR
    ev_global = total_co2 * 1e6 / (total_gdp * 1e9 / 1000)
    recip_va = total_gdp - eu_va
    recip_co2 = total_co2 - eu_co2
    ev_recip = recip_co2 * 1e6 / (recip_va * 1e9 / 1000)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 4.0),
                                   gridspec_kw={"width_ratios": [1.3, 1]})

    # --- Panel (a)
    y = np.arange(len(categories))[::-1]
    ax1.barh(y, eu_share, color=COLOR_EU, label="EU member states")
    ax1.barh(y, row_share, left=eu_share, color=COLOR_ROW,
             label="Recipients and other non-EU")
    for yi, (e, w) in enumerate(zip(eu_share, row_share)):
        yy = y[yi]
        if e > 3:
            ax1.text(e / 2, yy, f"{e:.1f}%", ha="center", va="center",
                     color="white", fontsize=9, fontweight="bold")
        else:
            ax1.text(e + 0.5, yy, f"{e:.1f}%", ha="left", va="center",
                     color=COLOR_EU, fontsize=9, fontweight="bold")
        ax1.text(e + w / 2, yy, f"{w:.1f}%", ha="center", va="center",
                 color="white", fontsize=9, fontweight="bold")
    ax1.set_yticks(y)
    ax1.set_yticklabels(categories)
    ax1.set_xlim(0, 100)
    ax1.set_xlabel("Share of investment-induced total (%)")
    ax1.set_title(r"(a) EU vs non-EU shares of induced GDP and CO$_2$",
                  loc="left", fontweight="bold")
    # Annotation noting the 0% direct-investment baseline
    ax1.text(50, -0.55, "EU receives 0% of direct investment",
             ha="center", va="center", fontsize=8.5,
             style="italic", color="#555555")
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, -0.32),
               ncol=2, frameon=False, fontsize=9)
    ax1.grid(axis="x", color=COLOR_GRID, linewidth=0.5)
    ax1.set_axisbelow(True)

    # --- Panel (b): EV-ratio
    labels = ["EU spillover", "EUGG\naverage", "Recipient\nproduction"]
    vals = [ev_eu, ev_global, ev_recip]
    colors = [COLOR_EU, "#888888", COLOR_ROW]
    bars = ax2.bar(labels, vals, color=colors, width=0.55)
    for b, v in zip(bars, vals):
        ax2.text(b.get_x() + b.get_width() / 2, v + 0.02,
                 f"{v:.2f}", ha="center", va="bottom",
                 fontsize=9, fontweight="bold")
    ax2.axhline(ev_global, color="#888888", linestyle="--", linewidth=0.8)
    ax2.set_ylabel(r"tCO$_2$ per kEUR value added")
    ax2.set_ylim(0, max(vals) * 1.18)
    ax2.set_title("(b) Emission-to-value ratio",
                  loc="left", fontweight="bold")
    ax2.grid(axis="y", color=COLOR_GRID, linewidth=0.5)
    ax2.set_axisbelow(True)

    fig.tight_layout()
    _save(fig, "Figure_4-02_Carbon_Output_Asymmetry")
    logger.info("Wrote Figure_4-02_Carbon_Output_Asymmetry")


# --------------------------------------------------------------------------- #
# Figure 4.8 - Recipients vs non-recipients (§4.2.3)
# --------------------------------------------------------------------------- #
def fig_4_08_recipients_vs_nonrec() -> None:
    """Direct investment recipients vs non-recipients: improvement and dGini."""
    df = pd.read_excel(EXCEL_PATH, sheet_name="13_TripleAsymm_4D")
    df = df.dropna(subset=["Gini_Change"])
    recip = df[df["Investment_MEur"].fillna(0) > 1e-6]
    non = df[df["Investment_MEur"].fillna(0) <= 1e-6]

    def summary(d: pd.DataFrame) -> tuple[int, int, float]:
        improved = int((d["Gini_Change"] < 0).sum())
        return len(d), improved, d["Gini_Change"].mean()

    n_r, i_r, m_r = summary(recip)
    n_n, i_n, m_n = summary(non)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 4.0),
                                   gridspec_kw={"width_ratios": [1, 1.3]})

    # --- Panel (a): improvement share
    labels = [f"Recipients\n(N={n_r})", f"Non-recipients\n(N={n_n})"]
    pct_impr = [100 * i_r / n_r, 100 * i_n / n_n]
    pct_wors = [100 - p for p in pct_impr]
    x = np.arange(len(labels))
    ax1.bar(x, pct_impr, color="#4F81BD", label="Domestic Gini improved",
            width=0.55)
    ax1.bar(x, pct_wors, bottom=pct_impr, color="#C0504D",
            label="Worsened or unchanged", width=0.55)
    for xi, (pi, pw) in enumerate(zip(pct_impr, pct_wors)):
        ax1.text(xi, pi / 2, f"{pi:.0f}%", ha="center", va="center",
                 color="white", fontweight="bold", fontsize=10)
        ax1.text(xi, pi + pw / 2, f"{pw:.0f}%", ha="center", va="center",
                 color="white", fontweight="bold", fontsize=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("Share of countries (%)")
    ax1.set_title("(a) Domestic inequality outcome",
                  loc="left", fontweight="bold")
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, -0.30),
               ncol=2, frameon=False, fontsize=9)
    ax1.grid(axis="y", color=COLOR_GRID, linewidth=0.5)
    ax1.set_axisbelow(True)

    # --- Panel (b): dGini distribution (strip + box)
    r_vals = recip["Gini_Change"].values * 1e3   # scale to 10^-3 for readability
    n_vals = non["Gini_Change"].values * 1e3
    positions = [1, 2]
    parts = ax2.violinplot([r_vals, n_vals], positions=positions,
                           showmeans=False, showmedians=False,
                           showextrema=False, widths=0.7)
    for body, c in zip(parts["bodies"], [COLOR_RECIP, COLOR_NONRECIP]):
        body.set_facecolor(c)
        body.set_alpha(0.25)
        body.set_edgecolor(c)
    rng = np.random.default_rng(42)
    for pos, vals, c in zip(positions, [r_vals, n_vals],
                            [COLOR_RECIP, COLOR_NONRECIP]):
        jitter = rng.normal(0, 0.04, size=len(vals))
        ax2.scatter(np.full_like(vals, pos) + jitter, vals,
                    s=14, color=c, alpha=0.65, edgecolors="white",
                    linewidths=0.4)
    # Means
    for pos, m in zip(positions, [m_r * 1e3, m_n * 1e3]):
        ax2.hlines(m, pos - 0.28, pos + 0.28, color="black",
                   linewidth=1.8)
        ax2.text(pos + 0.32, m, rf"mean = {m:+.2f}$\times 10^{{-3}}$",
                 va="center", fontsize=8.5)
    ax2.axhline(0, color="black", linewidth=0.7, linestyle="--")
    ax2.set_xticks(positions)
    ax2.set_xticklabels([f"Recipients (N={n_r})",
                         f"Non-recipients (N={n_n})"])
    ax2.set_ylabel(r"$\Delta$Gini ($\times 10^{-3}$)")
    ax2.set_title(r"(b) Distribution of domestic $\Delta$Gini",
                  loc="left", fontweight="bold")
    # Clip to reasonable range so medians are visible
    lo = np.percentile(np.concatenate([r_vals, n_vals]), 1)
    hi = np.percentile(np.concatenate([r_vals, n_vals]), 99)
    pad = (hi - lo) * 0.12
    ax2.set_ylim(lo - pad, hi + pad)
    ax2.grid(axis="y", color=COLOR_GRID, linewidth=0.5)
    ax2.set_axisbelow(True)

    fig.tight_layout()
    _save(fig, "Figure_4-08_Recipients_vs_NonRecipients")
    logger.info("Wrote Figure_4-08_Recipients_vs_NonRecipients")


# --------------------------------------------------------------------------- #
# Figure 4.10 - Baseline carbon-footprint pyramid (§4.3.1)
# --------------------------------------------------------------------------- #
def fig_4_10_baseline_pyramid() -> None:
    """Population weight vs footprint share and within-country Theil by income group."""
    df = pd.read_excel(EXCEL_PATH, sheet_name="11_IncGroup_Theil")
    order = ["High income", "Upper middle income",
             "Lower middle income", "Low income"]
    df = df.set_index("IncomeGroup").loc[order].reset_index()

    pop = df["PopShare_Total"].values * 100
    fp_share = df["IncShare_Base"].values * 100
    t_mean = df["TWithin_Mean_Base"].values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2),
                                   gridspec_kw={"width_ratios": [1.25, 1]})

    y = np.arange(len(order))[::-1]

    # --- Panel (a): diverging bars
    ax1.barh(y, -pop, color="#4F81BD", label="Population weight",
             height=0.55)
    ax1.barh(y, fp_share, color="#C0504D", label="Footprint share",
             height=0.55)
    for yi, (p, i) in enumerate(zip(pop, fp_share)):
        yy = y[yi]
        ax1.text(-p - 2, yy, f"{p:.1f}%", ha="right", va="center",
                 fontsize=9, color="#4F81BD", fontweight="bold")
        ax1.text(i + 2, yy, f"{i:.2f}%" if i < 1 else f"{i:.1f}%",
                 ha="left", va="center",
                 fontsize=9, color="#C0504D", fontweight="bold")
    ax1.axvline(0, color="black", linewidth=0.7)
    ax1.set_yticks(y)
    ax1.set_yticklabels(order)
    ax1.set_xlim(-85, 85)
    xt = np.array([-80, -60, -40, -20, 0, 20, 40, 60, 80])
    ax1.set_xticks(xt)
    ax1.set_xticklabels([f"{abs(v):.0f}" for v in xt])
    ax1.set_xlabel("Share (%)  <- Population weight | Footprint share ->")
    ax1.set_title("(a) Population weight vs footprint share",
                  loc="left", fontweight="bold")
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, -0.28),
               ncol=2, frameon=False, fontsize=9)
    ax1.grid(axis="x", color=COLOR_GRID, linewidth=0.5)
    ax1.set_axisbelow(True)

    # --- Panel (b): within-country Theil mean
    colors = ["#4F81BD", "#6DA4CB", "#C87A74", "#9E3E3A"]
    bars = ax2.barh(y, t_mean, color=colors, height=0.55)
    for b, v in zip(bars, t_mean):
        ax2.text(v + 0.03, b.get_y() + b.get_height() / 2,
                 f"{v:.2f}", va="center", fontsize=9,
                 fontweight="bold")
    ax2.set_yticks(y)
    ax2.set_yticklabels(order)
    ax2.set_xlim(0, max(t_mean) * 1.22)
    ax2.set_xlabel("Mean within-country Theil T (baseline)")
    ax2.set_title("(b) Baseline carbon-footprint inequality",
                  loc="left", fontweight="bold")
    ax2.grid(axis="x", color=COLOR_GRID, linewidth=0.5)
    ax2.set_axisbelow(True)

    fig.tight_layout()
    _save(fig, "Figure_4-10_Baseline_Carbon_Pyramid")
    logger.info("Wrote Figure_4-10_Baseline_Carbon_Pyramid")


# --------------------------------------------------------------------------- #
# Figure 4.1 - Population / investment / footprint shares by income group (§4.1.2)
# --------------------------------------------------------------------------- #
def fig_4_01_pop_invest_income() -> None:
    """Three side-by-side bars by World Bank income group (Fig 4.1).

    Investment share is computed against the EUGG total (€300B), not
    against the sum of rows carrying an IncomeGroup label. ~49.7% of the
    investment is allocated to regional aggregates ('Rest of Africa',
    'Rest of Asia-Pacific') that do not map to a single income group.
    """
    df4d = pd.read_excel(EXCEL_PATH, sheet_name="13_TripleAsymm_4D")
    eugg_total_meur = float(df4d["Investment_MEur"].sum())  # 300 000 MEUR

    # Keep only country rows with an IncomeGroup for population/footprint/investment bars.
    df_grp = df4d.dropna(subset=["IncomeGroup"])

    order = ["High income", "Upper middle income",
             "Lower middle income", "Low income"]
    pop = df_grp.groupby("IncomeGroup")["PopShare"].sum().reindex(order).fillna(0.0) * 100
    fp_share = df_grp.groupby("IncomeGroup")["IncShare_Base"].sum().reindex(order).fillna(0.0) * 100
    inv = df_grp.groupby("IncomeGroup")["Investment_MEur"].sum().reindex(order).fillna(0.0)
    inv_share = inv / eugg_total_meur * 100
    unclassified_pop = 100 - pop.sum()
    unclassified_inv = 100 - inv_share.sum()
    unclassified_fp = 100 - fp_share.sum()

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    y = np.arange(len(order))
    h = 0.26
    b1 = ax.barh(y + h, pop.values,        h, color="#4F81BD", label="Population weight")
    b2 = ax.barh(y,     inv_share.values,  h, color=COLOR_EU, label="Investment share")
    b3 = ax.barh(y - h, fp_share.values,   h, color=COLOR_ROW, label="Footprint share")

    for bars, vals in [(b1, pop.values), (b2, inv_share.values), (b3, fp_share.values)]:
        for bar, v in zip(bars, vals):
            ax.text(v + 0.8, bar.get_y() + bar.get_height() / 2,
                    f"{v:.1f}%", va="center", fontsize=9, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(order)
    ax.invert_yaxis()
    ax.set_xlabel("Share of relevant total (%)")
    x_max = max(pop.max(), fp_share.max(), inv_share.max()) * 1.18
    ax.set_xlim(0, x_max)
    ax.set_title("Population weight, investment, and footprint shares by income group",
                 loc="left", fontweight="bold")
    ax.grid(axis="x", color=COLOR_GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False, ncol=1, fontsize=9)
    fig.text(0.5, -0.02,
             f"Bars cover rows with income-group classification. Unclassified rows account for "
             f"{unclassified_pop:.1f}% of population, {unclassified_inv:.1f}% of EUGG investment, "
             f"and {unclassified_fp:.1f}% of baseline footprint.",
             ha="center", va="top",
             fontsize=8, color="#555555", style="italic")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "Figure_4-01_Population_Investment_Income")
    logger.info("Wrote Figure_4-01_Population_Investment_Income (EUGG total denominator)")


# --------------------------------------------------------------------------- #
# Figure 4.6 - Income-group gradient in domestic Gini response (§4.2.3)
# --------------------------------------------------------------------------- #
def fig_4_06_incgroup_gini() -> None:
    """Share of improving countries + mean dGini by income group (Fig 4.5)."""
    df4d = pd.read_excel(EXCEL_PATH, sheet_name="13_TripleAsymm_4D")
    df4d = df4d.dropna(subset=["IncomeGroup", "Gini_Change"])

    order = ["High income", "Upper middle income",
             "Lower middle income", "Low income"]
    colors = ["#4F81BD", "#6DA4CB", "#C87A74", "#9E3E3A"]

    share_improve = []
    mean_dgini = []
    for ig in order:
        sub = df4d[df4d["IncomeGroup"] == ig]
        if len(sub) == 0:
            share_improve.append(0.0)
            mean_dgini.append(0.0)
            continue
        share_improve.append((sub["Gini_Change"] < 0).sum() / len(sub) * 100)
        mean_dgini.append(sub["Gini_Change"].mean())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.6))

    bars1 = ax1.bar(order, share_improve, color=colors, width=0.6)
    for b, v in zip(bars1, share_improve):
        ax1.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%",
                 ha="center", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Countries with domestic Gini improvement (%)")
    ax1.set_ylim(0, 100)
    ax1.set_title("(a) Share of improving countries",
                  loc="left", fontweight="bold")
    ax1.grid(axis="y", color=COLOR_GRID, linewidth=0.5)
    ax1.set_axisbelow(True)
    plt.setp(ax1.get_xticklabels(), rotation=18, ha="right")

    bar_colors = [COLOR_NEG if v < 0 else COLOR_POS for v in mean_dgini]
    bars2 = ax2.bar(order, np.array(mean_dgini) * 1e4, color=bar_colors, width=0.6)
    for b, v in zip(bars2, mean_dgini):
        off = 0.15 if v >= 0 else -0.3
        ax2.text(b.get_x() + b.get_width() / 2, v * 1e4 + off,
                 f"{v * 1e4:+.2f}", ha="center", fontsize=10, fontweight="bold")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_ylabel(r"Mean domestic $\Delta$Gini ($\times 10^{-4}$)")
    ax2.set_title("(b) Mean change in domestic Gini coefficient",
                  loc="left", fontweight="bold")
    ax2.grid(axis="y", color=COLOR_GRID, linewidth=0.5)
    ax2.set_axisbelow(True)
    plt.setp(ax2.get_xticklabels(), rotation=18, ha="right")

    fig.tight_layout()
    _save(fig, "Figure_4-06_Income_Group_Gradient")
    logger.info("Wrote Figure_4-06_Income_Group_Gradient")


# --------------------------------------------------------------------------- #
# Figure 4.7 - Regional distributional performance (§4.2.3)
# --------------------------------------------------------------------------- #
def fig_4_07_region_performance() -> None:
    """Improvement rates and mean domestic dGini by World Bank region."""
    df = pd.read_excel(EXCEL_PATH, sheet_name="2_Countries")
    df = df.dropna(subset=["Region", "Gini_Change"])
    df = df[~df["Region"].isin(["Rest of World", "Unclassified"])]

    preferred_order = [
        "South Asia",
        "Europe & Central Asia",
        "Latin America & Caribbean",
        "Middle East, North Africa, Afghanistan & Pakistan",
        "North America",
        "East Asia & Pacific",
        "Sub-Saharan Africa",
    ]
    rows = []
    for region in preferred_order:
        sub = df[df["Region"] == region]
        n = len(sub)
        if n == 0:
            continue
        improved = int((sub["Gini_Change"] < 0).sum())
        worsened = n - improved
        rows.append({
            "Region": region,
            "Short": region.replace("Middle East, North Africa, Afghanistan & Pakistan", "MENA, Afghanistan & Pakistan"),
            "N": n,
            "ImprovedPct": improved / n * 100,
            "WorsenedPct": worsened / n * 100,
            "MeanDGini": sub["Gini_Change"].mean(),
            "ImprovedN": improved,
            "WorsenedN": worsened,
        })
    reg = pd.DataFrame(rows)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.7),
                                   gridspec_kw={"width_ratios": [1.05, 1]})
    y = np.arange(len(reg))

    ax1.barh(y, reg["ImprovedPct"], color=COLOR_NEG, label="Improved")
    ax1.barh(y, reg["WorsenedPct"], left=reg["ImprovedPct"],
             color=COLOR_POS, label="Worsened or unchanged")
    for yi, row in reg.iterrows():
        if row["ImprovedPct"] >= 8:
            ax1.text(row["ImprovedPct"] / 2, yi, f"{row['ImprovedPct']:.0f}%",
                     ha="center", va="center", color="white",
                     fontsize=8.5, fontweight="bold")
        if row["WorsenedPct"] >= 8:
            ax1.text(row["ImprovedPct"] + row["WorsenedPct"] / 2, yi,
                     f"{row['WorsenedPct']:.0f}%",
                     ha="center", va="center", color="white",
                     fontsize=8.5, fontweight="bold")
    ax1.set_yticks(y)
    ax1.set_yticklabels([f"{s} (n={n})" for s, n in zip(reg["Short"], reg["N"])])
    ax1.invert_yaxis()
    ax1.set_xlim(0, 100)
    ax1.set_xlabel("Share of countries (%)")
    ax1.set_title("(a) Domestic Gini outcome by region",
                  loc="left", fontweight="bold")
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, -0.26),
               ncol=2, frameon=False, fontsize=9)
    ax1.grid(axis="x", color=COLOR_GRID, linewidth=0.5)
    ax1.set_axisbelow(True)

    vals = reg["MeanDGini"].values * 1e3
    bar_colors = [COLOR_NEG if v < 0 else COLOR_POS for v in vals]
    ax2.barh(y, vals, color=bar_colors)
    for yi, v in enumerate(vals):
        ha = "left" if v >= 0 else "right"
        dx = 0.03 if v >= 0 else -0.03
        ax2.text(v + dx, yi, f"{v:+.2f}", va="center", ha=ha,
                 fontsize=8.5, fontweight="bold")
    ax2.axvline(0, color="black", linewidth=0.8)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.invert_yaxis()
    ax2.set_xlabel(r"Mean domestic $\Delta$Gini ($\times 10^{-3}$)")
    ax2.set_title(r"(b) Mean domestic $\Delta$Gini by region",
                  loc="left", fontweight="bold")
    ax2.grid(axis="x", color=COLOR_GRID, linewidth=0.5)
    ax2.set_axisbelow(True)

    fig.tight_layout()
    _save(fig, "Figure_4-07_Regional_Performance")
    logger.info("Wrote Figure_4-07_Regional_Performance")


# --------------------------------------------------------------------------- #
# Figure 4.11 - Mean within-country Theil change by income group (§4.3.1)
# --------------------------------------------------------------------------- #
def fig_4_11_incgroup_theil_change() -> None:
    """Mean within-country Theil change by World Bank income group."""
    df = pd.read_excel(EXCEL_PATH, sheet_name="11_IncGroup_Theil")
    order = ["High income", "Upper middle income",
             "Lower middle income", "Low income"]
    df = df.set_index("IncomeGroup").loc[order].reset_index()

    vals = df["TWithin_Mean_Change"].values * 1e3
    colors = [COLOR_NEG if v < 0 else COLOR_POS for v in vals]

    fig, ax = plt.subplots(figsize=(7.8, 4.3))
    x = np.arange(len(order))
    bars = ax.bar(x, vals, color=colors, width=0.58)
    for b, v in zip(bars, vals):
        va = "bottom" if v >= 0 else "top"
        dy = 0.08 if v >= 0 else -0.08
        ax.text(b.get_x() + b.get_width() / 2, v + dy,
                f"{v:+.2f}", ha="center", va=va,
                fontsize=10, fontweight="bold")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylim(min(vals.min() * 3.0, -0.80), vals.max() * 1.25)
    ax.set_xticks(x)
    ax.set_xticklabels(order, rotation=16, ha="right")
    ax.set_ylabel(r"Mean within-country $\Delta$Theil ($\times 10^{-3}$)")
    ax.set_title("Mean within-country Theil change by income group",
                 loc="left", fontweight="bold")
    ax.grid(axis="y", color=COLOR_GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, "Figure_4-11_Amplification_Effect")
    logger.info("Wrote Figure_4-11_Amplification_Effect")


# --------------------------------------------------------------------------- #
# Figure 4.12 - Multi-dimensional Win Score distribution by income group (§4.3.3)
# --------------------------------------------------------------------------- #
def fig_4_12_winscore_by_income() -> None:
    """Stacked distribution of Win_Score (0-4) by income group (Fig 4.11)."""
    df4d = pd.read_excel(EXCEL_PATH, sheet_name="13_TripleAsymm_4D")
    df4d = df4d.dropna(subset=["IncomeGroup", "Win_Score"])

    order = ["High income", "Upper middle income",
             "Lower middle income", "Low income"]
    # colour ramp from worst (Score 0, red) to best (Score 4, green)
    score_colors = ["#9E3E3A", "#C87A74", "#BCBCBC", "#6DA4CB", "#4F81BD"]
    scores = [0, 1, 2, 3, 4]

    counts = pd.DataFrame(
        {s: [((df4d["IncomeGroup"] == ig) & (df4d["Win_Score"] == s)).sum()
             for ig in order] for s in scores},
        index=order,
    )
    pct = counts.div(counts.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    bottom = np.zeros(len(order))
    for s, c in zip(scores, score_colors):
        vals = pct[s].values
        ax.barh(order, vals, left=bottom, color=c,
                label=f"Score {s}", edgecolor="white", linewidth=0.5)
        for y_pos, (v, b_pos) in enumerate(zip(vals, bottom)):
            if v >= 6:  # suppress clutter on thin wedges
                ax.text(b_pos + v / 2, y_pos, f"{v:.0f}%",
                        ha="center", va="center", fontsize=9,
                        color="white" if c in ("#9E3E3A", "#4F81BD") else "black",
                        fontweight="bold")
        bottom += vals

    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.set_xlabel("Share of countries within income group (%)")
    ax.set_title("Distribution of multi-dimensional Win Score by income group",
                 loc="left", fontweight="bold")
    # Legend below the x-axis label; title kept short to avoid overlap.
    leg = ax.legend(loc="lower center", frameon=False, ncol=5,
                    bbox_to_anchor=(0.5, -0.34),
                    title="Win Score", title_fontsize=9.5)
    leg._legend_box.align = "center"
    ax.grid(axis="x", color=COLOR_GRID, linewidth=0.5)
    ax.set_axisbelow(True)

    # Footnote explaining the score scale (replaces the verbose legend title).
    fig.text(0.5, 0.01,
             "Score 0 = all four dimensions worsen; Score 4 = all four dimensions improve",
             ha="center", va="bottom", fontsize=8.5,
             style="italic", color="#555555")

    fig.tight_layout(rect=(0, 0.08, 1, 1))
    _save(fig, "Figure_4-12_WinScore_by_Income_Group")
    logger.info("Wrote Figure_4-12_WinScore_by_Income_Group")


# --------------------------------------------------------------------------- #
# Figure 4.9 - Country-level small-multiples grid for the 37 EUGG recipients (§4.2.3)
# --------------------------------------------------------------------------- #
def fig_4_09_recipient_grid() -> None:
    """Small-multiples grid showing dGini, dGDP, and within-country dTheil.

    All three metrics are normalised by their recipient-set maximum so
    panels share a common visual scale; bar colours encode the
    metric-specific "bad" direction (red = worsening; blue = improving).
    """
    df = pd.read_excel(EXCEL_PATH, sheet_name="13_TripleAsymm_4D")
    df = df[df["Investment_MEur"].fillna(0) > 1e-6].copy()
    df = df.dropna(subset=["Gini_Change", "Within_T_Change"])
    df = df.sort_values("Gini_Change", ascending=False).reset_index(drop=True)

    # Convert ΔGDP from MEUR to BEUR for cleaner labels
    df["GDP_Added_BEUR"] = df["GDP_Added"] / 1000.0

    n = len(df)
    ncols = 6
    nrows = (n + ncols - 1) // ncols

    g_max = max(abs(df["Gini_Change"].min()), abs(df["Gini_Change"].max()))
    gdp_max = df["GDP_Added_BEUR"].abs().max()
    theil_max = df["Within_T_Change"].abs().max()

    metric_labels = ["ΔGini", "ΔGDP\n(B€)", "ΔTheil"]
    # Sign convention for colouring: positive value in the bad direction → red
    #   ΔGini > 0 → worsening (red);    ΔGini < 0 → improving (blue)
    #   ΔGDP  > 0 → improving (blue);   ΔGDP  < 0 → worsening (red)
    #   ΔTheil > 0 -> worsening (red);   ΔTheil < 0 -> improving (blue)
    bad_dirs = [+1, -1, +1]

    income_palette = {
        "High income": "#1F497D",
        "Upper middle income": "#7DA8C4",
        "Lower middle income": "#E8A33D",
        "Low income": "#9E3E3A",
    }

    fig, axes = plt.subplots(nrows, ncols, figsize=(11.5, 1.55 * nrows + 0.6),
                             sharey=True)
    axes = np.atleast_2d(axes)

    for idx, row in df.iterrows():
        ax = axes[idx // ncols, idx % ncols]
        raw_vals = [row["Gini_Change"], row["GDP_Added_BEUR"], row["Within_T_Change"]]
        norm_vals = [
            row["Gini_Change"] / g_max if g_max else 0.0,
            row["GDP_Added_BEUR"] / gdp_max if gdp_max else 0.0,
            row["Within_T_Change"] / theil_max if theil_max else 0.0,
        ]
        colors = [
            COLOR_POS if (v * bd) > 0 else COLOR_NEG
            for v, bd in zip(raw_vals, bad_dirs)
        ]
        x_pos = np.arange(len(metric_labels))
        bars = ax.bar(x_pos, norm_vals, color=colors, width=0.62,
                      edgecolor="white", linewidth=0.5)
        # Annotate each bar with its raw absolute value
        raw_label_fmts = [
            f"{row['Gini_Change'] * 1e3:+.2f}",       # Gini ×10⁻³
            f"{row['GDP_Added_BEUR']:+.1f}",          # GDP in BEUR
            f"{row['Within_T_Change'] * 1e3:+.1f}",   # Theil ×10⁻³
        ]
        for bar, lbl, nv in zip(bars, raw_label_fmts, norm_vals):
            offset = 0.08 if nv >= 0 else -0.08
            va = "bottom" if nv >= 0 else "top"
            ax.text(bar.get_x() + bar.get_width() / 2,
                    nv + offset, lbl, ha="center", va=va,
                    fontsize=6.4, color="#333333")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_ylim(-1.35, 1.35)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(metric_labels, fontsize=7.2)
        ax.tick_params(axis="x", pad=1)
        ax.tick_params(axis="y", labelsize=7.2)
        ax.set_yticks([-1, 0, 1])
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.grid(axis="y", color=COLOR_GRID, linewidth=0.4)
        ax.set_axisbelow(True)

        # Country title with income-group colour band
        country = str(row["Country"])
        ig = row.get("IncomeGroup")
        ig_color = income_palette.get(ig, "#666666") if isinstance(ig, str) else "#666666"
        ax.set_title(country[:18], fontsize=8.5, fontweight="bold",
                     color=ig_color, pad=2)

    # Hide unused axes
    for k in range(n, nrows * ncols):
        axes[k // ncols, k % ncols].axis("off")

    # Legend for income-group colour coding
    handles = [plt.Line2D([0], [0], marker="s", linestyle="",
                          markerfacecolor=c, markeredgecolor=c, markersize=8,
                          label=lbl) for lbl, c in income_palette.items()]
    handles.append(plt.Line2D([0], [0], marker="s", linestyle="",
                              markerfacecolor=COLOR_POS, markeredgecolor=COLOR_POS,
                              markersize=8, label="Worsening direction"))
    handles.append(plt.Line2D([0], [0], marker="s", linestyle="",
                              markerfacecolor=COLOR_NEG, markeredgecolor=COLOR_NEG,
                              markersize=8, label="Improving direction"))
    fig.legend(handles=handles, loc="lower center", ncol=3,
               frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, -0.01))

    fig.suptitle(
        "Country-level outcomes for the 37 EUGG recipients\n"
        "Delta Gini (x10^-3), Delta GDP (B€), Delta within-country Theil (x10^-3); "
        "bars normalised to the recipient-set maximum, sorted by ΔGini",
        fontsize=9.5, y=0.997,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    _save(fig, "Figure_4-09_Recipient_Country_Grid")
    logger.info("Wrote Figure_4-09_Recipient_Country_Grid")


# --------------------------------------------------------------------------- #
# Figure 4.13 - Investment size versus within-country Theil change (§4.3.3)
# --------------------------------------------------------------------------- #
def fig_4_13_investment_vs_theil() -> None:
    """Investment received versus within-country Theil change for recipients."""
    df = pd.read_excel(EXCEL_PATH, sheet_name="13_TripleAsymm_4D")
    df = df[df["Investment_MEur"].fillna(0) > 1e-6].copy()
    df = df.dropna(subset=["Within_T_Change"])
    df["IncomeGroup"] = df["IncomeGroup"].fillna("Regional aggregate")

    income_palette = {
        "High income": "#1F497D",
        "Upper middle income": "#5B8F63",
        "Lower middle income": "#E8782E",
        "Low income": "#C0504D",
        "Regional aggregate": "#777777",
    }
    order = ["High income", "Upper middle income",
             "Lower middle income", "Low income", "Regional aggregate"]

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for label in order:
        sub = df[df["IncomeGroup"] == label]
        if sub.empty:
            continue
        ax.scatter(sub["Investment_MEur"], sub["Within_T_Change"],
                   color=income_palette[label], alpha=0.78, s=48,
                   label=label, edgecolors="white", linewidths=0.5,
                   zorder=3)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.65)
    ax.set_xscale("log")
    ax.set_xlabel("Investment received (M EUR, log scale)")
    ax.set_ylabel(r"Change in within-country Theil T ($\Delta T_c$)")
    ax.set_title("Investment size versus within-country Theil change",
                 loc="left", fontweight="bold")
    ax.legend(title="Income group", loc="upper right", frameon=True)

    n_imp = int((df["Within_T_Change"] < 0).sum())
    n_wor = int((df["Within_T_Change"] > 0).sum())
    ax.text(0.96, 0.06,
            f"Recipients: {len(df)}\nTheil improved: {n_imp} | worsened: {n_wor}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.35", fc="white",
                      ec="#333333", alpha=0.9))
    ax.grid(True, which="major", color=COLOR_GRID, linewidth=0.5)
    ax.set_axisbelow(True)

    fig.tight_layout()
    _save(fig, "Figure_4-13_Investment_vs_Inequality")
    logger.info("Wrote Figure_4-13_Investment_vs_Inequality")


# --------------------------------------------------------------------------- #
def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("fontTools").setLevel(logging.WARNING)
    fig_4_01_pop_invest_income()
    fig_4_02_carbon_output_asymmetry()
    fig_4_06_incgroup_gini()
    fig_4_07_region_performance()
    fig_4_08_recipients_vs_nonrec()
    fig_4_09_recipient_grid()
    fig_4_10_baseline_pyramid()
    fig_4_11_incgroup_theil_change()
    fig_4_12_winscore_by_income()
    fig_4_13_investment_vs_theil()


if __name__ == "__main__":
    main()
