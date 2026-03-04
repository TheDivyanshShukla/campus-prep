/**
 * Analytics dashboard charts and visualizations.
 * Reads all data from <script type="application/json" id="analytics-data"> in the template.
 */
(function () {
    'use strict';

    // ── Tab Switcher (global) ────────────────────────────────────────────────
    window.switchTab = function (tabName) {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(el => {
            el.classList.remove('active');
            el.classList.add('text-muted-foreground');
        });

        const activeTab = document.getElementById(tabName + '-tab');
        const activeBtn = document.getElementById('tab-btn-' + tabName);

        if (activeTab) activeTab.classList.add('active');
        if (activeBtn) {
            activeBtn.classList.add('active');
            activeBtn.classList.remove('text-muted-foreground');
        }

        window.dispatchEvent(new Event('resize'));
    };

    document.addEventListener('DOMContentLoaded', function () {
        const dataEl = document.getElementById('analytics-data');
        if (!dataEl) return;
        const D = JSON.parse(dataEl.textContent);

        // ── Theme helpers ────────────────────────────────────────────────────
        const isDark = () => document.documentElement.classList.contains('dark');
        const gridColor = () => isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
        const textColor = () => isDark() ? '#a1a1aa' : '#71717a';
        const tooltipOpts = () => ({
            backgroundColor: isDark() ? '#1c1c1e' : '#ffffff',
            titleColor: isDark() ? '#fff' : '#000',
            bodyColor: isDark() ? '#a1a1aa' : '#52525b',
            borderColor: isDark() ? '#3f3f46' : '#e4e4e7',
            borderWidth: 1, padding: 10, displayColors: false,
        });
        const FONT = { family: "'Inter', sans-serif" };

        // ── Animate progress bars ────────────────────────────────────────────
        setTimeout(() => {
            const goalBar = document.getElementById('dailyGoalBar');
            const xpBar = document.getElementById('xpLevelBar');
            if (goalBar) goalBar.style.width = D.daily_progress + '%';
            if (xpBar) xpBar.style.width = D.xp_level_pct + '%';
        }, 200);

        // ── Colour palettes ──────────────────────────────────────────────────
        const PALETTE = [
            '#6366f1', '#f43f5e', '#10b981', '#f59e0b', '#3b82f6',
            '#8b5cf6', '#14b8a6', '#ef4444', '#ec4899', '#84cc16'
        ];

        // ── 1. Weekly Bar Chart ──────────────────────────────────────────────
        (function () {
            const ctx = document.getElementById('weeklyChart');
            if (!ctx) return;
            const c = ctx.getContext('2d');
            const grad = c.createLinearGradient(0, 0, 0, 280);
            grad.addColorStop(0, 'rgba(99,102,241,0.55)');
            grad.addColorStop(1, 'rgba(99,102,241,0.0)');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: D.weekly_labels,
                    datasets: [{
                        label: 'Minutes',
                        data: D.weekly_minutes,
                        backgroundColor: D.weekly_minutes.map((v, i) =>
                            i === D.weekly_minutes.length - 1 ? '#6366f1' : 'rgba(99,102,241,0.4)'
                        ),
                        borderRadius: 8,
                        borderSkipped: false,
                        hoverBackgroundColor: '#6366f1',
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { ...tooltipOpts(), callbacks: { label: ctx => ctx.parsed.y + ' min' } }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: textColor(), font: FONT } },
                        y: { beginAtZero: true, grid: { color: gridColor() }, ticks: { color: textColor(), font: FONT } }
                    }
                }
            });
        })();

        // ── 2. 12-Week Trend (Line) ──────────────────────────────────────────
        (function () {
            const ctx = document.getElementById('trendChart');
            if (!ctx) return;
            const c = ctx.getContext('2d');
            const grad = c.createLinearGradient(0, 0, 0, 280);
            grad.addColorStop(0, 'rgba(16,185,129,0.35)');
            grad.addColorStop(1, 'rgba(16,185,129,0.0)');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: D.trend_labels,
                    datasets: [{
                        label: 'Min / Week',
                        data: D.trend_minutes,
                        borderColor: '#10b981',
                        borderWidth: 2.5,
                        backgroundColor: grad,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: '#10b981',
                        pointRadius: 3,
                        pointHoverRadius: 6,
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { ...tooltipOpts(), callbacks: { label: ctx => ctx.parsed.y + ' min' } }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: textColor(), font: FONT } },
                        y: { beginAtZero: true, grid: { color: gridColor() }, ticks: { color: textColor(), font: FONT } }
                    }
                }
            });
        })();

        // ── 3. Subject Donut ─────────────────────────────────────────────────
        (function () {
            const ctx = document.getElementById('subjectChart');
            if (!ctx) return;
            const labels = D.subject_labels;
            const minutes = D.subject_minutes;
            const legend = document.getElementById('subjectLegend');
            const total = minutes.reduce((a, b) => a + b, 0) || 1;

            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [{
                        data: minutes,
                        backgroundColor: PALETTE.slice(0, labels.length),
                        borderWidth: 0,
                        hoverOffset: 6,
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: true,
                    cutout: '68%',
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            ...tooltipOpts(),
                            callbacks: {
                                label: ctx => {
                                    const pct = ((ctx.parsed / total) * 100).toFixed(1);
                                    return ctx.parsed + ' min (' + pct + '%)';
                                }
                            }
                        }
                    }
                }
            });

            // Custom legend
            if (legend) {
                labels.forEach((lbl, i) => {
                    const min = minutes[i];
                    const pct = ((min / total) * 100).toFixed(1);
                    const div = document.createElement('div');
                    div.className = 'flex items-center justify-between gap-2';
                    div.innerHTML =
                        '<div class="flex items-center gap-2 min-w-0">' +
                        '<span class="w-3 h-3 rounded-full flex-shrink-0" style="background:' + PALETTE[i % PALETTE.length] + '"></span>' +
                        '<span class="text-xs text-foreground font-medium truncate">' + lbl + '</span>' +
                        '</div>' +
                        '<div class="flex items-center gap-2 flex-shrink-0">' +
                        '<span class="text-xs text-muted-foreground">' + min + ' min</span>' +
                        '<span class="text-[10px] font-bold text-muted-foreground">' + pct + '%</span>' +
                        '</div>';
                    legend.appendChild(div);
                });
            }
        })();

        // ── 4. Hourly Bar ────────────────────────────────────────────────────
        (function () {
            const container = document.getElementById('hourlyBar');
            if (!container) return;
            const hourly = D.hourly_data;
            const maxVal = Math.max(...hourly, 1);
            const HOUR_COLORS = [
                '#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#f43f5e',
                '#f97316', '#f59e0b', '#eab308', '#84cc16', '#22c55e',
                '#10b981', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6',
                '#a855f7', '#ec4899', '#f43f5e', '#f97316', '#f59e0b', '#eab308', '#84cc16', '#22c55e'
            ];
            hourly.forEach((val, h) => {
                const bar = document.createElement('div');
                bar.className = 'hour-cell';
                bar.style.background = HOUR_COLORS[h] || '#6366f1';
                bar.style.opacity = val === 0 ? '0.12' : (0.25 + 0.75 * (val / maxVal)).toFixed(2);
                const label = h === 0 ? '12 AM' : h < 12 ? h + ' AM' : h === 12 ? '12 PM' : (h - 12) + ' PM';
                bar.setAttribute('data-tip', label + ': ' + val + ' min');
                container.appendChild(bar);
            });
        })();

        // ── 5. 30-Day Heatmap ────────────────────────────────────────────────
        (function () {
            const grid = document.getElementById('heatmapGrid');
            if (!grid) return;
            const data = D.heatmap_data;
            const maxVal = Math.max(...data.map(d => d.minutes), 1);

            data.forEach(d => {
                const cell = document.createElement('span');
                cell.className = 'heatmap-cell';
                cell.title = d.date + ': ' + d.minutes + ' min';
                const ratio = d.minutes / maxVal;
                let bg;
                if (d.minutes === 0) bg = 'hsl(var(--muted))';
                else if (ratio < 0.25) bg = isDark() ? '#134e4a' : '#99f6e4';
                else if (ratio < 0.5) bg = isDark() ? '#0f766e' : '#2dd4bf';
                else if (ratio < 0.75) bg = '#14b8a6';
                else bg = '#0d9488';
                cell.style.background = bg;
                grid.appendChild(cell);
            });
        })();

        // ── 6. Practice Subject Bar Chart ────────────────────────────────────
        (function () {
            const ctx = document.getElementById('practiceSubjectChart');
            if (!ctx) return;
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: D.practice_subject_labels,
                    datasets: [{
                        label: 'Avg Accuracy (%)',
                        data: D.practice_subject_scores,
                        backgroundColor: '#4f46e5',
                        borderRadius: 8,
                        barThickness: 32,
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { ...tooltipOpts(), callbacks: { label: ctx => ctx.parsed.x + '%' } }
                    },
                    scales: {
                        x: { beginAtZero: true, max: 100, grid: { color: gridColor() }, ticks: { color: textColor(), font: FONT } },
                        y: { grid: { display: false }, ticks: { color: textColor(), font: FONT } }
                    }
                }
            });
        })();

        // ── 7. Practice Weekly Bar ───────────────────────────────────────────
        (function () {
            const ctx = document.getElementById('practiceWeeklyChart');
            if (!ctx) return;
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: D.practice_weekly_labels,
                    datasets: [{
                        label: 'Questions',
                        data: D.practice_weekly_qs,
                        backgroundColor: D.practice_weekly_qs.map((v, i) =>
                            i === D.practice_weekly_qs.length - 1 ? '#6366f1' : 'rgba(99,102,241,0.4)'
                        ),
                        borderRadius: 8,
                        borderSkipped: false,
                        hoverBackgroundColor: '#6366f1',
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { ...tooltipOpts(), callbacks: { label: ctx => ctx.parsed.y + ' questions' } }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: textColor(), font: FONT } },
                        y: { beginAtZero: true, grid: { color: gridColor() }, ticks: { color: textColor(), font: FONT } }
                    }
                }
            });
        })();

        // ── 8. Practice Accuracy Trend ───────────────────────────────────────
        (function () {
            const ctx = document.getElementById('practiceTrendChart');
            if (!ctx) return;
            const c = ctx.getContext('2d');
            const grad = c.createLinearGradient(0, 0, 0, 280);
            grad.addColorStop(0, 'rgba(16,185,129,0.35)');
            grad.addColorStop(1, 'rgba(16,185,129,0.0)');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: D.practice_trend_labels,
                    datasets: [{
                        label: 'Accuracy %',
                        data: D.practice_trend_scores,
                        borderColor: '#10b981',
                        borderWidth: 2.5,
                        backgroundColor: grad,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: '#10b981',
                        pointRadius: 3,
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { ...tooltipOpts(), callbacks: { label: ctx => ctx.parsed.y + '%' } }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: textColor(), font: FONT } },
                        y: { beginAtZero: true, max: 100, grid: { color: gridColor() }, ticks: { color: textColor(), font: FONT } }
                    }
                }
            });
        })();

        // ── 9. Practice Hourly Bar ───────────────────────────────────────────
        (function () {
            const container = document.getElementById('practiceHourlyBar');
            if (!container) return;
            const hourly = D.practice_hourly_data;
            const maxVal = Math.max(...hourly, 1);
            const COLORS = [
                '#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#f43f5e',
                '#f97316', '#f59e0b', '#eab308', '#84cc16', '#22c55e',
                '#10b981', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6',
                '#a855f7', '#ec4899', '#f43f5e', '#f97316', '#f59e0b', '#eab308', '#84cc16', '#22c55e'
            ];
            hourly.forEach((val, h) => {
                const bar = document.createElement('div');
                bar.className = 'hour-cell';
                bar.style.background = COLORS[h] || '#6366f1';
                bar.style.opacity = val === 0 ? '0.12' : (0.25 + 0.75 * (val / maxVal)).toFixed(2);
                const label = h === 0 ? '12 AM' : h < 12 ? h + ' AM' : h === 12 ? '12 PM' : (h - 12) + ' PM';
                bar.setAttribute('data-tip', label + ': ' + val + ' answers');
                container.appendChild(bar);
            });
        })();

        // ── 10. Practice Activity Heatmap ────────────────────────────────────
        (function () {
            const grid = document.getElementById('practiceHeatmapGrid');
            if (!grid) return;
            const data = D.practice_heatmap_data;
            const maxVal = Math.max(...data.map(d => d.qs), 1);

            data.forEach(d => {
                const cell = document.createElement('span');
                cell.className = 'heatmap-cell';
                cell.title = d.date + ': ' + d.qs + ' questions';
                const ratio = d.qs / maxVal;
                let bg;
                if (d.qs === 0) bg = 'hsl(var(--muted))';
                else if (ratio < 0.25) bg = isDark() ? '#312e81' : '#c7d2fe';
                else if (ratio < 0.5) bg = isDark() ? '#3730a3' : '#818cf8';
                else if (ratio < 0.75) bg = '#6366f1';
                else bg = '#4f46e5';
                cell.style.background = bg;
                grid.appendChild(cell);
            });
        })();
    });
})();
