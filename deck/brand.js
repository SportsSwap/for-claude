// Visual system for the PLS Group FMAA 2026 submission.
// Palette is built from the asset itself: Pilbara iron-oxide red earth, spodumene
// pegmatite grey-green, and the deep navy of an institutional research document.
module.exports = {
  // core
  INK:    "10233A",   // deep navy - primary, dominates
  INK2:   "1C3A5E",   // lighter navy for panels
  PAPER:  "FFFFFF",
  MIST:   "EEF2F6",   // pale panel fill
  MIST2:  "F7F9FB",
  RULE:   "D3DCE5",
  // accents
  SPOD:   "0E7C6B",   // spodumene green - positive / the "shared value" colour
  SPOD_L: "D6EBE7",
  OCHRE:  "C2610A",   // Pilbara ochre - attention, caution
  OCHRE_L:"FBEBD9",
  CRIMSON:"A3282C",   // negative
  CRIM_L: "F7E2E2",
  GOLD:   "C99A2E",
  // text
  TXT:    "1B2733",
  MUTE:   "5F7183",
  FAINT:  "8C9BA9",
  WHITE:  "FFFFFF",
  // type
  H:      "Cambria",  // headline serif - safe list, renders true in QA
  B:      "Calibri",  // body sans - safe list
  // geometry (LAYOUT_WIDE = 13.333 x 7.5)
  W: 13.333, HGT: 7.5,
  M: 0.45,            // page margin
};
