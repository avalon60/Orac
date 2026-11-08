/** Typed private Oracle CLOB boundary for authoritative Chess validation.
 * Author: Clive Bostock
 * Date: 06-Nov-2026
 * Purpose: Expose fixed validation operations without diagnostic JSON dispatch.
 * Usage: Private CHESS_MLE_* call specifications in the PURE Chess environment.
 */
import {validate, branch, header} from 'orac-chess-policy';

function text(input) {
  if (input === null) return null;
  if (input.length() > 4194304) return null;
  return input.getData();
}
export function validatePgn(input, single, fen) {
  return validate(text(input), single, fen);
}
export function validateBranch(parent, child, ply, fen) {
  return branch(text(parent), text(child), ply, fen);
}
export function pgnHeader(input, name) {
  return header(text(input), name);
}
