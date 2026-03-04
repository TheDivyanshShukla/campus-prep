(function () {
    'use strict';

    var dataEl = document.getElementById('quiz-data');
    if (!dataEl) return;
    var config = JSON.parse(dataEl.textContent);

    // Markdown + MathJax rendering
    window._md = window.markdownit({ html: false, linkify: true, typographer: true });

    document.querySelectorAll('.md-content').forEach(function (el) {
        el.innerHTML = _md.render(el.dataset.raw || '');
    });

    if (window.MathJax && MathJax.typesetPromise) {
        MathJax.typesetPromise();
    }

    // Progress tracking
    var total = config.questionCount;

    window.onAnswer = function () {
        var cards = document.querySelectorAll('.q-card');
        var count = 0;
        cards.forEach(function (card) {
            var radios = card.querySelectorAll('input[type=radio]:checked');
            var texts = card.querySelectorAll('textarea, input[type=text]');
            var hidden = card.querySelectorAll('input[type=hidden]');

            var hasAnswer = radios.length > 0;
            texts.forEach(function (t) { if (t.value.trim()) hasAnswer = true; });
            hidden.forEach(function (h) { if (h.value) hasAnswer = true; });

            if (hasAnswer) count++;
        });
        var pct = total ? Math.round((count / total) * 100) : 0;
        document.getElementById('progressBar').style.width = pct + '%';
        document.getElementById('progressLabel').textContent = count + '/' + total;
    };

    // True / False
    window.setTF = function (btn, fieldId, val) {
        var parent = btn.closest('.flex');
        parent.querySelectorAll('.tf-btn').forEach(function (b) { b.classList.remove('selected-tf'); });
        btn.classList.add('selected-tf');
        document.getElementById(fieldId).value = val;
        window.onAnswer();
    };

    // Initial progress check
    window.onAnswer();
})();
