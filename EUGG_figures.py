"""
EUGG_figures.py  |  Local figure generation
=========================================================================
Workflow:  EUGG_model.m  ->  EUGG_analysis.m  ->  THIS SCRIPT

Input:  results/Data/EUGG_Results.xlsx  (sheets 1-17)
Output: results/Figures/  (PNG @ 300 DPI + PDF)

Dependencies (required):
    pip install numpy pandas matplotlib openpyxl

Dependencies (optional):
    pip install geopandas   -- for Fig 03 choropleth (falls back to bar chart)
    pip install scipy       -- for OLS p-values in scatter plots

Figures (15):
    01  Lorenz curves                      -- global carbon inequality overview
    02  Simpson's Paradox histogram         -- country dGini distribution
    03  World choropleth                    -- spatial pattern of dGini
    04  Theil T decomposition              -- between/within country split
    05  Baseline amplification             -- pre-existing inequality -> larger change
    06  GDP multiplier & carbon intensity  -- structural asymmetry by income group
    07  Income group x Theil               -- decomposition by development level
    08  Regional x Theil                   -- geographic decomposition
    09  Investment vs domestic inequality   -- EUGG dosage-response
    10  Between-country ranking            -- top/bottom drivers of international gap
    11  EU27 spillover                     -- supply-chain spillover + EU domestic Gini impact
    12  Scenario heatmap (dGini + CO2)     -- mitigation scenario overview
    13  CO2 vs dGini trade-off scatter     -- emission-inequality frontier
    14  Theil decomposition across scen.   -- between/within by scenario
    15  Country-level dGini distribution   -- distribution shift
=========================================================================
"""

import os
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.lines import Line2D

warnings.filterwarnings("ignore", category=UserWarning)

# Optional imports
try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

try:
    from scipy import stats as sp_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# =========================================================================
# CONFIG
# =========================================================================
ROOT_DIR  = Path(__file__).resolve().parent
DATA_DIR  = ROOT_DIR / "results" / "Data"
FIG_DIR   = ROOT_DIR / "results" / "Figures"
XLSX_PATH = DATA_DIR / "EUGG_Results.xlsx"
DPI       = 300

FIG_DIR.mkdir(parents=True, exist_ok=True)

# Typography
FONT = "Arial"
matplotlib.rcParams.update({
    "font.family":       FONT,
    "font.size":         10,
    "axes.titlesize":    11,
    "axes.labelsize":    10,
    "xtick.labelsize":   9,
    "ytick.labelsize":   9,
    "legend.fontsize":   8,
    "figure.dpi":        150,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.25,
    "grid.linewidth":    0.5,
    "lines.linewidth":   1.8,
})

# =========================================================================
# COLOUR PALETTE
# =========================================================================
C_HIC   = "#1565C0"
C_UMIC  = "#2E7D32"
C_LMIC  = "#E65100"
C_LIC   = "#B71C1C"
C_UNC   = "#757575"

INC_COLORS = {
    "High income":           C_HIC,
    "Upper middle income":   C_UMIC,
    "Lower middle income":   C_LMIC,
    "Low income":            C_LIC,
}
INC_ORDER = ["High income", "Upper middle income", "Lower middle income", "Low income"]
INC_SHORT = ["High", "Upper mid", "Lower mid", "Low"]

REG_COLORS = {
    "East Asia & Pacific":        "#1565C0",
    "Europe & Central Asia":      "#6A1B9A",
    "Latin America & Caribbean":  "#00838F",
    "Middle East & North Africa": "#F57F17",
    "Middle East, North Africa, Afghanistan & Pakistan": "#F57F17",
    "North America":              "#37474F",
    "South Asia":                 "#558B2F",
    "Sub-Saharan Africa":         "#BF360C",
    "Rest of World":              "#78909C",
}

C_BETWEEN = "#C62828"
C_WITHIN  = "#1565C0"
C_TOTAL   = "#424242"
C_BASE    = "#546E7A"
C_FINAL   = "#FF6F00"
C_IMPROVE = "#2E8B57"
C_WORSEN  = "#D2691E"
C_EU      = "#1F77B4"
C_RECIP   = "#FF7F0E"

# V5 scenario colours
C_SCENARIO = {
    'Baseline':     '#4C72B0',
    'ServiceMax':   '#DD8452',
    'EnergyMax':    '#C44E52',
    'AFOLUMax':     '#55A868',
    'TransportMax': '#8172B3',
}
TECH_LABELS = {'T0': 'No transfer', 'T25': 'EU P25', 'T10': 'EU P10'}
SCENARIO_ORDER = ['Baseline', 'ServiceMax', 'EnergyMax', 'AFOLUMax', 'TransportMax']
TECH_ORDER = ['T0', 'T25', 'T10']

GLORIA_SECTORS = {
    "AFOLU":        list(range(1, 24)),
    "Energy":       list(range(35, 43)),
    "Transport":    list(range(82, 86)),
    "Heavy Mfg":    list(range(43, 71)),
    "Construction": [71],
    "Services":     list(range(86, 121)),
    "Other":        list(range(24, 35)) + list(range(72, 82)),
}


