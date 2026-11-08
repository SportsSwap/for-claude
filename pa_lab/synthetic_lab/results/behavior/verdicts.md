# Behavior test verdicts

Provenance: {'master_seed': 20220103, 'amendment': 0, 'locks': {'config/thresholds.json': '1668080849f616d0d27474d0927df3c23da355a9e6357c73aa9a26fd97e66f05', 'rulebook_spec.json': 'd33b0eea5948f28d57978984fdd307770eadf156a2fbe1b579407afeb2072078'}, 'written_utc': '2026-11-08T20:57:02+00:00'}

| test | verdict | NQ pooled (95% CI) | ES pooled | era 1 / era 2 | claim |
|---|---|---|---|---|---|
| `levels_vs_random` | **false** | -0.0021 (-0.0049, +0.0006) | -0.0005 | -0.0028 / -0.0017 | Real levels hold more often than random lines. NQ pooled points the other way. |
| `hold_by_touch_count` | **false** | +0.0027 (-0.0029, +0.0087) | -0.0057 | +0.0047 / +0.0015 | A level's 3rd+ touch holds more often than its 1st. NQ pooled has an interval that includes zero. |
| `wall_or_target` | **false** | -0.0018 (-0.0049, +0.0014) | -0.0008 | -0.0000 / -0.0028 | A level touched 3+ times acts as a wall (holds more than a random line touched as often), not a target. NQ pooled points the other way. |
| `shrinking_bounces` | **false** | -0.0072 (-0.0185, +0.0036) | -0.0021 | -0.0124 / -0.0042 | After two shrinking bounces, the next touch breaks more often. NQ pooled points the other way. |
| `line_vs_box` | **false** | +0.0006 (-0.0023, +0.0036) | +0.0016 | +0.0001 / +0.0009 | A level drawn as a box holds more often than one drawn as a line, beyond what the width alone gives. NQ pooled has an interval that includes zero. |
| `wick_vs_close_through` | **false** | -0.0158 (-0.0535, +0.0241) | -0.0339 | -0.0288 / -0.0079 | A wick through a level is followed by more move in the level's favour than a close through it. NQ pooled points the other way. |
| `flip_zones` | **false** | -0.0027 (-0.0095, +0.0044) | -0.0018 | -0.0032 / -0.0023 | A broken level holds from the other side more often than a random line. NQ pooled points the other way. |
| `bos_follow_10` | **false** | +0.0106 (-0.0538, +0.0730) | -0.0649 | +0.0518 / -0.0162 | A break of structure is followed by more move its way than random bars, at 10 bars. NQ pooled has an interval that includes zero. |
| `bos_follow_20` | **false** | -0.0083 (-0.1010, +0.0890) | -0.0501 | +0.0587 / -0.0521 | The same at 20 bars. NQ pooled points the other way. |
| `bos_follow_50` | **false** | -0.0333 (-0.2015, +0.1336) | -0.0984 | +0.0291 / -0.0738 | The same at 50 bars. NQ pooled points the other way. |
| `choch_follow_10` | **false** | +0.0211 (-0.0334, +0.0763) | -0.0055 | -0.0194 / +0.0467 | A change of character is followed by more move its way than random bars, at 10 bars. NQ pooled has an interval that includes zero. |
| `choch_follow_20` | **false** | -0.0084 (-0.0812, +0.0710) | +0.0309 | +0.0340 / -0.0352 | The same at 20 bars. NQ pooled points the other way. |
| `choch_follow_50` | **false** | -0.0613 (-0.1592, +0.0384) | -0.0024 | -0.1142 / -0.0279 | The same at 50 bars. NQ pooled points the other way. |
| `sweeps_vs_closes` | **false** | +0.0014 (-0.0221, +0.0264) | -0.0158 | +0.0025 / +0.0006 | A sweep reverses more than a close through the level does. NQ pooled has an interval that includes zero. |
| `trend_start_sweep` | **false** | +0.2597 (-0.0384, +0.5658) | -0.0387 | +0.5438 / +0.0844 | A change of character that starts with a sweep follows through more. NQ pooled has an interval that includes zero. |
| `trend_lines` | **false** | -0.0016 (-0.0063, +0.0034) | +0.0014 | -0.0032 / -0.0006 | Real trend lines hold more often than shifted lines. NQ pooled points the other way. |
| `fvg_hold` | **false** | +0.0034 (-0.0058, +0.0128) | -0.0091 | +0.0058 / +0.0020 | A fair value gap holds on its first return more often than a random band. NQ pooled has an interval that includes zero. |
| `fvg_fill` | **false** | -0.0028 (-0.0080, +0.0023) | +0.0032 | -0.0058 / -0.0009 | Price returns into a fair value gap within 50 bars more often than into a random band. NQ pooled points the other way. |
| `zones_first_vs_later` | **false** | -0.0016 (-0.0130, +0.0097) | -0.0069 | +0.0008 / -0.0029 | A supply/demand zone holds better on its first return than on later ones. NQ pooled points the other way. |
| `zones_vs_random` | **false** | -0.0020 (-0.0182, +0.0136) | -0.0006 | -0.0145 / +0.0060 | A supply/demand zone holds better than a random band on first return. NQ pooled points the other way. |
| `pullback_depth` | **false** | +0.0665 (-0.1742, +0.3025) | -0.1429 | -0.2607 / +0.2757 | A break after a shallow pullback follows through more than after a deep one. NQ pooled has an interval that includes zero. |
| `engulfing_at_levels` | **false** | -0.0253 (-0.1017, +0.0497) | -0.0402 | -0.0210 / -0.0284 | An engulfing candle at a level moves more its way than the same candle at random. NQ pooled points the other way. |
| `rejection_at_levels` | **false** | +0.0060 (-0.0338, +0.0457) | +0.0119 | +0.0051 / +0.0066 | A rejection candle at a level moves more its way than the same candle at random. NQ pooled has an interval that includes zero. |
