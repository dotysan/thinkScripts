# OpeningRange
# Draws horizontal lines at the high and low of a configurable opening range
# (default: first 30 minutes of the regular session) and paints bars to show
# whether price is inside the range, above it (bullish breakout), or below it
# (bearish breakdown).
#
# A cloud between the OR high and low is shown while the range is forming.
# After the range is locked, breakout arrows appear on the first bar that
# closes outside the range.
#
# Usage: Add as an upper (overlay) study on an intraday chart.
# Works best on 1-, 3-, or 5-minute charts during regular trading hours.

declare upper;

# ── Parameters ────────────────────────────────────────────────────────────────
input openRangeMinutes = 30;   # length of the opening range window
input startTime        = 0930; # market open in HHMM format
input extendLines      = yes;  # extend OR lines to the right across the day

# ── Opening Range Detection ────────────────────────────────────────────────────
# SecondsFromTime returns the number of seconds that have elapsed since the
# given HHMM time on the current bar.  A negative value means the bar is
# before that time.
def secondsFromOpen = SecondsFromTime(startTime);
def isInOpenRange   = secondsFromOpen >= 0 and
                      secondsFromOpen < openRangeMinutes * 60;

# Track the first bar of the opening range so the range can be "locked" once
# the window closes.
def firstBarOfRange = secondsFromOpen >= 0 and secondsFromOpen[1] < 0;

# ── Build the Opening Range High / Low ────────────────────────────────────────
# CompoundValue seeds the recursive definition with the current bar's value
# when [1] would otherwise be NaN (e.g. on bar 0).

def orHigh = if firstBarOfRange then high
             else if isInOpenRange then
                 CompoundValue(1, if high > orHigh[1] then high else orHigh[1], high)
             else
                 orHigh[1];

def orLow  = if firstBarOfRange then low
             else if isInOpenRange then
                 CompoundValue(1, if low < orLow[1] then low else orLow[1], low)
             else
                 orLow[1];

# Only plot once the range is established (i.e. after the open).
def rangeEstablished = secondsFromOpen >= 0;

# ── Plots ─────────────────────────────────────────────────────────────────────
plot ORHigh = if rangeEstablished then orHigh else Double.NaN;
ORHigh.SetDefaultColor(Color.CYAN);
ORHigh.SetStyle(if extendLines then Curve.FIRM else Curve.SHORT_DASH);
ORHigh.SetLineWeight(2);

plot ORLow = if rangeEstablished then orLow else Double.NaN;
ORLow.SetDefaultColor(Color.CYAN);
ORLow.SetStyle(if extendLines then Curve.FIRM else Curve.SHORT_DASH);
ORLow.SetLineWeight(2);

# Shade the cloud between OR high and low while the range is forming.
AddCloud(
    if isInOpenRange then orHigh else Double.NaN,
    if isInOpenRange then orLow  else Double.NaN,
    Color.CYAN,
    Color.CYAN
);

# ── Breakout Signals ──────────────────────────────────────────────────────────
# Signal only after the opening range window has closed.
def rangeComplete = not isInOpenRange and rangeEstablished;

def breakoutUp   = rangeComplete and close crosses above orHigh;
def breakoutDown = rangeComplete and close crosses below orLow;

plot BreakoutUpArrow   = if breakoutUp   then orHigh else Double.NaN;
plot BreakoutDownArrow = if breakoutDown then orLow  else Double.NaN;

BreakoutUpArrow.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
BreakoutUpArrow.SetDefaultColor(Color.GREEN);
BreakoutUpArrow.SetLineWeight(3);

BreakoutDownArrow.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);
BreakoutDownArrow.SetDefaultColor(Color.RED);
BreakoutDownArrow.SetLineWeight(3);

# ── Label ─────────────────────────────────────────────────────────────────────
def rangeSize = orHigh - orLow;
AddLabel(
    rangeEstablished,
    "OR(" + openRangeMinutes + "m)  H:" + AsText(orHigh) +
        "  L:" + AsText(orLow) +
        "  Rng:" + AsText(Round(rangeSize, 2)),
    Color.CYAN
);

# ── Alerts ────────────────────────────────────────────────────────────────────
Alert(breakoutUp,   "Opening Range Breakout — ABOVE OR High", Alert.BAR, Sound.Bell);
Alert(breakoutDown, "Opening Range Breakdown — BELOW OR Low",  Alert.BAR, Sound.Bell);
