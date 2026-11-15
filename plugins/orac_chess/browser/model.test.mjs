/** Browser replay contract tests. Author: Clive Bostock. Date: 14-Nov-2026.
 * Purpose: Verify legal snapshots, strict rejection and complete child line semantics.
 * Usage: node --test plugins/orac_chess/browser/model.test.mjs
 */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Chess} from '../vendor/chess.js-1.4.0/chess.mjs';
import {parsePgn,relationship} from './model.mjs';
const lion='1. e4 d6 2. d4 Nf6 3. Nc3 Nbd7 4. Nf3 e5 *';
const claw='1. e4 d6 2. d4 Nf6 3. Nc3 Nbd7 4. Nf3 e5 5. Bc4 Be7 6. O-O O-O 7. Re1 c6 *';
const fenPgn=(fen,line)=>`[SetUp "1"]\n[FEN "${fen}"]\n\n${line}`;
const examples=[lion,claw,'1. e4 {hello} e5 $1 2. Nf3!? Nc6 *',
 '1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 d5 5. exd5 Na5 6. Nxf7 *',
 '1. e4 a6 2. e5 d5 3. exd6 *',
 '1. f3 e5 2. g4 Qh4# 0-1'];
for(const [index,pgn] of examples.entries()) test(`Full six-field snapshots ${index}`,()=>{
 const parsed=parsePgn(pgn), replay=new Chess();
 assert.equal(parsed.positions.length,parsed.moves.length+1);
 for(const [i,move] of parsed.moves.entries()) {
  const legal=replay.move(move.san,{strict:true});assert.equal(move.uci,legal.from+legal.to+(legal.promotion||''));
  assert.equal(parsed.positions[i+1],replay.fen({forceEnpassantSquare:true}));assert.equal(parsed.positions[i+1].split(' ').length,6);
 }
});
for(const [fen,line,last] of [
 ['4k3/8/8/8/8/8/8/4K2R b K - 0 12','12... Kd7 *','Kd7'],
 ['4k3/P7/8/8/8/8/8/4K3 w - - 0 1','1. a8=N *','a8=N'],
 ['4k3/P7/8/8/8/8/8/4K3 w - - 0 1','1. a8=Q+ *','a8=Q+'],
 ['r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','1. O-O-O O-O *','O-O']]) test(`Custom FEN ${last}`,()=>{
 const model=parsePgn(fenPgn(fen,line),fen);assert.equal(model.initialFen,fen);assert.equal(model.moves.at(-1).san,last);
 const game=new Chess(fen);for(const move of model.moves)game.move(move.san,{strict:true});
 assert.equal(model.positions.at(-1),game.fen({forceEnpassantSquare:true}));
});
for(const value of ['', '   ','1. e5 *','1. e4','1. e4 * rubbish','1. e4 * 1. d4 *','1. e4 (1. d4) *','1. e4 {unclosed *','1. e4 *\n[Event "next"]'])test(`Reject ${JSON.stringify(value)}`,()=>assert.throws(()=>parsePgn(value)));
test('Alternative and continuation are independent complete PGNs',()=>{
 assert.equal(relationship(lion,claw,'CONTINUATION',8),null);
 assert.equal(relationship(lion,'1. e4 d6 2. d4 Nf6 3. Nc3 Nbd7 4. Nf3 c6 *','ALTERNATIVE',7),null);
 assert.ok(relationship(lion,claw,'CONTINUATION',7));
 assert.ok(relationship(lion,'1. d4 d5 *','ALTERNATIVE',1));
 assert.ok(relationship(lion,claw,'ALTERNATIVE',7));
 assert.ok(relationship(lion,claw,'UNKNOWN',8));
});
test('Tags remain data, never markup',()=>assert.equal(parsePgn('[Event "<img src=x onerror=alert(1)>"]\n1. e4 *').tags.Event,'<img src=x onerror=alert(1)>'));
