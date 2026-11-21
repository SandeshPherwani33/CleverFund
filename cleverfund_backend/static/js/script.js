/**
 * CleverFund Dashboard — Chart.js + POST /predict (charts from /api/dashboard-data).
 * Also supports ML-based predictions via /api/ml-predict endpoint.
 */
(function () {
  'use strict';

  const chartColors = {
    line: 'rgb(37, 99, 235)',
    lineFill: 'rgba(37, 99, 235, 0.08)',
    success: 'rgb(34, 197, 94)',
    failure: 'rgb(244, 63, 94)',
    barBlue: 'rgba(37, 99, 235, 0.85)',
    barTeal: 'rgba(14, 165, 233, 0.75)',
    probNeutral: 'rgba(59, 130, 246, 0.9)',
    probRemain: 'rgba(148, 163, 184, 0.35)',
  };

  // Model selection state
  let useMLModel = true;

  /** @type {Chart | null} */
  let predictionScoreChart = null;

  let predictionCount = 0;
  /** @type {Array<{name: string, funding: string, result: string, probability: string}>} */
  let reportRows = [];

  function formatPercentage(value) {
    if (value === null || value === undefined || value === '') return '—';

    const raw = typeof value === 'string' ? value.trim().replace(/%/g, '') : value;
    const number = Number(raw);

    if (!Number.isFinite(number)) return '—';

    const percentage = (number > 0 && number <= 1) ? number * 100 : number;
    const rounded = Math.round((percentage + Number.EPSILON) * 10) / 10;
    const display = Number.isInteger(rounded)
      ? rounded.toFixed(0)
      : rounded.toFixed(1).replace(/\.0$/, '');

    return `${display}%`;
  }

  window.formatPercentage = formatPercentage;

  function initCharts(d) {
    const growthCtx = document.getElementById('growthChart');
    const outcomeCtx = document.getElementById('outcomeChart');
    const industryCtx = document.getElementById('industryChart');
    const frCtx = document.getElementById('fundingRevenueChart');
    if (!growthCtx || !outcomeCtx) return;

    const growthLabels = (d && d.growth && d.growth.labels) || ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'];
    const growthValues = (d && d.growth && d.growth.values) || [1000, 500, 1500, 200, 1800, 300, 2200, 400];

    const doughnutLabels = (d && d.outcome && d.outcome.labels) || ['Success', 'Failure'];
    let doughnutValues = (d && d.outcome && d.outcome.values) || [1, 0];
    const sum = doughnutValues.reduce(function (a, b) {
      return a + b;
    }, 0);
    if (sum === 0) doughnutValues = [1, 0];

    const industryLabels = (d && d.industry && d.industry.labels) || ['—'];
    const industryCounts = (d && d.industry && d.industry.counts) || [1];

    const frLabels = (d && d.funding_revenue && d.funding_revenue.labels) || ['Q1', 'Q2', 'Q3', 'Q4'];
    const fundingIndexed =
      (d && d.funding_revenue && d.funding_revenue.funding_indexed) || [80, 40, 120, 60];
    const revenueIndexed =
      (d && d.funding_revenue && d.funding_revenue.revenue_indexed) || [70, 90, 30, 100];

    new Chart(growthCtx, {
      type: 'line',
      data: {
        labels: growthLabels,
        datasets: [
          {
            label: 'Startups tracked',
            data: growthValues,
            borderColor: chartColors.line,
            backgroundColor: chartColors.lineFill,
            fill: true,
            tension: 0.35,
            pointRadius: 4,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(148, 163, 184, 0.2)' },
          },
          x: {
            grid: { display: false },
          },
        },
      },
    });

    new Chart(outcomeCtx, {
      type: 'doughnut',
      data: {
        labels: doughnutLabels,
        datasets: [
          {
            data: doughnutValues,
            backgroundColor: [chartColors.success, chartColors.failure],
            borderWidth: 0,
            hoverOffset: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '62%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { usePointStyle: true, padding: 16 },
          },
        },
      },
    });

    if (industryCtx) {
      new Chart(industryCtx, {
        type: 'bar',
        data: {
          labels: industryLabels,
          datasets: [
            {
              label: 'Startups',
              data: industryCounts,
              backgroundColor: [
                'rgba(37, 99, 235, 0.85)',
                'rgba(59, 130, 246, 0.75)',
                'rgba(14, 165, 233, 0.8)',
                'rgba(99, 102, 241, 0.7)',
                'rgba(148, 163, 184, 0.65)',
              ],
              borderRadius: 8,
              borderSkipped: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(148, 163, 184, 0.2)' },
            },
            x: {
              grid: { display: false },
            },
          },
        },
      });
    }

    if (frCtx) {
      new Chart(frCtx, {
        type: 'bar',
        data: {
          labels: frLabels,
          datasets: [
            {
              label: 'Funding (index)',
              data: fundingIndexed,
              backgroundColor: chartColors.barBlue,
              borderRadius: 6,
            },
            {
              label: 'Revenue (index)',
              data: revenueIndexed,
              backgroundColor: chartColors.barTeal,
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { usePointStyle: true, padding: 16 },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              max: 120,
              grid: { color: 'rgba(148, 163, 184, 0.2)' },
            },
            x: {
              grid: { display: false },
            },
          },
        },
      });
    }
  }

  function formatCurrency(num) {
    if (num >= 1_000_000) return '₹' + (num / 1_000_000).toFixed(1) + 'M';
    if (num >= 1_000) return '₹' + (num / 1_000).toFixed(0) + 'K';
    return '₹' + num.toFixed(0);
  }

  function renderTable() {
    const tbody = document.getElementById('reports-body');
    if (!tbody) return;
    tbody.innerHTML = reportRows
      .map(
        (row) => `
      <tr class="table-row-animate hover:bg-slate-50/80">
        <td class="px-6 py-3 font-medium text-slate-900">${escapeHtml(row.name)}</td>
        <td class="px-6 py-3 text-slate-600">${escapeHtml(row.funding)}</td>
        <td class="px-6 py-3">
          <span class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
            row.result === 'Success'
              ? 'bg-emerald-100 text-emerald-800'
              : 'bg-rose-100 text-rose-800'
          }">${escapeHtml(row.result)}</span>
        </td>
        <td class="px-6 py-3 text-slate-700">${escapeHtml(row.probability)}</td>
      </tr>
    `
      )
      .join('');
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function updateStatsFromPayload(stats) {
    const totalEl = document.getElementById('stat-total');
    const rateEl = document.getElementById('stat-rate');
    const failedEl = document.getElementById('stat-failed');
    if (totalEl && stats) totalEl.textContent = Number(stats.total).toLocaleString();
    if (rateEl && stats) rateEl.textContent = window.formatPercentage(stats.success_rate);
    if (failedEl && stats) failedEl.textContent = Number(stats.failed).toLocaleString();
  }

  function updateStats() {
    const el = document.getElementById('stat-predictions');
    if (el) el.textContent = String(predictionCount);
  }

  function setLoading(isLoading) {
    const btn = document.getElementById('predict-btn');
    const spinner = document.getElementById('btn-spinner');
    const label = document.getElementById('btn-label');
    if (!btn || !spinner || !label) return;
    btn.disabled = isLoading;
    spinner.classList.toggle('hidden', !isLoading);
    label.textContent = isLoading ? 'Predicting…' : 'Predict';
  }

  function updatePredictionChart(probability, result) {
    const ctx = document.getElementById('predictionScoreChart');
    if (!ctx || typeof Chart === 'undefined') return;

    const p = Math.min(100, Math.max(0, Number(probability)));
    const remainder = Math.max(0, 100 - p);
    const mainColor = result === 'Success' ? chartColors.success : chartColors.failure;

    if (predictionScoreChart) {
      predictionScoreChart.destroy();
      predictionScoreChart = null;
    }

    predictionScoreChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Success likelihood', 'Remaining risk'],
        datasets: [
          {
            data: [p, remainder],
            backgroundColor: [mainColor, chartColors.probRemain],
            borderWidth: 0,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        animation: {
          animateRotate: true,
          animateScale: true,
          duration: 600,
          easing: 'easeOutQuart',
        },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              usePointStyle: true,
              padding: 12,
              font: { size: 11 },
            },
          },
          tooltip: {
            callbacks: {
              label: function (item) {
                return item.label + ': ' + window.formatPercentage(item.raw);
              },
            },
          },
        },
      },
    });
  }

  function showResult(probability, result, scores = null, featureImportance = [], recommendations = []) {
    const placeholder = document.getElementById('result-placeholder');
    const panel = document.getElementById('result-panel');
    const probEl = document.getElementById('prob-value');
    const badge = document.getElementById('result-badge');
    const ring = document.getElementById('result-ring');
    const riskScore = document.getElementById('risk-score-value');
    const riskProgress = document.getElementById('risk-progress');
    const confidence = document.getElementById('confidence-value');

    if (placeholder) placeholder.classList.add('hidden');
    if (panel) panel.classList.remove('hidden');
    if (probEl) {
      probEl.textContent = window.formatPercentage(probability);
      probEl.classList.add('count-up');
      setTimeout(() => probEl.classList.remove('count-up'), 500);
    }
    if (badge) {
      badge.textContent = result === 'Success' ? 'High Potential' : 'Needs Attention';
      badge.className =
        'inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ' +
        (result === 'Success'
          ? 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200'
          : 'bg-rose-100 text-rose-800 ring-1 ring-rose-200');
    }
    if (ring) ring.style.setProperty('--ring-pct', String(probability));

    const risk = Math.max(0, Math.min(100, 100 - Number(probability)));
    const riskLabel = risk <= 25 ? 'Low' : risk <= 55 ? 'Medium' : 'High';
    if (riskScore) riskScore.textContent = riskLabel + ' (' + risk.toFixed(2) + '/100)';
    if (riskProgress) {
      riskProgress.style.width = window.formatPercentage(risk);
      riskProgress.className =
        'h-full rounded-full transition-all duration-500 ' +
        (risk <= 25 ? 'bg-emerald-500' : risk <= 55 ? 'bg-amber-500' : 'bg-rose-500');
    }
    if (confidence) {
      const confidenceValue = Math.max(55, Math.min(99.5, Number(probability) + 8.5));
      confidence.textContent = window.formatPercentage(confidenceValue);
    }

    // Display score breakdown if provided
    const breakdownEl = document.getElementById('score-breakdown');
    if (scores && breakdownEl) {
      document.getElementById('funding-score').textContent = scores.funding.toFixed(1);
      document.getElementById('team-score').textContent = scores.team.toFixed(1);
      document.getElementById('revenue-score').textContent = scores.revenue.toFixed(1);
      document.getElementById('industry-score').textContent = scores.industry.toFixed(1);
      document.getElementById('location-score').textContent = scores.location.toFixed(1);
      document.getElementById('total-score').textContent = scores.total.toFixed(1);
      breakdownEl.classList.remove('hidden');
    } else if (breakdownEl) {
      breakdownEl.classList.add('hidden');
    }

    // Display feature importance chart
    const featureSection = document.getElementById('feature-importance-section');
    if (featureImportance.length > 0) {
      updateFeatureImportanceChart(featureImportance);
      if (featureSection) featureSection.classList.remove('hidden');
    } else if (featureSection) {
      featureSection.classList.add('hidden');
    }

    // Display recommendations
    const recSection = document.getElementById('recommendations-section');
    if (recommendations.length > 0) {
      displayRecommendations(recommendations);
      if (recSection) recSection.classList.remove('hidden');
    } else if (recSection) {
      recSection.classList.add('hidden');
    }

    const aiContainer = document.getElementById('ai-advisor-container');
    const aiSection = document.getElementById('ai-advisor-section');
    const currentStartupData = window.__currentStartupData || {};
    const mlResult = window.__currentMLResult || {
      prediction: result,
      success_probability: Number(probability) || 0,
      failure_probability: Math.max(0, 100 - Number(probability)),
      confidence: Number(probability) || 0,
    };
    if (aiSection) aiSection.classList.remove('hidden');
    if (aiContainer && window.CleverFundAI && window.CleverFundAI.initAIAdvisor) {
      CleverFundAI.initAIAdvisor(aiContainer, currentStartupData, mlResult);
    }

    updatePredictionChart(probability, result);
  }

  function updateFeatureImportanceChart(featureImportance) {
    const ctx = document.getElementById('featureImportanceChart');
    if (!ctx || typeof Chart === 'undefined' || !featureImportance.length) return;

    // Destroy existing chart
    if (window.featureImportanceChart && typeof window.featureImportanceChart.destroy === 'function') {
      try {
        window.featureImportanceChart.destroy();
      } catch (error) {
        console.warn('Error destroying feature importance chart:', error);
      }
    }

    const labels = featureImportance.map(item => item.feature);
    const values = featureImportance.map(item => item.value);

    window.featureImportanceChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Feature Contribution (%)',
          data: values,
          backgroundColor: [
            'rgba(37, 99, 235, 0.8)',
            'rgba(34, 197, 94, 0.8)',
            'rgba(245, 158, 11, 0.8)',
            'rgba(239, 68, 68, 0.8)',
            'rgba(168, 85, 247, 0.8)'
          ],
          borderRadius: 6,
          borderSkipped: false,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                return context.label + ': ' + window.formatPercentage(context.raw);
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            grid: { color: 'rgba(148, 163, 184, 0.2)' },
            ticks: {
              callback: function(value) {
                return window.formatPercentage(value);
              }
            }
          },
          x: {
            grid: { display: false }
          }
        }
      }
    });
  }

  function displayRecommendations(recommendations) {
    const container = document.getElementById('recommendations-container');
    if (!container) return;

    container.innerHTML = '';

    if (recommendations.length === 0) {
      container.innerHTML = '<p class="text-sm text-slate-500">No specific recommendations at this time.</p>';
      return;
    }

    recommendations.forEach(rec => {
      const recEl = document.createElement('div');
      recEl.className = 'p-4 rounded-xl border border-slate-200 bg-white shadow-sm';

      const priorityColor = rec.priority === 'high' ? 'text-rose-600 bg-rose-50 border-rose-200' :
                           rec.priority === 'medium' ? 'text-amber-600 bg-amber-50 border-amber-200' :
                           'text-slate-600 bg-slate-50 border-slate-200';

      recEl.innerHTML = `
        <div class="flex items-start gap-3">
          <div class="flex-shrink-0 w-8 h-8 rounded-full ${priorityColor} flex items-center justify-center">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
          </div>
          <div class="flex-1">
            <h4 class="font-semibold text-slate-900 text-sm">${rec.title}</h4>
            <p class="text-sm text-slate-600 mt-1">${rec.description}</p>
            <p class="text-xs text-brand-600 mt-2 font-medium">${rec.suggestion}</p>
          </div>
        </div>
      `;

      container.appendChild(recEl);
    });
  }

  function showError(msg) {
    const el = document.getElementById('form-error');
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
  }

  function clearError() {
    const el = document.getElementById('form-error');
    if (!el) return;
    el.textContent = '';
    el.classList.add('hidden');
  }

  function setDatasetBanner(msg) {
    const el = document.getElementById('dataset-banner');
    if (!el) return;
    if (!msg) {
      el.textContent = '';
      el.classList.add('hidden');
      return;
    }
    el.textContent = msg;
    el.classList.remove('hidden');
  }

  async function handlePredict(e) {
    e.preventDefault();
    clearError();

    const funding = parseFloat(document.getElementById('funding').value);
    const employees = parseInt(document.getElementById('employees').value, 10);
    const industryEl = document.getElementById('market_sector') || document.getElementById('industry');
    const industry = industryEl ? industryEl.value : 'Other';
    const startupNameInput = document.getElementById('startup_name');
    const startup_name = startupNameInput ? startupNameInput.value.trim() : '';
    const yearsOpEl = document.getElementById('years_operation');
    const yearsInOp = yearsOpEl ? parseFloat(yearsOpEl.value || '0') : 0;
    const revenueInput = document.getElementById('revenue');
    const fundingRoundEl = document.querySelector('input[name="funding_round"]:checked');
    const funding_round = fundingRoundEl ? fundingRoundEl.value : null;
    // Backend expects revenue. Estimate from funding and years when explicit revenue is absent.
    const estimatedRevenue = Math.max(0, funding * (0.45 + yearsInOp * 0.15));
    if (revenueInput && (!revenueInput.value || Number(revenueInput.value) <= 0)) {
      revenueInput.value = String(estimatedRevenue.toFixed(2));
    }
    const revenue = parseFloat((revenueInput && revenueInput.value) || String(estimatedRevenue));
    const location = document.getElementById('location').value.trim();
    const fallbackStartupName = `${(industry.split('/')[0] || 'Startup').trim() || 'Startup'} Venture #${predictionCount + 1}`;
    const currentStartupData = {
      startup_name: startup_name || fallbackStartupName,
      industry: industry,
      location: location,
      funding_amount: funding,
      revenue: revenue,
      employees: employees,
      funding_round: funding_round,
      years_operation: yearsInOp,
    };
    window.__currentStartupData = currentStartupData;

    const payload = {
      startup_name: startup_name || fallbackStartupName,
      funding_amount: funding,
      employees: employees,
      industry: industry,
      revenue: revenue,
      location: location,
      funding_round: funding_round,
      years_operation: yearsInOp,
    };

    setLoading(true);
    try {
      // Use ML endpoint if toggled, otherwise use rule-based
      const endpoint = useMLModel ? '/api/ml-predict' : '/predict';
      
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'same-origin',
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        window.location.href = data.login || '/login';
        return;
      }
      if (!res.ok) {
        throw new Error(data.error || 'Prediction failed');
      }

      // Handle both rule-based and ML responses
      const probability = data.probability || data.success_probability || 0;
      const result = data.result || data.prediction || 'Unknown';
      
      // For ML model, we don't have scores breakdown, so create estimated ones
      let scores = null;
      if (useMLModel) {
        // Estimate scores from ML probability for display
        scores = {
          funding: probability / 5,
          team: probability / 5,
          revenue: probability / 5,
          industry: probability / 5,
          location: probability / 5,
          total: probability
        };
      } else {
        // Calculate scores locally for rule-based (keeping for backward compatibility)
        const fundingScore = Math.min(funding / 5000000, 1.0) * 25;
        const teamScore = Math.min(employees / 200, 1.0) * 20;
        const revenueScore = Math.min(revenue / 10000000, 1.0) * 25;

        let industryBonus = 0;
        if (industry.toLowerCase().includes('technology') || industry.toLowerCase().includes('software')) {
          industryBonus = 20;
        } else if (industry.toLowerCase().includes('healthcare') || industry.toLowerCase().includes('biotech')) {
          industryBonus = 15;
        } else if (industry.toLowerCase().includes('finance') || industry.toLowerCase().includes('fintech')) {
          industryBonus = 10;
        }

        let locationBonus = 0;
        if (location.toLowerCase().includes('san francisco') || location.toLowerCase().includes('silicon valley')) {
          locationBonus = 10;
        } else if (location.toLowerCase().includes('new york') || location.toLowerCase().includes('boston')) {
          locationBonus = 8;
        } else if (location.toLowerCase().includes('austin') || location.toLowerCase().includes('seattle')) {
          locationBonus = 5;
        }

        const totalScore = fundingScore + teamScore + revenueScore + industryBonus + locationBonus;
        scores = {
          funding: fundingScore,
          team: teamScore,
          revenue: revenueScore,
          industry: industryBonus,
          location: locationBonus,
          total: totalScore
        };
      }

      const featureImportance = data.feature_importance || [];
      const recommendations = data.recommendations || [];
      const reportName = startup_name || `${(industry.split('/')[0] || 'Startup').trim() || 'Startup'} Venture #${predictionCount + 1}`;
      const mlResult = {
        prediction: result,
        success_probability: Number(probability) || 0,
        failure_probability: 100 - (Number(probability) || 0),
        confidence: Number(probability) || 0,
      };
      window.__currentMLResult = mlResult;
      window.__currentStartupData = {
        ...window.__currentStartupData,
        startup_name: reportName,
      };

      showResult(probability, result, scores, featureImportance, recommendations);

      predictionCount += 1;
      updateStats();

      reportRows = [
        {
          name: reportName,
          funding: formatCurrency(funding),
          result: result,
          probability: window.formatPercentage(probability),
        },
        ...reportRows,
      ];
      renderTable();
    } catch (err) {
      showError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }

  function toggleMLModel() {
    useMLModel = !useMLModel;
    const toggle = document.getElementById('model-toggle');
    const dot = document.getElementById('model-toggle-dot');
    const label = document.getElementById('model-label');
    const info = document.getElementById('model-info');

    if (useMLModel) {
      toggle.classList.remove('bg-slate-300');
      toggle.classList.add('bg-blue-600');
      dot.classList.remove('translate-x-0');
      dot.classList.add('translate-x-5');
      label.textContent = 'ML (SMOTE+RF)';
      toggle.setAttribute('aria-checked', 'true');
      if (info) info.classList.remove('hidden');
      // Show notification
      showError(''); // Clear any errors
      const msg = 'Switched to ML-based predictions with SMOTE class balancing';
      console.log(msg);
    } else {
      toggle.classList.add('bg-slate-300');
      toggle.classList.remove('bg-blue-600');
      dot.classList.add('translate-x-0');
      dot.classList.remove('translate-x-5');
      label.textContent = 'Rule-Based';
      toggle.setAttribute('aria-checked', 'false');
      if (info) info.classList.add('hidden');
    }
  }

  async function loadDashboard() {
    try {
      const res = await fetch('/api/dashboard-data', { credentials: 'same-origin' });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        window.location.href = data.login || '/login';
        return;
      }
      if (!data.ok) {
        setDatasetBanner(data.error || 'Could not load dataset for charts.');
        initCharts(null);
        return;
      }
      setDatasetBanner('');
      updateStatsFromPayload(data.stats);
      initCharts(data);
      if (data.recent_activity && data.recent_activity.length) {
        reportRows = data.recent_activity.map(function (r) {
          return {
            name: r.name,
            funding: r.funding,
            result: r.result,
            probability: r.probability,
          };
        });
        renderTable();
      }
    } catch (err) {
      setDatasetBanner(err.message || 'Failed to load dashboard data');
      initCharts(null);
    }
  }

  async function exportPDF() {
    const btn = document.getElementById('export-pdf-btn');
    if (!btn || btn.disabled) return;
    
    btn.disabled = true;
    btn.textContent = 'Generating...';
    
    try {
      const response = await fetch('/api/export-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          predictions: reportRows,
          stats: {
            total: predictionCount,
            useML: useMLModel
          }
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to generate PDF');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `startup-report-${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      alert('Error exporting PDF: ' + err.message);
      console.error(err);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Export PDF';
    }
  }

  async function shareReport() {
    const btn = document.getElementById('share-report-btn');
    if (!btn || btn.disabled) return;
    
    btn.disabled = true;
    btn.textContent = 'Sharing...';
    
    try {
      const response = await fetch('/api/share-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          predictions: reportRows,
          stats: {
            total: predictionCount,
            useML: useMLModel
          }
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to create shareable link');
      }
      
      const data = await response.json();
      const shareUrl = data.share_url || data.url;
      
      if (navigator.share) {
        navigator.share({
          title: 'CleverFund Prediction Report',
          text: 'Check out my startup success prediction analysis',
          url: shareUrl
        }).catch(err => console.log('Share cancelled', err));
      } else {
        const copied = await copyToClipboard(shareUrl);
        if (copied) {
          alert('Share link copied to clipboard!\n\n' + shareUrl);
        }
      }
    } catch (err) {
      alert('Error creating share link: ' + err.message);
      console.error(err);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Share Report';
    }
  }

  async function copyToClipboard(text) {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        return true;
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        return true;
      }
    } catch (err) {
      console.error('Failed to copy:', err);
      return false;
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    loadDashboard();
    updateStats();

    const form = document.getElementById('predict-form');
    if (form) form.addEventListener('submit', handlePredict);

    // Add model toggle listener
    const modelToggle = document.getElementById('model-toggle');
    if (modelToggle) {
      modelToggle.addEventListener('click', toggleMLModel);
    }

    // Add export PDF button listener
    const exportBtn = document.getElementById('export-pdf-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', exportPDF);
    }

    // Add share report button listener
    const shareBtn = document.getElementById('share-report-btn');
    if (shareBtn) {
      shareBtn.addEventListener('click', shareReport);
    }
  });
})();
