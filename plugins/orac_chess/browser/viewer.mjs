/** Independent, read-only PGN viewer with local SVG board assets.
 * Author: Clive Bostock
 * Date: 14-Nov-2026
 * Purpose: Provide bounded move navigation and accessible move selection.
 * Usage: new PgnViewer({container}).loadPgn(pgn).
 */
import {Chessboard} from '../vendor/cm-chessboard-8.15.4/src/Chessboard.js';
import {Markers, MARKER_TYPE} from '../vendor/cm-chessboard-8.15.4/src/extensions/markers/Markers.js';
import {parsePgn} from './model.mjs';
const assets = new URL('../vendor/cm-chessboard-8.15.4/assets/', import.meta.url).href;
const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
};

/** A disposable viewer; goToMove uses half-move counts, with zero the initial position. */
export class PgnViewer {
    constructor({container}) {
        if (!(container instanceof HTMLElement)) throw new TypeError('A container element is required');
        this.container = container;
        this.destroyed = false;
        this.orientation = 'w';
        this.ply = 0;
        this.game = null;
        this.root = element('section', undefined, 'orac-pgn-viewer');
        this.root.tabIndex = 0;
        this.root.setAttribute('aria-label', 'Chess move viewer. Use left and right arrows to navigate.');
        this.boardHost = element('div', undefined, 'orac-pgn-board');
        this.status = element('p', 'No PGN available.', 'orac-pgn-status');
        this.status.setAttribute('role', 'status');
        this.controls = element('div', undefined, 'orac-pgn-controls');
        this.buttons = {};
        for (const [method, label] of [['first','First'],['previous','Previous'],['next','Next'],['last','Last'],['flip','Flip'],['reset','Reset']]) {
            const button = element('button', label);
            button.type = 'button';
            button.setAttribute('aria-label', label + (method === 'flip' ? ' board' : ' position'));
            button.addEventListener('click', () => this[method]());
            this.buttons[method] = button;
            this.controls.append(button);
        }
        this.moves = element('div', undefined, 'orac-pgn-moves');
        this.moves.setAttribute('aria-label', 'Moves');
        this.root.append(this.boardHost, this.controls, this.status, this.moves);
        container.append(this.root);
        this.keyHandler = event => {
            if (event.target.closest('input,textarea,select,[contenteditable="true"]')) return;
            const method = {ArrowLeft:'previous', ArrowRight:'next', Home:'first', End:'last'}[event.key];
            if (method) { event.preventDefault(); this[method](); }
        };
        this.root.addEventListener('keydown', this.keyHandler);
        this.update();
    }

    /** Load a complete PGN, clearing any previous position on failure. */
    loadPgn(pgn, startingFen = null) {
        if (this.destroyed) return false;
        this.clear();
        try {
            if (!pgn || !pgn.trim()) { this.status.textContent = 'No PGN available.'; return false; }
            this.game = parsePgn(pgn, startingFen);
            this.board = new Chessboard(this.boardHost, {position:this.game.initialFen, assetsUrl:assets,
                assetsCache:false, style:{animationDuration:0, pieces:{file:new URL('./pieces.svg', import.meta.url).href}}, extensions:[{class:Markers, props:{autoMarkers:null}}]});
            for (const move of this.game.moves) {
                const button = element('button', `${move.number}${move.color === 'w' ? '.' : '...'} ${move.san}`);
                button.type = 'button';
                button.dataset.ply = move.ply;
                button.addEventListener('click', () => this.goToMove(move.ply));
                this.moves.append(button);
            }
            this.update();
            return true;
        } catch (error) {
            this.clear();
            this.status.textContent = 'This PGN cannot be displayed: ' + String(error.message || 'Invalid PGN').slice(0, 180);
            return false;
        }
    }
    /** Clear loaded data and stale board graphics. */
    clear() {
        this.renderVersion = (this.renderVersion || 0) + 1;
        const previousBoard = this.board;
        this.renderTask = (this.renderTask || Promise.resolve()).catch(() => {}).then(() => previousBoard?.destroy());
        this.board = null;
        this.game = null;
        this.ply = 0;
        this.moves.replaceChildren();
        this.boardHost.replaceChildren();
        this.status.textContent = 'No PGN available.';
        this.update();
    }
    /** Navigate to a bounded half-move count. */
    goToMove(ply) {
        if (this.destroyed || !this.game || !Number.isFinite(Number(ply))) return;
        this.ply = Math.max(0, Math.min(this.game.moves.length, Math.trunc(Number(ply))));
        this.update();
    }
    first() { this.goToMove(0); }
    previous() { this.goToMove(this.ply - 1); }
    next() { this.goToMove(this.ply + 1); }
    last() { this.goToMove(this.game?.moves.length || 0); }
    flip() {
        if (this.destroyed) return;
        this.orientation = this.orientation === 'w' ? 'b' : 'w';
        this.update();
    }
    reset() {
        if (this.destroyed) return;
        this.orientation = 'w';
        this.first();
    }
    /** Render the full position and the last move markers. */
    update() {
        const count = this.game?.moves.length || 0;
        for (const name of ['first','previous']) this.buttons[name].disabled = !this.game || this.ply === 0;
        for (const name of ['next','last']) this.buttons[name].disabled = !this.game || this.ply === count;
        for (const name of ['flip','reset']) this.buttons[name].disabled = !this.game;
        if (!this.game) return;
        const move = this.game.moves[this.ply - 1];
        const board = this.board, fen = this.game.positions[this.ply], orientation = this.orientation;
        const ticket = this.renderVersion = (this.renderVersion || 0) + 1;
        // The renderer queues even unanimated operations. Await each before the next,
        // and retire the old board only after its outstanding work has completed.
        this.renderTask = (this.renderTask || Promise.resolve()).catch(() => {}).then(async () => {
            if (this.destroyed || ticket !== this.renderVersion || !board) return;
            await board.setPosition(fen, false);
            if (this.destroyed || ticket !== this.renderVersion) return;
            await board.setOrientation(orientation, false);
            if (this.destroyed || ticket !== this.renderVersion) return;
            board.removeMarkers();
            if (move) for (const square of [move.from, move.to]) board.addMarker(MARKER_TYPE.framePrimary, square);
        });
        this.status.textContent = this.ply ? `Move ${move.number}${move.color === 'w' ? '.' : '...'} ${move.san} — ${this.ply} of ${count} half-moves` : `Initial position — ${count} half-moves`;
        for (const button of this.moves.children) {
            const current = Number(button.dataset.ply) === this.ply;
            button.classList.toggle('is-current', current);
            if (current) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current');
        }
    }
    /** Release observers and event listeners; calling twice is safe. */
    destroy() {
        if (this.destroyed) return;
        this.clear();
        this.root.removeEventListener('keydown', this.keyHandler);
        this.root.remove();
        this.destroyed = true;
    }
}
