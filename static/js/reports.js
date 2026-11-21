/**
 * Reports — filter table + export full dataset CSV.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var q = document.getElementById('filter-q');
    var result = document.getElementById('filter-result');
    var table = document.getElementById('reports-full-table');
    var exportBtn = document.getElementById('export-csv-btn');

    function applyFilters() {
      if (!table) return;
      var query = (q && q.value ? q.value : '').toLowerCase();
      var want = result && result.value ? result.value : 'all';
      var rows = table.querySelectorAll('tbody tr');
      rows.forEach(function (row) {
        var cells = row.querySelectorAll('td');
        if (cells.length < 4) return;
        var name = (cells[0].textContent || '').toLowerCase();
        var resText = (cells[3].textContent || '').trim();
        var okQ = !query || name.indexOf(query) !== -1;
        var okR = want === 'all' || resText.indexOf(want) !== -1;
        row.classList.toggle('hidden', !(okQ && okR));
      });
    }

    if (q) q.addEventListener('input', applyFilters);
    if (result) result.addEventListener('change', applyFilters);

    if (exportBtn) {
      exportBtn.addEventListener('click', function () {
        window.location.href = '/api/dataset/export';
      });
    }

    var chartCanvas = document.getElementById('dataset-success-chart');
    if (chartCanvas && typeof Chart !== 'undefined') {
      fetch('/api/ai-dataset-insights', { credentials: 'same-origin' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          var stats = data && data.stats ? data.stats : {};
          var success = Number(stats.successful_startups || 0);
          var failed = Number(stats.failed_startups || 0);
          if (!success && !failed) return;
          new Chart(chartCanvas.getContext('2d'), {
            type: 'doughnut',
            data: {
              labels: ['Successful', 'Failed'],
              datasets: [{ data: [success, failed], backgroundColor: ['#22c55e', '#f87171'], borderWidth: 0 }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
          });
        })
        .catch(function () {});
    }
  });
})();
