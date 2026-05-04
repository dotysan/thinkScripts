# thinkScripts

A collection of thinkScripts that can be used as trading indicators in the
[thinkorswim](https://www.schwab.com/trading/thinkorswim) platform by Charles
Schwab (formerly TD Ameritrade).

> **Note:** ThinkScript is a strange, poorly documented, and oddly-typed
> language. These scripts attempt to follow consistent conventions and are
> heavily commented to compensate for the lack of official documentation.

---

## What is ThinkScript?

ThinkScript is a proprietary scripting language built into the thinkorswim
trading platform. It allows traders to create custom studies (indicators),
strategies, scanners, and alerts. The language is loosely typed, has quirky
scoping rules, and relies on an implicit bar-by-bar evaluation model that
can be non-obvious to developers coming from general-purpose languages.

---

## Indicators

| File | Description |
|------|-------------|
| [`indicators/GapPercent.ts`](indicators/GapPercent.ts) | Displays the percentage gap between the previous close and today's open. Useful for pre-market gap analysis. |
| [`indicators/RelativeVolume.ts`](indicators/RelativeVolume.ts) | Compares current bar volume to a moving average of volume. Values above 1.0 indicate above-average activity. |
| [`indicators/OpeningRange.ts`](indicators/OpeningRange.ts) | Draws the high and low of a configurable opening range period and signals breakouts above or below that range. |
| [`indicators/SuperTrend.ts`](indicators/SuperTrend.ts) | A trend-following indicator based on ATR that paints the trend direction and flips sides when price crosses the band. |

---

## Installation

1. Open thinkorswim and navigate to **Charts → Studies → Edit Studies**.
2. Click **Create** (or **Import**).
3. Paste the contents of the desired `.ts` file into the editor.
4. Click **OK** to save and apply the study to your chart.

Alternatively, use the **thinkScript Editor** (under the **Scan** or **Charts**
tab) to paste and save individual scripts.

---

## Contributing

Pull requests are welcome. When adding a new script, please:

- Place it under the appropriate subdirectory (`indicators/`, `strategies/`,
  `scanners/`, etc.).
- Include a header comment block with at minimum a `# Title`, a brief
  description, and any important usage notes.
- Keep variable names descriptive — ThinkScript has no namespace support.
- Test the script in thinkorswim before submitting.

---

## License

[MIT](LICENSE)