# =========================================================================
# HELPERS
# =========================================================================
def save_fig(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(FIG_DIR / f"{name}.{ext}",
                    dpi=DPI, bbox_inches="tight", facecolor="white")
    print(f"  -> {name}.png/pdf")
    plt.close(fig)


def classify_inc(ig_str):
    s = str(ig_str).lower().strip()
    if "high" in s and "upper" not in s:
        return "High income"
    elif "upper" in s:
        return "Upper middle income"
    elif "lower" in s:
        return "Lower middle income"
    elif "low" in s:
        return "Low income"
    return "Unclassified"


def inc_color(label):
    return INC_COLORS.get(label, C_UNC)


def reg_color(label):
    return REG_COLORS.get(label, "#78909C")


def ols_line(x, y):
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return None
    if HAS_SCIPY:
        slope, intercept, r, p, se = sp_stats.linregress(x, y)
    else:
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs
        r = np.corrcoef(x, y)[0, 1]
        p = np.nan
    x_range = np.linspace(x.min(), x.max(), 80)
    y_hat = slope * x_range + intercept
    return {"slope": slope, "intercept": intercept, "r": r, "p": p,
            "x": x_range, "y": y_hat, "n": len(x), "x_raw": x, "y_raw": y}


# =========================================================================
# DATA LOADING
# =========================================================================
def load_all():
    print("Loading data ...")
    xl = pd.ExcelFile(XLSX_PATH)
    sheets = xl.sheet_names
    print(f"  Sheets: {sheets}")

    d = {}
    d["T1"]  = pd.read_excel(XLSX_PATH, sheet_name="1_Global")
    d["T2"]  = pd.read_excel(XLSX_PATH, sheet_name="2_Countries")
    d["T4"]  = pd.read_excel(XLSX_PATH, sheet_name="4_TripleAsymmetry")
    d["T5"]  = pd.read_excel(XLSX_PATH, sheet_name="5_EU27_Spillover")
    d["T6"]  = pd.read_excel(XLSX_PATH, sheet_name="6_EU_Backflow_Sector")
    d["T7"]  = pd.read_excel(XLSX_PATH, sheet_name="7_Sensitivity")
    d["T8"]  = pd.read_excel(XLSX_PATH, sheet_name="8_Theil_Global")
    d["T9"]  = pd.read_excel(XLSX_PATH, sheet_name="9_Theil_Countries")

    # Analysis sheets (from EUGG_analysis.m)
    for sname in ["10b_Between_Ranked", "11_IncGroup_Theil", "12_Region_Theil",
                   "13_TripleAsymm_4D", "14_Lorenz"]:
        key = "T" + sname.split("_")[0]
        if sname in sheets:
            d[key] = pd.read_excel(XLSX_PATH, sheet_name=sname)
        else:
            print(f"  WARNING: sheet {sname} not found")
            d[key] = None

    # V5 scenario sheets
    for sname in ["15_Scenario_Summary", "16_Country_Gini_Scenarios", "17_Country_CO2_Scenarios"]:
        key = "T" + sname.split("_")[0]
        if sname in sheets:
            d[key] = pd.read_excel(XLSX_PATH, sheet_name=sname)
        else:
            print(f"  WARNING: sheet {sname} not found")
            d[key] = None

    # Classify income groups consistently
    d["T2"]["inc_class"] = d["T2"]["IncomeGroup"].apply(classify_inc)
    d["T9"]["inc_class"] = d["T9"]["IncomeGroup"].apply(classify_inc)

    # EU27 ISO3 list
    eu27 = {"AUT","BEL","BGR","HRV","CYP","CZE","DNK","EST","FIN","FRA","DEU",
            "GRC","HUN","IRL","ITA","LVA","LTU","LUX","MLT","NLD","POL","PRT",
            "ROU","SVK","SVN","ESP","SWE"}
    d["T2"]["is_eu"] = d["T2"]["ISO3"].isin(eu27)
    d["T2"]["is_recipient"] = (d["T2"]["Investment_MEur"] > 100) & (~d["T2"]["is_eu"])
    d["eu27"] = eu27

    # Theil scalars
    def theil_val(metric):
        row = d["T8"][d["T8"]["Metric"] == metric]
        if row.empty:
            return (0, 0, 0)
        return row["Baseline"].values[0], row["PostInvestment"].values[0], row["Change"].values[0]
    d["theil"] = {
        "total":   theil_val("Theil_T_Total"),
        "between": theil_val("Theil_T_Between"),
        "within":  theil_val("Theil_T_Within"),
        "b_share": theil_val("Between_Share_Pct"),
        "w_share": theil_val("Within_Share_Pct"),
    }

    # Global scalars
    d["gini_base"]  = d["T1"]["Gini_Base"].values[0]
    d["gini_final"] = d["T1"]["Gini_Final"].values[0]
    d["gini_change"]= d["T1"]["Gini_Change"].values[0]

    print(f"  Loaded: {len(d['T2'])} countries, Gini={d['gini_base']:.5f}->{d['gini_final']:.5f}")
    return d


# =========================================================================
# FIGURES 01-11: Baseline analysis (from V4)
# =========================================================================

def fig01_lorenz(d):
    print("[Fig 01] Lorenz curves ...")
    T14 = d.get("T14")
    if T14 is None or T14.empty:
        print("  SKIP -- sheet 14_Lorenz not found")
        return

    Lx, Lb, Lf = T14["Pop_Share"].values, T14["Lorenz_Base"].values, T14["Lorenz_Final"].values
    gb, gf = d["gini_base"], d["gini_final"]

    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([0, 1], [0, 1], "--", color="#AAAAAA", lw=0.8, zorder=1)
    ax.fill_between(Lx, Lb, Lf, alpha=0.20, color=C_FINAL, zorder=2)
    ax.plot(Lx, Lb, color=C_BASE,  lw=2.0, label=f"Baseline (Gini = {gb:.5f})", zorder=3)
    ax.plot(Lx, Lf, color=C_FINAL, lw=2.0, label=f"Post-investment (Gini = {gf:.5f})", zorder=3)

    ax.set_xlabel("Cumulative population share")
    ax.set_ylabel("Cumulative carbon footprint share")
    ax.set_title("Global Carbon Footprint Inequality -- Lorenz Curves")
    ax.legend(loc="upper left", frameon=True, framealpha=0.9)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal")

    ax.text(0.52, 0.70, f"dGini = {gf - gb:+.5f}",
            fontsize=10, fontweight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.9))

    axins = ax.inset_axes([0.52, 0.05, 0.45, 0.35])
    mask = Lx >= 0.85
    axins.plot([0.85, 1], [0.85, 1], "--", color="#AAAAAA", lw=0.6)
    axins.plot(Lx[mask], Lb[mask], color=C_BASE,  lw=1.5)
    axins.plot(Lx[mask], Lf[mask], color=C_FINAL, lw=1.5)
    axins.fill_between(Lx[mask], Lb[mask], Lf[mask], alpha=0.25, color=C_FINAL)
    axins.set_xlim(0.85, 1.0); axins.set_ylim(0.70, 1.0)
    axins.set_title("High-income tail (zoom)", fontsize=7, pad=2)
    axins.tick_params(labelsize=7)
    ax.indicate_inset_zoom(axins, edgecolor="#555555", linewidth=0.8)

    fig.tight_layout()
    save_fig(fig, "fig01_lorenz")


