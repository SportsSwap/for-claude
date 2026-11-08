# Behavior test verdicts

Provenance: {'master_seed': 20220103, 'amendment': 0, 'locks': {'config/thresholds.json': '1668080849f616d0d27474d0927df3c23da355a9e6357c73aa9a26fd97e66f05', 'rulebook_spec.json': 'd33b0eea5948f28d57978984fdd307770eadf156a2fbe1b579407afeb2072078'}, 'written_utc': '2026-11-08T10:58:06+00:00'}

| test | verdict | NQ pooled (95% CI) | ES pooled | era 1 / era 2 | claim |
|---|---|---|---|---|---|
| `levels_vs_random` | **false** | +0.0012 (-0.0016, +0.0043) | +0.0011 | +0.0023 / +0.0004 | Real levels hold more often than random lines. NQ pooled has an interval that includes zero. |
| `hold_by_touch_count` | **false** | +0.0004 (-0.0057, +0.0066) | +0.0040 | +0.0014 / -0.0005 | A level's 3rd+ touch holds more often than its 1st. NQ pooled has an interval that includes zero. |
| `wall_or_target` | **false** | -0.0007 (-0.0040, +0.0024) | -0.0001 | +0.0026 / -0.0031 | A level touched 3+ times acts as a wall (holds more than a random line touched as often), not a target. NQ pooled points the other way. |
| `shrinking_bounces` | **false** | -0.0069 (-0.0175, +0.0039) | -0.0036 | -0.0084 / -0.0060 | After two shrinking bounces, the next touch breaks more often. NQ pooled points the other way. |
| `line_vs_box` | **false** | +0.0026 (-0.0002, +0.0053) | -0.0028 | +0.0067 / +0.0000 | A level drawn as a box holds more often than one drawn as a line, beyond what the width alone gives. NQ pooled has an interval that includes zero. |
| `wick_vs_close_through` | **false** | +0.0269 (-0.0030, +0.0574) | +0.0071 | +0.0305 / +0.0240 | A wick through a level is followed by more move in the level's favour than a close through it. NQ pooled has an interval that includes zero. |
| `flip_zones` | **false** | +0.0023 (-0.0056, +0.0102) | -0.0014 | -0.0058 / +0.0074 | A broken level holds from the other side more often than a random line. NQ pooled has an interval that includes zero. |
| `bos_follow_10` | **false** | +0.0000 (-0.0544, +0.0562) | -0.0146 | -0.0265 / +0.0172 | A break of structure is followed by more move its way than random bars, at 10 bars. NQ pooled has an interval that includes zero. |
| `bos_follow_20` | **false** | +0.0132 (-0.0719, +0.0957) | -0.0069 | -0.0166 / +0.0327 | The same at 20 bars. NQ pooled has an interval that includes zero. |
| `bos_follow_50` | **false** | +0.0472 (-0.0920, +0.1894) | -0.0535 | +0.0403 / +0.0520 | The same at 50 bars. NQ pooled has an interval that includes zero. |
| `choch_follow_10` | **false** | +0.0352 (-0.0139, +0.0826) | +0.0407 | +0.0671 / +0.0143 | A change of character is followed by more move its way than random bars, at 10 bars. NQ pooled has an interval that includes zero. |
| `choch_follow_20` | **false** | +0.0228 (-0.0437, +0.0884) | -0.0120 | +0.0334 / +0.0158 | The same at 20 bars. NQ pooled has an interval that includes zero. |
| `choch_follow_50` | **false** | +0.0260 (-0.0685, +0.1242) | -0.0482 | +0.0234 / +0.0275 | The same at 50 bars. NQ pooled has an interval that includes zero. |
| `sweeps_vs_closes` | **false** | +0.0087 (-0.0111, +0.0286) | +0.0080 | +0.0053 / +0.0106 | A sweep reverses more than a close through the level does. NQ pooled has an interval that includes zero. |
| `trend_start_sweep` | **false** | -0.1005 (-0.4062, +0.1957) | -0.0561 | -0.0023 / -0.1676 | A change of character that starts with a sweep follows through more. NQ pooled points the other way. |
| `trend_lines` | **false** | +0.0006 (-0.0043, +0.0059) | -0.0008 | -0.0020 / +0.0021 | Real trend lines hold more often than shifted lines. NQ pooled has an interval that includes zero. |
| `fvg_hold` | **false** | -0.0044 (-0.0152, +0.0062) | -0.0022 | -0.0180 / +0.0050 | A fair value gap holds on its first return more often than a random band. NQ pooled points the other way. |
| `fvg_fill` | **false** | -0.0006 (-0.0063, +0.0053) | -0.0039 | -0.0005 / -0.0006 | Price returns into a fair value gap within 50 bars more often than into a random band. NQ pooled points the other way. |
| `zones_first_vs_later` | **false** | -0.0066 (-0.0216, +0.0087) | -0.0005 | -0.0006 / -0.0111 | A supply/demand zone holds better on its first return than on later ones. NQ pooled points the other way. |
| `zones_vs_random` | **false** | +0.0007 (-0.0189, +0.0201) | +0.0068 | -0.0034 / +0.0036 | A supply/demand zone holds better than a random band on first return. NQ pooled has an interval that includes zero. |
| `pullback_depth` | **false** | +0.0064 (-0.2119, +0.2192) | +0.0928 | +0.0550 / -0.0235 | A break after a shallow pullback follows through more than after a deep one. NQ pooled has an interval that includes zero. |
| `engulfing_at_levels` | **split** | +0.0822 (+0.0252, +0.1391) | -0.0073 | +0.0654 / +0.0927 | An engulfing candle at a level moves more its way than the same candle at random. NQ pooled holds, but ES has the opposite sign. |
| `rejection_at_levels` | **true** | +0.0411 (+0.0126, +0.0705) | +0.0040 | +0.0285 / +0.0490 | A rejection candle at a level moves more its way than the same candle at random. NQ pooled points the claimed way with an interval excluding zero; ES agrees; both eras agree. |
