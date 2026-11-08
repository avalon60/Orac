/** Oracle CLOB boundary for the private diagnostic module.
 * Author: Clive Bostock
 * Date: 06-Nov-2026
 * Purpose: Exercise genuine CLOB input/output in a PURE MLE environment.
 * Usage: Called only by ORAC_CHESS.CHESS_MLE_PROOF_RUN diagnostic call spec.
 */
import {validate, branch, header} from 'orac-chess-policy';
import {OracleClob} from 'mle-js-plsqltypes';
export function run(input) {
  if (input === null || input.length() > 16777216) throw new Error('Invalid diagnostic request CLOB');
  const request = JSON.parse(input.getData());
  const results = request.cases.map(c => {
    if (c.depth !== undefined) c.pgn = '1.e4 ('.repeat(c.depth) + '1.d4' + ')'.repeat(c.depth) + ' *';
    if (c.size !== undefined) c.pgn = '1.e4 {' + 'a'.repeat(c.size - 9) + '} *';
    const error = c.op === 'branch' ? branch(c.parent,c.child,c.ply,c.fen) : validate(c.pgn,c.single,c.fen);
    return {name:c.name, valid:error === null, error};
  });
  const output = OracleClob.createTemporary(false);
  try {
    output.open(OracleClob.LOB_READWRITE);
    output.write(1, JSON.stringify({results, echo:request.echo ?? null, header:header('[Event "proof"] 1.e4 *','Event')}));
    output.close();
    return output;
  } catch(error) {
    if (output.isOpen()) output.close();
    output.freeTemporary();
    throw error;
  }
}
