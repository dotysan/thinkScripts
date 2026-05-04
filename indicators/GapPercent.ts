# GapPercent
# Displays the percentage gap between the previous session's close and the
# current session's open.  Positive values (green) indicate a gap up;
# negative values (red) indicate a gap down.
#
# Usage: Add as a lower study on any intraday chart.
# The label updates once per session because the open is fixed after the
# first bar of the day.

declare lower;

# ── Parameters ────────────────────────────────────────────────────────────────
input showLabel = yes;

# ── Calculations ──────────────────────────────────────────────────────────────
# Grab the daily-aggregation close from the previous session and today's open.
def prevClose = close(period = AggregationPeriod.DAY)[1];
def todayOpen  = open(period = AggregationPeriod.DAY);

# Avoid a division-by-zero on the very first bar of history.
def gapPct = if prevClose != 0
             then (todayOpen - prevClose) / prevClose * 100
             else 0;

# ── Plots ─────────────────────────────────────────────────────────────────────
plot GapPercent = gapPct;
GapPercent.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
GapPercent.AssignValueColor(
    if gapPct > 0 then Color.GREEN
    else if gapPct < 0 then Color.RED
    else Color.GRAY
);
GapPercent.SetLineWeight(2);

plot ZeroLine = 0;
ZeroLine.SetDefaultColor(Color.GRAY);
ZeroLine.SetStyle(Curve.LONG_DASH);

# ── Label ─────────────────────────────────────────────────────────────────────
AddLabel(
    showLabel,
    "Gap: " + AsPercent(gapPct / 100),
    if gapPct > 0 then Color.GREEN
    else if gapPct < 0 then Color.RED
    else Color.GRAY
);