def fig02_simpsons_paradox(d):
    print("[Fig 02] Simpson's Paradox histogram ...")
    gc = d["T2"]["Gini_Change"].values
    gc_global = d["gini_change"]
    nC = len(gc)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    clip_lo, clip_hi = -0.003, 0.004
    gc_disp = np.clip(gc, clip_lo + 1e-8, clip_hi - 1e-8)
    bin_w = 0.0003
    bins = np.arange(clip_lo, clip_hi + bin_w, bin_w)

    n_imp = np.sum(gc < -1e-10)
    n_wor = nC - n_imp

    for i in range(len(bins) - 1):
        mask = (gc_disp >= bins[i]) & (gc_disp < bins[i + 1])
        if mask.sum() == 0:
            continue
        color = C_IMPROVE if bins[i] + bin_w / 2 < 0 else C_WORSEN
        ax.bar(bins[i] + bin_w / 2, mask.sum(), width=bin_w * 0.92,
               color=color, alpha=0.75, edgecolor="white", linewidth=0.5)

    ax.axvline(0, color="black", lw=1.5, zorder=5)
    ax.axvline(gc_global, color="#CC1111", lw=1.5, ls="--", zorder=5)

    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, ymax * 1.55)
    ymax2 = ax.get_ylim()[1]

    ax.text(-0.0016, ymax2 * 0.92,
            f"{n_imp} countries\nimproved ({n_imp / nC * 100:.1f}%)",
            fontsize=10, fontweight="bold", color=C_IMPROVE, ha="center")
    ax.text(0.0028, ymax2 * 0.65,
            f"{n_wor} countries\nworsened ({n_wor / nC * 100:.1f}%)",
            fontsize=10, fontweight="bold", color=C_WORSEN, ha="center")

    ax.text(gc_global + 0.00005, ymax * 0.45, "Global Gini up",
            fontsize=8, color="#CC1111", ha="left")

    ax.text(0.97, 0.97,
            "Simpson's Paradox:\nGlobal Gini increases despite\nmajority of countries improving",
            transform=ax.transAxes, fontsize=8, va="top", ha="right",
            bbox=dict(boxstyle="round,pad=0.4", fc="#F5F5F5", ec="#999999", alpha=0.95))

    ax.set_xlabel("Change in domestic Gini coefficient (dGini)")
    ax.set_ylabel("Number of countries")
    ax.set_title(f"Country-Level dGini Distribution (n = {nC})")
    fig.tight_layout()
    save_fig(fig, "fig02_simpsons_paradox")


def fig03_choropleth(d):
    print("[Fig 03] World choropleth ...")
    T2 = d["T2"]

    if not HAS_GEOPANDAS:
        print("  geopandas not installed -> falling back to regional bar chart")
        _fig03_fallback(d)
        return

    # geopandas >= 1.0 removed built-in datasets; use naturalearth online
    world = None
    ne_url = ("https://naciscdn.org/naturalearth/110m/cultural/"
              "ne_110m_admin_0_countries.zip")
    # Try local cache first, then online
    cache_dir = DATA_DIR / ".ne_cache"
    cache_path = os.path.join(cache_dir, "ne_110m_admin_0_countries.shp")
    for src in [
        cache_path,
        ne_url,
        # legacy geopandas < 1.0 built-in
        lambda: gpd.datasets.get_path("naturalearth_lowres") if hasattr(gpd, "datasets") and hasattr(gpd.datasets, "get_path") else None,
    ]:
        if world is not None:
            break
        try:
            if callable(src):
                p = src()
                if p is None:
                    continue
                world = gpd.read_file(p)
            else:
                world = gpd.read_file(src)
                # Cache downloaded data locally
                if src == ne_url:
                    os.makedirs(cache_dir, exist_ok=True)
                    world.to_file(cache_path)
        except Exception:
            continue
    if world is None:
        print("  Cannot load world shapefile -> falling back")
        _fig03_fallback(d)
        return

    iso_col = "iso_a3" if "iso_a3" in world.columns else "ISO_A3"
    world = world.rename(columns={iso_col: "ISO3"})
    merged = world.merge(T2[["ISO3", "Gini_Change", "Investment_MEur"]],
                         on="ISO3", how="left")
    merged["is_rec"] = merged["Investment_MEur"].fillna(0) > 100

    vals = merged["Gini_Change"].dropna()
    if vals.empty:
        _fig03_fallback(d)
        return
    vmax = max(abs(float(vals.quantile(0.01))), abs(float(vals.quantile(0.99)))) * 1.15

    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("dGini", [
        (0.00, "#BF4000"), (0.35, "#F5C6A0"), (0.50, "#FFFFFF"),
        (0.65, "#A8D5B5"), (1.00, "#1E6B3C")], N=512)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_facecolor("#CDDFF0")

    merged[merged["Gini_Change"].isna()].plot(ax=ax, color="#CCCCCC", linewidth=0.2, edgecolor="white")
    non_rec = merged[merged["Gini_Change"].notna() & ~merged["is_rec"]]
    non_rec.plot(ax=ax, column="Gini_Change", cmap=cmap, norm=norm, linewidth=0.2, edgecolor="white")
    rec = merged[merged["Gini_Change"].notna() & merged["is_rec"]]
    rec.plot(ax=ax, column="Gini_Change", cmap=cmap, norm=norm, linewidth=0.8, edgecolor="#111111")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal",
                        fraction=0.025, pad=0.02, aspect=50, shrink=0.55)
    cbar.set_label("dGini  |  Bold border = EUGG recipient", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    n_imp = int((T2["Gini_Change"] < -1e-10).sum())
    n_wor = int((T2["Gini_Change"] > 1e-10).sum())
    ax.text(0.012, 0.30,
            f"n = {len(T2)} countries\nImprove: {n_imp} ({n_imp/len(T2)*100:.1f}%)\nWorsen:  {n_wor} ({n_wor/len(T2)*100:.1f}%)",
            transform=ax.transAxes, fontsize=8, va="top",
            bbox=dict(boxstyle="round", fc="white", alpha=0.88, ec="#999999"))

    ax.set_xlim(-180, 180); ax.set_ylim(-58, 85)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Country-Level dGini: Distributional Impact of EU Global Gateway", fontweight="bold")
    fig.tight_layout()
    save_fig(fig, "fig03_choropleth")


def _fig03_fallback(d):
    T2 = d["T2"]
    regions = T2.groupby("Region").agg(
        mean_dg=("Gini_Change", "mean"), n=("Gini_Change", "size")).reset_index()
    regions = regions[regions["Region"].str.strip() != ""].sort_values("mean_dg")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = [C_IMPROVE if v < 0 else C_WORSEN for v in regions["mean_dg"]]
    bars = ax.barh(regions["Region"], regions["mean_dg"] * 1e3, color=colors, alpha=0.8, edgecolor="white")
    ax.axvline(0, color="black", lw=0.8)
    for bar, n in zip(bars, regions["n"]):
        ax.text(bar.get_width() + np.sign(bar.get_width()) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"n={int(n)}", va="center", fontsize=8)
    ax.set_xlabel("Mean dGini (x10^-3)")
    ax.set_title("Regional Mean dGini (choropleth requires geopandas)", fontweight="bold")
    fig.tight_layout()
    save_fig(fig, "fig03_choropleth")


def fig04_theil_decomp(d):
    print("[Fig 04] Theil T decomposition ...")
    th = d["theil"]
    T_b, T_f, dT = th["total"]
    B_b, B_f, dB = th["between"]
    W_b, W_f, dW = th["within"]
    Bs_b = th["b_share"][0]
    Ws_b = th["w_share"][0]
    Bs_f = th["b_share"][1]
    Ws_f = th["w_share"][1]

    fig = plt.figure(figsize=(11, 4.5))
    gs = GridSpec(1, 2, figure=fig, wspace=0.38)
    ax1, ax2 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    x = np.array([0, 1])
    w = 0.4
    ax1.bar(x, [B_b, B_f], w, label="Between-country", color=C_BETWEEN, alpha=0.85)
    ax1.bar(x, [W_b, W_f], w, bottom=[B_b, B_f],
            label="Within-country", color=C_WITHIN, alpha=0.85)

    for i, (bv, wv) in enumerate(zip([B_b, B_f], [W_b, W_f])):
        total = bv + wv
        bs = [Bs_b, Bs_f][i]; ws = [Ws_b, Ws_f][i]
        ax1.text(x[i], bv / 2, f"{bs:.1f}%", ha="center", va="center",
                 fontsize=9, color="white", fontweight="bold")
        ax1.text(x[i], bv + wv / 2, f"{ws:.1f}%", ha="center", va="center",
                 fontsize=9, color="white", fontweight="bold")
        ax1.text(x[i], total + 0.005, f"T = {total:.4f}",
                 ha="center", va="bottom", fontsize=8, color=C_TOTAL)

    ax1.set_xticks(x); ax1.set_xticklabels(["Baseline", "Post-investment"])
    ax1.set_ylabel("Theil T index")
    ax1.set_title("(a) Composition of carbon inequality")
    ax1.legend(loc="upper right", frameon=True)
    ax1.set_ylim(0, max(B_b + W_b, B_f + W_f) * 1.08)

    labels = ["dT total", "dT between\n(international)", "dT within\n(domestic)"]
    vals = [dT, dB, dW]
    cols = [C_TOTAL, C_BETWEEN, C_WITHIN]
    bars = ax2.bar(np.arange(3), vals, 0.50, color=cols, alpha=0.85, edgecolor="white")
    ax2.axhline(0, color="black", lw=0.8)

    for bar, v in zip(bars, vals):
        offset = max(abs(v) * 0.15, 5e-6)
        if v >= 0:
            y = v + offset
            va = "bottom"
            color = "black"
        else:
            y = v + offset
            va = "bottom"
            color = "white"
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 y, f"{v:+.2e}", ha="center", va=va,
                 fontsize=8.5, fontweight="bold", color=color)

    pad = max(max(abs(v) for v in vals) * 0.18, 2e-5)
    ax2.set_ylim(min(vals + [0]) - pad, max(vals + [0]) + pad)

    ax2.set_xticks(np.arange(3)); ax2.set_xticklabels(labels, fontsize=8.5)
    ax2.set_ylabel("Change in Theil T (dT)")
    ax2.set_title("(b) EUGG-induced inequality change")

    fig.suptitle("Theil T Index -- Between vs Within Country Decomposition",
                 fontsize=12, fontweight="bold", y=1.01)
    fig.tight_layout()
    save_fig(fig, "fig04_theil_decomp")


