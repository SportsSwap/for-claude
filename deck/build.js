const pptxgen = require('pptxgenjs');
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.author = 'FMAA Asset Management - Shared Value Coverage Team';
pres.company = 'FMAA x Shared Value Project 2026';
pres.title = 'PLS Group Limited (ASX:PLS) - Investing for the Future 2026';
const ctx = { p: 0 };
const parts = process.argv.slice(2);
parts.forEach((f) => require('./' + f)(pres, ctx));
const out = process.env.OUT || '/home/user/for-claude/deck/PLS_Group_FMAA_2026.pptx';
pres.writeFile({ fileName: out }).then(() => {
  console.log('wrote ' + out + '  |  content slides counted: ' + ctx.p + '  |  total slides: ' + pres.slides.length);
});
