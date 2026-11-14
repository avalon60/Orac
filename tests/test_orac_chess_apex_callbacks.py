"""Protect Query Chess HTML controls and callback behaviour in both APEX exports."""
# Author: Clive Bostock
# Date: 12-Nov-2026
# Description: Check query rendering, on-demand callbacks and safe client behaviour.

import os
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('relative', ['orac_chess_admin.sql',
                                     'recovery/orac_chess_admin_readonly.sql'])
def test_query_callbacks_use_importable_on_demand_point(relative: str) -> None:
    """The two JavaScript-invoked query processes import as on-demand callbacks."""
    export = (ROOT / 'plugins/orac_chess/apex' / relative).read_text()
    processes = re.findall(r'wwv_flow_imp_page\.create_page_process\((.*?)\n\);',
                           export, re.S)
    for name in ('CHESS_QUERY_SUBMIT', 'CHESS_QUERY_READ'):
        matches = [body for body in processes if f"p_process_name=>'{name}'" in body]
        assert len(matches) == 1
        assert "p_process_point=>'ON_DEMAND'" in matches[0]
        assert "p_process_type=>'NATIVE_PLSQL'" in matches[0]
        assert f'apex.server.process("{name}"' in export
        assert "apex_authorization.is_authorized(''Administration Rights'')" in matches[0]
    assert "p_process_point=>'AJAX_CALLBACK'" not in export


@pytest.mark.parametrize('relative', ['orac_chess_admin.sql',
                                     'recovery/orac_chess_admin_readonly.sql'])
def test_query_region_renders_interactive_html(relative: str) -> None:
    """The static region must render the accessible query controls as HTML."""
    export = (ROOT / 'plugins/orac_chess/apex' / relative).read_text(encoding='utf-8')
    page = export.split('prompt --application/pages/page_00120', 1)[1]
    assert "p_name=>'P120_QUESTION'" in page
    assert "p_display_as=>'NATIVE_TEXTAREA'" in page
    assert "p_prompt=>'Your question'" in page
    assert "p_cMaxlength=>2048" in page
    assert "p_button_action=>'DEFINED_BY_DA'" in page
    assert "p_button_image_alt=>'Ask Chess'" in page
    assert "p_button_static_id=>'chess-query-submit'" in page
    assert 'role="status" aria-live="polite" aria-atomic="true"' in page
    assert 'aria-busy="false"' in page
    assert 'width:max-content;min-width:100%' in page
    assert 'min-width:8rem;max-width:32rem' in page
    assert '<textarea' not in page


@pytest.mark.parametrize('relative', ['orac_chess_admin.sql',
                                     'recovery/orac_chess_admin_readonly.sql'])