def fig05_amplification(d):
    print("[Fig 05] Baseline amplification ...")
    T2 = d["T2"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    ax1, ax2 = axes

    for label in INC_ORDER:
        sub = T2[T2["inc_class"] == label]
        ax1.scatter(sub["Gini_Base"], sub["Gini_Change"],
                    c=inc_color(label), s=30, alpha=0.7, label=label, zorder=3)
    ax1.axhline(0, color="black", lw=0.8, ls="--", zorder=2)

    res = ols_line(T2["Gini_Base"].values, T2["Gini_Change"].values)
    if res:
        ax1.plot(res["x"], res["y"], "--", color="#444444", lw=1.5, zorder=4)
        p_str = f"p = {res['p']:.3f}" if not np.isnan(res["p"]) else ""
        ax1.text(0.04, 0.04, f"r = {res['r']:.3f}, {p_str}, n = {res['n']}",
                 transform=ax1.transAxes, fontsize=8, color="#444444")

    ax1.legend(loc="upper left", frameon=True, fontsize=7)
    ax1.set_xlabel("Baseline Gini coefficient")
    ax1.set_ylabel("dGini")
    ax1.set_title("(a) All countries (n = 164)")

    rec = T2[T2["is_recipient"]].copy()
    for label in INC_ORDER:
        sub = rec[rec["inc_class"] == label]
        if sub.empty:
            continue
        ax2.scatter(sub["Gini_Base"], sub["Gini_Change"],
                    c=inc_color(label), s=45, alpha=0.8, label=label,
                    edgecolors="black", linewidths=0.5, zorder=3)

    ax2.axhline(0, color="black", lw=0.8, ls="--", zorder=2)

    res2 = ols_line(rec["Gini_Base"].values, rec["Gini_Change"].values)
    if res2:
        ax2.plot(res2["x"], res2["y"], "--", color="#444444", lw=1.5, zorder=4)
        n_ols = res2["n"]
        y_hat_raw = res2["slope"] * res2["x_raw"] + res2["intercept"]
        residuals = res2["y_raw"] - y_hat_raw
        se = np.std(residuals) * np.sqrt(
            1 / n_ols + (res2["x"] - res2["x_raw"].mean()) ** 2 /
            np.sum((res2["x_raw"] - res2["x_raw"].mean()) ** 2))
        ax2.fill_between(res2["x"], res2["y"] - 1.96 * se, res2["y"] + 1.96 * se,
                         alpha=0.15, color="#777777", zorder=2)
        p_str = f"p = {res2['p']:.3f}" if not np.isnan(res2["p"]) else ""
        sig = "**" if res2["p"] < 0.01 else ("*" if res2["p"] < 0.05 else "")
        ax2.text(0.04, 0.04, f"r = {res2['r']:.3f}, {p_str} {sig}, n = {res2['n']}",
                 transform=ax2.transAxes, fontsize=8, color="#444444")

    ax2.legend(loc="upper left", frameon=True, fontsize=7)
    ax2.set_xlabel("Baseline Gini coefficient")
    ax2.set_ylabel("dGini")
    ax2.set_title(f"(b) EUGG recipients only (n = {len(rec)})")

    fig.suptitle("Baseline Inequality Amplification -- Pre-Existing Inequality Predicts Change",
                 fontsize=12, fontweight="bold", y=1.01)
    fig.tight_layout()
    save_fig(fig, "fig05_amplification")


def fig06_gdp_carbon(d):
    print("[Fig 06] Investment share & carbon intensity ...")
    T4 = d["T4"]
    T4["inc_class"] = T4["IncomeGroup"].apply(classify_inc)
    rec = T4[T4["Investment_MEur"] > 100].copy()
    total_inv = rec["Investment_MEur"].sum()

    # Include aggregate regions as a separate category
    groups = INC_ORDER + ["Aggregate regions"]
    short_labels = INC_SHORT + ["Aggregate\nregions"]
    group_colors = [inc_color(l) for l in INC_ORDER] + [C_UNC]

    inv_shares, cis, ns = [], [], []
    for label in groups:
        if label == "Aggregate regions":
            sub = rec[rec["inc_class"] == "Unclassified"]
        else:
            sub = rec[rec["inc_class"] == label]
        n = len(sub)
        ns.append(n)
        inv_sum = sub["Investment_MEur"].sum()
        inv_shares.append(inv_sum / total_inv * 100)
        if n > 0 and inv_sum > 100:
            co2_sum = sub["CO2_Added"].sum()
            cis.append(abs(co2_sum / inv_sum) if inv_sum > 0.01 else 0)
        else:
            cis.append(0)

    fig, ax1 = plt.subplots(figsize=(8, 5))
    x = np.arange(len(groups))

    bars = ax1.bar(x, inv_shares, 0.55, color=group_colors, alpha=0.85, edgecolor="white")

    for i, (sh, n) in enumerate(zip(inv_shares, ns)):
        if n > 0:
            ax1.text(i, sh + 0.8, f"{sh:.1f}%\n(n={n})", ha="center", fontsize=8, fontweight="bold")

    ax1.set_ylabel("Share of total EUGG investment (%)")
    ax1.set_ylim(0, max(inv_shares) * 1.25 if max(inv_shares) > 0 else 100)

    ax2 = ax1.twinx()
    ci_scaled = [c * 1e4 for c in cis]
    ax2.plot(x, ci_scaled, "o-", color="#7B1FA2", lw=2.0, markersize=8,
             markerfacecolor="#7B1FA2", zorder=5)
    for i, ci_val in enumerate(ci_scaled):
        va_pos = "bottom" if i < len(ci_scaled) - 1 else "top"
        y_off = 0.02 if va_pos == "bottom" else -0.02
        ax2.text(i + 0.12, ci_val + y_off, f"{ci_val:.2f}", fontsize=7.5,
                 color="#7B1FA2", ha="left", va=va_pos)
    ax2.set_ylabel("Embedded carbon intensity (Mt CO2 / M EUR, ×10⁻⁴)", color="#7B1FA2")
    ax2.tick_params(axis="y", labelcolor="#7B1FA2")
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color("#7B1FA2")

    ax1.set_xticks(x); ax1.set_xticklabels(short_labels, fontsize=9)
    ax1.set_xlabel("Recipient country income group")
    ax1.set_title("Investment Allocation & Carbon Intensity by Income Group (Recipients)",
                  fontweight="bold")
    fig.tight_layout()
    save_fig(fig, "fig06_gdp_carbon")


def fig07_incgroup_theil(d):
    print("[Fig 07] Income group x Theil ...")
    T11 = d.get("T11")
    if T11 is None:
        print("  SKIP -- sheet 11_IncGroup_Theil not found")
        return

    df = T11.copy()
    order_map = {l: i for i, l in enumerate(INC_ORDER)}
    df["_sort"] = df["IncomeGroup"].apply(lambda x: order_map.get(x, 99))
    df = df.sort_values("_sort").reset_index(drop=True)

    fig = plt.figure(figsize=(11, 4.5))
    gs = GridSpec(1, 2, figure=fig, wspace=0.4)
    ax1, ax2 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    colors = [inc_color(ig) for ig in df["IncomeGroup"]]
    x = np.arange(len(df))
    w = 0.32

    ax1.bar(x - w / 2, df["TWithin_Contrib_Base"], w,
            color=colors, alpha=0.50, edgecolor="white", label="Baseline")
    ax1.bar(x + w / 2, df["TWithin_Contrib_Final"], w,
            color=colors, alpha=0.90, edgecolor="white", label="Post-investment")
    ax1.set_xticks(x); ax1.set_xticklabels(INC_SHORT, fontsize=8.5)
    ax1.set_ylabel("Sum s_k * T_k (within-T contribution)")
    ax1.set_title("(a) Within-country Theil T\nby income group")
    ax1.legend(frameon=True)

    ax2.bar(x - w / 2, df["TBetween_Contrib_Change"], w,
            color=colors, alpha=0.85, edgecolor="white", hatch="//", label="dT_between")
    ax2.bar(x + w / 2, df["TWithin_Contrib_Change"], w,
            color=colors, alpha=0.85, edgecolor="white", label="dT_within")
    ax2.axhline(0, color="black", lw=0.8, ls="--")
    ax2.set_xticks(x); ax2.set_xticklabels(INC_SHORT, fontsize=8.5)
    ax2.set_ylabel("Change in Theil T contribution")
    ax2.set_title("(b) EUGG-induced change\nby income group")
    ax2.legend(frameon=True)

    fig.suptitle("Theil T Decomposition by Income Group", fontsize=12, fontweight="bold", y=1.01)
    fig.tight_layout()
    save_fig(fig, "fig07_incgroup_theil")


def fig08_region_theil(d):
    print("[Fig 08] Regional x Theil ...")
    T12 = d.get("T12")
    if T12 is None:
        print("  SKIP -- sheet 12_Region_Theil not found")
        return

    df = T12.copy()
    df = df[df["Region"].astype(str).str.strip() != ""].copy()
    df = df.sort_values("TBetween_Contrib_Change", ascending=True).reset_index(drop=True)

    fig = plt.figure(figsize=(14, 6))
    gs = GridSpec(1, 2, figure=fig, wspace=0.55)
    ax1, ax2 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    colors = [reg_color(r) for r in df["Region"]]
    y = np.arange(len(df))

    ax1.barh(y, df["TBetween_Contrib_Change"], color=colors, alpha=0.85,
             edgecolor="white", height=0.55)
    ax1.axvline(0, color="black", lw=0.8)
    ax1.set_yticks(y); ax1.set_yticklabels(df["Region"], fontsize=9)
    ax1.set_xlabel("dT_between contribution")
    ax1.set_title("(a) Between-country\ninequality change")

    ax2.barh(y, df["TWithin_Contrib_Change"], color=colors, alpha=0.85,
             edgecolor="white", height=0.55)
    ax2.axvline(0, color="black", lw=0.8)
    ax2.set_yticks(y); ax2.set_yticklabels(df["Region"], fontsize=9)
    ax2.set_xlabel("dT_within contribution")
    ax2.set_title("(b) Within-country\ninequality change")

    fig.suptitle("Theil T Decomposition by World Bank Region", fontsize=12, fontweight="bold", y=1.01)
    fig.tight_layout()
    save_fig(fig, "fig08_region_theil")


def fig09_investment_scatter(d):
    print("[Fig 09] Investment vs Within-T scatter ...")
    T9 = d["T9"]
    df = T9[T9["Investment_MEur"] > 10].copy()
    df["inc_class"] = df["IncomeGroup"].apply(classify_inc)

    fig, ax = plt.subplots(figsize=(7, 5))
    for label in INC_ORDER:
        sub = df[df["inc_class"] == label]
        if sub.empty:
            continue
        ax.scatter(sub["Investment_MEur"], sub["Within_T_Change"],
                   color=inc_color(label), alpha=0.75, s=40, label=label, zorder=3)

    ax.axhline(0, color="black", lw=0.8, ls="--", alpha=0.6)
    ax.set_xscale("log")
    ax.set_xlabel("Investment received (M EUR, log scale)")
    ax.set_ylabel("Change in within-country Theil T (dTc)")
    ax.set_title("EUGG Investment vs Domestic Carbon Inequality Change")
    ax.legend(title="Income group", loc="best", frameon=True)

    n_imp = (df["Within_T_Change"] < 0).sum()
    n_wor = (df["Within_T_Change"] > 0).sum()
    ax.text(0.97, 0.05,
            f"Recipients: {len(df)}\nImproved: {n_imp}  |  Worsened: {n_wor}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))

    fig.tight_layout()
    save_fig(fig, "fig09_investment_scatter")


def fig10_between_ranking(d):
    print("[Fig 10] Between-country contribution ranking ...")
    T10b = d.get("T10b")
    if T10b is None:
        print("  SKIP -- sheet 10b_Between_Ranked not found")
        return

    df = T10b.dropna(subset=["BC_Change"]).copy()
    top20 = df.nlargest(20, "BC_Change")
    bot20 = df.nsmallest(20, "BC_Change")
    plot_df = pd.concat([top20, bot20]).drop_duplicates("Country").sort_values("BC_Change")

    colors = [C_BETWEEN if v > 0 else C_WITHIN for v in plot_df["BC_Change"]]

    fig, ax = plt.subplots(figsize=(8, 7.5))
    bars = ax.barh(plot_df["Country"], plot_df["BC_Change"],
                   color=colors, alpha=0.85, edgecolor="white", height=0.7)
    ax.axvline(0, color="black", lw=0.8)

    patch_inc = mpatches.Patch(color=C_BETWEEN, alpha=0.85, label="Increases international gap")
    patch_dec = mpatches.Patch(color=C_WITHIN, alpha=0.85, label="Decreases international gap")
    ax.legend(handles=[patch_inc, patch_dec], loc="lower right", frameon=True)

    ax.set_xlabel("Change in T_between contribution (dBC)")
    ax.set_title("Top 20 & Bottom 20 -- Contribution to\nBetween-Country Carbon Inequality Change",
                 fontweight="bold")
    ax.tick_params(axis="y", labelsize=7.5)
    fig.tight_layout()
    save_fig(fig, "fig10_between_ranking")


def fig11_eu_spillover(d):
    print("[Fig 11] EU27 spillover ...")
    T5 = d["T5"]
    T6 = d["T6"]

    fig = plt.figure(figsize=(12, 5))
    gs = GridSpec(1, 2, figure=fig, wspace=0.4)
    ax1, ax2 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    eu = T5.sort_values("Gini_Change").copy()
    colors_eu = [C_IMPROVE if v < 0 else C_WORSEN for v in eu["Gini_Change"]]
    ax1.barh(eu["Country"], eu["Gini_Change"], color=colors_eu, alpha=0.85,
             edgecolor="white", height=0.65)
    ax1.axvline(0, color="black", lw=0.8)

    n_imp_eu = (eu["Gini_Change"] < 0).sum()
    n_wor_eu = (eu["Gini_Change"] > 0).sum()
    mean_dg = eu["Gini_Change"].mean()
    ax1.set_xlabel("dGini")
    ax1.set_title(f"(a) EU27 Domestic Gini Change\n"
                  f"Mean = {mean_dg:+.5f} | {n_imp_eu} improve / {n_wor_eu} worsen")
    ax1.tick_params(axis="y", labelsize=7)

    bf = T6.copy()
    bf["Sector_ID"] = bf["Sector_ID"].astype(int)
    sector_data = {}
    for name, ids in GLORIA_SECTORS.items():
        total = bf[bf["Sector_ID"].isin(ids)]["Backflow_MEUR"].sum()
        sector_data[name] = total

    sec_df = pd.DataFrame(list(sector_data.items()), columns=["Sector", "Backflow_MEUR"])
    sec_df = sec_df.sort_values("Backflow_MEUR", ascending=True)
    sec_colors = ["#1565C0", "#2E7D32", "#E65100", "#7B1FA2", "#00838F", "#BF360C", "#546E7A"]

    ax2.barh(sec_df["Sector"], sec_df["Backflow_MEUR"],
             color=sec_colors[:len(sec_df)], alpha=0.85, edgecolor="white", height=0.55)
    for bar, v in zip(ax2.patches, sec_df["Backflow_MEUR"]):
        ax2.text(v + max(sec_df["Backflow_MEUR"]) * 0.01,
                 bar.get_y() + bar.get_height() / 2,
                 f"{v:,.0f}", va="center", fontsize=8)

    total_bf = sec_df["Backflow_MEUR"].sum()
    ax2.set_xlabel("EU supply-chain spillover gross output (M EUR)")
    ax2.set_title(f"(b) EU Supply Chain Backflow by Sector\nGross output = {total_bf:,.0f} M EUR")

    fig.suptitle("EU27 Spillover -- Supply Chain Feedback & Domestic Inequality",
                 fontsize=12, fontweight="bold", y=1.01)
    fig.tight_layout()
    save_fig(fig, "fig11_eu_spillover")


# =========================================================================
# FIGURES 12-15: Scenario analysis (from V5)
# =========================================================================

def fig12_scenario_heatmap(d):
    print("[Fig 12] Scenario dashboard ...")
    df_sum = d.get("T15")
    if df_sum is None:
        print("  SKIP -- sheet 15_Scenario_Summary not found")
        return

    metrics = [
        ("Gini_Change", "Global ΔGini (x10^5)", 1e5, "YlOrRd", "bad_high"),
        ("CO2_Mt", "Total induced CO2 (Mt)", 1.0, "OrRd", "bad_high"),
        ("Theil_Between_Change", "ΔTheil between (x10^4)", 1e4, "YlOrRd", "bad_high"),
        ("Countries_Gini_Improved", "Countries improving", 1.0, "YlGn", "good_high"),
    ]

    mats = {}
    for col, _, scale, _, _ in metrics:
        mat = np.full((5, 3), np.nan)
        for i, sc in enumerate(SCENARIO_ORDER):
            for j, tech in enumerate(TECH_ORDER):
                row = df_sum[(df_sum["Scenario"] == sc) & (df_sum["Tech_Level"] == tech)]
                if len(row) > 0:
                    mat[i, j] = row[col].values[0] * scale
        mats[col] = mat

    fig, axes = plt.subplots(2, 2, figsize=(11, 7.2), constrained_layout=True)
    axes = axes.ravel()

    for ax, (col, title, _, cmap, direction) in zip(axes, metrics):
        mat = mats[col]
        im = ax.imshow(mat, cmap=cmap, aspect="auto")
        vmin, vmax = np.nanmin(mat), np.nanmax(mat)
        midpoint = (vmin + vmax) / 2
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                val = mat[i, j]
                if np.isnan(val):
                    continue
                if col == "Countries_Gini_Improved":
                    label = f"{val:.0f}"
                elif col == "CO2_Mt":
                    label = f"{val:.1f}"
                else:
                    label = f"{val:.2f}"
                high = val > midpoint
                txt_color = "white" if (high and direction == "bad_high") or (high and col == "Countries_Gini_Improved") else "black"
                ax.text(j, i, label, ha="center", va="center",
                        fontsize=8.5, fontweight="bold", color=txt_color)

        ax.set_xticks(range(3))
        ax.set_xticklabels([TECH_LABELS[t] for t in TECH_ORDER])
        ax.set_yticks(range(5))
        ax.set_yticklabels(SCENARIO_ORDER)
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("Technology transfer level")
        ax.grid(False)
        ax.spines["left"].set_visible(True)
        ax.spines["bottom"].set_visible(True)
        cbar = fig.colorbar(im, ax=ax, shrink=0.82, pad=0.015)
        cbar.ax.tick_params(labelsize=8)

    fig.suptitle("Global Mitigation Scenario Dashboard",
                 fontsize=13, fontweight="bold", y=1.02)
    save_fig(fig, 'fig12_scenario_heatmap')


def fig13_tradeoff_scatter(d):
    print("[Fig 13] Trade-off scatter ...")
    df_sum = d.get("T15")
    if df_sum is None:
        print("  SKIP -- sheet 15_Scenario_Summary not found")
        return

    markers = {'T0': 'o', 'T25': 's', 'T10': 'D'}
    marker_sizes = {'T0': 70, 'T25': 60, 'T10': 60}

    fig, ax = plt.subplots(figsize=(8.6, 5.8))

    for sc in SCENARIO_ORDER:
        sc_data = df_sum[df_sum['Scenario'] == sc].copy()
        tech_order_map = {t: i for i, t in enumerate(TECH_ORDER)}
        sc_data['tech_rank'] = sc_data['Tech_Level'].map(tech_order_map)
        sc_data = sc_data.sort_values('tech_rank')
        color = C_SCENARIO[sc]
        ax.plot(sc_data['CO2_Mt'], sc_data['Gini_Change'], '-',
                color=color, alpha=0.55, linewidth=1.4, zorder=1)
        for _, row in sc_data.iterrows():
            tech = row['Tech_Level']
            ax.scatter(row['CO2_Mt'], row['Gini_Change'],
                       c=color, marker=markers[tech], s=marker_sizes[tech],
                       edgecolors='black', linewidths=0.5, zorder=3)

    ax.set_xscale('log')
    ax.set_xlim(15, 340)
    ax.set_xticks([17, 30, 50, 100, 200, 320])
    ax.get_xaxis().set_major_formatter(mticker.ScalarFormatter())
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1e'))
    ax.set_xlabel('Total induced CO2 (Mt, log scale)')
    ax.set_ylabel('Global ΔGini')
    ax.set_title('Emission-Inequality Trade-off across Mitigation Scenarios',
                 fontweight='bold')

    labels_to_annotate = {
        'S4_T0': 'TransportMax_T0\nlowest ΔGini',
        'S4_T10': 'TransportMax_T10\nlowest CO2',
        'S4_T25': 'TransportMax_T25\nfrontier midpoint',
    }
    offsets = {
        'S4_T0': (-120, -8),
        'S4_T10': (10, 12),
        'S4_T25': (8, -34),
    }
    for key, label in labels_to_annotate.items():
        row = df_sum[df_sum['Key'] == key]
        if row.empty:
            continue
        row = row.iloc[0]
        ax.annotate(label, xy=(row['CO2_Mt'], row['Gini_Change']),
                    xytext=offsets[key], textcoords='offset points',
                    fontsize=8, arrowprops=dict(arrowstyle='-', color='grey',
                    linewidth=0.8), ha='left')

    sc_handles = [Line2D([0], [0], marker='o', color=C_SCENARIO[sc],
                         markeredgecolor='black', markeredgewidth=0.5,
                         markersize=7, linestyle='-', linewidth=1.2,
                         label=sc) for sc in SCENARIO_ORDER]
    tech_handles = [Line2D([0], [0], marker=markers[t], color='grey',
                           markeredgecolor='black', markeredgewidth=0.5,
                           markersize=6, linestyle='none',
                           label=TECH_LABELS[t]) for t in TECH_ORDER]
    leg1 = ax.legend(handles=sc_handles, loc='upper left',
                     bbox_to_anchor=(1.01, 1.0),
                     title='Sector scenario', title_fontsize=8, framealpha=0.9)
    ax.add_artist(leg1)
    ax.legend(handles=tech_handles, loc='upper left',
              bbox_to_anchor=(1.01, 0.46),
              title='Tech transfer', title_fontsize=8, framealpha=0.9)

    fig.tight_layout(rect=[0, 0, 0.82, 1])
    save_fig(fig, 'fig13_tradeoff_scatter')


def fig14_theil_scenarios(d):
    print("[Fig 14] Theil decomposition across scenarios ...")
    df_sum = d.get("T15")
    if df_sum is None:
        print("  SKIP -- sheet 15_Scenario_Summary not found")
        return

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.4), sharey=True)
    width = 0.35

    for ax, tech in zip(axes, ['T0', 'T10']):
        tech_df = df_sum[df_sum['Tech_Level'] == tech].set_index('Scenario').reindex(SCENARIO_ORDER)
        x = np.arange(len(SCENARIO_ORDER))
        between_vals = tech_df['Theil_Between_Change'].values
        within_vals = tech_df['Theil_Within_Change'].values
        total_vals = tech_df['Theil_Total_Change'].values

        ax.bar(x - width / 2, between_vals, width, label='ΔTheil between',
               color=C_BETWEEN, edgecolor='black', linewidth=0.5, alpha=0.85)
        ax.bar(x + width / 2, within_vals, width, label='ΔTheil within',
               color=C_WITHIN, edgecolor='black', linewidth=0.5, alpha=0.85)
        ax.plot(x, total_vals, marker='o', color=C_TOTAL, linewidth=1.4,
                markersize=4.5, label='ΔTheil total')
        ax.axhline(y=0, color='black', linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(SCENARIO_ORDER, rotation=25, ha='right')
        ax.set_title(f'{TECH_LABELS[tech]}', fontweight='bold')
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1e'))
        ax.grid(axis='y', alpha=0.25)

    axes[0].set_ylabel('Change in Theil T')
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, framealpha=0.95,
               bbox_to_anchor=(0.5, -0.03))
    fig.suptitle('Theil Decomposition across Global Mitigation Scenarios',
                 fontsize=13, fontweight='bold', y=1.02)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    save_fig(fig, 'fig14_theil_scenarios')


