(function () {
    'use strict';

    var dataEl = document.getElementById('practice-config-data');
    if (!dataEl) return;
    var config = JSON.parse(dataEl.textContent);

    var selectedSubjectId = null;
    var selectedUnitId = '';
    var selectedDiff = 'MEDIUM';
    var CSRF = config.csrfToken;

    window.selectSubject = function (el) {
        document.querySelectorAll('.subject-card').forEach(function (c) { c.classList.remove('selected'); });
        el.classList.add('selected');
        selectedSubjectId = el.dataset.subjectId;

        var unitsRaw = el.dataset.units;
        var unitBtns = document.getElementById('unitBtns');
        unitBtns.innerHTML = '<button class="unit-btn active border border-border text-sm font-medium px-4 py-2 rounded-xl" data-unit-id="" onclick="selectUnit(this)">All Units</button>';

        if (unitsRaw) {
            try {
                var units = JSON.parse('[' + unitsRaw + ']');
                units.forEach(function (u) {
                    unitBtns.innerHTML += '<button class="unit-btn border border-border text-sm font-medium px-4 py-2 rounded-xl" data-unit-id="' + u.id + '" onclick="selectUnit(this)">' + u.name + '</button>';
                });
            } catch (e) { /* ignore */ }
        }
        selectedUnitId = '';
        updatePregenLink();
        document.getElementById('configSection').classList.remove('hidden');
        document.getElementById('configSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    window.selectUnit = function (el) {
        document.querySelectorAll('.unit-btn').forEach(function (b) { b.classList.remove('active'); });
        el.classList.add('active');
        selectedUnitId = el.dataset.unitId;
        updatePregenLink();
    };

    window.toggleType = function (el) {
        el.classList.toggle('active');
    };

    window.selectDiff = function (el) {
        document.querySelectorAll('.diff-btn').forEach(function (b) { b.classList.remove('active'); });
        el.classList.add('active');
        selectedDiff = el.dataset.diff;
    };

    function getSelectedTypes() {
        return Array.from(document.querySelectorAll('.type-btn.active')).map(function (b) { return b.dataset.type; });
    }

    function updatePregenLink() {
        var a = document.getElementById('pregenBtn');
        var url = '/practice/sets/' + selectedSubjectId + '/';
        if (selectedUnitId) url += '?unit=' + selectedUnitId;
        a.href = url;
    }

    window.aiGenerate = async function () {
        if (!selectedSubjectId) return alert('Please select a subject first.');
        var types = getSelectedTypes();
        if (!types.length) return alert('Select at least one question type.');

        var btn = document.getElementById('aiBtn');
        var icon = document.getElementById('ai-icon');
        var text = document.getElementById('ai-text');
        var spinner = document.getElementById('ai-spinner');

        btn.disabled = true;
        icon.style.display = 'none';
        text.textContent = 'Generating\u2026';
        spinner.style.display = 'block';

        try {
            var resp = await fetch('/practice/api/generate/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
                body: JSON.stringify({
                    subject_id: selectedSubjectId,
                    unit_id: selectedUnitId || null,
                    types: types,
                    difficulty: selectedDiff,
                    count: 10,
                })
            });
            var data = await resp.json();
            if (data.success) {
                window.location.href = '/practice/quiz/' + data.set_id + '/';
            } else {
                alert('AI generation failed: ' + data.error);
            }
        } catch (e) {
            alert('Network error: ' + e.message);
        } finally {
            btn.disabled = false;
            icon.style.display = '';
            text.textContent = 'Generate with AI';
            spinner.style.display = 'none';
        }
    };
})();
