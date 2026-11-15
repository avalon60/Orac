/** Adapter late-response tests. Author: Clive Bostock. Date: 14-Nov-2026.
 * Purpose: Exercise real adapter control flow with isolated DOM, viewer and AJAX boundaries.
 * Usage: node plugins/orac_chess/browser/apex.test.mjs
 */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
class Node {
 constructor(tag){this.tagName=tag;this.children=[];this.events={};this.dataset={};this.isConnected=true;}
 append(...values){this.children.push(...values);}
 prepend(...values){this.children.unshift(...values);}
 replaceChildren(...values){this.children=values;}
 setAttribute(name,value){(this.attributes ??= {})[name]=value;}
 addEventListener(name,fn){this.events[name]=fn;}
 get options(){return this.children.flatMap(value=>value.tagName==='option'?[value]:value.options||[]);}
}
const viewers=[];
globalThis.TestViewer=class {
 constructor(){this.loaded=[];this.destroyed=false;viewers.push(this);}
 clear(){}
 loadPgn(pgn,fen){this.loaded.push(pgn);(this.fens ??= []).push(fen);return true;}
 goToMove(){}
 destroy(){this.destroyed=true;}
};
globalThis.document={createElement:tag=>new Node(tag)};
const descendants=node=>node.children.flatMap(child=>[child,...descendants(child)]);
const byTag=(root,tag)=>descendants(root).filter(node=>node.tagName===tag);
const lineSelect=root=>descendants(root).find(node=>node.attributes?.['aria-label']==='Variation line');
const status=root=>descendants(root).find(node=>node.attributes?.role==='status');
const button=(root,text)=>byTag(root,'button').find(node=>node.textContent===text);
const values={};
const pending=[];
globalThis.apex={item:name=>({getValue:()=>values[name]}),server:{process(name,args,callbacks){const request={args,callbacks,aborted:false,always(){},abort(){this.aborted=true;}};pending.push(request);return request;}}};
// Substitute only the renderer import, leaving the adapter implementation intact.
let source=readFileSync(new URL('./apex.mjs',import.meta.url),'utf8');
source=source.replace("import {PgnViewer} from './viewer.mjs';",'const PgnViewer=globalThis.TestViewer;')
 .replace("'./model.mjs'",JSON.stringify(new URL('./model.mjs',import.meta.url).href));
const {mount,destroyDetached}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const settle=async()=>{await Promise.resolve();await Promise.resolve();await Promise.resolve();};
test('Late selected-line replies cannot replace a newer choice; disposal aborts and ignores pending work',async()=>{
 const container=new Node('div');container.dataset.page='11';const handle=mount(container);
 pending[0].callbacks.success({lines:[{id:1,name:'First'},{id:2,name:'Second'}],more:false});await settle();
 const select=lineSelect(container),viewer=viewers[0];
 assert.equal(pending[1].args.x02,1);
 select.value='2';select.events.change();assert.equal(pending[2].args.x02,'2');
 pending[2].callbacks.success({id:2,name:'Second',rootId:2,pgn:'1. d4 *'});await settle();
 pending[1].callbacks.success({id:1,name:'First',rootId:1,pgn:'1. e4 *'});await settle();
 assert.deepEqual(viewer.loaded,['1. d4 *']);
 select.value='1';select.events.change();const late=pending.at(-1);
 handle.destroy();handle.destroy();assert.equal(late.aborted,true);assert.equal(viewer.destroyed,true);
 late.callbacks.success({id:1,name:'First',rootId:1,pgn:'1. e4 *'});await settle();
 assert.deepEqual(viewer.loaded,['1. d4 *']);assert.equal(container.children.length,0);
});
test('Removed dialog containers dispose their viewer',()=>{
 const container=new Node('div');container.dataset.page='11';mount(container);
 container.isConnected=false;destroyDetached();assert.equal(viewers.at(-1).destroyed,true);
});

