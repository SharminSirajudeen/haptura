// The mutant list is the concatenation of test/mutants/*.js, one file per area of the code. Each entry breaks one
// guarded line, names the test that must go red, and the assertion it must fail on.
'use strict';
const fs = require('fs'), path = require('path');
const dir = path.join(__dirname, 'mutants');
module.exports = [].concat(...fs.readdirSync(dir).filter(f => f.endsWith('.js')).sort().map(f => require(path.join(dir, f))));
