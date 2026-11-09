# Behavior test verdicts

Provenance: {'master_seed': 20220103, 'amendment': 0, 'locks': {'config/thresholds.json': '1668080849f616d0d27474d0927df3c23da355a9e6357c73aa9a26fd97e66f05', 'rulebook_spec.json': 'd33b0eea5948f28d57978984fdd307770eadf156a2fbe1b579407afeb2072078'}, 'written_utc': '2026-11-09T05:03:01+00:00'}

| test | verdict | NQ pooled (95% CI) | ES pooled | era 1 / era 2 | claim |
|---|---|---|---|---|---|
| `levels_vs_random` | **false** | -0.0012 (-0.0046, +0.0022) | -0.0028 | -0.0012 / -0.0013 | Real levels hold more often than random lines. NQ pooled points the other way. |
| `hold_by_touch_count` | **true** | +0.0189 (+0.0117, +0.0254) | +0.0113 | +0.0355 / +0.0082 | A level's 3rd+ touch holds more often than its 1st. NQ pooled points the claimed way with an interval excluding zero; ES agrees; both eras agree. |
| `wall_or_target` | **false** | +0.0021 (-0.0018, +0.0062) | +0.0016 | +0.0041 / +0.0008 | A level touched 3+ times acts as a wall (holds more than a random line touched as often), not a target. NQ pooled has an interval that includes zero. |
| `shrinking_bounces` | **true** | +0.0179 (+0.0034, +0.0322) | +0.0250 | +0.0055 / +0.0246 | After two shrinking bounces, the next touch breaks more often. NQ pooled points the claimed way with an interval excluding zero; ES agrees; both eras agree. |
| `line_vs_box` | **false** | +0.0017 (-0.0014, +0.0049) | +0.0015 | +0.0004 / +0.0024 | A level drawn as a box holds more often than one drawn as a line, beyond what the width alone gives. NQ pooled has an interval that includes zero. |
| `wick_vs_close_through` | **false** | +0.0427 (-0.0451, +0.1331) | +0.0134 | +0.0620 / +0.0305 | A wick through a level is followed by more move in the level's favour than a close through it. NQ pooled has an interval that includes zero. |
| `flip_zones` | **false** | +0.0008 (-0.0073, +0.0089) | -0.0004 | +0.0038 / -0.0011 | A broken level holds from the other side more often than a random line. NQ pooled has an interval that includes zero. |
| `bos_follow_10` | **false** | -0.0815 (-0.1700, +0.0043) | -0.0499 | -0.1433 / -0.0425 | A break of structure is followed by more move its way than random bars, at 10 bars. NQ pooled points the other way. |
| `bos_follow_20` | **false** | +0.0033 (-0.1472, +0.1450) | -0.0920 | -0.0607 / +0.0434 | The same at 20 bars. NQ pooled has an interval that includes zero. |
| `bos_follow_50` | **false** | -0.0944 (-0.3421, +0.1662) | -0.1400 | -0.1872 / -0.0358 | The same at 50 bars. NQ pooled points the other way. |
| `choch_follow_10` | **false** | -0.0111 (-0.0834, +0.0659) | +0.0359 | +0.0339 / -0.0409 | A change of character is followed by more move its way than random bars, at 10 bars. NQ pooled points the other way. |
| `choch_follow_20` | **false** | -0.0480 (-0.1574, +0.0630) | +0.0923 | -0.1271 / +0.0039 | The same at 20 bars. NQ pooled points the other way. |
| `choch_follow_50` | **false** | +0.0997 (-0.0782, +0.2661) | +0.1078 | +0.1454 / +0.0686 | The same at 50 bars. NQ pooled has an interval that includes zero. |
| `sweeps_vs_closes` | **false** | +0.0277 (-0.0239, +0.0784) | +0.0129 | +0.0512 / +0.0135 | A sweep reverses more than a close through the level does. NQ pooled has an interval that includes zero. |
| `trend_start_sweep` | **false** | +0.1926 (-0.1490, +0.5381) | +0.1651 | +0.4963 / -0.0020 | A change of character that starts with a sweep follows through more. NQ pooled has an interval that includes zero. |
| `trend_lines` | **false** | -0.0036 (-0.0085, +0.0013) | -0.0125 | -0.0080 / -0.0008 | Real trend lines hold more often than shifted lines. NQ pooled points the other way. |
| `fvg_hold` | **false** | -0.0118 (-0.0212, -0.0016) | -0.0095 | -0.0020 / -0.0182 | A fair value gap holds on its first return more often than a random band. NQ pooled points the other way. |
| `fvg_fill` | **false** | -0.0012 (-0.0070, +0.0044) | +0.0003 | +0.0020 / -0.0033 | Price returns into a fair value gap within 50 bars more often than into a random band. NQ pooled points the other way. |
| `zones_first_vs_later` | **false** | -0.0038 (-0.0180, +0.0098) | +0.0172 | +0.0009 / -0.0066 | A supply/demand zone holds better on its first return than on later ones. NQ pooled points the other way. |
| `zones_vs_random` | **false** | -0.0061 (-0.0225, +0.0101) | +0.0133 | +0.0058 / -0.0134 | A supply/demand zone holds better than a random band on first return. NQ pooled points the other way. |
| `pullback_depth` | **false** | -0.2688 (-0.6472, +0.0868) | -0.1695 | +0.1442 / -0.5419 | A break after a shallow pullback follows through more than after a deep one. NQ pooled points the other way. |
| `engulfing_at_levels` | **false** | +0.0176 (-0.2241, +0.2645) | +0.1795 | +0.3385 / -0.1667 | An engulfing candle at a level moves more its way than the same candle at random. NQ pooled has an interval that includes zero. |
| `rejection_at_levels` | **false** | -0.0068 (-0.0929, +0.0827) | -0.0047 | -0.0201 / +0.0000 | A rejection candle at a level moves more its way than the same candle at random. NQ pooled points the other way. |
