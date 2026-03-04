/**
 * Reader search: toggle bar, PDF full-text search, native highlight search,
 * navigate between results, keyboard shortcuts (Ctrl+F / Escape).
 * Requires: window.pdfDocGlobal (set by reader-pdf-viewer.js).
 */
(function () {
    'use strict';

    var searchResults = [];
    var searchCurrentIdx = 0;
    var searchMode = 'pdf';

    function getSearchUi() {
        return {
            controls: document.getElementById('searchControls'),
            searchSpinner: document.getElementById('searchSpinner'),
            searchIcon: document.getElementById('searchIcon'),
            searchCount: document.getElementById('searchCount'),
        };
    }

    function clearNativeHighlights() {
        var container = document.getElementById('secure-content-container');
        var marks = document.querySelectorAll('mark.reader-search-hit');
        marks.forEach(function (mark) {
            var textNode = document.createTextNode(mark.textContent || '');
            mark.replaceWith(textNode);
        });
        if (container) container.normalize();
    }

    function escapeRegExp(value) {
        return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function buildNativeSearchResults(query) {
        searchResults = [];
        searchCurrentIdx = 0;

        var container = document.getElementById('secure-content-container');
        if (!container || !query) return;

        clearNativeHighlights();

        var walker = document.createTreeWalker(
            container,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function (node) {
                    if (!node || !node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
                    var parent = node.parentElement;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    var blocked = ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'MARK'];
                    if (blocked.includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        var textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);

        var regex = new RegExp(escapeRegExp(query), 'gi');
        textNodes.forEach(function (node) {
            var text = node.nodeValue || '';
            if (!regex.test(text)) {
                regex.lastIndex = 0;
                return;
            }
            regex.lastIndex = 0;

            var fragment = document.createDocumentFragment();
            var lastIndex = 0;
            var match;
            while ((match = regex.exec(text)) !== null) {
                var before = text.slice(lastIndex, match.index);
                if (before) fragment.appendChild(document.createTextNode(before));

                var hit = document.createElement('mark');
                hit.className = 'reader-search-hit bg-yellow-300 text-black rounded px-0.5';
                hit.textContent = match[0];
                fragment.appendChild(hit);
                searchResults.push(hit);

                lastIndex = match.index + match[0].length;
            }

            var tail = text.slice(lastIndex);
            if (tail) fragment.appendChild(document.createTextNode(tail));

            node.parentNode.replaceChild(fragment, node);
        });
    }

    function showSearchState() {
        var ui = getSearchUi();
        var input = document.getElementById('pdfSearchInput');
        var hasQuery = !!(input && input.value.trim());

        if (ui.controls) {
            if (hasQuery) ui.controls.classList.remove('hidden');
            else ui.controls.classList.add('hidden');
        }

        if (!ui.searchCount) return;
        if (!hasQuery || !searchResults.length) {
            ui.searchCount.innerText = '0/0';
            return;
        }

        ui.searchCount.innerText = (searchCurrentIdx + 1) + '/' + searchResults.length;
    }

    function toggleSearch() {
        var bar = document.getElementById('floatingSearchBar');
        var input = document.getElementById('pdfSearchInput');
        if (bar.classList.contains('opacity-0')) {
            bar.classList.remove('opacity-0', '-translate-y-4', 'pointer-events-none');
            bar.classList.add('translate-y-0');
            setTimeout(function () { input.focus(); }, 100);
        } else {
            closeSearch();
        }
    }

    function closeSearch() {
        var bar = document.getElementById('floatingSearchBar');
        bar.classList.add('opacity-0', '-translate-y-4', 'pointer-events-none');
        bar.classList.remove('translate-y-0');
        document.querySelectorAll('canvas').forEach(function (c) { c.style.boxShadow = ''; });
        clearNativeHighlights();
        searchResults = [];
        searchCurrentIdx = 0;
        showSearchState();
    }

    async function executeSearch() {
        var query = document.getElementById('pdfSearchInput').value.toLowerCase().trim();
        var ui = getSearchUi();

        if (!query) {
            document.querySelectorAll('canvas').forEach(function (c) { c.style.boxShadow = ''; });
            clearNativeHighlights();
            searchResults = [];
            searchCurrentIdx = 0;
            showSearchState();
            return;
        }

        if (ui.searchIcon) ui.searchIcon.classList.add('hidden');
        if (ui.searchSpinner) ui.searchSpinner.classList.remove('hidden');
        searchResults = [];
        searchCurrentIdx = 0;

        var hasPdfContainer = !!document.getElementById('pdf-container');
        if (hasPdfContainer && !window.pdfDocGlobal) {
            if (ui.controls) ui.controls.classList.remove('hidden');
            if (ui.searchCount) ui.searchCount.innerText = '...';
            return;
        }

        if (window.pdfDocGlobal) {
            searchMode = 'pdf';
            for (var i = 1; i <= window.pdfDocGlobal.numPages; i++) {
                try {
                    var page = await window.pdfDocGlobal.getPage(i);
                    var textContent = await page.getTextContent();
                    var pageText = textContent.items.map(function (item) { return item.str; }).join(' ').toLowerCase();
                    if (pageText.includes(query)) searchResults.push(i);
                } catch (e) {
                    console.error('Search error on page', i, e);
                }
            }
        } else {
            searchMode = 'native';
            buildNativeSearchResults(query);
        }

        if (ui.searchSpinner) ui.searchSpinner.classList.add('hidden');
        if (ui.searchIcon) ui.searchIcon.classList.remove('hidden');

        if (searchResults.length > 0) scrollToSearchResult(0);
        else showSearchState();
    }

    function scrollToSearchResult(idx) {
        if (searchResults.length === 0) return;
        searchCurrentIdx = idx;
        showSearchState();

        if (searchMode === 'pdf') {
            var canvas = document.getElementById('page-canvas-' + searchResults[idx]);
            if (canvas) {
                canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
                canvas.style.boxShadow = '0 0 0 8px #eab308';
                setTimeout(function () { canvas.style.boxShadow = ''; }, 2500);
            }
            return;
        }

        var active = searchResults[idx];
        if (active) {
            document.querySelectorAll('mark.reader-search-hit-active').forEach(function (el) {
                el.classList.remove('reader-search-hit-active', 'ring-2', 'ring-yellow-500');
            });
            active.classList.add('reader-search-hit-active', 'ring-2', 'ring-yellow-500');
            active.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    // Expose for toolbar onclick handlers
    window.toggleSearch = toggleSearch;
    window.closeSearch = closeSearch;
    window.executeSearch = executeSearch;
    window.nextSearchResult = function () {
        scrollToSearchResult(searchCurrentIdx < searchResults.length - 1 ? searchCurrentIdx + 1 : 0);
    };
    window.prevSearchResult = function () {
        scrollToSearchResult(searchCurrentIdx > 0 ? searchCurrentIdx - 1 : searchResults.length - 1);
    };

    document.addEventListener('DOMContentLoaded', function () {
        var searchInput = document.getElementById('pdfSearchInput');
        if (!searchInput) return;

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { executeSearch(); e.stopPropagation(); }
        });

        var debounceTimer;
        searchInput.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () { executeSearch(); }, 400);
        });

        document.addEventListener('keydown', function (e) {
            if ((e.ctrlKey || e.metaKey) && (e.key === 'f' || e.key === 'F')) {
                e.preventDefault();
                window.expandHeader();
                toggleSearch();
            }
            if (e.key === 'Escape') closeSearch();
        });

        window.addEventListener('readerPdfReady', function () {
            if (searchInput.value.trim()) executeSearch();
        });
    });
})();
