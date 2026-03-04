/**
 * Reader toolbar: collapse/expand header, zoom, page nav, cinema mode,
 * font size, eye-care tint, URL pseudo-slug, back-to-top.
 * Reads document title from <script id="reader-data">.
 */
(function () {
    'use strict';

    // ---------- Toolbar Collapse / Expand ----------

    function collapseHeader() {
        var header = document.getElementById('stickyHeader');
        var toggleBtn = document.getElementById('headerToggleBtn');
        header.style.overflow = 'hidden';
        header.style.height = '0px';
        header.style.paddingTop = '0px';
        header.style.paddingBottom = '0px';
        header.style.marginBottom = '0px';
        header.style.borderBottomWidth = '0px';
        header.style.opacity = '0';
        header.style.pointerEvents = 'none';
        toggleBtn.style.transform = 'translateY(0)';
        toggleBtn.style.opacity = '1';
        toggleBtn.style.pointerEvents = 'auto';
    }

    function expandHeader() {
        var header = document.getElementById('stickyHeader');
        var toggleBtn = document.getElementById('headerToggleBtn');
        header.style.height = 'auto';
        header.style.paddingTop = '';
        header.style.paddingBottom = '';
        header.style.marginBottom = '';
        header.style.borderBottomWidth = '';
        header.style.opacity = '1';
        header.style.overflow = '';
        header.style.pointerEvents = '';
        toggleBtn.style.transform = '';
        toggleBtn.style.opacity = '0';
        toggleBtn.style.pointerEvents = 'none';
    }

    // Expose for other modules
    window.collapseHeader = collapseHeader;
    window.expandHeader = expandHeader;

    // ---------- Zoom Controls ----------

    window.currentZoom = 100;

    function applyZoom() {
        document.getElementById('zoomPercentage').innerText = window.currentZoom + '%';

        var zoomMenuEl = document.getElementById('zoomPercentageMenu');
        if (zoomMenuEl) zoomMenuEl.innerText = window.currentZoom + '%';

        var isZoomed = window.currentZoom > 100;

        var pdfContainer = document.getElementById('pdf-container');
        if (pdfContainer) {
            pdfContainer.style.width = window.currentZoom + '%';
            pdfContainer.style.margin = '0 auto';
            var pdfWrapper = pdfContainer.parentElement;
            if (pdfWrapper) {
                pdfWrapper.style.overflowX = isZoomed ? 'auto' : 'hidden';
                pdfWrapper.style.overflowY = 'visible';
                pdfWrapper.style.WebkitOverflowScrolling = 'touch';
            }
        }

        document.querySelectorAll('#pdf-container canvas').forEach(function (c) {
            c.style.width = '100%';
            c.style.display = 'block';
        });

        var nativeContainer = document.getElementById('secure-content-container');
        if (nativeContainer) {
            nativeContainer.style.width = window.currentZoom + '%';
            nativeContainer.style.margin = '0 auto';
            var nativeWrapper = nativeContainer.parentElement;
            if (nativeWrapper) {
                nativeWrapper.style.overflowX = isZoomed ? 'auto' : 'hidden';
                nativeWrapper.style.overflowY = 'visible';
                nativeWrapper.style.WebkitOverflowScrolling = 'touch';
            }
        }
    }

    window.applyZoom = applyZoom;

    window.zoomIn = function () {
        if (window.currentZoom < 250) { window.currentZoom += 25; applyZoom(); }
    };

    window.zoomOut = function () {
        if (window.currentZoom > 50) { window.currentZoom -= 25; applyZoom(); }
    };

    // ---------- Page Navigation ----------

    window.scrollToPage = function (pageNum) {
        pageNum = parseInt(pageNum);
        if (!pageNum || !window.pdfDocGlobal) return;
        if (pageNum < 1) pageNum = 1;
        if (pageNum > window.pdfDocGlobal.numPages) pageNum = window.pdfDocGlobal.numPages;
        var canvas = document.getElementById('page-canvas-' + pageNum);
        if (canvas) {
            canvas.scrollIntoView({ behavior: 'smooth', block: 'start' });
            document.getElementById('pageNavInput').value = pageNum;
            document.getElementById('pageNavInput').blur();
        }
    };

    // ---------- Cinema Mode ----------

    window.toggleCinemaMode = function () {
        var body = document.body;
        var mainContainer = document.getElementById('reader-main-container');
        var cinemaStatusEl = document.getElementById('cinemaStatus');

        body.classList.toggle('cinema-mode');

        if (body.classList.contains('cinema-mode')) {
            mainContainer.classList.remove('max-w-4xl');
            mainContainer.classList.add('max-w-none');
            document.getElementById('cinemaModeIcon').innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 4H5a2 2 0 00-2 2v4m0 0a2 2 0 002 2h4m0 0V4m0 8a2 2 0 00-2-2H5m16 0h4a2 2 0 012 2v4m0 0a2 2 0 01-2 2h-4m0 0v-8m0 8a2 2 0 01-2-2h-4m16-4h-4a2 2 0 01-2-2v-4"></path>';
            if (cinemaStatusEl) cinemaStatusEl.innerText = 'ON';
        } else {
            mainContainer.classList.add('max-w-4xl');
            mainContainer.classList.remove('max-w-none');
            document.getElementById('cinemaModeIcon').innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path>';
            if (cinemaStatusEl) cinemaStatusEl.innerText = 'OFF';
        }

        if (typeof applyZoom === 'function') applyZoom();
    };

    // ---------- Options Menu Toggle ----------

    window.toggleOptionsMenu = function () {
        var menu = document.getElementById('optionsMenu');
        menu.classList.toggle('hidden');
        menu.classList.toggle('opacity-0');
        menu.classList.toggle('pointer-events-none');

        if (!menu.classList.contains('hidden')) {
            setTimeout(function () {
                document.addEventListener('click', closeOptionsMenuOnClickOutside);
            }, 0);
        } else {
            document.removeEventListener('click', closeOptionsMenuOnClickOutside);
        }
    };

    function closeOptionsMenuOnClickOutside(e) {
        var menu = document.getElementById('optionsMenu');
        var btn = document.getElementById('optionsMenuBtn');
        if (!menu.contains(e.target) && !btn.contains(e.target)) {
            menu.classList.add('hidden', 'opacity-0', 'pointer-events-none');
            document.removeEventListener('click', closeOptionsMenuOnClickOutside);
        }
    }

    // ---------- Font Size Controls ----------

    window.currentFontSize = 100;

    function applyFontSize() {
        var container = document.getElementById('secure-content-container');
        if (container) container.style.fontSize = window.currentFontSize + '%';
        var fontSizeEl = document.getElementById('fontSizePercentage');
        if (fontSizeEl) fontSizeEl.innerText = window.currentFontSize + '%';
        var fontSizeMenuEl = document.getElementById('fontSizePercentageMenu');
        if (fontSizeMenuEl) fontSizeMenuEl.innerText = window.currentFontSize + '%';
    }

    window.fontSizeIncrease = function () {
        if (window.currentFontSize < 200) { window.currentFontSize += 10; applyFontSize(); }
    };

    window.fontSizeDecrease = function () {
        if (window.currentFontSize > 80) { window.currentFontSize -= 10; applyFontSize(); }
    };

    // ---------- Eye Care Tint Toggle ----------

    window.toggleTint = function () {
        var body = document.body;
        var btn = document.getElementById('tintToggleBtn');
        var tintStatusEl = document.getElementById('tintStatus');

        body.classList.toggle('tint-enabled');

        if (body.classList.contains('tint-enabled')) {
            if (btn) {
                btn.classList.add('bg-emerald-500/10', 'text-emerald-500', 'border-emerald-500/50');
                btn.classList.remove('bg-neutral-100', 'dark:bg-neutral-800');
            }
            if (tintStatusEl) tintStatusEl.innerText = 'ON';
        } else {
            if (btn) {
                btn.classList.remove('bg-emerald-500/10', 'text-emerald-500', 'border-emerald-500/50');
                btn.classList.add('bg-neutral-100', 'dark:bg-neutral-800');
            }
            if (tintStatusEl) tintStatusEl.innerText = 'OFF';
        }
    };

    // ---------- URL Pseudo-Slug (SEO/UX) ----------

    document.addEventListener('DOMContentLoaded', function () {
        // Auto-enable tint if in dark mode on load
        if (document.documentElement.classList.contains('dark')) {
            document.body.classList.add('tint-enabled');
            var btn = document.getElementById('tintToggleBtn');
            if (btn) {
                btn.classList.add('bg-emerald-500/10', 'text-emerald-500', 'border-emerald-500/50');
                btn.classList.remove('bg-neutral-100', 'dark:bg-neutral-800');
            }
            var tintStatusEl = document.getElementById('tintStatus');
            if (tintStatusEl) tintStatusEl.innerText = 'ON';
        }

        var dataEl = document.getElementById('reader-data');
        var docTitle = dataEl ? JSON.parse(dataEl.textContent).document_title : '';
        if (!docTitle) return;

        var slug = docTitle.toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .trim()
            .replace(/[-\s]+/g, '-');

        var currentPath = window.location.pathname;

        if (slug && !currentPath.includes(slug)) {
            var newUrl = currentPath.endsWith('/')
                ? currentPath + slug
                : currentPath + '/' + slug;
            window.history.replaceState({ path: newUrl }, '', newUrl);
        }
    });

    // ---------- Back To Top ----------

    document.addEventListener('DOMContentLoaded', function () {
        var topBtn = document.getElementById('backToTopBtn');
        if (topBtn) {
            topBtn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
        }
    });
})();