test('Variation preview reads unsaved editor values without explorer actions or save requests',async()=>{
 Object.assign(values,{P31_PGN:'1. e4 *',P31_STARTING_FEN:'first fen',P31_PARENT_VARIATION_ID:''});
 const start=pending.length,container=new Node('div');container.dataset.page='31';const handle=mount(container),viewer=viewers.at(-1);
 await settle();
 assert.equal(byTag(container,'select').length,0);
 assert.deepEqual(byTag(container,'button').map(node=>node.textContent),['Update preview']);
 assert.deepEqual(viewer.loaded,['1. e4 *']);assert.deepEqual(viewer.fens,['first fen']);
 values.P31_PGN='1. d4 *';values.P31_STARTING_FEN='changed fen';
 await button(container,'Update preview').events.click();
 assert.deepEqual(viewer.loaded,['1. e4 *','1. d4 *']);assert.deepEqual(viewer.fens,['first fen','changed fen']);
 assert.equal(pending.length,start);handle.destroy();
});
test('Variation parent FEN respects newer previews and disposal',async()=>{
 Object.assign(values,{P31_PGN:'1. e4 *',P31_STARTING_FEN:'ignored',P31_PARENT_VARIATION_ID:'8'});
 const container=new Node('div');container.dataset.page='31';const handle=mount(container),viewer=viewers.at(-1),old=pending.at(-1);
 assert.equal(old.args.x01,'PARENT');assert.equal(old.args.x02,'8');
 values.P31_PGN='1. d4 *';button(container,'Update preview').events.click();const current=pending.at(-1);
 current.callbacks.success({startingFen:'parent root fen'});await settle();
 old.callbacks.success({startingFen:'stale fen'});await settle();
 assert.deepEqual(viewer.loaded,['1. d4 *']);assert.deepEqual(viewer.fens,['parent root fen']);
 button(container,'Update preview').events.click();const late=pending.at(-1);handle.destroy();
 assert.equal(late.aborted,true);late.callbacks.success({startingFen:'disposed fen'});await settle();
 assert.deepEqual(viewer.loaded,['1. d4 *']);
});
test('Explorer pages group principal and children and validate complete selected child lines',async()=>{
 for(const page of ['11','21','22']) {
  const container=new Node('div');container.dataset.page=page;const handle=mount(container),viewer=viewers.at(-1);
  assert.equal(pending.at(-1).args.x01,'LIST');
  pending.at(-1).callbacks.success({lines:[{id:1,name:'Root'},{id:2,name:'Child',parentId:1,parentName:'Root',kind:'ALTERNATIVE',branchPly:1}],more:false});await settle();
  const select=lineSelect(container);
  assert.deepEqual(byTag(select,'optgroup').map(node=>node.label),['Principal lines','Children of Root']);
  assert.deepEqual(select.options.map(node=>node.value),[1,2]);
  pending.at(-1).callbacks.success({id:1,name:'Root',rootId:1,pgn:'1. e4 e5 *'});await settle();
  select.value='2';select.events.change();
  pending.at(-1).callbacks.success({id:2,name:'Child',parentId:1,rootId:1,kind:'ALTERNATIVE',branchPly:1,pgn:'1. e4 c5 *'});await settle();
  assert.equal(pending.at(-1).args.x02,1);
  pending.at(-1).callbacks.success({id:1,pgn:'1. e4 e5 *'});await settle();
  assert.deepEqual(viewer.loaded,['1. e4 e5 *','1. e4 c5 *']);
  select.events.change();pending.at(-1).callbacks.success({id:2,name:'Invalid',parentId:1,rootId:1,kind:'ALTERNATIVE',branchPly:1,pgn:'1. d4 d5 *'});await settle();
  pending.at(-1).callbacks.success({id:1,pgn:'1. e4 e5 *'});await settle();
  assert.equal(viewer.loaded.length,2);
  assert.match(status(container).textContent,/inconsistent with its parent/);
  handle.destroy();
 }
});
