/** Strict PGN policy adapter for the isolated MLE feasibility proof.
 * Author: Clive Bostock
 * Date: 06-Nov-2026
 * Purpose: Replay every PGN branch using pinned chess.js legal moves.
 * Usage: Imported by the diagnostic corpus runner; no public writer integration.
 */
import { Chess, DEFAULT_POSITION } from '../../vendor/chess.js-1.4.0/chess.mjs';

const need = (ok, message) => { if (!ok) throw new Error(message); };
const TAG = /^\[([A-Za-z][A-Za-z0-9_]*)\s+"((?:[^"\\\r\n]|\\["\\])*)"\s*\]/;
const TOKEN = /^(?:1\/2-1\/2|1-0|0-1|\*|[0-9]+\.(?:\.\.)?|\$[0-9]+|[!?]{1,2}|(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)[+#]?[!?]{0,2})/;

function position(fen) {
  need(typeof fen === 'string' && /^[prnbqkPRNBQK1-8]+(?:\/[prnbqkPRNBQK1-8]+){7} [wb] (?:-|K?Q?k?q?) (?:-|[a-h][36]) [0-9]+ [1-9][0-9]*$/.test(fen), 'Invalid FEN syntax');
  const [pieces, turn, rights, ep, half] = fen.split(' ');
  const ranks = pieces.split('/');
  for (const rank of ranks) {
    need(!/[1-8][1-8]/.test(rank), 'Noncanonical FEN empty squares');
    need([...rank].reduce((n, c) => n + (/[1-8]/.test(c) ? Number(c) : 1), 0) === 8, 'Invalid FEN rank width');
  }
  for (const p of ['P', 'p']) need([...pieces].filter(c => c === p).length <= 8, 'Too many FEN pawns');
  for (const pattern of [/[A-Z]/g, /[a-z]/g]) need((pieces.match(pattern) || []).length <= 16, 'Too many FEN pieces');
  const board = new Chess(fen);
  const previous = turn === 'w' ? 'b' : 'w';
  const king = board.board().flat().find(p => p?.type === 'k' && p.color === previous);
  need(king && !board.isAttacked(king.square, turn), 'FEN leaves previous side in check');
  const has = (square, type, color) => board.get(square)?.type === type && board.get(square)?.color === color;
  for (const [right, kingSquare, rookSquare, color] of [['K','e1','h1','w'],['Q','e1','a1','w'],['k','e8','h8','b'],['q','e8','a8','b']]) {
    if (rights.includes(right)) need(has(kingSquare,'k',color) && has(rookSquare,'r',color), 'Invalid castling right');
  }
  if (ep !== '-') {
    const white = turn === 'w';
    need(ep[1] === (white ? '6' : '3') && half === '0', 'Invalid en passant state');
    need(has(ep[0] + (white ? '5' : '4'), 'p', previous), 'Missing en passant pawn');
    need(!board.get(ep) && !board.get(ep[0] + (white ? '7' : '2')), 'Invalid en passant origin or target');
  }
  return board;
}

/** Parse complete input and replay all recursive annotation variations. */
export function parse(text, single = 0, expectedFen = null) {
  need(typeof text === 'string' && text.length > 0 && text.length <= 4194304, 'PGN must contain 1 to 4194304 characters');
  let at = 0;
  const tags = Object.create(null);
  function space() {
    while (at < text.length) {
      if (/\s/.test(text[at])) { at++; continue; }
      if (text[at] === ';') { while (at < text.length && !/[\r\n]/.test(text[at])) at++; continue; }
      if (text[at] === '{') {
        const end = text.indexOf('}', at + 1), nested = text.indexOf('{', at + 1);
        need(end >= 0 && (nested < 0 || nested > end), 'Unclosed or nested PGN comment');
        at = end + 1; continue;
      }
      break;
    }
  }
  function token() {
    space();
    if (at === text.length) return null;
    if ('()'.includes(text[at])) return text[at++];
    const match = text.slice(at).match(TOKEN);
    need(match, 'Invalid PGN token at character ' + (at + 1));
    const value = match[0]; at += value.length;
    need(at === text.length || /\s/.test(text[at]) || '{}();$!?'.includes(text[at]) || value.endsWith('.'), 'Missing PGN token separator');
    return value;
  }
  function line(fen, depth) {
    need(depth <= 64, 'PGN RAV nesting exceeds 64');
    const board = position(fen), moves = [], positions = [board.fen({forceEnpassantSquare: true})];
    let previous = null, result = null, numberPending = false;
    while (true) {
      const t = token();
      if (t === null || t === ')') {
        need(!numberPending && (depth > 0 ? t !== null : t === null), 'Unbalanced PGN variation or incomplete number');
        if (depth === 0) need(result !== null, 'Complete PGN requires a terminal result');
        break;
      }
      if (t === '(') {
        need(result === null && single !== 1 && previous !== null && !numberPending, 'Invalid RAV');
        line(previous, depth + 1); continue;
      }
      need(result === null, 'Tokens after PGN result');
      if (/^[0-9]+\./.test(t)) {
        need(!numberPending && t === board.fen().split(' ')[5] + (board.turn() === 'w' ? '.' : '...'), 'Move number conflicts with position');
        numberPending = true; continue;
      }
      if (t.startsWith('$') || /^[!?]+$/.test(t)) { need(previous !== null && !numberPending, 'Annotation without move'); continue; }
      if (['*','1-0','0-1','1/2-1/2'].includes(t)) { need(!numberPending, 'Result after incomplete number'); result = t; continue; }
      const san = t.replace(/[!?]+$/, '');
      const before = board.fen({forceEnpassantSquare: true});
      const move = board.move(san, {strict: true});
      need(move && move.san === san, 'Invalid or ambiguous SAN: ' + san);
      previous = before; numberPending = false;
      moves.push(move.from + move.to + (move.promotion || ''));
      positions.push(board.fen({forceEnpassantSquare: true}));
    }
    need(moves.length > 0, 'PGN line has no moves');
    return {moves, positions, result};
  }
  space();
  while (text[at] === '[') {
    const match = text.slice(at).match(TAG);
    need(match && !Object.hasOwn(tags, match[1]), 'Invalid or duplicate PGN header');
    tags[match[1]] = match[2].replace(/\\(["\\])/g, '$1'); at += match[0].length; space();
  }
  const fen = tags.FEN;
  need((fen === undefined && tags.SetUp === undefined) || (fen !== undefined && tags.SetUp === '1'), 'FEN and SetUp 1 must occur together');
  if (expectedFen !== null) { position(expectedFen); need(expectedFen === fen, 'PGN FEN differs from root'); }
  else need(fen === undefined || single !== 1, 'Variation FEN must match root');
  const parsed = line(fen ?? DEFAULT_POSITION, 0);
  need(tags.Result === undefined || tags.Result === parsed.result, 'Result header differs from movetext');
  return {...parsed, tags};
}

/** Return null for valid PGN, otherwise a bounded error; exceptions fail closed. */
export function validate(text, single = 0, fen = null) {
  try { parse(text, single, fen); return null; } catch (error) { return String(error?.message || 'Invalid PGN/FEN').slice(0,700); }
}

/** Validate the exact common prefix and divergent next half-move. */
export function branch(parent, child, ply, fen = null) {
  try {
    const p = parse(parent,1,fen), c = parse(child,1,fen);
    need(Number.isInteger(ply) && ply >= 0 && ply < p.moves.length && ply < c.moves.length, 'Branch must diverge before parent ends');
    need(p.moves.slice(0,ply).join(',') === c.moves.slice(0,ply).join(',') && p.positions[ply] === c.positions[ply], 'Branch prefix differs');
    need(p.moves[ply] !== c.moves[ply], 'Branch must differ on next half-move'); return null;
  } catch (error) { return String(error?.message || 'Invalid PGN/FEN').slice(0,700); }
}

/** Validate an exact complete-parent prefix followed by at least one legal move. */
export function continuation(parent, child, ply, fen = null) {
  try {
    const p = parse(parent,1,fen), c = parse(child,1,fen);
    need(Number.isInteger(ply) && ply === p.moves.length, 'Continuation ply must equal parent length');
    need(c.moves.length > p.moves.length, 'Continuation must extend the complete parent');
    need(p.moves.join(',') === c.moves.slice(0,ply).join(',') &&
      p.positions.every((position,index) => position === c.positions[index]), 'Continuation prefix differs');
    return null;
  } catch (error) { return String(error?.message || 'Invalid PGN/FEN').slice(0,700); }
}

/** Extract a header only after full validation, matching the Java policy. */
export function header(text, name) { return parse(text).tags[name] ?? null; }
