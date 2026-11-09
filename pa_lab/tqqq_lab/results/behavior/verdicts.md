# Behavior test verdicts

Provenance: {'master_seed': 20220103, 'amendment': 0, 'locks': {'config/thresholds.json': '1668080849f616d0d27474d0927df3c23da355a9e6357c73aa9a26fd97e66f05', 'rulebook_spec.json': 'd33b0eea5948f28d57978984fdd307770eadf156a2fbe1b579407afeb2072078'}, 'written_utc': '2026-11-09T07:41:51+00:00'}

| test | verdict | NQ pooled (95% CI) | ES pooled | era 1 / era 2 | claim |
|---|---|---|---|---|---|
| `levels_vs_random` | **false** | -0.0008 (-0.0072, +0.0057) | -0.0043 | +0.0038 / -0.0034 | Real levels hold more often than random lines. NQ pooled points the other way. |
| `hold_by_touch_count` | **true** | +0.0213 (+0.0089, +0.0336) | +0.0250 | +0.0426 / +0.0077 | A level's 3rd+ touch holds more often than its 1st. NQ pooled points the claimed way with an interval excluding zero; ES agrees; both eras agree. |
| `wall_or_target` | **false** | +0.0020 (-0.0050, +0.0091) | +0.0013 | +0.0078 / -0.0014 | A level touched 3+ times acts as a wall (holds more than a random line touched as often), not a target. NQ pooled has an interval that includes zero. |
| `shrinking_bounces` | **false** | +0.0036 (-0.0191, +0.0279) | +0.0046 | -0.0373 / +0.0264 | After two shrinking bounces, the next touch breaks more often. NQ pooled has an interval that includes zero. |
| `line_vs_box` | **false** | +0.0052 (-0.0017, +0.0116) | -0.0047 | +0.0053 / +0.0050 | A level drawn as a box holds more often than one drawn as a line, beyond what the width alone gives. NQ pooled has an interval that includes zero. |
| `wick_vs_close_through` | **false** | +0.0391 (-0.0992, +0.1799) | +0.0619 | -0.0963 / +0.1204 | A wick through a level is followed by more move in the level's favour than a close through it. NQ pooled has an interval that includes zero. |
| `flip_zones` | **true** | +0.0154 (+0.0013, +0.0310) | +0.0089 | +0.0402 / +0.0001 | A broken level holds from the other side more often than a random line. NQ pooled points the claimed way with an interval excluding zero; ES agrees; both eras agree. |
| `bos_follow_10` | **false** | -0.0139 (-0.2122, +0.1810) | -0.0021 | -0.2649 / +0.1513 | A break of structure is followed by more move its way than random bars, at 10 bars. NQ pooled points the other way. |
| `bos_follow_20` | **false** | +0.0090 (-0.2836, +0.2777) | -0.0461 | -0.3028 / +0.2153 | The same at 20 bars. NQ pooled has an interval that includes zero. |
| `bos_follow_50` | **false** | +0.0337 (-0.4562, +0.4930) | +0.1425 | -0.4749 / +0.3747 | The same at 50 bars. NQ pooled has an interval that includes zero. |
| `choch_follow_10` | **false** | -0.1273 (-0.3018, +0.0440) | +0.0956 | -0.1136 / -0.1390 | A change of character is followed by more move its way than random bars, at 10 bars. NQ pooled points the other way. |
| `choch_follow_20` | **false** | +0.0305 (-0.1884, +0.2494) | +0.0916 | +0.0635 / +0.0067 | The same at 20 bars. NQ pooled has an interval that includes zero. |
| `choch_follow_50` | **false** | +0.1830 (-0.1337, +0.5047) | +0.0030 | +0.3862 / +0.0430 | The same at 50 bars. NQ pooled has an interval that includes zero. |
| `sweeps_vs_closes` | **false** | +0.0744 (-0.0172, +0.1660) | +0.0579 | +0.0663 / +0.0805 | A sweep reverses more than a close through the level does. NQ pooled has an interval that includes zero. |
| `trend_start_sweep` | **false** | -0.1153 (-0.7443, +0.5930) | +0.0002 | -0.6250 / +0.2299 | A change of character that starts with a sweep follows through more. NQ pooled points the other way. |
| `trend_lines` | **false** | -0.0069 (-0.0241, +0.0100) | -0.0008 | -0.0190 / +0.0011 | Real trend lines hold more often than shifted lines. NQ pooled points the other way. |
| `fvg_hold` | **true** | +0.0343 (+0.0156, +0.0532) | +0.0224 | +0.0401 / +0.0303 | A fair value gap holds on its first return more often than a random band. NQ pooled points the claimed way with an interval excluding zero; ES agrees; both eras agree. |
| `fvg_fill` | **false** | -0.0122 (-0.0242, -0.0011) | -0.0135 | -0.0157 / -0.0099 | Price returns into a fair value gap within 50 bars more often than into a random band. NQ pooled points the other way. |
| `zones_first_vs_later` | **false** | -0.0035 (-0.0308, +0.0242) | -0.0032 | +0.0037 / -0.0083 | A supply/demand zone holds better on its first return than on later ones. NQ pooled points the other way. |
| `zones_vs_random` | **false** | +0.0006 (-0.0341, +0.0358) | -0.0186 | +0.0071 / -0.0036 | A supply/demand zone holds better than a random band on first return. NQ pooled has an interval that includes zero. |
| `pullback_depth` | **false** | +0.1770 (-0.4549, +0.7816) | +0.7006 | +1.0672 / -0.3725 | A break after a shallow pullback follows through more than after a deep one. NQ pooled has an interval that includes zero. |
| `engulfing_at_levels` | **false** | -0.0041 (-0.2570, +0.2656) | +0.2417 | +0.1686 / -0.1105 | An engulfing candle at a level moves more its way than the same candle at random. NQ pooled points the other way. |
| `rejection_at_levels` | **false** | -0.0067 (-0.1401, +0.1298) | +0.0093 | -0.1465 / +0.0610 | A rejection candle at a level moves more its way than the same candle at random. NQ pooled points the other way. |
