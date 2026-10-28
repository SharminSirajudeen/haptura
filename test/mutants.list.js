// The mutant list is the concatenation of test/mutants/*.js, one file per lane (§6 of the plan: one lane, one set of
// files). Each entry breaks one guarded line; see the kit's format in docs/project-kit/test/mutants.list.js.
'use strict';
const fs = require('fs'), path = require('path');
const dir = path.join(__dirname, 'mutants');
module.exports = [].concat(...fs.readdirSync(dir).filter(f => f.endsWith('.js')).sort().map(f => require(path.join(dir, f))));
