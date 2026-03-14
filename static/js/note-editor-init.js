(function () {
    'use strict';

    var dataEl = document.getElementById('editor-config');
    if (!dataEl) return;
    var config = JSON.parse(dataEl.textContent);

    // Initialize the NoteEditor (exposed globally for inline onclick handlers)
    var editor = window.editor = new NoteEditor({
        noteId: config.noteId,
        csrfToken: config.csrfToken,
        saveUrl: config.saveUrl,
        uploadUrl: config.uploadUrl,
        versionsUrl: config.versionsUrl,
        restoreBaseUrl: config.restoreBaseUrl,
        versionDetailBaseUrl: config.versionDetailBaseUrl,
        initialBlocks: config.initialBlocks,
    });

    // Toolbar collapse/expand
    window.collapseEditorToolbar = function () {
        var toolbar = document.getElementById('editor-toolbar');
        var toggleBtn = document.getElementById('editorToolbarToggleBtn');
        if (!toolbar || !toggleBtn) return;

        toolbar.dataset.collapsed = 'true';
        stabilizeMobileToolbar();

        toolbar.style.overflow = 'hidden';
        toolbar.style.height = '0px';
        toolbar.style.paddingTop = '0px';
        toolbar.style.paddingBottom = '0px';
        toolbar.style.marginBottom = '0px';
        toolbar.style.borderBottomWidth = '0px';
        toolbar.style.opacity = '0';
        toolbar.style.pointerEvents = 'none';

        toggleBtn.style.transform = 'translateY(0)';
        toggleBtn.style.opacity = '1';
        toggleBtn.style.pointerEvents = 'auto';
    };

    window.expandEditorToolbar = function () {
        var toolbar = document.getElementById('editor-toolbar');
        var toggleBtn = document.getElementById('editorToolbarToggleBtn');
        if (!toolbar || !toggleBtn) return;

        toolbar.dataset.collapsed = 'false';

        toolbar.style.height = 'auto';
        toolbar.style.paddingTop = '';
        toolbar.style.paddingBottom = '';
        toolbar.style.marginBottom = '';
        toolbar.style.borderBottomWidth = '';
        toolbar.style.opacity = '1';
        toolbar.style.overflow = '';
        toolbar.style.pointerEvents = '';

        toggleBtn.style.transform = '';
        toggleBtn.style.opacity = '0';
        toggleBtn.style.pointerEvents = 'none';

        stabilizeMobileToolbar();
    };

    function stabilizeMobileToolbar() {
        var toolbar = document.getElementById('editor-toolbar');
        var app = document.getElementById('editor-app');
        if (!toolbar || !app) return;

        var isMobile = window.matchMedia('(max-width: 639px)').matches;
        var isCollapsed = toolbar.dataset.collapsed === 'true';

        if (!isMobile) {
            toolbar.classList.remove('toolbar-mobile-fixed');
            app.classList.remove('has-mobile-toolbar-offset');
            app.style.paddingTop = '';
            toolbar.style.transform = '';
            return;
        }

        toolbar.classList.add('toolbar-mobile-fixed');

        if (isCollapsed) {
            app.classList.remove('has-mobile-toolbar-offset');
            app.style.paddingTop = '0px';
            return;
        }

        app.classList.add('has-mobile-toolbar-offset');

        var toolbarHeight = Math.round(toolbar.getBoundingClientRect().height || 56);
        app.style.paddingTop = toolbarHeight + 'px';

        var viewportOffsetTop = window.visualViewport ? Math.round(window.visualViewport.offsetTop) : 0;
        toolbar.style.transform = 'translate3d(0, ' + viewportOffsetTop + 'px, 0)';
    }

    window.addEventListener('resize', stabilizeMobileToolbar, { passive: true });
    window.addEventListener('orientationchange', stabilizeMobileToolbar, { passive: true });
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', stabilizeMobileToolbar, { passive: true });
        window.visualViewport.addEventListener('scroll', stabilizeMobileToolbar, { passive: true });
    }
    requestAnimationFrame(stabilizeMobileToolbar);

    // Quick-revision dropdown toggle
    window.toggleQRMenu = function () {
        document.getElementById('qr-menu').classList.toggle('hidden');
    };
    document.addEventListener('click', function (e) {
        if (!e.target.closest('#qr-dropdown')) {
            var qrMenu = document.getElementById('qr-menu');
            if (qrMenu) qrMenu.classList.add('hidden');
        }
    });
})();
