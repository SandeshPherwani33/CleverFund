/**
 * Analytics — charts from /api/analytics-data (your CSV aggregates).
 */
(function () {
  'use strict';

  console.log('ANALYTICS.JS LOADED - STARTING EXECUTION');

  var colors = {
    blue: 'rgb(37, 99, 235)',
    blueSoft: 'rgba(37, 99, 235, 0.2)',
    teal: 'rgb(14, 165, 233)',
    slate: 'rgba(148, 163, 184, 0.35)',
  };

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function showBanner(msg) {
    var b = document.getElementById('analytics-banner');
    if (!b) return;
    if (!msg) {
      b.textContent = '';
      b.classList.add('hidden');
      return;
    }
    b.textContent = msg;
    b.classList.remove('hidden');
  }

  function initVolume(ctx, d) {
    var labels = (d && d.labels) || ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'];
    var values = (d && d.values) || [1000, 500, 1500, 200, 1800, 300, 2200, 400];
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Startup Count',
            data: values,
            borderColor: colors.blue,
            backgroundColor: colors.blueSoft,
            fill: true,
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(148, 163, 184, 0.2)' } },
          x: { grid: { display: false } },
        },
      },
    });
  }

  function initRadar(ctx, d) {
    var labels = (d && d.labels) || ['Team', 'Market', 'Product', 'Funding', 'Timing', 'Traction'];
    var portfolio = (d && d.portfolio) || [65, 65, 65, 65, 65, 65];
    var benchmark = (d && d.benchmark) || [65, 65, 65, 65, 65, 65];
    return new Chart(ctx, {
      type: 'radar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Dataset avg.',
            data: portfolio,
            borderColor: colors.blue,
            backgroundColor: 'rgba(37, 99, 235, 0.15)',
            pointBackgroundColor: colors.blue,
          },
          {
            label: 'Benchmark',
            data: benchmark,
            borderColor: colors.teal,
            backgroundColor: 'rgba(14, 165, 233, 0.08)',
            pointBackgroundColor: colors.teal,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            min: 0,
            max: 100,
            ticks: { stepSize: 20 },
            grid: { color: 'rgba(148, 163, 184, 0.25)' },
          },
        },
      },
    });
  }

  function initRegion(ctx, d) {
    var labels = (d && d.labels) || ['—'];
    var rates = (d && d.rates) || [0];
    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Success rate %',
            data: rates,
            backgroundColor: [
              'rgba(37, 99, 235, 0.85)',
              'rgba(59, 130, 246, 0.75)',
              'rgba(14, 165, 233, 0.8)',
              'rgba(99, 102, 241, 0.72)',
              'rgba(148, 163, 184, 0.65)',
            ],
            borderRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: {
            beginAtZero: true,
            max: 100,
            grid: { color: 'rgba(148, 163, 184, 0.2)' },
          },
          y: { grid: { display: false } },
        },
      },
    });
  }

  function waitForChartJS(callback) {
    if (typeof Chart !== 'undefined') {
      callback();
    } else {
      setTimeout(function() { waitForChartJS(callback); }, 100);
    }
  }

  function initAnalytics() {
    // Set loading text
    var medianEl = document.getElementById('kpi-median');
    var volatilityEl = document.getElementById('kpi-volatility');
    
    if (medianEl) medianEl.textContent = 'Loading...';
    if (volatilityEl) volatilityEl.textContent = 'Loading...';
    
    // Fetch analytics data
    fetch('/api/analytics-data', { credentials: 'same-origin' })
      .then(function (res) {
        return res.json().then(function (data) {
          return { res: res, data: data };
        });
      })
      .then(function (o) {
        if (o.res.status === 401) {
          window.location.href = o.data.login || '/login';
          return;
        }
        if (!o.data.ok) {
          showBanner(o.data.error || 'Could not load analytics.');
          return;
        }
        showBanner('');

        var k = o.data.kpis || {};
        setText('kpi-median', window.formatPercentage(k.median_probability != null ? k.median_probability : null));
        setText('kpi-volatility', k.volatility || '—');

        // Initialize charts
        var v = document.getElementById('analyticsVolumeChart');
        var r = document.getElementById('analyticsRadarChart');
        var g = document.getElementById('analyticsRegionChart');
        
        if (v) initVolume(v.getContext('2d'), o.data.volume);
        if (r) initRadar(r.getContext('2d'), o.data.radar);
        if (g) initRegion(g.getContext('2d'), o.data.region);
      })
      .catch(function (err) {
        showBanner('Failed to load analytics.');
      });
  }

  // Initialize when DOM and Chart.js are ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      waitForChartJS(initAnalytics);
    });
  } else {
    waitForChartJS(initAnalytics);
  }
})();
