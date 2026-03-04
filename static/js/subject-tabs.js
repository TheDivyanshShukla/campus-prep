(function () {
    'use strict';

    var dataEl = document.getElementById('tab-switcher-data');
    if (!dataEl) return;
    var config = JSON.parse(dataEl.textContent);
    var storageKey = 'rgpv_active_tab_' + config.subjectId;

    window.switchTab = function (tabId) {
        // Remove the Anti-FOUC block once JS takes over
        var foucStyle = document.getElementById('anti-fouc-tabs');
        if (foucStyle) {
            foucStyle.remove();
        }

        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(function (el) {
            el.classList.add('hidden');
        });

        // Show the selected tab content
        var target = document.getElementById(tabId);
        if (target) {
            target.classList.remove('hidden');
        }

        // Reset all buttons
        document.querySelectorAll('.tab-btn').forEach(function (btn) {
            btn.classList.remove('bg-primary', 'text-primary-foreground', 'font-bold', 'shadow-md');
            btn.classList.add('bg-muted', 'text-muted-foreground', 'font-semibold', 'hover:bg-muted/80');
        });

        // Activate clicked button
        var btnId = tabId.replace('tab-', 'btn-');
        var activeBtn = document.getElementById(btnId);
        if (activeBtn) {
            activeBtn.classList.remove('bg-muted', 'text-muted-foreground', 'font-semibold', 'hover:bg-muted/80');
            activeBtn.classList.add('bg-primary', 'text-primary-foreground', 'font-bold', 'shadow-md');
        }

        localStorage.setItem(storageKey, tabId);
    };

    // On initial load: restore the last visited tab
    document.addEventListener('DOMContentLoaded', function () {
        var savedTab = localStorage.getItem(storageKey) || 'tab-pyqs';
        window.switchTab(savedTab);
    });
})();
