# RelativeVolume
# Compares each bar's volume to a simple moving average of volume over a
# configurable look-back period.  A value of 1.0 means volume is exactly
# at its average; 2.0 means twice the average, etc.
#
# Colour coding:
#   Green   — at or above the alert threshold (unusually high activity)
#   Yellow  — above average but below the alert threshold
#   Red     — below average
#
# Usage: Add as a lower study on any chart timeframe.

declare lower;

# ── Parameters ────────────────────────────────────────────────────────────────
input length         = 20;   # look-back period for the volume average
input alertThreshold = 2.0;  # relative-volume level that triggers an alert
input showLabel      = yes;

# ── Calculations ──────────────────────────────────────────────────────────────
def avgVol = Average(volume, length);

# Guard against bars where the average is zero (e.g. extended-hours gaps).
def relVol = if avgVol != 0 then volume / avgVol else 0;

# ── Plots ─────────────────────────────────────────────────────────────────────
plot RelativeVolume = relVol;
RelativeVolume.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
RelativeVolume.AssignValueColor(
    if relVol >= alertThreshold then Color.GREEN
    else if relVol >= 1.0       then Color.YELLOW
    else Color.RED
);
RelativeVolume.SetLineWeight(2);

# 1.0 reference line — "average" volume
plot AverageLine = 1.0;
AverageLine.SetDefaultColor(Color.WHITE);
AverageLine.SetStyle(Curve.LONG_DASH);
AverageLine.SetLineWeight(1);

# Threshold line — marks the high-activity alert level
plot ThresholdLine = alertThreshold;
ThresholdLine.SetDefaultColor(Color.GREEN);
ThresholdLine.SetStyle(Curve.SHORT_DASH);
ThresholdLine.SetLineWeight(1);

# ── Label ─────────────────────────────────────────────────────────────────────
AddLabel(
    showLabel,
    "RelVol(" + length + "): " + AsText(Round(relVol, 2)) + "x",
    if relVol >= alertThreshold then Color.GREEN
    else if relVol >= 1.0       then Color.YELLOW
    else Color.GRAY
);

# ── Alert ─────────────────────────────────────────────────────────────────────
Alert(
    relVol crosses above alertThreshold,
    "High Relative Volume: " + AsText(Round(relVol, 2)) + "x average",
    Alert.BAR,
    Sound.Bell
);