def fig15_country_distribution(d):
    print("[Fig 15] Country-level improvement status ...")
    df_gini = d.get("T16")
    if df_gini is None:
        print("  SKIP -- sheet 16_Country_Gini_Scenarios not found")
        return

    scenarios = [
        ('S0_T0', 'Baseline_T0', C_SCENARIO['Baseline']),
        ('S2_T10', 'EnergyMax_T10', C_SCENARIO['EnergyMax']),
        ('S4_T10', 'TransportMax_T10', C_SCENARIO['TransportMax']),
    ]
    for col, _, _ in scenarios:
        if col not in df_gini.columns:
            print(f"  SKIP -- column {col} not found")
            return

    n_total = len(df_gini)
    improved_counts = [int((df_gini[col] < 0).sum()) for col, _, _ in scenarios]
    not_improved_counts = [n_total - n for n in improved_counts]

    base_imp = df_gini['S0_T0'] < 0
    energy_imp = df_gini['S2_T10'] < 0
    transport_imp = df_gini['S4_T10'] < 0

    transitions = {
        'EnergyMax_T10': [
            int((base_imp & energy_imp).sum()),
            int((base_imp & ~energy_imp).sum()),
            int((~base_imp & energy_imp).sum()),
            int((~base_imp & ~energy_imp).sum()),
        ],
        'TransportMax_T10': [
            int((base_imp & transport_imp).sum()),
            int((base_imp & ~transport_imp).sum()),
            int((~base_imp & transport_imp).sum()),
            int((~base_imp & ~transport_imp).sum()),
        ],
    }
    transition_labels = ['Remain improving', 'Lose improvement',
                         'Gain improvement', 'Remain not improving']
    transition_colors = ['#2E8B57', '#C44E52', '#4C72B0', '#9E9E9E']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 5.2),
                                    gridspec_kw={'width_ratios': [0.9, 1.2]})

    x = np.arange(len(scenarios))
    ax1.bar(x, improved_counts, color='#2E8B57', edgecolor='black',
            linewidth=0.5, label='Improving')
    ax1.bar(x, not_improved_counts, bottom=improved_counts, color='#BDBDBD',
            edgecolor='black', linewidth=0.5, label='Not improving')
    for i, count in enumerate(improved_counts):
        ax1.text(i, count / 2, f'{count}', ha='center', va='center',
                 fontsize=10, fontweight='bold', color='white')
        ax1.text(i, count + not_improved_counts[i] / 2,
                 f'{not_improved_counts[i]}', ha='center', va='center',
                 fontsize=9, color='black')
    ax1.set_xticks(x)
    ax1.set_xticklabels([label for _, label, _ in scenarios],
                        rotation=20, ha='right')
    ax1.set_ylim(0, n_total)
    ax1.set_ylabel('Number of countries')
    ax1.set_title('(a) Countries with domestic Gini improvement',
                  fontweight='bold')
    ax1.legend(loc='upper right', framealpha=0.9)

    x2 = np.arange(len(transitions))
    bottoms = np.zeros(len(transitions))
    for idx, (lab, color) in enumerate(zip(transition_labels, transition_colors)):
        vals = [transitions[name][idx] for name in transitions]
        ax2.bar(x2, vals, bottom=bottoms, color=color, edgecolor='black',
                linewidth=0.5, label=lab)
        for i, val in enumerate(vals):
            if val >= 8:
                ax2.text(i, bottoms[i] + val / 2, f'{val}', ha='center',
                         va='center', fontsize=9,
                         color='white' if color != '#9E9E9E' else 'black')
        bottoms += np.array(vals)

    ax2.set_xticks(x2)
    ax2.set_xticklabels(list(transitions.keys()), rotation=15, ha='right')
    ax2.set_ylim(0, n_total)
    ax2.set_ylabel('Number of countries')
    ax2.set_title('(b) Switching status relative to Baseline_T0',
                  fontweight='bold')
    ax2.legend(loc='upper right', fontsize=8, framealpha=0.9)

    fig.suptitle('Country-Level Inequality Status under Frontier Transfer',
                 fontsize=13, fontweight='bold', y=1.02)
    fig.tight_layout()
    save_fig(fig, 'fig15_country_distribution')


# =========================================================================
# MAIN
# =========================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("  EUGG_figures.py -- local figure generation (15 figures)")
    print("=" * 65 + "\n")

    D = load_all()
    print()

    # Baseline analysis figures (Ch 4)
    fig01_lorenz(D)
    fig02_simpsons_paradox(D)
    fig03_choropleth(D)
    fig04_theil_decomp(D)
    fig05_amplification(D)
    fig06_gdp_carbon(D)
    fig07_incgroup_theil(D)
    fig08_region_theil(D)
    fig09_investment_scatter(D)
    fig10_between_ranking(D)
    fig11_eu_spillover(D)

    # Scenario analysis figures (Ch 6)
    fig12_scenario_heatmap(D)
    fig13_tradeoff_scatter(D)
    fig14_theil_scenarios(D)
    fig15_country_distribution(D)

    print(f"\n{'=' * 65}")
    print(f"  All 15 figures saved to: {FIG_DIR.resolve()}")
    print(f"  Format: PNG ({DPI} DPI) + PDF (vector)")
    print(f"{'=' * 65}")
