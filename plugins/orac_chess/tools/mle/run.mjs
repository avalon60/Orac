/** Execute the portable policy corpus and meaningful parser boundaries.
 * Author: Clive Bostock
 * Date: 06-Nov-2026
 * Purpose: Verify the isolated MLE adapter under Node before database testing.
 * Usage: node plugins/orac_chess/tools/mle/run.mjs [--help]
 */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {validate, branch, continuation, header} from './validator.mjs';
if (process.argv.includes('--help')) {
  console.log('Usage: node plugins/orac_chess/tools/mle/run.mjs');
  process.exit(0);
}
assert.equal(process.argv.length, 2, 'Unexpected argument');
const cases = JSON.parse(fs.readFileSync(new URL('./corpus.json', import.meta.url)));
for (const c of cases) {
  const error = c.op === 'continuation' ? continuation(c.parent,c.child,c.ply,c.fen) : c.op === 'branch' ? branch(c.parent,c.child,c.ply,c.fen) : validate(c.pgn,c.single,c.fen);
  assert.equal(error === null,c.valid,`${c.name}: ${error}`);
}
assert.equal(header('[Event "hello"] 1.e4 *','Event'),'hello');
assert.equal(header('1.e4 *','Missing'),null);
assert.throws(() => header('1.e4 * garbage','Event'));
const nested = depth => '1.e4 (' .repeat(depth) + '1.d4' + ')'.repeat(depth) + ' *';
assert.equal(validate(nested(64)),null);
assert.notEqual(validate(nested(65)),null);
const prefix = '1.e4 {';
const large = prefix + 'a'.repeat(4194304-prefix.length-3) + '} *';
assert.equal(large.length,4194304);
assert.equal(validate(large),null);
assert.notEqual(validate(large+' '),null);
assert.notEqual(validate(null),null);
assert.notEqual(branch('1.e4 *','1.d4 *',-1),null);
assert.notEqual(branch('1.e4 *','1.d4 *',0.5),null);
assert.equal(branch('1.e4 *','1.d4 *',0),null);
console.log(`${cases.length} portable corpus cases and boundary/header checks passed`);
