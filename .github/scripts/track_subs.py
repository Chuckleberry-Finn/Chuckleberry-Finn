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
pivot_df = df.pivot_table(index="date", columns="mod", values="subscribers", aggfunc="last").ffill()

# Sort mods by change since tracking started (not total subscribers)
initial_totals = pivot_df.apply(lambda col: col[col.first_valid_index()] if col.first_valid_index() is not None else pd.NA)
final_totals = pivot_df.iloc[-1] - initial_totals
sorted_mods = final_totals.sort_values(ascending=False).index
pivot_df = pivot_df[sorted_mods]

# --- Precompute legend labels for each time range ---
legend_labels = {"1w": [], "1m": [], "3m": [], "All": []}
mod_traces = []

for mod in pivot_df.columns:
    y_vals = pivot_df[mod].tolist()
    mod_traces.append((mod, y_vals))
    trimmed_mod = (mod[:37] + "...") if len(mod) > 40 else mod
    for label, days in [("1w", 7), ("1m", 30), ("3m", 90), ("All", None)]:
        if days is not None and len(y_vals) > 1:
            valid_vals = [v for v in y_vals[-days-1:] if not pd.isna(v)]
            if len(valid_vals) < 2:
                change = 0
            else:
                change = int(valid_vals[-1]) - int(valid_vals[0])
        elif days is None:
            first_valid_index = next((i for i, v in enumerate(y_vals) if not pd.isna(v)), None)
            last_valid_index = next((i for i in reversed(range(len(y_vals))) if not pd.isna(y_vals[i])), None)
            if first_valid_index is not None and last_valid_index is not None and first_valid_index != last_valid_index:
                change = int(y_vals[last_valid_index]) - int(y_vals[first_valid_index])
            else:
                change = 0
        else:
            change = 0

        symbol = "▲" if change > 0 else "▼" if change < 0 else "•"
        final_val = int(y_vals[-1]) if not pd.isna(y_vals[-1]) else 0
        legend_labels[label].append(f"{trimmed_mod} ({final_val} {symbol}{abs(change)})")

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
        new_names += [legend_labels["All"][i] for i in range(len(new_names), total_traces)]

    buttons.append(dict(
        label=label,
        method="restyle",
        args=[{"visible": vis, "name": new_names}]
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
            bgcolor="#333333",
            bordercolor="#888888",
            font=dict(color="#ffffff"),
            buttons=buttons
        )
    ]
)

fig.write_html("mod_subscriber_graph.html")