/** Legal, complete linear PGN replay for browser viewers.
 * Author: Clive Bostock
 * Date: 14-Nov-2026
 * Purpose: Build immutable move and six-field FEN snapshots without server execution.
 * Usage: import {parsePgn, relationship} from './model.mjs'.
 */
import {Chess} from '../vendor/chess.js-1.4.0/chess.mjs';
import {parse, branch, continuation} from '../tools/mle/validator.mjs';

/** Parse a complete PGN under the same strict policy as catalogue writers. */
export function parsePgn(pgn, startingFen = null) {
    const parsed = parse(pgn, 1, startingFen || null);
    const chess = new Chess(parsed.positions[0]);
    const moves = parsed.moves.map((uci, index) => {
        const before = chess.fen({forceEnpassantSquare: true});
        const move = chess.move({from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4]});
        return Object.freeze({ply: index + 1, san: move.san, uci, from: move.from, to: move.to,
            color: move.color, number: Number(before.split(' ')[5]), fen: parsed.positions[index + 1]});
    });
    return Object.freeze({tags: Object.freeze(parsed.tags), result: parsed.result,
        initialFen: parsed.positions[0], positions: Object.freeze(parsed.positions), moves: Object.freeze(moves)});
}

/** Return a safe error for a contradictory child relationship, otherwise null. */
export function relationship(parent, child, kind, ply, startingFen = null) {
    if (kind === 'ALTERNATIVE') return branch(parent, child, ply, startingFen || null);
    if (kind === 'CONTINUATION') return continuation(parent, child, ply, startingFen || null);
    return 'Unknown variation relationship';
}
