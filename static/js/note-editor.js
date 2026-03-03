/**
 * CampusPrep — Notion-like Block Editor for Student Notes
 * v1.0  —  Vanilla JS, zero dependencies (KaTeX optional for formulas)
 */
(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════════════════════
    // CONSTANTS
    // ═══════════════════════════════════════════════════════════════════════

    const BLOCK_TYPES = {
        paragraph:     { label: 'Paragraph',      ph: "Type '/' for commands…" },
        heading1:      { label: 'Heading 1',       ph: 'Heading 1' },
        heading2:      { label: 'Heading 2',       ph: 'Heading 2' },
        heading3:      { label: 'Heading 3',       ph: 'Heading 3' },
        quote:         { label: 'Quote',           ph: 'Quote' },
        callout:       { label: 'Callout',         ph: 'Type a callout…' },
        divider:       { label: 'Divider',         noContent: true },
        bullet_list:   { label: 'Bullet List',     ph: 'List item' },
        numbered_list: { label: 'Numbered List',   ph: 'List item' },
        checklist:     { label: 'Checklist',       ph: 'To-do' },
        code:          { label: 'Code Block',      ph: 'Code…' },
        image:         { label: 'Image',           noContent: true },
        video:         { label: 'Video',           noContent: true },
        toggle:        { label: 'Toggle',          ph: 'Toggle heading' },
        table:         { label: 'Table',           noContent: true },
        formula:       { label: 'Formula',         ph: 'LaTeX…' },
        highlight:     { label: 'Highlight',       ph: 'Note…' },
    };

    const SLASH_COMMANDS = [
        { cmd: '/h1',        type: 'heading1',      label: 'Heading 1',      desc: 'Large section heading',  icon: 'H1' },
        { cmd: '/h2',        type: 'heading2',      label: 'Heading 2',      desc: 'Medium heading',         icon: 'H2' },
        { cmd: '/h3',        type: 'heading3',      label: 'Heading 3',      desc: 'Small heading',          icon: 'H3' },
        { cmd: '/bullet',    type: 'bullet_list',   label: 'Bullet List',    desc: 'Unordered list',         icon: '•' },
        { cmd: '/numbered',  type: 'numbered_list', label: 'Numbered List',  desc: 'Ordered list',           icon: '1.' },
        { cmd: '/checklist', type: 'checklist',     label: 'Checklist',      desc: 'Task checkbox',          icon: '☑' },
        { cmd: '/code',      type: 'code',          label: 'Code Block',     desc: 'Monospace code',         icon: '</>' },
        { cmd: '/image',     type: 'image',         label: 'Image',          desc: 'Upload / embed',         icon: '🖼' },
        { cmd: '/video',     type: 'video',         label: 'Video',          desc: 'YouTube embed',          icon: '🎬' },
        { cmd: '/table',     type: 'table',         label: 'Table',          desc: 'Simple table',           icon: '⊞' },
        { cmd: '/quote',     type: 'quote',         label: 'Quote',          desc: 'Block quote',            icon: '❝' },
        { cmd: '/callout',   type: 'callout',       label: 'Callout',        desc: 'Highlighted box',        icon: '💡' },
        { cmd: '/divider',   type: 'divider',       label: 'Divider',        desc: 'Horizontal rule',        icon: '—' },
        { cmd: '/toggle',    type: 'toggle',        label: 'Toggle',         desc: 'Collapsible section',    icon: '▶' },
        { cmd: '/formula',   type: 'formula',       label: 'Formula',        desc: 'LaTeX math block',       icon: '∑' },
    ];

    const HL_META = {
        important: { icon: '⭐', label: 'Important', cls: 'hl-important' },
        revise:    { icon: '🔄', label: 'Revise',    cls: 'hl-revise' },
        formula:   { icon: '📐', label: 'Formula',   cls: 'hl-formula' },
        doubt:     { icon: '❓', label: 'Doubt',     cls: 'hl-doubt' },
    };

    // ═══════════════════════════════════════════════════════════════════════
    // EDITOR CLASS
    // ═══════════════════════════════════════════════════════════════════════

    class NoteEditor {
        constructor(cfg) {
            this.noteId          = cfg.noteId;
            this.csrfToken       = cfg.csrfToken;
            this.saveUrl         = cfg.saveUrl;
            this.uploadUrl       = cfg.uploadUrl;
            this.versionsUrl     = cfg.versionsUrl;
            this.restoreBaseUrl  = cfg.restoreBaseUrl;
            this.versionDetailBaseUrl = cfg.versionDetailBaseUrl;

            this.readOnly  = false;
            this.focusMode = false;
            this.isDirty   = false;
            this.isSaving  = false;
            this._lastSavedStr  = '';
            this._lastVersionTs = Date.now();

            // Slash-menu state
            this._slashVisible   = false;
            this._slashIdx       = -1;   // block index where slash started
            this._slashSelIdx    = 0;
            this._slashFiltered  = [];

            // Search state
            this._searchOpen    = false;
            this._searchMatches = [];
            this._searchCur     = -1;

            // Undo / redo
            this._undoStack  = [];
            this._redoStack  = [];
            this._undoTimer  = null;
            this._katexRetryTimer = null;



            // DOM
            this.editorEl       = document.getElementById('editor-blocks');
            this.statusEl       = document.getElementById('save-status');
            this.slashMenuEl    = document.getElementById('slash-menu');
            this.inlineToolbarEl = document.getElementById('inline-toolbar');
            this.searchPanelEl  = document.getElementById('search-panel');
            this.searchInputEl  = document.getElementById('search-input');
            this.searchCountEl  = document.getElementById('search-count');
            this.ctxMenuEl      = document.getElementById('block-ctx-menu');

            // Blocks
            this.blocks = (cfg.initialBlocks && cfg.initialBlocks.blocks) ? cfg.initialBlocks.blocks : [];
            if (!this.blocks.length) this.blocks.push(this._newBlock('paragraph'));

            this._init();

            // Push initial state so Ctrl+Z can always go back to blank
            this._undoStack.push(JSON.stringify(this.blocks));
        }

        // ── Initialization ────────────────────────────────────────────────
        _init() {
            this._render();
            this._ensureKatexReadyRender();
            this._setupAutoSave();
            this._setupGlobalKeys();
            this._setupPasteAndDrop();
            this._setupSelectionWatch();
            this._setupCrossBlockSelect();
            this._focusBlock(0);
        }

        _ensureKatexReadyRender() {
            // KaTeX is loaded via deferred CDN script in template, so editor may init first.
            if (typeof katex !== 'undefined') return;

            let tries = 0;
            const maxTries = 40; // ~4s max wait
            const tick = () => {
                if (typeof katex !== 'undefined') {
                    this._render();
                    return;
                }
                tries += 1;
                if (tries < maxTries) this._katexRetryTimer = setTimeout(tick, 100);
            };

            this._katexRetryTimer = setTimeout(tick, 100);
            window.addEventListener('load', () => {
                if (typeof katex !== 'undefined') this._render();
            }, { once: true });
        }

        // ── Block factory ─────────────────────────────────────────────────
        _newBlock(type = 'paragraph', content = '', attrs = {}) {
            return { id: this._uuid(), type, content, attrs: { ...attrs }, children: [] };
        }

        // ── Rendering ─────────────────────────────────────────────────────
        _render() {
            this.editorEl.innerHTML = '';
            this.blocks.forEach((b, i) => this.editorEl.appendChild(this._renderBlock(b, i)));
        }

        _renderBlock(block, index) {
            const wrap = document.createElement('div');
            wrap.className = 'note-block group flex items-start gap-1 py-0.5 rounded-lg px-1 -mx-1';
            wrap.dataset.blockId = block.id;
            wrap.dataset.index = index;

            // Highlight class
            const hlType = block.attrs.highlight_type;
            if (hlType && HL_META[hlType]) wrap.classList.add(HL_META[hlType].cls, 'pl-3', 'pr-2', 'py-1', 'rounded-lg', 'my-0.5');

            // Grip handle
            if (!this.readOnly) {
                const grip = document.createElement('div');
                grip.className = 'block-grip opacity-0 group-hover:opacity-100 transition-opacity select-none mt-0.5';
                grip.innerHTML = '⋮⋮';
                wrap.appendChild(grip);
            }

            // Content
            const contentEl = this._createContentElement(block, index);
            contentEl.dataset.index = index;
            wrap.appendChild(contentEl);

            // Context menu button
            if (!this.readOnly) {
                const btn = document.createElement('button');
                btn.className = 'block-menu-btn opacity-0 group-hover:opacity-100 transition-opacity';
                btn.innerHTML = '⋯';
                btn.addEventListener('click', e => { e.stopPropagation(); this._showCtxMenu(e, index); });
                wrap.appendChild(btn);
            }

            return wrap;
        }

        // ── Content element factories ─────────────────────────────────────
        _createContentElement(block, index) {
            const t = block.type;
            if (t === 'divider')       return this._elDivider();
            if (t === 'image')         return this._elImage(block, index);
            if (t === 'video')         return this._elVideo(block, index);
            if (t === 'code')          return this._elCode(block, index);
            if (t === 'checklist')     return this._elChecklist(block, index);
            if (t === 'formula')       return this._elFormula(block, index);
            if (t === 'callout')       return this._elCallout(block, index);
            if (t === 'toggle')        return this._elToggle(block, index);
            if (t === 'table')         return this._elTable(block, index);
            if (t === 'highlight')     return this._elHighlightBlock(block, index);
            // Default: contenteditable block
            return this._elText(block, index);
        }

        _elText(block, index) {
            const cls = {
                heading1: 'bt-heading1', heading2: 'bt-heading2', heading3: 'bt-heading3',
                quote: 'bt-quote',
                bullet_list: 'list-disc ml-6', numbered_list: 'list-decimal ml-6',
            };
            const el = document.createElement('div');
            el.className = `block-content flex-1 outline-none ${cls[block.type] || ''} text-sm leading-relaxed`;
            el.contentEditable = !this.readOnly;
            el.innerHTML = block.content || '';
            el.dataset.placeholder = (BLOCK_TYPES[block.type] || {}).ph || '';
            this._attachBlockEvents(el, index);
            return el;
        }

        _elDivider() {
            const el = document.createElement('div');
            el.className = 'flex-1 py-2';
            el.innerHTML = '<hr class="border-border">';
            return el;
        }

        _elChecklist(block, index) {
            const wrap = document.createElement('div');
            wrap.className = 'flex items-start gap-2 flex-1';
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = !!block.attrs.checked;
            cb.className = 'mt-1 w-4 h-4 rounded border-border accent-emerald-500 flex-shrink-0';
            cb.addEventListener('change', () => { block.attrs.checked = cb.checked; txt.classList.toggle('line-through', cb.checked); txt.classList.toggle('text-muted-foreground', cb.checked); this._markDirty(); });
            if (this.readOnly) cb.disabled = true;
            const txt = document.createElement('div');
            txt.className = `block-content flex-1 outline-none text-sm ${block.attrs.checked ? 'line-through text-muted-foreground' : ''}`;
            txt.contentEditable = !this.readOnly;
            txt.innerHTML = block.content || '';
            txt.dataset.placeholder = 'To-do';
            this._attachBlockEvents(txt, index);
            wrap.appendChild(cb);
            wrap.appendChild(txt);
            return wrap;
        }

        _elCode(block, index) {
            const wrap = document.createElement('div');
            wrap.className = 'flex-1 relative bg-muted rounded-lg p-3 font-mono text-xs overflow-x-auto';
            if (!this.readOnly) {
                const sel = document.createElement('select');
                sel.className = 'absolute top-2 right-2 text-[10px] bg-background border border-border rounded px-1.5 py-0.5 no-custom';
                ['plain','javascript','python','java','c','cpp','html','css'].forEach(l => {
                    const o = document.createElement('option'); o.value = l; o.textContent = l;
                    if (block.attrs.language === l) o.selected = true; sel.appendChild(o);
                });
                sel.addEventListener('change', () => { block.attrs.language = sel.value; this._markDirty(); });
                wrap.appendChild(sel);
            }
            const pre = document.createElement('pre');
            pre.className = 'outline-none whitespace-pre-wrap mt-4 block-content';
            pre.contentEditable = !this.readOnly;
            pre.textContent = block.content || '';
            pre.dataset.placeholder = 'Code…';
            pre.addEventListener('keydown', e => { if (e.key === 'Tab') { e.preventDefault(); document.execCommand('insertText', false, '  '); } });
            pre.addEventListener('input', () => this._markDirty());
            pre.addEventListener('blur', () => { block.content = pre.textContent; });
            return (wrap.appendChild(pre), wrap);
        }

        _elImage(block, index) {
            const wrap = document.createElement('div');
            wrap.className = 'flex-1 my-1';
            if (block.attrs.url) {
                const fig = document.createElement('figure');
                fig.className = `${block.attrs.align === 'center' ? 'text-center' : block.attrs.align === 'right' ? 'text-right' : ''}`;
                const img = document.createElement('img');
                img.src = block.attrs.url; img.alt = block.attrs.caption || ''; img.loading = 'lazy';
                img.className = 'max-w-full rounded-lg inline-block'; if (block.attrs.width) img.style.width = block.attrs.width;
                if (block.attrs.uploading) {
                    img.style.opacity = '0.5';
                    img.title = 'Uploading…';
                    const badge = document.createElement('div');
                    badge.className = 'text-xs text-muted-foreground mt-1 animate-pulse';
                    badge.textContent = '⏳ Uploading…';
                    fig.appendChild(img);
                    fig.appendChild(badge);
                } else {
                    fig.appendChild(img);
                }
                if (!this.readOnly || block.attrs.caption) {
                    const cap = document.createElement('figcaption');
                    cap.className = 'text-xs text-muted-foreground mt-1 outline-none';
                    cap.contentEditable = !this.readOnly; cap.textContent = block.attrs.caption || '';
                    cap.dataset.placeholder = 'Caption…';
                    cap.addEventListener('input', () => { block.attrs.caption = cap.textContent; this._markDirty(); });
                    fig.appendChild(cap);
                }
                if (!this.readOnly) {
                    const ctl = document.createElement('div');
                    ctl.className = 'flex gap-1 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity';
                    ['Left','Center','Right'].forEach(a => {
                        const b = document.createElement('button');
                        b.className = 'text-[10px] px-2 py-0.5 border border-border rounded hover:bg-muted';
                        b.textContent = a;
                        b.addEventListener('click', () => { block.attrs.align = a.toLowerCase(); this._render(); this._markDirty(); });
                        ctl.appendChild(b);
                    });
                    const del = document.createElement('button');
                    del.className = 'text-[10px] px-2 py-0.5 border border-border rounded text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 ml-auto';
                    del.textContent = 'Remove';
                    del.addEventListener('click', () => { this.deleteBlock(index); });
                    ctl.appendChild(del);
                    fig.appendChild(ctl);
                }
                wrap.appendChild(fig);
            } else if (!this.readOnly) {
                const up = document.createElement('div');
                up.className = 'border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-emerald-500/40 transition-colors';
                up.innerHTML = '<div class="text-2xl mb-2">🖼</div><p class="text-xs text-muted-foreground">Click to upload or drag & drop an image</p><input type="file" accept="image/*" class="hidden">';
                up.addEventListener('click', () => up.querySelector('input').click());
                up.querySelector('input').addEventListener('change', e => { if (e.target.files[0]) this._handleImageUpload(e.target.files[0], index); });
                wrap.appendChild(up);
            }
            return wrap;
        }

        _elVideo(block, index) {
            const wrap = document.createElement('div');
            wrap.className = 'flex-1 my-1';
            if (block.attrs.url) {
                const yid = this._ytId(block.attrs.url);
                if (yid) {
                    const ifr = document.createElement('iframe');
                    ifr.src = `https://www.youtube.com/embed/${yid}`; ifr.className = 'w-full aspect-video rounded-lg'; ifr.allowFullscreen = true; ifr.loading = 'lazy';
                    wrap.appendChild(ifr);
                } else { wrap.innerHTML = '<p class="text-xs text-muted-foreground">Invalid video URL</p>'; }
            } else if (!this.readOnly) {
                const inp = document.createElement('div');
                inp.className = 'border border-border rounded-lg p-4 flex items-center gap-2';
                inp.innerHTML = '<span class="text-lg">🎬</span><input type="text" placeholder="Paste YouTube URL and press Enter…" class="flex-1 bg-transparent outline-none text-sm">';
                inp.querySelector('input').addEventListener('keydown', e => { if (e.key === 'Enter') { block.attrs.url = e.target.value; this._render(); this._markDirty(); } });
                wrap.appendChild(inp);
            }
            return wrap;
        }

        _elFormula(block, index) {
            const wrap = document.createElement('div');
            wrap.className = 'flex-1 border border-border rounded-lg p-3 my-1';
            const preview = document.createElement('div');
            preview.className = `${this.readOnly ? 'text-center py-1' : 'text-center min-h-[1.5rem] block-content cursor-text'}`;
            this._renderKatex(preview, block.content || '');

            if (!this.readOnly) {
                preview.tabIndex = 0;
                preview.title = 'Click to edit formula';

                const ta = document.createElement('textarea');
                ta.className = 'w-full bg-transparent outline-none font-mono text-xs resize-none hidden';
                ta.value = block.content || '';
                ta.placeholder = 'LaTeX formula…';
                ta.rows = 2;

                const openEditor = () => {
                    preview.classList.add('hidden');
                    ta.classList.remove('hidden');
                    ta.focus();
                    ta.setSelectionRange(ta.value.length, ta.value.length);
                };

                const closeEditor = () => {
                    block.content = ta.value;
                    this._renderKatex(preview, block.content || '');
                    ta.classList.add('hidden');
                    preview.classList.remove('hidden');
                };

                preview.addEventListener('click', openEditor);
                preview.addEventListener('keydown', e => {
                    if (e.key === 'Enter' || e.key === 'F2') {
                        e.preventDefault();
                        openEditor();
                    }
                });

                ta.addEventListener('input', () => {
                    block.content = ta.value;
                    this._renderKatex(preview, ta.value);
                    this._markDirty();
                });
                ta.addEventListener('keydown', e => {
                    if (e.key === 'Escape') {
                        e.preventDefault();
                        closeEditor();
                        preview.focus();
                    }
                });
                ta.addEventListener('blur', () => {
                    closeEditor();
                    this._markDirty();
                });

                wrap.appendChild(preview);
                wrap.appendChild(ta);
            } else {
                wrap.appendChild(preview);
            }
            return wrap;
        }

        _elCallout(block, index) {
            const wrap = document.createElement('div');
            wrap.className = 'flex items-start gap-3 flex-1 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/30 rounded-lg p-3 my-0.5';
            const icon = document.createElement('span'); icon.className = 'text-lg flex-shrink-0 mt-0.5'; icon.textContent = block.attrs.icon || '💡';
            const txt = document.createElement('div');
            txt.className = 'block-content flex-1 outline-none text-sm'; txt.contentEditable = !this.readOnly;
            txt.innerHTML = block.content || ''; txt.dataset.placeholder = 'Callout…';
            this._attachBlockEvents(txt, index);
            wrap.appendChild(icon); wrap.appendChild(txt);
            return wrap;
        }

        _elToggle(block, index) {
            const det = document.createElement('details');
            det.className = 'flex-1 border border-border rounded-lg overflow-hidden my-0.5';
            if (!block.attrs.collapsed) det.open = true;
            const sum = document.createElement('summary');
            sum.className = 'px-3 py-2 cursor-pointer bg-muted/30 font-medium text-sm select-none outline-none';
            sum.contentEditable = !this.readOnly; sum.innerHTML = block.content || 'Toggle';
            sum.dataset.placeholder = 'Toggle heading…';
            sum.addEventListener('input', () => { block.content = sum.innerHTML; this._markDirty(); });
            const body = document.createElement('div'); body.className = 'px-3 py-2 text-sm';
            if (block.children && block.children.length) {
                block.children.forEach((c, ci) => {
                    const ch = document.createElement('div');
                    ch.contentEditable = !this.readOnly; ch.className = 'outline-none py-0.5';
                    ch.innerHTML = c.content || ''; ch.dataset.placeholder = 'Content…';
                    ch.addEventListener('input', () => { c.content = ch.innerHTML; this._markDirty(); });
                    body.appendChild(ch);
                });
            } else if (!this.readOnly) {
                const ch = document.createElement('div');
                ch.contentEditable = true; ch.className = 'outline-none py-0.5'; ch.dataset.placeholder = 'Content…';
                ch.addEventListener('input', () => {
                    if (!block.children.length) block.children.push({ id: this._uuid(), type: 'paragraph', content: '', attrs: {}, children: [] });
                    block.children[0].content = ch.innerHTML; this._markDirty();
                });
                body.appendChild(ch);
            }
            det.addEventListener('toggle', () => { block.attrs.collapsed = !det.open; });
            det.appendChild(sum); det.appendChild(body);
            return det;
        }

        _elTable(block, index) {
            const wrap = document.createElement('div');
            wrap.className = 'flex-1 overflow-x-auto my-1';
            if (!block.attrs.rows) block.attrs.rows = [['','',''],['','',''],['','','']];
            const tbl = document.createElement('table');
            tbl.className = 'w-full border-collapse text-sm';
            block.attrs.rows.forEach((row, ri) => {
                const tr = document.createElement('tr');
                row.forEach((cell, ci) => {
                    const td = document.createElement(ri === 0 ? 'th' : 'td');
                    td.className = `border border-border px-3 py-1.5 outline-none ${ri === 0 ? 'bg-muted font-medium text-xs' : ''}`;
                    td.contentEditable = !this.readOnly; td.textContent = cell;
                    td.addEventListener('input', () => { block.attrs.rows[ri][ci] = td.textContent; this._markDirty(); });
                    tr.appendChild(td);
                });
                tbl.appendChild(tr);
            });
            wrap.appendChild(tbl);
            if (!this.readOnly) {
                const ctl = document.createElement('div');
                ctl.className = 'flex gap-1 mt-1';
                const btn = (text, fn) => { const b = document.createElement('button'); b.className = 'text-[10px] px-2 py-0.5 border border-border rounded hover:bg-muted'; b.textContent = text; b.addEventListener('click', fn); return b; };
                ctl.appendChild(btn('+ Row', () => { block.attrs.rows.push(new Array(block.attrs.rows[0].length).fill('')); this._render(); this._markDirty(); }));
                ctl.appendChild(btn('+ Col', () => { block.attrs.rows.forEach(r => r.push('')); this._render(); this._markDirty(); }));
                ctl.appendChild(btn('− Row', () => { if (block.attrs.rows.length > 1) { block.attrs.rows.pop(); this._render(); this._markDirty(); } }));
                ctl.appendChild(btn('− Col', () => { if (block.attrs.rows[0].length > 1) { block.attrs.rows.forEach(r => r.pop()); this._render(); this._markDirty(); } }));
                wrap.appendChild(ctl);
            }
            return wrap;
        }

        _elHighlightBlock(block, index) {
            const t = block.attrs.highlight_type || 'important';
            const m = HL_META[t] || HL_META.important;
            const wrap = document.createElement('div');
            wrap.className = `flex-1 rounded-lg p-3 my-0.5 ${m.cls}`;
            const hdr = document.createElement('div');
            hdr.className = 'flex items-center gap-1.5 mb-1';
            hdr.innerHTML = `<span class="text-sm">${m.icon}</span><span class="text-[10px] font-bold uppercase tracking-wider opacity-50">${m.label}</span>`;
            const txt = document.createElement('div');
            txt.className = 'block-content flex-1 outline-none text-sm';
            txt.contentEditable = !this.readOnly; txt.innerHTML = block.content || '';
            txt.dataset.placeholder = `${m.label} note…`;
            this._attachBlockEvents(txt, index);
            wrap.appendChild(hdr); wrap.appendChild(txt);
            return wrap;
        }

        // ── Block events (keydown, input, focus) ──────────────────────────
        _attachBlockEvents(el, index) {
            el.addEventListener('keydown',  e => this._handleKeyDown(e, el, index));
            el.addEventListener('input',    () => this._handleInput(el, index));
            el.addEventListener('focus',    () => { this._activeIdx = index; });
        }

        _handleKeyDown(e, el, index) {
            // Slash menu navigation
            if (this._slashVisible) {
                if (e.key === 'ArrowDown')  { e.preventDefault(); this._slashSelIdx = Math.min(this._slashSelIdx + 1, this._slashFiltered.length - 1); this._renderSlashItems(); return; }
                if (e.key === 'ArrowUp')    { e.preventDefault(); this._slashSelIdx = Math.max(this._slashSelIdx - 1, 0); this._renderSlashItems(); return; }
                if (e.key === 'Enter')      { e.preventDefault(); this._executeSlash(index); return; }
                if (e.key === 'Escape')     { e.preventDefault(); this._hideSlashMenu(); return; }
            }

            // Enter → new block
            if (e.key === 'Enter' && !e.shiftKey) {
                const bt = this.blocks[index].type;
                if (bt === 'code') return;
                e.preventDefault();
                this._checkpoint();
                // Split content at caret
                const sel = window.getSelection();
                if (sel.rangeCount) {
                    const range = sel.getRangeAt(0);
                    const after = range.cloneRange();
                    after.selectNodeContents(el);
                    after.setStart(range.endContainer, range.endOffset);
                    const frag = after.extractContents();
                    const tmp = document.createElement('div'); tmp.appendChild(frag);
                    this.blocks[index].content = el.innerHTML;
                    // New block type logic
                    let newType = 'paragraph';
                    if (bt === 'bullet_list' || bt === 'numbered_list' || bt === 'checklist') {
                        if (!el.textContent.trim()) { this.changeBlockType(index, 'paragraph'); return; }
                        newType = bt;
                    }
                    const nb = this._newBlock(newType, tmp.innerHTML);
                    if (newType === 'checklist') nb.attrs.checked = false;
                    this.blocks.splice(index + 1, 0, nb);
                    this._render();
                    this._focusBlock(index + 1, 0);
                    this._markDirty();
                }
                return;
            }

            // Backspace at start → merge up
            if (e.key === 'Backspace') {
                const sel = window.getSelection();
                if (sel.isCollapsed && this._caretAtStart(el) && index > 0) {
                    e.preventDefault();
                    this._checkpoint();
                    this._syncBlock(index);
                    const prev = this.blocks[index - 1];
                    if (BLOCK_TYPES[prev.type]?.noContent) { this.blocks.splice(index - 1, 1); this._render(); this._focusBlock(Math.max(0, index - 1)); }
                    else {
                        const prevLen = (prev.content || '').length;
                        prev.content = (prev.content || '') + (this.blocks[index].content || '');
                        this.blocks.splice(index, 1);
                        this._render();
                        this._focusBlock(index - 1, prevLen);
                    }
                    this._markDirty();
                }
            }

            // Arrow up/down → navigate blocks
            if (e.key === 'ArrowUp' && index > 0 && this._caretAtStart(el)) { e.preventDefault(); this._focusBlock(index - 1, 'end'); }
            if (e.key === 'ArrowDown' && index < this.blocks.length - 1 && this._caretAtEnd(el)) { e.preventDefault(); this._focusBlock(index + 1, 0); }

            // Tab → indent (lists only — change to sub-type for now just prevent default)
            if (e.key === 'Tab') { e.preventDefault(); }
        }

        _handleInput(el, index) {
            this.blocks[index].content = el.innerHTML;
            this._markDirty();

            // ── Markdown shortcuts (like Notion) ──────────────────────
            // Note: contentEditable inserts \u00a0 (non-breaking space)
            // instead of regular space, so we use a character class [ \u00a0]
            if (this.blocks[index].type === 'paragraph') {
                const plain = el.textContent;
                const S = '[ \\u00a0]';  // matches both regular and non-breaking space
                const shortcuts = [
                    { pattern: new RegExp('^#' + S + '$'),         type: 'heading1' },
                    { pattern: new RegExp('^##' + S + '$'),        type: 'heading2' },
                    { pattern: new RegExp('^###' + S + '$'),       type: 'heading3' },
                    { pattern: new RegExp('^-' + S + '$'),         type: 'bullet_list' },
                    { pattern: new RegExp('^\\*' + S + '$'),       type: 'bullet_list' },
                    { pattern: new RegExp('^1\\.' + S + '$'),      type: 'numbered_list' },
                    { pattern: new RegExp('^>' + S + '$'),         type: 'quote' },
                    { pattern: new RegExp('^\\[\\]' + S + '$'),    type: 'checklist' },
                    { pattern: new RegExp('^\\[' + S + '\\]' + S + '$'), type: 'checklist' },
                    { pattern: /^---[\s\u00a0]?$/,                 type: 'divider' },
                ];
                for (const sc of shortcuts) {
                    if (sc.pattern.test(plain)) {
                        this._checkpoint();
                        el.innerHTML = '';
                        this.blocks[index].content = '';
                        if (sc.type === 'checklist') this.blocks[index].attrs.checked = false;
                        this.blocks[index].type = sc.type;
                        this._render();
                        this._focusBlock(index);
                        this._markDirty();
                        return;
                    }
                }
            }

            // Slash command detection
            const text = el.textContent;
            const pos = this._getCaretPos(el);
            const before = text.substring(0, pos);
            const match = before.match(/\/(\w*)$/);
            if (match) {
                this._slashIdx = index;
                this._slashSelIdx = 0;
                const query = match[1].toLowerCase();
                this._slashFiltered = SLASH_COMMANDS.filter(c => c.cmd.substring(1).includes(query) || c.label.toLowerCase().includes(query));
                if (this._slashFiltered.length) {
                    const rect = el.getBoundingClientRect();
                    this.slashMenuEl.style.top = (rect.bottom + window.scrollY + 4) + 'px';
                    this.slashMenuEl.style.left = Math.min(rect.left, window.innerWidth - 270) + 'px';
                    this._renderSlashItems();
                    this.slashMenuEl.classList.remove('hidden');
                    this._slashVisible = true;
                } else { this._hideSlashMenu(); }
            } else { this._hideSlashMenu(); }
        }

        // ── Slash menu ────────────────────────────────────────────────────
        _renderSlashItems() {
            this.slashMenuEl.innerHTML = this._slashFiltered.map((c, i) =>
                `<div class="slash-item flex items-center gap-3 px-3 py-2 cursor-pointer rounded-lg mx-1 transition-colors ${i === this._slashSelIdx ? 'bg-accent' : 'hover:bg-muted'}" data-idx="${i}">
                    <span class="w-8 h-8 flex items-center justify-center bg-muted rounded-lg text-sm font-medium">${c.icon}</span>
                    <div><div class="text-sm font-medium">${c.label}</div><div class="text-[11px] text-muted-foreground">${c.desc}</div></div>
                </div>`
            ).join('');
            this.slashMenuEl.querySelectorAll('.slash-item').forEach(el => {
                el.addEventListener('click', () => { this._slashSelIdx = +el.dataset.idx; this._executeSlash(this._slashIdx); });
            });
        }

        _executeSlash(blockIndex) {
            const cmd = this._slashFiltered[this._slashSelIdx];
            if (!cmd) return;
            // Remove slash text from both block data AND dom element
            // (so _syncBlock inside changeBlockType reads the cleaned value)
            const el = this._getContentEl(blockIndex);
            let cleaned = '';
            if (el) {
                const text = el.textContent;
                cleaned = text.replace(/\/\w*$/, '').trim();
                el.innerHTML = cleaned;
                this.blocks[blockIndex].content = cleaned;
            }
            this._checkpoint(); // snapshot before slash command changes block type
            if (!cleaned) {
                // Block is now empty — convert it in-place (skip changeBlockType
                // to avoid _syncBlock re-reading stale DOM)
                this.blocks[blockIndex].type = cmd.type;
                this.blocks[blockIndex].content = '';
                if (cmd.type === 'checklist') this.blocks[blockIndex].attrs.checked = false;
                this._render();
                this._focusBlock(blockIndex);
            } else {
                const nb = this._newBlock(cmd.type);
                if (cmd.type === 'checklist') nb.attrs.checked = false;
                this.blocks.splice(blockIndex + 1, 0, nb);
                this._render();
                this._focusBlock(blockIndex + 1);
            }
            this._hideSlashMenu();
            this._markDirty();
        }

        _hideSlashMenu() {
            this._slashVisible = false;
            this.slashMenuEl.classList.add('hidden');
        }

        // ── Block operations ──────────────────────────────────────────────
        addBlockAfter(index, type = 'paragraph', content = '', attrs = {}) {
            this._checkpoint();
            const nb = this._newBlock(type, content, attrs);
            this.blocks.splice(index + 1, 0, nb);
            this._render();
            this._focusBlock(index + 1);
            this._markDirty();
        }

        addBlockAtEnd() {
            const last = this.blocks[this.blocks.length - 1];
            if (last && !last.content && last.type === 'paragraph') { this._focusBlock(this.blocks.length - 1); return; }
            this.addBlockAfter(this.blocks.length - 1);
        }

        deleteBlock(index) {
            this._checkpoint();
            if (this.blocks.length <= 1) { this.blocks[0] = this._newBlock('paragraph'); this._render(); this._focusBlock(0); this._markDirty(); return; }
            this.blocks.splice(index, 1);
            this._render();
            this._focusBlock(Math.min(index, this.blocks.length - 1));
            this._markDirty();
        }

        changeBlockType(index, newType) {
            this._checkpoint();
            this._syncBlock(index);
            this.blocks[index].type = newType;
            if (newType === 'checklist' && this.blocks[index].attrs.checked === undefined) this.blocks[index].attrs.checked = false;
            this._render();
            this._focusBlock(index);
            this._markDirty();
        }

        duplicateBlock(index) {
            this._checkpoint();
            const copy = JSON.parse(JSON.stringify(this.blocks[index]));
            copy.id = this._uuid();
            this.blocks.splice(index + 1, 0, copy);
            this._render();
            this._focusBlock(index + 1);
            this._markDirty();
        }

        moveBlockUp(index) { if (index > 0) { this._checkpoint(); [this.blocks[index - 1], this.blocks[index]] = [this.blocks[index], this.blocks[index - 1]]; this._render(); this._focusBlock(index - 1); this._markDirty(); } }
        moveBlockDown(index) { if (index < this.blocks.length - 1) { this._checkpoint(); [this.blocks[index], this.blocks[index + 1]] = [this.blocks[index + 1], this.blocks[index]]; this._render(); this._focusBlock(index + 1); this._markDirty(); } }

        // ── Context menu ──────────────────────────────────────────────────
        _showCtxMenu(e, index) {
            const block = this.blocks[index];
            const items = [
                { label: '⬆ Move up',        action: () => this.moveBlockUp(index) },
                { label: '⬇ Move down',      action: () => this.moveBlockDown(index) },
                { label: '📋 Duplicate',      action: () => this.duplicateBlock(index) },
                { label: '🗑 Delete',         action: () => this.deleteBlock(index), cls: 'text-red-500' },
                '---',
                { label: '¶ Paragraph',       action: () => this.changeBlockType(index, 'paragraph') },
                { label: 'H1 Heading 1',      action: () => this.changeBlockType(index, 'heading1') },
                { label: 'H2 Heading 2',      action: () => this.changeBlockType(index, 'heading2') },
                { label: 'H3 Heading 3',      action: () => this.changeBlockType(index, 'heading3') },
                { label: '• Bullet list',     action: () => this.changeBlockType(index, 'bullet_list') },
                { label: '1. Number list',    action: () => this.changeBlockType(index, 'numbered_list') },
                { label: '☑ Checklist',       action: () => this.changeBlockType(index, 'checklist') },
                { label: '❝ Quote',           action: () => this.changeBlockType(index, 'quote') },
                '---',
                { label: '⭐ Mark Important', action: () => this.setBlockHighlight(index, 'important') },
                { label: '🔄 Mark Revise',    action: () => this.setBlockHighlight(index, 'revise') },
                { label: '📐 Mark Formula',   action: () => this.setBlockHighlight(index, 'formula') },
                { label: '❓ Mark Doubt',     action: () => this.setBlockHighlight(index, 'doubt') },
                { label: '✕ Clear mark',      action: () => this.setBlockHighlight(index, null) },
            ];

            this.ctxMenuEl.innerHTML = items.map(it => {
                if (it === '---') return '<div class="border-t border-border my-1"></div>';
                return `<button class="w-full text-left px-3 py-1.5 hover:bg-muted rounded-lg transition-colors ${it.cls || ''}" data-action="1">${it.label}</button>`;
            }).join('');

            let actionIdx = 0;
            this.ctxMenuEl.querySelectorAll('[data-action]').forEach(btn => {
                const item = items.filter(i => i !== '---')[actionIdx++];
                if (item) btn.addEventListener('click', () => { item.action(); this.ctxMenuEl.classList.add('hidden'); });
            });

            this.ctxMenuEl.style.top = e.clientY + 'px';
            this.ctxMenuEl.style.left = Math.min(e.clientX, window.innerWidth - 220) + 'px';
            this.ctxMenuEl.classList.remove('hidden');
        }

        // ── Highlight system ──────────────────────────────────────────────
        setBlockHighlight(index, type) {
            if (type) this.blocks[index].attrs.highlight_type = type;
            else delete this.blocks[index].attrs.highlight_type;
            this._render();
            this._focusBlock(index);
            this._markDirty();
        }

        showQuickRevision(filter) {
            document.getElementById('qr-menu').classList.add('hidden');
            const wrappers = this.editorEl.children;
            for (let i = 0; i < this.blocks.length; i++) {
                const b = this.blocks[i];
                let show = false;
                if (filter === 'heading') show = ['heading1','heading2','heading3'].includes(b.type);
                else if (filter === 'checklist') show = b.type === 'checklist';
                else show = b.attrs.highlight_type === filter;
                if (wrappers[i]) wrappers[i].classList.toggle('qr-dimmed', !show);
            }
        }

        exitQuickRevision() {
            document.getElementById('qr-menu').classList.add('hidden');
            Array.from(this.editorEl.children).forEach(el => el.classList.remove('qr-dimmed'));
        }

        // ── Inline formatting toolbar ─────────────────────────────────────
        // ── Cross-block drag selection ─────────────────────────────────────────────
        // Strategy: let mousedown happen naturally so browser sets focus, caret,
        // and keyboard context (Backspace / typing all work). We do NOT call
        // preventDefault on mousedown.
        //
        // Once the pointer actually moves (drag threshold ~4px), we call
        // e.preventDefault() on mousemove — this kills Chrome's confined-to-one-
        // contenteditable selection extension for that frame — and replace it with
        // setBaseAndExtent which crosses block boundaries freely.
        _setupCrossBlockSelect() {
            let anchor    = null;
            let lastCaret = null;
            let activeEl  = null;
            let pid       = null;
            let dragging  = false;
            let downX = 0, downY = 0;

            const caretAt = (x, y) => {
                if (document.caretRangeFromPoint) {
                    const r = document.caretRangeFromPoint(x, y);
                    return r ? { node: r.startContainer, offset: r.startOffset } : null;
                }
                if (document.caretPositionFromPoint) {
                    const p = document.caretPositionFromPoint(x, y);
                    return p ? { node: p.offsetNode, offset: p.offset } : null;
                }
                return null;
            };

            const ceOf = node => (node?.nodeType === Node.TEXT_NODE
                ? node.parentElement : node)?.closest('[contenteditable]');

            const allCE  = () => [...this.editorEl.querySelectorAll('[contenteditable]')];
            const freeze = () => allCE().forEach(el => { el._pe = el.style.pointerEvents; el.style.pointerEvents = 'none'; });
            const thaw   = () => allCE().forEach(el => { el.style.pointerEvents = el._pe ?? ''; delete el._pe; });

            this.editorEl.addEventListener('pointerdown', e => {
                if (e.button !== 0) return;
                activeEl  = e.target.closest('[contenteditable]') || e.currentTarget;
                pid       = e.pointerId;
                dragging  = false;
                lastCaret = null;
                downX     = e.clientX;
                downY     = e.clientY;
                anchor    = null;
                setTimeout(() => {
                    const sel = window.getSelection();
                    if (sel?.rangeCount) anchor = { node: sel.anchorNode, offset: sel.anchorOffset };
                }, 0);
            });

            document.addEventListener('pointermove', e => {
                if (!anchor || !activeEl || !(e.buttons & 1)) return;
                if (!dragging) {
                    const dx = e.clientX - downX, dy = e.clientY - downY;
                    if (dx * dx + dy * dy < 25) return;
                    dragging = true;
                    freeze();
                    try { activeEl.releasePointerCapture(pid); } catch (_) {}
                }
                const caret = caretAt(e.clientX, e.clientY);
                if (!caret || !this.editorEl.contains(caret.node)) return;
                lastCaret = caret;
                try {
                    window.getSelection()?.setBaseAndExtent(
                        anchor.node, anchor.offset, caret.node, caret.offset
                    );
                } catch (_) {}
            });

            document.addEventListener('pointerup', () => {
                if (dragging) {
                    thaw();
                    // After thaw, focus the anchor CE so keyboard events fire,
                    // then immediately re-apply the cross-block selection (focus
                    // collapses it, the nested setTimeout re-extends it).
                    const a = anchor, lc = lastCaret;
                    if (a && lc) {
                        const anchorCE = ceOf(a.node);
                        if (anchorCE) {
                            anchorCE.focus({ preventScroll: true });
                            setTimeout(() => {
                                try {
                                    window.getSelection()?.setBaseAndExtent(
                                        a.node, a.offset, lc.node, lc.offset
                                    );
                                } catch (_) {}
                            }, 0);
                        }
                    }
                }
                anchor = null; lastCaret = null; activeEl = null; pid = null; dragging = false;
            });

            // Handle keyboard ops when selection spans multiple blocks.
            document.addEventListener('keydown', e => {
                if (this.readOnly) return;
                const sel = window.getSelection();
                if (!sel || sel.isCollapsed) return;

                // Walk up from the TEXT node to find the block wrapper with data-index
                const wrapOf = node => {
                    let el = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
                    while (el && !el.dataset?.index) el = el.parentElement;
                    return el;
                };
                const anchorWrap = wrapOf(sel.anchorNode);
                const focusWrap  = wrapOf(sel.focusNode);
                if (!anchorWrap || !focusWrap) return;
                const aIdx = +anchorWrap.dataset.index;
                const fIdx = +focusWrap.dataset.index;
                if (aIdx === fIdx) return; // single block — native handler takes care of it

                const startIdx = Math.min(aIdx, fIdx);
                const endIdx   = Math.max(aIdx, fIdx);

                const isCtrl   = e.ctrlKey || e.metaKey;
                const isDelete = e.key === 'Backspace' || e.key === 'Delete';
                const isCut    = isCtrl && e.key === 'x';
                const isCopy   = isCtrl && e.key === 'c';
                // Printable: single visible character, no ctrl/meta/alt
                const isPrintable = e.key.length === 1 && !isCtrl && !e.altKey;

                // Ctrl+C: copy selected block text without deleting
                if (isCopy) {
                    const lines = [];
                    for (let i = startIdx; i <= endIdx; i++) {
                        const ce = this._getContentEl(i);
                        if (ce) lines.push(ce.textContent);
                    }
                    navigator.clipboard?.writeText(lines.join('\n')).catch(() => {});
                    return;
                }

                if (!isDelete && !isCut && !isPrintable) return; // let Ctrl+Z, arrows etc. pass through

                e.preventDefault();

                this._checkpoint(); // snapshot before cross-block delete

                // Compute keepStart / keepEnd from the live DOM before syncing
                const startCE = this._getContentEl(startIdx);
                const endCE   = this._getContentEl(endIdx);
                let keepStart = '', keepEnd = '';
                try {
                    const sNode   = aIdx <= fIdx ? sel.anchorNode : sel.focusNode;
                    const sOff    = aIdx <= fIdx ? sel.anchorOffset : sel.focusOffset;
                    const eNode   = aIdx <= fIdx ? sel.focusNode   : sel.anchorNode;
                    const eOff    = aIdx <= fIdx ? sel.focusOffset  : sel.anchorOffset;
                    if (startCE) {
                        const r = document.createRange();
                        r.selectNodeContents(startCE);
                        r.setEnd(sNode, sOff);
                        keepStart = startCE.textContent.slice(0, r.toString().length);
                    }
                    if (endCE) {
                        const r = document.createRange();
                        r.selectNodeContents(endCE);
                        r.setStart(eNode, eOff);
                        keepEnd = endCE.textContent.slice(endCE.textContent.length - r.toString().length);
                    }
                } catch (_) {}

                // Ctrl+X: copy selected text to clipboard first
                if (isCut) {
                    const lines = [];
                    for (let i = startIdx; i <= endIdx; i++) {
                        const ce = this._getContentEl(i);
                        if (ce) lines.push(ce.textContent);
                    }
                    navigator.clipboard?.writeText(lines.join('\n')).catch(() => {});
                }

                const insertChar = isPrintable ? e.key : '';
                this.blocks[startIdx].content = keepStart + insertChar + keepEnd;
                this.blocks.splice(startIdx + 1, endIdx - startIdx);

                this._render();
                this._focusBlock(startIdx, keepStart.length + insertChar.length);
                this._markDirty();
            });
        }

        _setupSelectionWatch() {
            document.addEventListener('selectionchange', () => {
                if (this.readOnly) return;
                const sel = window.getSelection();
                if (!sel || !sel.rangeCount || sel.isCollapsed) { this._hideInlineToolbar(); return; }
                const inEditor = this.editorEl.contains(sel.anchorNode) || this.editorEl.contains(sel.focusNode);
                if (!inEditor) { this._hideInlineToolbar(); return; }
                const range = sel.getRangeAt(0);
                const rect = range.getBoundingClientRect();
                if (rect.width < 2) { this._hideInlineToolbar(); return; }

                // inline toolbar is `position: fixed`, so use viewport coords directly
                const top = Math.max(8, rect.top - 44);
                const left = Math.min(window.innerWidth - 16, Math.max(16, rect.left + rect.width / 2));
                this.inlineToolbarEl.style.top  = `${top}px`;
                this.inlineToolbarEl.style.left = `${left}px`;
                this.inlineToolbarEl.classList.remove('hidden');
            });
        }

        _hideInlineToolbar() {
            this.inlineToolbarEl.classList.add('hidden');
            document.getElementById('txt-color-picker')?.classList.add('hidden');
        }



        applyFormat(cmd) {
            if (cmd === 'code') {
                // Wrap selection in <code>
                const sel = window.getSelection();
                if (!sel.rangeCount) return;
                const range = sel.getRangeAt(0);
                const code = document.createElement('code');
                code.className = 'bg-muted px-1 py-0.5 rounded text-xs font-mono';
                range.surroundContents(code);
            } else {
                document.execCommand(cmd, false, null);
            }
            this._markDirty();
        }

        promptLink() {
            const url = prompt('Enter URL:');
            if (url) document.execCommand('createLink', false, url);
            this._markDirty();
        }

        applyHighlightColor(color) {
            if (color) document.execCommand('hiliteColor', false, color);
            else document.execCommand('removeFormat', false, null);
            this._markDirty();
        }

        applyTextColor(color) {
            // Close picker
            document.getElementById('txt-color-picker')?.classList.add('hidden');
            if (color) {
                document.execCommand('foreColor', false, color);
                const bar = document.getElementById('txt-color-bar');
                if (bar) bar.style.background = color;
            } else {
                // Restore default: wrap in a span that inherits color
                const sel = window.getSelection();
                if (sel && sel.rangeCount) {
                    const range = sel.getRangeAt(0);
                    const span = document.createElement('span');
                    span.style.color = '';
                    range.surroundContents(span);
                }
                const bar = document.getElementById('txt-color-bar');
                if (bar) bar.style.background = '#a3a3a3';
            }
            this._markDirty();
        }

        // ── Auto-save ────────────────────────────────────────────────────
        _setupAutoSave() {
            // Periodic save
            setInterval(() => { if (this.isDirty && !this.isSaving) this._save(false); }, 5000);
            // Version snapshot every 5 minutes
            setInterval(() => { if (Date.now() - this._lastVersionTs > 300000 && this.isDirty) { this._save(true); this._lastVersionTs = Date.now(); } }, 60000);
            // Save on blur
            window.addEventListener('blur', () => { if (this.isDirty) this._save(false); });
            // Warn unsaved on navigate
            window.addEventListener('beforeunload', e => { if (this.isDirty) { e.preventDefault(); e.returnValue = ''; } });
        }

        _markDirty() {
            this.isDirty = true;
            this._updateStatus('Unsaved', 'dirty');
            // Debounced snapshot for typing (800 ms of inactivity)
            clearTimeout(this._undoTimer);
            this._undoTimer = setTimeout(() => this._pushUndo(), 800);
        }

        // Push current block state onto the undo stack immediately.
        // Call this BEFORE any structural change (delete, type-change, etc.).
        _checkpoint() {
            clearTimeout(this._undoTimer);
            this._pushUndo();
        }

        _pushUndo() {
            this._syncAllBlocks();
            const snap = JSON.stringify(this.blocks);
            // Avoid duplicate consecutive entries
            if (this._undoStack.length && this._undoStack[this._undoStack.length - 1] === snap) return;
            this._undoStack.push(snap);
            if (this._undoStack.length > 100) this._undoStack.shift();
            // Any new change invalidates the redo stack
            this._redoStack = [];
        }

        _undo() {
            this._syncAllBlocks();
            // Need at least 2 entries: one for 'before', one for 'current'
            if (this._undoStack.length < 2) return;
            const current = JSON.stringify(this.blocks);
            // Push current state to redo (if not already there)
            if (!this._redoStack.length || this._redoStack[this._redoStack.length - 1] !== current) {
                this._redoStack.push(current);
            }
            this._undoStack.pop(); // discard current top (which matches current state)
            const prev = this._undoStack[this._undoStack.length - 1];
            this.blocks = JSON.parse(prev);
            this._render();
            this._focusBlock(Math.min(this._activeIdx ?? 0, this.blocks.length - 1));
        }

        _redo() {
            if (!this._redoStack.length) return;
            this._syncAllBlocks();
            const snap = JSON.stringify(this.blocks);
            this._undoStack.push(snap);
            const next = this._redoStack.pop();
            this.blocks = JSON.parse(next);
            this._render();
            this._focusBlock(Math.min(this._activeIdx ?? 0, this.blocks.length - 1));
        }

        async _save(createVersion = false) {
            if (this.isSaving) return;
            this._syncAllBlocks();
            const data = JSON.stringify(this.blocks);
            if (data === this._lastSavedStr && !createVersion) { this.isDirty = false; this._updateStatus('Saved', 'saved'); return; }
            this.isSaving = true;
            this._updateStatus('Saving…', 'saving');
            try {
                const r = await fetch(this.saveUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                    body: JSON.stringify({ note_id: this.noteId, blocks: { blocks: this.blocks }, create_version: createVersion }),
                });
                const j = await r.json();
                if (j.success) { this.isDirty = false; this._lastSavedStr = data; this._updateStatus('Saved', 'saved'); }
                else this._updateStatus('Error', 'error');
            } catch { this._updateStatus('Offline', 'error'); }
            finally { this.isSaving = false; }
        }

        _updateStatus(text, type) {
            if (!this.statusEl) return;
            this.statusEl.textContent = text;
            this.statusEl.className = 'text-xs mr-1 hidden sm:inline ' + ({ saved: 'text-emerald-500', saving: 'text-muted-foreground', dirty: 'text-amber-500', error: 'text-red-500' }[type] || 'text-muted-foreground');
        }

        // ── Search ────────────────────────────────────────────────────────
        toggleSearch() {
            this._searchOpen = !this._searchOpen;
            this.searchPanelEl.classList.toggle('hidden', !this._searchOpen);
            if (this._searchOpen) { this.searchInputEl.value = ''; this.searchInputEl.focus(); this._clearSearchHL(); }
            else this._clearSearchHL();
            this.searchInputEl.addEventListener('input', () => this._doSearch(this.searchInputEl.value));
        }

        _doSearch(q) {
            this._clearSearchHL();
            if (!q.trim()) { this.searchCountEl.textContent = ''; this._searchMatches = []; return; }
            const query = q.toLowerCase();
            this._searchMatches = [];
            this.editorEl.querySelectorAll('.block-content, pre.block-content, [contenteditable]').forEach(el => {
                if (el.textContent.toLowerCase().includes(query)) this._searchMatches.push(el);
            });
            this._searchMatches.forEach(el => el.style.outline = '2px solid hsl(var(--ring))');
            this._searchCur = this._searchMatches.length ? 0 : -1;
            this.searchCountEl.textContent = this._searchMatches.length ? `${this._searchCur + 1}/${this._searchMatches.length}` : 'No results';
            if (this._searchCur >= 0) this._searchMatches[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        searchNext() { if (!this._searchMatches.length) return; this._searchCur = (this._searchCur + 1) % this._searchMatches.length; this._jumpSearch(); }
        searchPrev() { if (!this._searchMatches.length) return; this._searchCur = (this._searchCur - 1 + this._searchMatches.length) % this._searchMatches.length; this._jumpSearch(); }

        _jumpSearch() {
            this._searchMatches.forEach((el, i) => el.style.outline = i === this._searchCur ? '2px solid hsl(var(--ring))' : '1px dashed hsl(var(--border))');
            this._searchMatches[this._searchCur].scrollIntoView({ behavior: 'smooth', block: 'center' });
            this.searchCountEl.textContent = `${this._searchCur + 1}/${this._searchMatches.length}`;
        }

        _clearSearchHL() { this.editorEl.querySelectorAll('[style*="outline"]').forEach(el => el.style.outline = ''); }

        // ── Mode toggles ─────────────────────────────────────────────────
        toggleReadMode() {
            if (this.isDirty) this._save(false);
            this.readOnly = !this.readOnly;
            this.editorEl.parentElement.classList.toggle('read-mode', this.readOnly);
            document.getElementById('mode-icon-edit').classList.toggle('hidden', this.readOnly);
            document.getElementById('mode-icon-read').classList.toggle('hidden', !this.readOnly);
            document.getElementById('add-block-area').classList.toggle('hidden', this.readOnly);
            this._render();
        }

        toggleFocusMode() {
            this.focusMode = !this.focusMode;
            document.body.classList.toggle('focus-mode', this.focusMode);
        }

        // ── Markdown parser for pasted content ────────────────────────────
        _parseMarkdownToBlocks(text) {
            const blocks = [];
            const lines = text.split('\n');
            let i = 0;

            while (i < lines.length) {
                const line = lines[i];
                const trimmed = line.trim();

                // Skip empty lines
                if (!trimmed) { i++; continue; }

                // Fenced math block:  $$ … $$
                if (trimmed === '$$') {
                    i++;
                    const mathLines = [];
                    while (i < lines.length && lines[i].trim() !== '$$') { mathLines.push(lines[i]); i++; }
                    if (lines[i]?.trim() === '$$') i++; // consume closing $$
                    blocks.push(this._newBlock('formula', mathLines.join('\n').trim()));
                    continue;
                }

                // Bracket math block (Notion export):  [  … ]
                // A lone '[' or '\[' on its own line starts a display math block
                if (trimmed === '[' || trimmed === '\\[') {
                    const closing = trimmed === '[' ? ']' : '\\]';
                    i++;
                    const mathLines = [];
                    while (i < lines.length && lines[i].trim() !== closing) { mathLines.push(lines[i]); i++; }
                    if (lines[i]?.trim() === closing) i++;
                    const latex = mathLines.join('\n').trim();
                    if (latex) blocks.push(this._newBlock('formula', latex));
                    continue;
                }

                // Fenced code block:  ```lang … ```
                const codeFenceMatch = trimmed.match(/^```(\w*)$/);
                if (codeFenceMatch) {
                    const lang = codeFenceMatch[1] || 'plain';
                    i++;
                    const codeLines = [];
                    while (i < lines.length && lines[i].trim() !== '```') { codeLines.push(lines[i]); i++; }
                    if (lines[i]?.trim() === '```') i++;
                    const nb = this._newBlock('code', codeLines.join('\n'));
                    nb.attrs.language = lang;
                    blocks.push(nb);
                    continue;
                }

                // Divider (---, ___, ***)
                if (/^(-{3,}|_{3,}|\*{3,})$/.test(trimmed)) {
                    blocks.push(this._newBlock('divider'));
                    i++;
                    continue;
                }

                // Heading
                const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
                if (headingMatch) {
                    const level = headingMatch[1].length;
                    blocks.push(this._newBlock(`heading${level}`, this._parseInlineMarkdown(headingMatch[2])));
                    i++;
                    continue;
                }

                // Checklist:  - [ ] text  or  - [x] text
                const checklistMatch = trimmed.match(/^[-*]\s*\[\s*([xX ]?)\s*\]\s+(.+)$/);
                if (checklistMatch) {
                    const checked = /[xX]/.test(checklistMatch[1]);
                    const block = this._newBlock('checklist', this._parseInlineMarkdown(checklistMatch[2]));
                    block.attrs.checked = checked;
                    blocks.push(block);
                    i++;
                    continue;
                }

                // Bullet list
                const bulletMatch = trimmed.match(/^[-*]\s+(.+)$/);
                if (bulletMatch) {
                    blocks.push(this._newBlock('bullet_list', this._parseInlineMarkdown(bulletMatch[1])));
                    i++;
                    continue;
                }

                // Numbered list
                const numberedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
                if (numberedMatch) {
                    blocks.push(this._newBlock('numbered_list', this._parseInlineMarkdown(numberedMatch[1])));
                    i++;
                    continue;
                }

                // Image  ![alt](url)
                const imgMatch = trimmed.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
                if (imgMatch) {
                    const nb = this._newBlock('image', '', { url: imgMatch[2], caption: imgMatch[1] || '', align: 'left' });
                    blocks.push(nb);
                    i++;
                    continue;
                }

                // Quote
                const quoteMatch = trimmed.match(/^>\s+(.+)$/);
                if (quoteMatch) {
                    blocks.push(this._newBlock('quote', this._parseInlineMarkdown(quoteMatch[1])));
                    i++;
                    continue;
                }

                // Default: paragraph
                blocks.push(this._newBlock('paragraph', this._parseInlineMarkdown(trimmed)));
                i++;
            }

            return blocks;
        }

        // Parse inline markdown → HTML  (bold, italic, strikethrough, inline-code, links, inline math)
        _parseInlineMarkdown(text) {
            // Inline code first (avoid mangling * inside backticks)
            text = text.replace(/`([^`]+)`/g, '<code class="bg-muted px-1 py-0.5 rounded text-xs font-mono">$1</code>');
            // Bold  **text**  or  __text__
            text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            text = text.replace(/__(.+?)__/g, '<strong>$1</strong>');
            // Italic  *text*  or  _text_  (single asterisk/underscore)
            text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
            text = text.replace(/_([^_]+)_/g, '<em>$1</em>');
            // Strikethrough  ~~text~~
            text = text.replace(/~~(.+?)~~/g, '<s>$1</s>');
            // Inline math  $...$ or ( \latex )
            text = text.replace(/\$([^$\n]+)\$/g, (_, tex) => this._inlineKatex(tex));
            // Notion-style inline math wrapped in ( ... )
            // Handles: ( \hbar ), ( \hat{H} ), ( |\psi|^2 ), ( i ), ( m ), ( V ) etc.
            text = text.replace(/\(\s*([^()]{1,50})\s*\)/g, (match, inner) => {
                const t = inner.trim();
                // Has a LaTeX command like \hbar, \hat{H}, \nabla
                if (/\\[a-zA-Z]/.test(t)) return this._inlineKatex(t);
                // Single math variable letter: ( i ), ( m ), ( V ), ( E ), ( x )
                if (/^[A-Za-z]$/.test(t)) return this._inlineKatex(t);
                // Short math expression with operators: ( x^2 ), ( a_0 ), ( F = ma )
                if (t.length <= 15 && /[\^_|=]/.test(t)) return this._inlineKatex(t);
                return match; // leave plain English parentheses alone
            });
            // Links  [text](url)
            text = text.replace(/\[([^\]]*)\]\(([^)]+)\)/g, (_, linkText, url) => {
                let display = linkText.trim();
                if (!display) { try { display = new URL(url).hostname; } catch { display = url; } }
                return `<a href="${url}" target="_blank" class="text-blue-500 underline cursor-pointer">${display}</a>`;
            });
            return text;
        }

        // Render a single inline KaTeX expression, fallback to raw text
        _inlineKatex(tex) {
            if (typeof katex !== 'undefined') {
                try { return katex.renderToString(tex, { displayMode: false, throwOnError: false }); } catch {}
            }
            return `<span class="font-mono text-xs">\$${tex}\$</span>`;
        }

        // Keep alias so any remaining callers don't break
        _parseInlineLinks(text) { return this._parseInlineMarkdown(text); }

        // ── Image upload (paste / drag & drop / file) ─────────────────────
        _setupPasteAndDrop() {
            this.editorEl.addEventListener('paste', e => {
                const items = e.clipboardData?.items;
                if (!items) return;
                
                // Check for images first
                for (const item of items) {
                    if (item.type.startsWith('image/')) {
                        e.preventDefault();
                        this._handleImageUpload(item.getAsFile(), this._activeIdx ?? this.blocks.length - 1);
                        return;
                    }
                }
                
                // Check for text (markdown parsing)
                for (const item of items) {
                    if (item.type === 'text/plain') {
                        e.preventDefault(); // must be synchronous — getAsString is async
                        item.getAsString(text => {
                            if (!text) return;
                            const isMultiLine = text.includes('\n');
                            const looksLikeMarkdown = /^[#\-*>]|^\d+\.\s|\[ \]|\[x\]|^\$\$|^```|^\[$|^\\\[/im.test(text);

                            if (isMultiLine || looksLikeMarkdown) {
                                const blocks = this._parseMarkdownToBlocks(text);
                                if (blocks.length) {
                                    this._checkpoint();
                                    const afterIndex = this._activeIdx ?? this.blocks.length - 1;
                                    this.blocks.splice(afterIndex + 1, 0, ...blocks);
                                    this._render();
                                    this._focusBlock(afterIndex + 1);
                                    this._markDirty();
                                    return;
                                }
                            }

                            // Single-line plain text: insert at cursor in active contenteditable
                            const active = this.editorEl.querySelector('[contenteditable]:focus');
                            if (active) {
                                document.execCommand('insertText', false, text);
                            } else {
                                // No focused element – append as paragraph
                                this._checkpoint();
                                const afterIndex = this._activeIdx ?? this.blocks.length - 1;
                                this.blocks.splice(afterIndex + 1, 0, this._newBlock('paragraph', text.trim()));
                                this._render();
                                this._focusBlock(afterIndex + 1);
                                this._markDirty();
                            }
                        });
                        return;
                    }
                }
            });
            this.editorEl.addEventListener('dragover', e => e.preventDefault());
            this.editorEl.addEventListener('drop', e => {
                e.preventDefault();
                const file = e.dataTransfer?.files?.[0];
                if (file && file.type.startsWith('image/')) {
                    this._handleImageUpload(file, this._activeIdx ?? this.blocks.length - 1);
                }
            });
        }

        async _handleImageUpload(file, afterIndex) {
            // Show a local blob preview immediately so the user sees the image at once
            const blobUrl = URL.createObjectURL(file);
            const nb = this._newBlock('image', '', { url: blobUrl, caption: '', align: 'left', uploading: true });
            this.blocks.splice(afterIndex + 1, 0, nb);
            this._render();
            this._markDirty();

            const insertedIdx = afterIndex + 1;

            // Upload in background; when done, swap blob URL for real URL
            const form = new FormData();
            form.append('image', file);
            try {
                const r = await fetch(this.uploadUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': this.csrfToken },
                    body: form,
                });
                const j = await r.json();
                if (j.success) {
                    // Find the block (index may have shifted)
                    const idx = this.blocks.findIndex(b => b.attrs?.url === blobUrl);
                    if (idx !== -1) {
                        this.blocks[idx].attrs.url = j.url;
                        delete this.blocks[idx].attrs.uploading;
                        this._render();
                        this._markDirty();
                    }
                } else {
                    // Remove the preview block on failure
                    const idx = this.blocks.findIndex(b => b.attrs?.url === blobUrl);
                    if (idx !== -1) this.blocks.splice(idx, 1);
                    this._render();
                    alert(j.error || 'Upload failed');
                }
            } catch {
                const idx = this.blocks.findIndex(b => b.attrs?.url === blobUrl);
                if (idx !== -1) this.blocks.splice(idx, 1);
                this._render();
                alert('Image upload failed');
            } finally {
                URL.revokeObjectURL(blobUrl);
            }
        }

        // ── Version history ───────────────────────────────────────────────
        async showVersionHistory() {
            const modal = document.getElementById('version-modal');
            const list = document.getElementById('version-list');
            modal.classList.remove('hidden');
            list.innerHTML = '<p class="text-sm text-muted-foreground text-center py-8">Loading…</p>';
            try {
                const r = await fetch(this.versionsUrl, { headers: { 'X-CSRFToken': this.csrfToken } });
                const j = await r.json();
                if (!j.success || !j.versions.length) { list.innerHTML = '<p class="text-sm text-muted-foreground text-center py-8">No versions saved yet</p>'; return; }
                list.innerHTML = j.versions.map(v => {
                    const d = new Date(v.created_at);
                    return `<div class="flex items-center justify-between py-2 border-b border-border last:border-0">
                        <span class="text-sm">${d.toLocaleDateString()} ${d.toLocaleTimeString()}</span>
                        <button class="text-xs px-3 py-1 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90" onclick="editor.restoreVersion(${v.id})">Restore</button>
                    </div>`;
                }).join('');
            } catch { list.innerHTML = '<p class="text-sm text-red-500 text-center py-8">Failed to load</p>'; }
        }

        async restoreVersion(versionId) {
            if (!confirm('Restore this version? Current note will be saved as a version first.')) return;
            try {
                const r = await fetch(this.restoreBaseUrl + versionId + '/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                    body: '{}',
                });
                const j = await r.json();
                if (j.success) {
                    this.blocks = j.blocks.blocks || j.blocks;
                    this._render();
                    this._focusBlock(0);
                    this._lastSavedStr = JSON.stringify(this.blocks);
                    this.isDirty = false;
                    document.getElementById('version-modal').classList.add('hidden');
                    this._updateStatus('Restored', 'saved');
                } else { alert(j.error || 'Restore failed'); }
            } catch { alert('Restore failed'); }
        }

        // ── Global keyboard shortcuts ─────────────────────────────────────
        _setupGlobalKeys() {
            document.addEventListener('keydown', e => {
                const isCtrlCmd = e.ctrlKey || e.metaKey;
                const inEditor  = this.editorEl.contains(document.activeElement);

                // Ctrl+Z → undo
                if (isCtrlCmd && e.key === 'z' && !e.shiftKey) { e.preventDefault(); this._undo(); return; }

                // Ctrl+Y / Ctrl+Shift+Z → redo
                if (isCtrlCmd && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) { e.preventDefault(); this._redo(); return; }

                // Ctrl+S → save with version
                if (isCtrlCmd && e.key === 's') { e.preventDefault(); this._save(true); }

                // Ctrl+F → search
                if (isCtrlCmd && e.key === 'f' && inEditor) { e.preventDefault(); this.toggleSearch(); }

                // Ctrl+D → duplicate current block
                if (isCtrlCmd && e.key === 'd' && inEditor) {
                    e.preventDefault();
                    const idx = this._activeIdx ?? 0;
                    const copy = JSON.parse(JSON.stringify(this.blocks[idx]));
                    copy.id = this._uuid();
                    this.blocks.splice(idx + 1, 0, copy);
                    this._render();
                    this._focusBlock(idx + 1);
                    this._markDirty();
                }

                // Ctrl+A → select all text across all blocks
                if (isCtrlCmd && e.key === 'a' && inEditor) {
                    e.preventDefault();
                    const allCE = [...this.editorEl.querySelectorAll('[contenteditable="true"]')];
                    if (!allCE.length) return;
                    const first = allCE[0], last = allCE[allCE.length - 1];
                    // Find deepest first/last text nodes
                    const firstNode = (el => { while (el.firstChild) el = el.firstChild; return el; })(first);
                    const lastNode  = (el => { while (el.lastChild)  el = el.lastChild;  return el; })(last);
                    try {
                        window.getSelection()?.setBaseAndExtent(firstNode, 0, lastNode, lastNode.textContent?.length ?? 0);
                    } catch (_) {}
                }
            });

            // Close menus on outside click
            document.addEventListener('click', e => {
                if (!this.slashMenuEl.contains(e.target)) this._hideSlashMenu();
                if (!this.ctxMenuEl.contains(e.target) && !e.target.classList.contains('block-menu-btn')) this.ctxMenuEl.classList.add('hidden');
            });
        }

        // ── DOM sync helpers ──────────────────────────────────────────────
        _syncBlock(index) {
            const el = this._getContentEl(index);
            if (!el) return;
            const b = this.blocks[index];
            if (b.type === 'code') { const pre = this.editorEl.children[index]?.querySelector('pre'); if (pre) b.content = pre.textContent; }
            else if (b.type === 'formula') { const ta = this.editorEl.children[index]?.querySelector('textarea'); if (ta) b.content = ta.value; }
            else if (b.type === 'checklist') {
                const txt = this.editorEl.children[index]?.querySelector('.block-content');
                const cb = this.editorEl.children[index]?.querySelector('input[type="checkbox"]');
                if (txt) b.content = txt.innerHTML; if (cb) b.attrs.checked = cb.checked;
            } else if (el.isContentEditable) { b.content = el.innerHTML; }
        }

        _syncAllBlocks() { for (let i = 0; i < this.blocks.length; i++) this._syncBlock(i); }

        _getContentEl(index) {
            const wrap = this.editorEl.children[index];
            if (!wrap) return null;
            return wrap.querySelector('.block-content') || wrap.querySelector('[contenteditable="true"]') || wrap.querySelector('pre');
        }

        _focusBlock(index, position = 0) {
            requestAnimationFrame(() => {
                const el = this._getContentEl(index);
                if (!el) return;
                el.focus();
                if (!el.isContentEditable && !el.contentEditable) return;
                try {
                    const sel = window.getSelection();
                    const range = document.createRange();
                    if (position === 'end') {
                        range.selectNodeContents(el);
                        range.collapse(false);
                    } else if (typeof position === 'number' && position > 0) {
                        // Approximate: set to end if position is big
                        range.selectNodeContents(el);
                        range.collapse(position > (el.textContent || '').length);
                    } else {
                        range.selectNodeContents(el);
                        range.collapse(true);
                    }
                    sel.removeAllRanges();
                    sel.addRange(range);
                } catch (e) { /* ok */ }
            });
        }

        // ── Caret helpers ─────────────────────────────────────────────────
        _caretAtStart(el) {
            const sel = window.getSelection();
            if (!sel.isCollapsed) return false;
            const range = sel.getRangeAt(0);
            const pre = range.cloneRange();
            pre.selectNodeContents(el);
            pre.setEnd(range.startContainer, range.startOffset);
            return pre.toString().length === 0;
        }

        _caretAtEnd(el) {
            const sel = window.getSelection();
            if (!sel.isCollapsed) return false;
            const range = sel.getRangeAt(0);
            const post = range.cloneRange();
            post.selectNodeContents(el);
            post.setStart(range.endContainer, range.endOffset);
            return post.toString().length === 0;
        }

        _getCaretPos(el) {
            const sel = window.getSelection();
            if (!sel.rangeCount) return 0;
            const range = sel.getRangeAt(0);
            const pre = range.cloneRange();
            pre.selectNodeContents(el);
            pre.setEnd(range.startContainer, range.startOffset);
            return pre.toString().length;
        }

        // ── Utility ───────────────────────────────────────────────────────
        _uuid() { return crypto.randomUUID ? crypto.randomUUID() : 'xxxx-xxxx'.replace(/x/g, () => ((Math.random() * 16) | 0).toString(16)); }

        _ytId(url) { const m = (url || '').match(/(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([\w-]{11})/); return m ? m[1] : null; }

        _renderKatex(el, tex) {
            if (!tex || !tex.trim()) { el.innerHTML = '<span class="text-muted-foreground text-xs">Empty formula</span>'; return; }
            if (typeof katex !== 'undefined') { try { katex.render(tex, el, { displayMode: true, throwOnError: false }); } catch { el.textContent = tex; } }
            else { el.textContent = tex; }
        }
    }

    window.NoteEditor = NoteEditor;
})();
