/** Install APEX viewer lifecycle hooks. Author: Clive Bostock. Date: 14-Nov-2026.
 * Purpose: Mount disposable viewers after page and region rendering.
 * Usage: Loaded once as a module by generated APEX viewer regions.
 */
import {mountAll,destroyAll,destroyDetached} from './apex.mjs';
mountAll();
apex.jQuery(document).on('apexbeforerefresh.oracPgn',event=>destroyAll(event.target));
apex.jQuery(document).on('apexafterrefresh.oracPgn',event=>mountAll(event.target));
window.addEventListener('pagehide',()=>destroyAll());
// Dialog DOM can be removed without a region refresh.
const observer=new MutationObserver(()=>{destroyDetached();for(const el of document.querySelectorAll('[data-orac-pgn]'))mountAll(el);});
observer.observe(document.body,{childList:true,subtree:true});
window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
