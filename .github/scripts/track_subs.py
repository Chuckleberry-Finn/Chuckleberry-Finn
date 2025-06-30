import os
import sys
import subprocess
import re
from datetime import datetime
import plotly.graph_objects as go
import pandas as pd

# --- Ensure required libraries are available ---
def ensure_libs():
    for lib in ["plotly", "pandas"]:
        try:
            __import__(lib)
        except ImportError:
            print(f"Installing {lib}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", lib])

ensure_libs()

# --- Config ---
REPO_DIR = "../../"
FILE_PATH = "README.md"
GIT_PATH = r"C:\\Program Files\\Git\\cmd\\git.exe"  # Adjust if necessary

# --- Step 1: Gather commit data ---
os.chdir(REPO_DIR)
commits = subprocess.check_output([GIT_PATH, "log", "--format=%H|%ct", "main"]).decode().splitlines()
commits = list(reversed(commits))

# --- Extract mod subscriber data ---
data = []
seen_dates = set()
for entry in commits:
    sha, timestamp = entry.strip().split("|")
    date = datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
    if date in seen_dates:
        continue
    seen_dates.add(date)
    try:
        content = subprocess.check_output([GIT_PATH, "show", f"{sha}:{FILE_PATH}"], stderr=subprocess.DEVNULL).decode()
    except subprocess.CalledProcessError:
        continue

    align_row = re.search(r"\|:?-{3,}.*\|", content)
    end_marker = content.find("<!-- END:WORKSHOP -->")
    if not align_row or end_marker == -1:
        continue

    table = content[align_row.end():end_marker].strip().splitlines()
    seen_mods = set()
    for line in table:
        parts = line.strip().split("|")
        if len(parts) < 4:
            continue
        mod = parts[1].strip().lower()
        if mod in seen_mods:
            continue
        seen_mods.add(mod)
        count_str = parts[2].strip().replace(",", "")
        try:
            count = int(count_str)
            data.append({"mod": mod, "date": date, "subscribers": count})
        except ValueError:
            continue

# --- Step 2: Create DataFrame ---
df = pd.DataFrame(data)
df = df.sort_values(by="date")
df = df.drop_duplicates(subset=["mod", "date"], keep="last")
pivot_df = df.pivot_table(index="date", columns="mod", values="subscribers", aggfunc="last").fillna(0).ffill()

# Sort mods by total subscribers (last value)
final_totals = pivot_df.iloc[-1].sort_values(ascending=False)
pivot_df = pivot_df[final_totals.index]

# --- Precompute legend labels for each time range ---
legend_labels = {"1w": [], "1m": [], "3m": [], "All": []}
mod_traces = []

for mod in pivot_df.columns:
    y_vals = pivot_df[mod].tolist()
    mod_traces.append((mod, y_vals))
    trimmed_mod = (mod[:37] + "...") if len(mod) > 40 else mod
    for label, days in [("1w", 7), ("1m", 30), ("3m", 90), ("All", None)]:
        if days is not None and len(y_vals) > days:
            change = y_vals[-1] - y_vals[-days-1]
        elif days is None and len(y_vals) > 1:
            change = y_vals[-1] - y_vals[0]
        else:
            change = 0
        symbol = "▲" if change > 0 else "▼" if change < 0 else "•"
        legend_labels[label].append(f"{trimmed_mod} ({int(y_vals[-1])} {symbol}{abs(int(change))})")

# --- Build traces ---
fig = go.Figure()
for i, (mod, y_vals) in enumerate(mod_traces):
    fig.add_trace(go.Scatter(
        x=pivot_df.index,
        y=y_vals,
        mode='lines+markers',
        name=legend_labels["All"][i],
        visible=True,
        legendgroup=mod,
        showlegend=True,
        xaxis="x1"
    ))

# --- Visibility pattern ---
def visibility_pattern(show_deltas, n):
    return [True for _ in range(n)]

# --- Range helpers ---
def safe_range(df, days_back):
    total = len(df.index)
    start = max(0, total - days_back)
    return [df.index[start], df.index[-1]]

# --- Update buttons with precomputed names ---
buttons = []
total_traces = len(mod_traces)

for label, days, show_deltas in [("1w", 7, True), ("1m", 30, True), ("3m", 90, False), ("All", None, False)]:
    vis = visibility_pattern(show_deltas, total_traces)
    new_names = legend_labels[label]
    if len(new_names) < total_traces:
        new_names += ["" for _ in range(total_traces - len(new_names))]  # pad to avoid index error

    args = [{"visible": vis, "name": new_names}]
    if days is not None:
        args.append({"xaxis.range": safe_range(pivot_df, days)})
    else:
        args.append({"xaxis.autorange": True})

    buttons.append(dict(
        label=label,
        method="update",
        args=args
    ))

fig.update_layout(
    title="Mod Subscriber Counts Over Time",
    xaxis=dict(
        title="Date",
        type="date",
        domain=[0, 1],
        rangeslider=dict(visible=True),
        anchor="y",
        overlaying=None
    ),
    yaxis_title="Subscribers",
    hovermode="x unified",
    plot_bgcolor="#1e1e1e",
    paper_bgcolor="#1e1e1e",
    font=dict(color="#eeeeee"),
    updatemenus=[
        dict(
            type="buttons",
            direction="right",
            showactive=False,
            active=3,
            x=0.5,
            xanchor="center",
            y=1.2,
            yanchor="top",
            bordercolor="#888888",
            bgcolor="#555555",
            font=dict(color="#ffffff"),
            buttons=buttons
        )
    ]
)

fig.show()
