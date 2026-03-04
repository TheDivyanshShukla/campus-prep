(function () {
    'use strict';

    var dataEl = document.getElementById('result-data');
    if (!dataEl) return;
    var config = JSON.parse(dataEl.textContent);

    window._md = window.markdownit({ html: false, linkify: true, typographer: true });

    // Render all markdown blocks
    document.querySelectorAll('.md-rendered, .md-preview').forEach(function (el) {
        var raw = el.dataset.raw || '';
        el.innerHTML = el.classList.contains('md-preview')
            ? _md.renderInline(raw)
            : _md.render(raw);
    });

    // Animate ring chart
    var pct = config.percentage;
    var ring = document.getElementById('ringFg');
    if (ring) {
        var circumference = 2 * Math.PI * 45; // ~283
        var offset = circumference * (1 - pct / 100);
        setTimeout(function () { ring.style.strokeDashoffset = offset; }, 200);
    }

    // Typeset math
    if (window.MathJax && MathJax.typesetPromise) {
        MathJax.typesetPromise();
    }
})();
