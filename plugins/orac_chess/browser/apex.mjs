/** APEX lifecycle adapter for local, read-only PGN viewers and variation exploration.
 * Author: Clive Bostock
 * Date: 14-Nov-2026
 * Purpose: Fetch bounded metadata and one complete selected line through page callbacks.
 * Usage: mountAll(document); bootstrap.mjs installs APEX lifecycle handlers.
 */
import {PgnViewer} from './viewer.mjs';
import {relationship} from './model.mjs';
const mounts = new Map();
const node = (tag, text) => {const el=document.createElement(tag); if(text !== undefined) el.textContent=text; return el;};

/** Mount one page region and return a cleanup handle. */
export function mount(container) {
    mounts.get(container)?.destroy();
    let disposed = false, sequence = 0, active = null, offset = 0, principal = null;
    const requests = new Set();
    const page = container.dataset.page;
    const item = `P${page}_${page === '11' ? 'OPENING' : page === '31' ? 'VARIATION' : 'GAMBIT'}_ID`;
    container.replaceChildren();
    const message = node('p', 'Loading variations…');
    message.setAttribute('role','status');
    const host = node('div');
    const viewer = new PgnViewer({container:host});
    let select, earlier, more, back;
    container.append(message,host);
    const request = (action, id, pageOffset = 0) => new Promise((resolve,reject) => {
        const xhr = apex.server.process('PGN_VIEWER',{x01:action,x02:id || '',x03:pageOffset,pageItems:'#'+item+(page==='31' ? ',#P31_OPENING_ID,#P31_GAMBIT_ID' : '')},
            {dataType:'json', success:data=>{ if(data.error) reject(new Error(data.error)); else resolve(data); },error:()=>reject(new Error('The selected line could not be loaded.'))});
        requests.add(xhr);
        xhr.always?.(()=>requests.delete(xhr));
    });
    async function choose(id) {
        const ticket = ++sequence;
        viewer.clear(); message.textContent='Loading selected line…'; back.disabled=true;
        try {
            const data=await request('LINE',id);
            if(disposed || ticket !== sequence) return;
            if(data.parentId) {
                const parent=await request('LINE',data.parentId);
                if(disposed || ticket !== sequence) return;
                const error=relationship(parent.pgn,data.pgn,data.kind,Number(data.branchPly),data.startingFen);
                if(error) throw new Error('This child line is inconsistent with its parent: '+error);
            }
            active=data;
            if (!Array.from(select.options).some(option=>String(option.value)===String(data.id))) {
                const option=node('option',data.name); option.value=data.id; select.prepend(option);
            }
            select.value=String(data.id);
            principal=data.rootId;
            if (!viewer.loadPgn(data.pgn,data.startingFen)) {message.textContent='The selected line is unavailable.'; return;}
            if(data.parentId) viewer.goToMove(data.branchPly);
            message.textContent=data.name+(data.parentId ? ` — ${data.kind.toLowerCase()} at half-move ${data.branchPly}` : ' — principal line');
            back.disabled=String(data.id) === String(principal);
        } catch(error) {if(!disposed && ticket === sequence) {viewer.clear();message.textContent=error.message;}}
    }
    async function list() {
        const ticket=++sequence;
        viewer.clear(); select.replaceChildren(); message.textContent='Loading variations…';
        try {
            const data=await request('LIST',null,offset);
            if(disposed || ticket !== sequence) return;
            const groups=new Map();
            for(const line of data.lines) {
                const groupName=line.parentId ? `Children of ${line.parentName || line.parentId}` : 'Principal lines';
                if(!groups.has(groupName)) {const group=node('optgroup');group.label=groupName;select.append(group);groups.set(groupName,group);}
                const option=node('option',line.name+(line.parentId ? ` — ${line.kind.toLowerCase()}, half-move ${line.branchPly}` : ''));
                option.value=line.id;groups.get(groupName).append(option);
            }
            earlier.disabled=offset===0;more.disabled=!data.more;
            if(data.lines.length) choose(data.lines[0].id); else {message.textContent='No PGN lines are available for this subject.';select.disabled=true;}
        } catch(error) {if(!disposed && ticket===sequence) message.textContent=error.message;}
    }
    if(page==='31') {
        const update=node('button','Update preview');update.type='button';container.prepend(update);
        const preview=async()=>{
            const ticket=++sequence;
            viewer.clear(); message.textContent='Updating preview…';
            try {
                let fen=apex.item('P31_STARTING_FEN').getValue() || null;
                const parentId=apex.item('P31_PARENT_VARIATION_ID').getValue();
                if(parentId) {const data=await request('PARENT',parentId); if(disposed || ticket!==sequence)return;fen=data.startingFen;}
                if(disposed || ticket!==sequence)return;
                viewer.loadPgn(apex.item('P31_PGN').getValue(),fen);
                message.textContent='Preview of the current PGN. Use Save to persist changes.';
            } catch(error) {if(!disposed && ticket===sequence)message.textContent=error.message;}
        };
        update.addEventListener('click',preview);preview();
    } else {
        const label = node('label','Choose a principal line or child variation ');
        select = node('select'); select.setAttribute('aria-label','Variation line'); label.append(select);
        earlier = node('button','Earlier lines'); more = node('button','More lines'); back = node('button','Return to principal line');
        for(const button of [earlier,more,back]) button.type='button';
        container.prepend(label,earlier,more,back);
        select.addEventListener('change',()=>choose(select.value));
        more.addEventListener('click',()=>{offset+=100;list();});
        earlier.addEventListener('click',()=>{offset=Math.max(0,offset-100);list();});
        back.addEventListener('click',()=>{if(principal) choose(principal);});
        list();
    }
    const handle={destroy(){if(disposed)return;disposed=true;sequence++;for(const xhr of requests)xhr.abort?.();requests.clear();viewer.destroy();container.replaceChildren();mounts.delete(container);}};
    mounts.set(container,handle);return handle;
}
/** Mount all new viewer regions in a refreshed subtree. */
export function mountAll(root=document) {
    const containers=[...(root.matches?.('[data-orac-pgn]') ? [root] : []),...root.querySelectorAll('[data-orac-pgn]')];
    for(const container of containers) if(!mounts.has(container)) mount(container);
}
/** Dispose viewers in an APEX region before refresh or dialog removal. */
export function destroyAll(root=document) {
    for(const [container,handle] of mounts) if(root===document || root===container || root.contains(container))handle.destroy();
}

/** Dispose viewers whose dialog or region was removed from the document. */
export function destroyDetached() {
    for(const [container,handle] of mounts) if(!container.isConnected)handle.destroy();
}