def test_query_page_submit_poll_render_and_recovery(relative: str) -> None:
    """Execute exported JavaScript to verify query outcomes and safe text rendering."""
    export = (ROOT / 'plugins/orac_chess/apex' / relative).read_text(encoding='utf-8')
    page = export.split('prompt --application/pages/page_00120', 1)[1]
    onload = page.split('p_javascript_code_onload=>wwv_flow_string.join(wwv_flow_t_varchar2(', 1)[1].split("\n);", 1)[0]
    source = '\n'.join(re.findall(r"^'((?:[^']|'')*)'[,)]*$", onload, re.M)).replace("''", "'")
    program = r'''
import assert from 'node:assert/strict';
import vm from 'node:vm';
// Author: Clive Bostock
// Date: 12-Nov-2026
// Purpose: Exercise exported Query Chess code with deterministic browser boundaries.
// Usage: Invoked by pytest through Node's module evaluator.
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.disabled = false; this.value = ''; this.text = ''; this.attributes = {}; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  set innerHTML(value) { throw new Error('Result data must never become HTML'); }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; this.text = ''; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, callback) { assert.equal(name, 'click'); this.click = callback; }
}
function setup(questionText = 'Which <opening>?') {
  const question = new Element('textarea'), button = new Element('button'), output = new Element('div'), status = new Element('p');
  const elements = {'chess-query-submit':button, 'chess-query-output':output, 'chess-query-status':status};
  const calls = [], timers = [], delays = []; let focused = false;
  vm.runInNewContext(process.env.CHESS_QUERY_SOURCE, {
    document:{getElementById:id => elements[id], createElement:tag => new Element(tag)},
    apex:{item:name => { assert.equal(name, 'P120_QUESTION'); return {getValue:() => question.value, setFocus:() => { focused = true; }}; }, server:{process:(name, data, callbacks) => calls.push({name, data, callbacks})}},
    window:{setTimeout:(callback, delay) => { assert.ok([2000, 4000].includes(delay)); delays.push(delay); timers.push(callback); }}
  });
  question.value = questionText; button.click();
  return {button, output, status, calls, timers, delays, focused:() => focused};
}
function submit(s) {
  assert.equal(s.button.disabled, true);
  assert.equal(s.output.attributes['aria-busy'], 'true');
  assert.equal(s.calls[0].name, 'CHESS_QUERY_SUBMIT');
  assert.equal(s.calls[0].data.x01, 'Which <opening>?');
  s.button.click(); assert.equal(s.calls.length, 1);
  s.calls[0].callbacks.success({requestId:42});
  assert.equal(s.calls[1].name, 'CHESS_QUERY_READ');
  assert.equal(s.calls[1].data.x01, '42');
}
function released(s) { assert.equal(s.button.disabled, false); assert.equal(s.output.attributes['aria-busy'], 'false'); }
function descendants(element, tag) { return element.children.flatMap(child => [ ...(child.tag === tag ? [child] : []), ...descendants(child, tag)]); }
const blank = setup('  '); assert.equal(blank.calls.length, 0); assert.equal(blank.focused(), true); released(blank);
const s = setup(); submit(s);
for (const status of ['QUEUED', 'PROCESSING']) {
  s.calls.at(-1).callbacks.success({status}); assert.equal(s.button.disabled, true); s.timers.shift()();
}
const literal = '<img src=x onerror=alert(1)>';
s.calls.at(-1).callbacks.success({status:'COMPLETED', result:{status:'COMPLETED', columns:[literal, 'count'], rows:[[literal, 7], [null, false]], sql:'select ' + literal, truncated:true, catalogue_answer:literal, general_knowledge_answer:'General '+literal, answer_status:'complete_clipped'}});
released(s); assert.equal(s.status.textContent, 'Results truncated at the safety limit.');
assert.deepEqual(descendants(s.output, 'th').map(cell => cell.textContent), [literal, 'count']);
assert.deepEqual(descendants(s.output, 'td').map(cell => cell.textContent), [literal, '7', '', 'false']);
assert.equal(descendants(s.output, 'pre')[0].textContent, 'select ' + literal);
assert.deepEqual(descendants(s.output, 'summary').map(node => node.textContent), ['Supporting records (2)', 'View query SQL']);
const normalDetails = descendants(s.output, 'details');
assert.equal(normalDetails[0].open, false); assert.notEqual(normalDetails[1].open, true);
assert.deepEqual(s.output.children.filter(node => node.tag === 'h3').map(node => node.textContent), ['From the Chess catalogue','General chess knowledge']);
assert.deepEqual(descendants(s.output, 'h3').map(node => node.textContent), ['From the Chess catalogue','General chess knowledge']);
assert.ok(descendants(s.output, 'p').some(node => node.textContent === literal));
// The worker serialises QueryResult unchanged, including lowercase model outcomes.
for (const status of ['clarification', 'unsupported']) {
  const f = setup(); submit(f);
  f.calls[1].callbacks.success({status:'COMPLETED', result:{status, dataset_id:'orac_chess.reference', metadata_version:'test', columns:[], rows:[], sql:null, message:literal, truncated:false}});
  released(f); assert.equal(f.status.textContent, literal); assert.equal(f.output.children.length, 0);
  f.button.click(); assert.equal(f.button.disabled, true);
}
const groundedOnly = setup(); submit(groundedOnly);
groundedOnly.calls[1].callbacks.success({status:'COMPLETED',result:{columns:['name'],rows:[['Italian Game']],catalogue_answer:'Italian Game',general_knowledge_answer:'',answer_status:'complete'}});
released(groundedOnly);
assert.deepEqual(descendants(groundedOnly.output, 'h3').map(node => node.textContent), ['From the Chess catalogue','General chess knowledge']);
assert.ok(descendants(groundedOnly.output, 'p').some(node => node.textContent === 'No supplementary general chess knowledge was used.'));
for (const result of [
  {answer_status:'unavailable',catalogue_answer:'',general_knowledge_answer:''},
  {answer_status:'complete',catalogue_answer:'',general_knowledge_answer:''},
  {answer_status:'complete',catalogue_answer:' ',general_knowledge_answer:' '},
  {answer_status:'unavailable',catalogue_answer:'Incomplete explanation',general_knowledge_answer:''}
]) {
  const fallback = setup(); submit(fallback);
  fallback.calls[1].callbacks.success({status:'COMPLETED',result:{columns:['name'],rows:[['Italian Game']],sql:'select name',...result}});
  released(fallback);
  assert.equal(descendants(fallback.output, 'details')[0].open, true);
  assert.notEqual(descendants(fallback.output, 'details')[1].open, true);
}
const variationList = setup(); submit(variationList);
const wideColumns = Array.from({length:16}, (_, column) => 'column_' + column);
const variationRows = Array.from({length:47}, (_, row) => wideColumns.map((_, column) => column === 0 ? row + 1 : column === 1 ? 'Same variation name' : literal));
variationList.calls[1].callbacks.success({status:'COMPLETED',result:{columns:wideColumns,rows:variationRows,catalogue_answer:'47 variation records',general_knowledge_answer:'',answer_status:'complete'}});
released(variationList);
assert.equal(descendants(variationList.output, 'details')[0].open, false);
assert.equal(descendants(variationList.output, 'summary')[0].textContent, 'Supporting records (47)');
assert.deepEqual(descendants(variationList.output, 'th').map(node => node.textContent), wideColumns);
assert.deepEqual(descendants(variationList.output, 'td').map(node => node.textContent), variationRows.flat().map(String));
const empty = setup(); submit(empty); empty.calls[1].callbacks.success({status:'COMPLETED',result:{columns:['name'],rows:[]}}); released(empty); assert.match(empty.status.textContent, /No matching/);
for (const stage of ['submit', 'read', 'missing', 'nullSubmit', 'failed', 'expired', 'refused', 'nullRead', 'malformed', 'unknown']) {
  const f = setup();
  if (stage === 'submit') f.calls[0].callbacks.error({message:literal});
  else if (stage === 'missing') f.calls[0].callbacks.success({});
  else if (stage === 'nullSubmit') f.calls[0].callbacks.success(null);
  else {
    submit(f);
    if (stage === 'read') f.calls[1].callbacks.error({message:literal});
    else if (stage === 'failed') f.calls[1].callbacks.success({status:'FAILED'});
    else if (stage === 'expired') f.calls[1].callbacks.success({status:'EXPIRED'});
    else if (stage === 'nullRead') f.calls[1].callbacks.success(null);
    else if (stage === 'malformed') f.calls[1].callbacks.success({status:'COMPLETED',result:{columns:['x'], rows:[{}]}});
    else if (stage === 'unknown') f.calls[1].callbacks.success({status:literal});
    else f.calls[1].callbacks.success({status:'COMPLETED',result:{status:'REFUSED',message:literal}});
  }
  released(f); assert.equal(f.timers.length, 0);
  const expected = ['submit','missing','nullSubmit'].includes(stage) ? /could not be started/ : stage === 'failed' ? /could not be completed/ : stage === 'expired' ? /expired/ : stage === 'refused' ? /<img/ : /status could not be retrieved/;
  assert.match(f.status.textContent, expected);
  const old = f.calls.at(-1).callbacks; f.button.click(); assert.equal(f.button.disabled, true);
  old.error(); assert.equal(f.button.disabled, true);
}
// Retry only transient status reads, never submission, using the same request.
for (const [code, kind] of [[408,'error'],[502,'error'],[503,'error'],[504,'error'],[0,'error'],[0,'timeout']]) {
  const f = setup(); submit(f);
  f.calls.at(-1).callbacks.error({status:code,responseText:literal}, kind, literal);
  assert.equal(f.button.disabled, true); assert.equal(f.output.attributes['aria-busy'], 'true');
  assert.equal(f.status.textContent, 'Connection interrupted. Retrying query status...');
  assert.equal(f.delays.at(-1), 2000); f.button.click(); assert.equal(f.calls.length, 2);
  f.timers.shift()(); assert.equal(f.calls.at(-1).name, 'CHESS_QUERY_READ'); assert.equal(f.calls.at(-1).data.x01, '42');
  f.calls.at(-1).callbacks.success({status:'COMPLETED',result:{columns:['name'],rows:[]}}); released(f);
  assert.equal(f.calls.filter(call => call.name === 'CHESS_QUERY_SUBMIT').length, 1);
}
const budget = setup(); submit(budget);
for (let retry = 0; retry < 2; retry++) {
  budget.calls.at(-1).callbacks.error({status:503}, 'error', literal);
  assert.equal(budget.delays.at(-1), (retry + 1) * 2000); budget.timers.shift()();
  // A successful queued response does not reset the total retry budget.
  budget.calls.at(-1).callbacks.success({status:'QUEUED'}); budget.timers.shift()();
}
budget.calls.at(-1).callbacks.error({status:503}, 'error', literal); released(budget);
assert.equal(budget.timers.length, 0); assert.match(budget.status.textContent, /Reload the page and sign in if prompted/);
assert.ok(!budget.status.textContent.includes(literal));
for (const [xhr, kind] of [[{status:401},'error'],[{status:403},'error'],[{status:503},'APEX'],[{status:503},'parsererror'],[{status:503},'abort'],[{status:503},'cancel'],[{status:503},'superseded'],[{status:503},'unknown'],[{status:NaN},'timeout'],[{status:500},'error'],[{status:404},'error'],[{},'timeout'],[{status:503},undefined],[undefined,undefined]]) {
  const f = setup(); submit(f); f.calls.at(-1).callbacks.error(xhr, kind, literal); released(f);
  assert.equal(f.timers.length, 0); assert.ok(!f.status.textContent.includes(literal));
  if (xhr && [401,403].includes(xhr.status)) assert.match(f.status.textContent, /Sign-in or access could not be verified/);
  if (['APEX','parsererror'].includes(kind)) assert.match(f.status.textContent, /response could not be read/);
}
const noSubmitRetry = setup(); noSubmitRetry.calls[0].callbacks.error({status:503},'error',literal); released(noSubmitRetry); assert.equal(noSubmitRetry.timers.length, 0); assert.equal(noSubmitRetry.calls.length, 1);
const stale = setup(); submit(stale); stale.calls[1].callbacks.error({status:503},'error',literal);
const staleTimer = stale.timers.shift(); stale.calls[1].callbacks.success({status:'FAILED'}); released(stale);
stale.button.click(); const before = stale.calls.length; staleTimer(); assert.equal(stale.calls.length, before); assert.equal(stale.button.disabled, true);
const capped = setup(); submit(capped);
for (let read = 1; read < 100; read++) { capped.calls.at(-1).callbacks.success({status:'QUEUED'}); capped.timers.shift()(); }
capped.calls.at(-1).callbacks.error({status:503},'error',literal); released(capped); assert.equal(capped.calls.length, 101); assert.equal(capped.timers.length, 0);
const pending = setup(); submit(pending);
for (let attempt = 0; attempt < 100; attempt++) { pending.calls.at(-1).callbacks.success({status:'QUEUED'}); pending.timers.shift()(); }
assert.equal(pending.calls.length, 101); assert.equal(pending.timers.length, 0); released(pending);
assert.equal(pending.status.textContent, 'Your query is still pending. Submit again later.');
pending.button.click(); assert.equal(pending.button.disabled, true);
'''
    subprocess.run(['node', '--input-type=module', '--eval', program],
                   env=os.environ | {'CHESS_QUERY_SOURCE': source}, check=True,
                   capture_output=True, text=True, timeout=30)
