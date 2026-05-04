# SuperTrend
# A trend-following overlay indicator based on the Average True Range (ATR).
# It draws a single line (the "SuperTrend band") that sits below price in an
# uptrend and above price in a downtrend.  When price crosses the band the
# trend flips and the line switches sides.
#
# Interpretation:
#   Green line below price → uptrend (consider long positions)
#   Red line above price   → downtrend (consider short positions)
#   Flip arrows mark potential trend-change entries
#
# Parameters:
#   atrLength  — period for ATR calculation (default 10)
#   multiplier — how many ATRs the band is placed from the midpoint (default 3.0)
#
# Usage: Add as an upper (overlay) study on any chart timeframe.

declare upper;

# ── Parameters ────────────────────────────────────────────────────────────────
input atrLength  = 10;
input multiplier = 3.0;
input showArrows = yes;
input showLabel  = yes;

# ── ATR Band Construction ─────────────────────────────────────────────────────
def atr    = multiplier * ATR(atrLength);
def midPt  = (high + low) / 2;

def upperBand = midPt + atr;
def lowerBand = midPt - atr;

# The final bands are adjusted to never move against the trend: the lower band
# can only move up when price is in an uptrend; the upper band can only move
# down when price is in a downtrend.
def finalUpperBand =
    if upperBand < finalUpperBand[1] or close[1] > finalUpperBand[1]
    then upperBand
    else finalUpperBand[1];

def finalLowerBand =
    if lowerBand > finalLowerBand[1] or close[1] < finalLowerBand[1]
    then lowerBand
    else finalLowerBand[1];

# ── Trend Direction ───────────────────────────────────────────────────────────
# 1 = uptrend, -1 = downtrend
# Seed the first bar as an uptrend (CompoundValue handles the NaN bootstrap).
def trend =
    CompoundValue(
        1,
        if trend[1] == -1 and close > finalUpperBand[1] then  1
        else if trend[1] ==  1 and close < finalLowerBand[1] then -1
        else trend[1],
        1
    );

# Active band: lower band in uptrend, upper band in downtrend.
def superTrendValue =
    if trend ==  1 then finalLowerBand
    else               finalUpperBand;

# ── Plots ─────────────────────────────────────────────────────────────────────
plot SuperTrend = superTrendValue;
SuperTrend.AssignValueColor(
    if trend == 1 then Color.GREEN else Color.RED
);
SuperTrend.SetLineWeight(2);

# ── Flip Arrows ───────────────────────────────────────────────────────────────
def flipUp   = trend ==  1 and trend[1] == -1;
def flipDown = trend == -1 and trend[1] ==  1;

plot FlipUpArrow   = if showArrows and flipUp   then superTrendValue else Double.NaN;
plot FlipDownArrow = if showArrows and flipDown then superTrendValue else Double.NaN;

FlipUpArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
FlipUpArrow.SetDefaultColor(Color.GREEN);
FlipUpArrow.SetLineWeight(3);

FlipDownArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
FlipDownArrow.SetDefaultColor(Color.RED);
FlipDownArrow.SetLineWeight(3);

# ── Label ─────────────────────────────────────────────────────────────────────
AddLabel(
    showLabel,
    "SuperTrend(" + atrLength + "," + multiplier + "): " +
        (if trend == 1 then "UP" else "DOWN"),
    if trend == 1 then Color.GREEN else Color.RED
);

# ── Alerts ────────────────────────────────────────────────────────────────────
Alert(flipUp,   "SuperTrend flipped UP",   Alert.BAR, Sound.Bell);
Alert(flipDown, "SuperTrend flipped DOWN", Alert.BAR, Sound.Bell);
