/** Viewer lifecycle and navigation tests. Author: Clive Bostock. Date: 14-Nov-2026.
 * Purpose: Test bounded independent state and disposal with a renderer/DOM boundary stub.
 * Usage: node plugins/orac_chess/browser/viewer.test.mjs
 */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {PgnViewer} from './viewer.mjs';
import {parsePgn} from './model.mjs';
function viewer() {
 const value=Object.create(PgnViewer.prototype), calls=[];
 Object.assign(value,{game:parsePgn('1. e4 e5 2. Nf3 Nc6 *'),ply:0,orientation:'w',destroyed:false,
  buttons:Object.fromEntries(['first','previous','next','last','flip','reset'].map(key=>[key,{}])),
  status:{textContent:''}, moves:{children:[],replaceChildren(){}},boardHost:{replaceChildren(){}},
  root:{removeEventListener(){calls.push('unlisten');},remove(){calls.push('remove');}},
  board:{setPosition(fen){calls.push(fen);},setOrientation(color){calls.push(color);},removeMarkers(){},addMarker(){},destroy(){calls.push('destroy');}}});
 return {value,calls};
}
test('Navigation is bounded, direct, reversible and instance-local',async()=>{
 const {value:a,calls}=viewer(), {value:b}=viewer();
 a.previous();assert.equal(a.ply,0);a.last();assert.equal(a.ply,4);a.next();assert.equal(a.ply,4);
 assert.equal(a.buttons.next.disabled,true);assert.equal(a.buttons.previous.disabled,false);
 a.goToMove(2);assert.equal(a.ply,2);await a.renderTask;assert.ok(calls.includes(a.game.positions[2]));
 a.goToMove(-99);assert.equal(a.ply,0);a.goToMove(999);assert.equal(a.ply,4);
 a.goToMove(NaN);assert.equal(a.ply,4);assert.equal(b.ply,0);
 a.flip();assert.equal(a.orientation,'b');assert.equal(b.orientation,'w');
 a.reset();assert.equal(a.orientation,'w');assert.equal(a.ply,0);
});
test('Failure clears previous board and all navigation; destroy is idempotent',async()=>{
 const {value,calls}=viewer();value.last();
 assert.equal(value.loadPgn('1. e5 *'),false);assert.equal(value.game,null);assert.equal(value.board,null);
 assert.equal(value.ply,0);assert.ok(value.status.textContent.includes('cannot be displayed'));
 assert.ok(Object.values(value.buttons).every(button=>button.disabled));
 assert.equal(value.loadPgn(''),false);assert.equal(value.status.textContent,'No PGN available.');
 value.destroy();value.destroy();await value.renderTask;assert.equal(calls.filter(x=>x==='destroy').length,1);
 assert.equal(calls.filter(x=>x==='remove').length,1);assert.equal(value.loadPgn('1. e4 *'),false);
});
test('Renderer operations serialize and disposal waits for an in-flight position',async()=>{
 const {value,calls}=viewer();let release,started;
 const began=new Promise(resolve=>{started=resolve;});
 value.board.setPosition=()=>{calls.push('position-start');started();return new Promise(resolve=>{release=()=>{calls.push('position-end');resolve();};});};
 value.board.setOrientation=()=>{calls.push('orientation');};
 value.next();await began;
 value.flip();value.clear();
 assert.equal(calls.includes('destroy'),false);
 release();await value.renderTask;
 assert.ok(calls.indexOf('destroy')>calls.indexOf('position-end'));
 assert.equal(calls.includes('orientation'),false);
});
