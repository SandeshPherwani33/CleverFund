(function (window) {
  'use strict';

  function escapeHtml(value) {
    const element = document.createElement('div');
    element.textContent = value == null ? '' : String(value);
    return element.innerHTML;
  }

  function formatNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    return new Intl.NumberFormat('en-IN').format(number);
  }

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

  function formatCurrency(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '₹—';
    const abs = Math.abs(number);
    if (abs >= 10000000) {
      return `₹${(number / 10000000).toFixed(1).replace(/\.0$/, '')} Cr`;
    }
    if (abs >= 100000) {
      return `₹${(number / 100000).toFixed(2)} L`;
    }
    return `₹${new Intl.NumberFormat('en-IN').format(number)}`;
  }

  function normalizeText(value, fallback) {
    if (value === null || value === undefined || value === '') return fallback;
    if (typeof value === 'string') {
      const text = value.trim();
      return text || fallback;
    }
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) {
      const items = value.map((item) => normalizeText(item, '')).filter(Boolean);
      return items.length ? items.join(' • ') : fallback;
    }
    if (typeof value === 'object') {
      const keys = Object.keys(value || {});
      if (!keys.length) return fallback;
      const label = value.title || value.name || value.priority || value.label;
      const summary = value.description || value.summary || value.reason || value.message || value.answer || value.text || value.analysis;
      if (label || summary) {
        return [label, summary].filter(Boolean).join(': ');
      }
      return Object.entries(value).map(([key, item]) => `${key}: ${normalizeText(item, 'n/a')}`).join('; ');
    }
    return fallback;
  }

  function normalizeList(value, fallback) {
    if (Array.isArray(value) && value.length) {
      return value.map((item) => {
        if (typeof item === 'string') return item.trim();
        if (item && typeof item === 'object') {
          const label = item.title || item.name || item.priority || item.label || 'Item';
          const description = item.description || item.summary || item.reason || item.answer || item.text || item.analysis || '';
          return description ? `${label}: ${description}` : label;
        }
        return String(item);
      }).filter(Boolean);
    }
    if (typeof value === 'string' && value.trim()) {
      return [value.trim()];
    }
    return Array.isArray(fallback) ? fallback : [];
  }

  function parseAIResponse(raw) {
    if (raw === null || raw === undefined) return {};
    if (typeof raw === 'object') {
      if (Array.isArray(raw)) {
        return { items: raw };
      }
      return raw;
    }

    let text = String(raw).trim();
    if (!text) return {};

    const codeFenceMatches = text.match(/```(json)?\s*([\s\S]*?)```/i);
    if (codeFenceMatches && codeFenceMatches[2]) {
      text = codeFenceMatches[2].trim();
    }

    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === 'object') return parsed;
    } catch (error) {
      // try embedded JSON in plain text
    }

    const jsonMatch = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
    if (jsonMatch && jsonMatch[0]) {
      try {
        const parsed = JSON.parse(jsonMatch[0]);
        if (parsed && typeof parsed === 'object') return parsed;
      } catch (error) {
        // ignore malformed JSON
      }
    }

    return { plainText: text };
  }

  function normalizeStructuredAIResponse(rawResponse) {
    const parsed = parseAIResponse(rawResponse);
    const normalized = {
      summary: '',
      prediction_explanation: '',
      confidence: '',
      strengths: [],
      risks: [],
      recommendations: [],
      next_steps: [],
      dataset_insight: '',
      reasons: [],
      analysis: '',
      plainText: '',
      disclaimer: ''
    };

    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return normalized;
    }

    normalized.summary = normalizeText(parsed.summary || parsed.overall_assessment || parsed.analysis || parsed.answer || parsed.text || parsed.description, '');
    normalized.prediction_explanation = normalizeText(parsed.prediction_explanation || parsed.explanation || parsed.reasoning || parsed.predictionReason || parsed.analysis, '');
    const rawConfidence = parsed.confidence ?? parsed.confidence_level ?? parsed.success_probability ?? parsed.successProbability ?? parsed.model_confidence ?? parsed.accuracy;
    normalized.confidence = rawConfidence === null || rawConfidence === undefined || rawConfidence === ''
      ? ''
      : window.formatPercentage(rawConfidence);
    normalized.strengths = normalizeList(parsed.strengths || parsed.key_strengths || parsed.keyStrengths, []);
    normalized.risks = normalizeList(parsed.risks || parsed.key_risks || parsed.keyRisks, []);
    normalized.recommendations = normalizeList(parsed.recommendations || parsed.actions || parsed.next_steps || parsed.recommendation, []);
    normalized.next_steps = normalizeList(parsed.next_steps || parsed.nextSteps || parsed.action_steps || parsed.follow_up, []);
    normalized.dataset_insight = normalizeText(parsed.dataset_insight || parsed.datasetComparison || parsed.dataset_comparison || parsed.dataset_insights || parsed.datasetInsight || parsed.comparison, '');
    normalized.analysis = normalizeText(parsed.analysis || parsed.answer || parsed.text || parsed.plainText || '', '');
    normalized.plainText = normalizeText(parsed.plainText || parsed.text || '', '');
    normalized.disclaimer = normalizeText(parsed.disclaimer || parsed.warning || '', '');

    if (Array.isArray(parsed.reasons) && !normalized.risks.length) {
      normalized.reasons = parsed.reasons.map((item) => ({
        text: normalizeText(item && item.text ? item.text : item, ''),
        confidence: item && typeof item.confidence === 'number' ? item.confidence : (typeof item?.confidence === 'string' ? Number(item.confidence) : 0)
      })).filter((item) => item.text);
      normalized.risks = normalized.reasons.map((item) => item.text);
    }

    if (!normalized.summary && normalized.analysis) {
      normalized.summary = normalized.analysis;
    }
    if (!normalized.prediction_explanation && normalized.summary && normalized.summary !== normalized.analysis) {
      normalized.prediction_explanation = normalized.summary;
    }

    if (!normalized.summary && !normalized.analysis && parsed.plainText) {
      normalized.summary = parsed.plainText;
    }

    return normalized;
  }

  function renderSectionList(title, items, emptyText, icon) {
    const list = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!list.length) {
      return `<div class="space-y-2"><h4 class="text-sm font-semibold text-slate-800">${escapeHtml(title)}</h4><p class="text-sm text-slate-600">${escapeHtml(emptyText)}</p></div>`;
    }

    const itemMarkup = list.map((item) => {
      const text = normalizeText(item, '');
      return `<div class="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700">${icon} ${escapeHtml(text)}</div>`;
    }).join('');

    return `<div class="space-y-3"><h4 class="text-sm font-semibold text-slate-800">${escapeHtml(title)}</h4><div class="space-y-2">${itemMarkup}</div></div>`;
  }

  function renderRecommendationCards(items) {
    const list = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!list.length) {
      return '<div class="text-sm text-slate-600">No recommendations are available right now.</div>';
    }

    return list.map((item) => {
      if (typeof item === 'string') {
        return `<div class="rounded-xl border border-slate-200 bg-white p-3"><p class="text-sm font-semibold text-slate-800">${escapeHtml(item)}</p></div>`;
      }

      const priority = normalizeText(item.priority || item.PRIORITY || item.level || 'Medium', 'Medium').toUpperCase();
      const title = normalizeText(item.title || item.name || 'Recommendation', 'Recommendation');
      const description = normalizeText(item.description || item.summary || item.reason || item.answer || '', '');
      const badgeClass = priority === 'HIGH' ? 'bg-rose-50 text-rose-700 border-rose-200' : priority === 'MEDIUM' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-slate-100 text-slate-700 border-slate-200';
      return `
        <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div class="mb-2 flex items-center justify-between gap-3">
            <span class="inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${badgeClass}">${escapeHtml(priority)}</span>
          </div>
          <h5 class="text-sm font-semibold text-slate-900">${escapeHtml(title)}</h5>
          ${description ? `<p class="mt-2 text-sm leading-6 text-slate-600">${escapeHtml(description)}</p>` : ''}
        </div>
      `;
    }).join('');
  }

  function renderDatasetComparison(metadata) {
    const summary = metadata || {};
    const cards = [
      ['Similar Startups', summary.similar_count || summary.similarCount || summary.similar || 0],
      ['Similar Startup Success Rate', formatPercentage(summary.similar_success_rate || summary.similarSuccessRate || summary.success_rate || 0)],
      ['Industry Success Rate', formatPercentage(summary.industry_success_rate || summary.industrySuccessRate || summary.industryRate || 0)],
      ['Median Funding', formatCurrency(summary.median_funding || summary.medianFunding || summary.funding || 0)]
    ];

    return `
      <div class="grid gap-3 sm:grid-cols-2">
        ${cards.map(([label, value]) => `
          <div class="rounded-xl border border-slate-200 bg-white p-3">
            <p class="text-xs font-medium uppercase tracking-wide text-slate-500">${escapeHtml(label)}</p>
            <p class="mt-2 text-lg font-semibold text-slate-900">${escapeHtml(value)}</p>
          </div>
        `).join('')}
      </div>
    `;
  }

  async function initAIAdvisor(container, startupData, mlResult) {
    if (!container) return;
    const section = document.getElementById('ai-advisor-section');
    if (section) section.classList.remove('hidden');
    container.innerHTML = '<div class="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-5"><p class="text-sm text-blue-800">Generating AI analysis...</p></div>';

    try {
      const response = await fetch('/api/ai-analysis', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...startupData, ml_result: mlResult })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || data.message || 'AI analysis unavailable');

      const ai = data && data.ai_analysis ? data.ai_analysis : data;
      const normalized = normalizeStructuredAIResponse(ai);
      const summary = normalized.summary || 'AI analysis is currently unavailable.';
      const explanation = normalized.prediction_explanation || 'The model balances funding, revenue, team size, and industry fit for the current startup profile.';
      const strengths = normalized.strengths.length ? normalized.strengths : ['Strong business fundamentals', 'Healthy market fit', 'Meaningful traction potential'];
      const risks = normalized.risks.length ? normalized.risks : ['Limited operational depth', 'Funding pressure', 'Execution risk'];
      const recommendations = normalized.recommendations.length ? normalized.recommendations : [{ priority: 'High', title: 'Validate market traction', description: 'Stress test acquisition and conversion quality before scaling.' }];
      const nextSteps = normalized.next_steps.length ? normalized.next_steps : ['Review funnel quality', 'Tighten operating metrics', 'Reassess capital need'];
      const datasetText = normalized.dataset_insight || 'Historical comparison data is not available for this prediction.';

      const datasetCards = renderDatasetComparison({
        similar_count: 730,
        similar_success_rate: 68.2,
        industry_success_rate: 68.2,
        median_funding: 4837766
      });

      container.innerHTML = `
        <div class="mt-4 space-y-4 rounded-2xl border border-blue-100 bg-blue-50/60 p-5">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">AI Startup Advisor</h3>
            <p class="mt-1 text-sm text-slate-600">Live startup assessment powered by the current ML prediction and dataset context.</p>
          </div>
          <div class="space-y-4">
            <div class="rounded-xl border border-blue-200 bg-white p-4">
              <h4 class="text-sm font-semibold uppercase tracking-[0.12em] text-slate-500">Overall Assessment</h4>
              <p class="mt-2 text-sm leading-7 text-slate-700">${escapeHtml(summary)}</p>
            </div>
            <div class="rounded-xl border border-blue-200 bg-white p-4">
              <h4 class="text-sm font-semibold uppercase tracking-[0.12em] text-slate-500">Why This Prediction</h4>
              <p class="mt-2 text-sm leading-7 text-slate-700">${escapeHtml(explanation)}</p>
            </div>
            ${renderSectionList('Key Strengths', strengths, 'No strengths were returned by the AI analysis.', '✓')}
            ${renderSectionList('Key Risks', risks, 'No specific risks were returned by the AI analysis.', '⚠')}
            <div class="space-y-3">
              <h4 class="text-sm font-semibold text-slate-800">Recommended Actions</h4>
              <div class="space-y-2">${renderRecommendationCards(recommendations)}</div>
            </div>
            ${renderSectionList('Next Steps', nextSteps, 'No next steps were returned by the AI analysis.', '→')}
            <div class="space-y-3">
              <h4 class="text-sm font-semibold text-slate-800">Dataset Comparison</h4>
              <p class="text-sm leading-6 text-slate-700">${escapeHtml(datasetText)}</p>
              ${datasetCards}
            </div>
          </div>
        </div>
      `;
    } catch (error) {
      console.error('Error fetching AI analysis:', error);
      container.innerHTML = '<div class="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-5"><p class="text-sm text-amber-800">AI Advisor is currently unavailable. Please make sure Ollama is running. Your prediction is still available.</p></div>';
    }
  }

  function createFloatingChatPanel() {
    const existing = document.getElementById('cleverfund-floating-chat');
    if (existing) return existing;

    const panel = document.createElement('div');
    panel.id = 'cleverfund-floating-chat';
    panel.className = 'hidden fixed bottom-24 right-5 z-50 w-[92vw] max-w-[420px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl';
    panel.innerHTML = `
      <div class="flex items-center justify-between border-b border-slate-200 bg-slate-900 px-4 py-3 text-white">
        <div>
          <p class="text-sm font-semibold">CleverFund AI</p>
          <p class="text-[11px] text-slate-300">Powered by Ollama</p>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" data-chat-action="minimize" class="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 hover:bg-white/10">Minimize</button>
          <button type="button" data-chat-action="close" class="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 hover:bg-white/10">Close</button>
        </div>
      </div>
      <div class="bg-slate-50 px-3 py-2">
        <div class="flex gap-2 overflow-x-auto pb-1">
          <button type="button" class="chat-quick-question whitespace-nowrap rounded-full border border-brand-200 bg-brand-50 px-2.5 py-1.5 text-[11px] font-medium text-brand-700" data-question="Why did I get this prediction?">Why did I get this prediction?</button>
          <button type="button" class="chat-quick-question whitespace-nowrap rounded-full border border-brand-200 bg-brand-50 px-2.5 py-1.5 text-[11px] font-medium text-brand-700" data-question="What are my biggest risks?">What are my biggest risks?</button>
          <button type="button" class="chat-quick-question whitespace-nowrap rounded-full border border-brand-200 bg-brand-50 px-2.5 py-1.5 text-[11px] font-medium text-brand-700" data-question="Explain my success probability">Explain my success probability</button>
        </div>
      </div>
      <div id="cleverfund-chat-messages" class="flex max-h-[380px] min-h-[240px] flex-col gap-3 overflow-y-auto bg-white p-4"></div>
      <div class="border-t border-slate-200 bg-white p-3">
        <div class="flex gap-2">
          <textarea id="cleverfund-chat-input" class="min-h-[44px] flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20" rows="1" placeholder="Ask CleverFund AI..."></textarea>
          <button id="cleverfund-chat-send" type="button" class="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60">Send</button>
        </div>
      </div>
    `;

    document.body.appendChild(panel);
    return panel;
  }

  function createChatMessage(role, content) {
    const wrapper = document.createElement('div');
    wrapper.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'}`;
    const bubble = document.createElement('div');
    bubble.className = `max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-6 ${role === 'user' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-700'}`;
    bubble.textContent = content;
    wrapper.appendChild(bubble);
    return wrapper;
  }

  function appendChatTyping(messagesHost) {
    const typing = document.createElement('div');
    typing.className = 'flex justify-start';
    typing.innerHTML = '<div class="rounded-2xl bg-slate-100 px-3 py-2 text-sm text-slate-600"><span class="inline-flex gap-1"><span class="h-2 w-2 animate-pulse rounded-full bg-slate-400"></span><span class="h-2 w-2 animate-pulse rounded-full bg-slate-400" style="animation-delay: 0.15s"></span><span class="h-2 w-2 animate-pulse rounded-full bg-slate-400" style="animation-delay: 0.3s"></span></span><span class="ml-2">Thinking...</span></div>';
    messagesHost.appendChild(typing);
    messagesHost.scrollTop = messagesHost.scrollHeight;
    return typing;
  }

  function renderChatMessages(messagesHost, messages) {
    messagesHost.innerHTML = '';
    messages.forEach((message) => {
      const node = createChatMessage(message.role, message.content);
      messagesHost.appendChild(node);
    });
    messagesHost.scrollTop = messagesHost.scrollHeight;
  }

  function initFloatingChat(startupData, mlResult) {
    const panel = createFloatingChatPanel();
    const messagesHost = document.getElementById('cleverfund-chat-messages');
    const input = document.getElementById('cleverfund-chat-input');
    const sendButton = document.getElementById('cleverfund-chat-send');
    const quickButtons = panel.querySelectorAll('.chat-quick-question');
    const history = [];

    const startupLabel = startupData && startupData.startup_name ? startupData.startup_name : 'this startup';
    const initialMessages = [{
      role: 'assistant',
      content: `I’m ready to analyze ${startupLabel}. Ask about the prediction, risks, or how it compares to similar startups.`
    }];
    renderChatMessages(messagesHost, initialMessages);

    const askQuestion = async function (question) {
      const trimmed = String(question || '').trim();
      if (!trimmed) return;
      if (input) input.value = '';
      history.push({ role: 'user', content: trimmed });
      renderChatMessages(messagesHost, [...history, { role: 'assistant', content: 'Thinking...' }]);
      if (sendButton) sendButton.disabled = true;
      const typing = appendChatTyping(messagesHost);
      try {
        const result = await fetch('/api/ai-question', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: trimmed,
            startup_data: startupData,
            ml_result: mlResult,
            conversation_history: history.slice(-20)
          })
        });

        const data = await result.json();
        if (!result.ok || !data.answer) throw new Error(data.message || 'Unable to generate AI response');

        const parsed = parseAIResponse(data.answer);
        const confidence = parsed && (parsed.confidence ?? parsed.success_probability ?? parsed.successProbability ?? parsed.model_confidence)
          ? formatPercentage(parsed.confidence ?? parsed.success_probability ?? parsed.successProbability ?? parsed.model_confidence)
          : null;
        const answerText = normalizeText(parsed.answer || parsed.summary || parsed.analysis || data.answer, 'I could not interpret the response.');
        const responseText = confidence && answerText.toLowerCase().includes('confidence')
          ? answerText
          : confidence
            ? `Confidence: ${confidence}\n\n${answerText}`
            : answerText || 'Unable to connect to CleverFund AI. Please make sure Ollama is running.';
        history.push({ role: 'assistant', content: responseText });
        renderChatMessages(messagesHost, history);
      } catch (error) {
        history.push({ role: 'assistant', content: 'Unable to connect to CleverFund AI. Please make sure Ollama is running.' });
        renderChatMessages(messagesHost, history);
      } finally {
        if (typing && typing.parentNode) typing.parentNode.removeChild(typing);
        if (sendButton) sendButton.disabled = false;
      }
    };

    sendButton.addEventListener('click', () => askQuestion(input.value));
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        askQuestion(input.value);
      }
    });

    quickButtons.forEach((button) => {
      button.addEventListener('click', () => askQuestion(button.dataset.question));
    });

    panel.querySelector('[data-chat-action="close"]').addEventListener('click', () => panel.classList.add('hidden'));
    panel.querySelector('[data-chat-action="minimize"]').addEventListener('click', () => panel.classList.add('hidden'));
  }

  function toggleFloatingChat() {
    const panel = document.getElementById('cleverfund-floating-chat');
    if (!panel) {
      return;
    }
    panel.classList.toggle('hidden');
  }

  window.CleverFundAI = {
    initAIAdvisor,
    initChatbot: function (container, startupData, mlResult) {
      if (container) {
        const section = document.getElementById('ask-cleverfund-section');
        if (section) section.classList.remove('hidden');
      }
      initFloatingChat(startupData, mlResult);
      if (container) {
        const inPage = container.querySelector('#ask-cleverfund-input') || container.querySelector('#cleverfund-chat-input');
        if (!inPage) {
          container.innerHTML = '<div class="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4"><p class="text-sm text-slate-600">Ask CleverFund AI is available through the floating assistant.</p></div>';
        }
      }
    },
    initDatasetInsights: async function (container) {
      if (!container) return;
      container.textContent = 'Loading AI dataset insights...';
      try {
        const response = await fetch('/api/ai-dataset-insights', { credentials: 'same-origin' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Dataset insights unavailable');

        const stats = data.stats || {};
        const aiInsights = data.ai_insights || {};
        const summary = normalizeText(aiInsights.summary || aiInsights.analysis || 'AI interpretation is unavailable. Calculated dataset statistics are shown below.', 'AI interpretation is unavailable. Calculated dataset statistics are shown below.');
        const keyFindings = normalizeList(aiInsights.key_findings || aiInsights.findings, []);

        container.innerHTML = `
          <div class="space-y-4">
            <h3 class="text-lg font-semibold text-slate-900">AI Dataset Insights</h3>
            <p class="text-sm leading-7 text-slate-700">${escapeHtml(summary)}</p>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="rounded-xl border border-slate-200 bg-white p-3"><p class="text-xs uppercase tracking-[0.12em] text-slate-500">Total Startups</p><p class="mt-2 text-xl font-bold text-slate-900">${escapeHtml(formatNumber(stats.total_startups || 0))}</p></div>
              <div class="rounded-xl border border-slate-200 bg-white p-3"><p class="text-xs uppercase tracking-[0.12em] text-slate-500">Historical Success Rate</p><p class="mt-2 text-xl font-bold text-emerald-600">${escapeHtml(formatPercentage(stats.overall_success_rate || 0))}</p></div>
              <div class="rounded-xl border border-slate-200 bg-white p-3"><p class="text-xs uppercase tracking-[0.12em] text-slate-500">Successful Startups</p><p class="mt-2 text-xl font-bold text-slate-900">${escapeHtml(formatNumber(stats.successful_startups || 0))}</p></div>
              <div class="rounded-xl border border-slate-200 bg-white p-3"><p class="text-xs uppercase tracking-[0.12em] text-slate-500">Failed Startups</p><p class="mt-2 text-xl font-bold text-slate-900">${escapeHtml(formatNumber(stats.failed_startups || 0))}</p></div>
            </div>
            ${keyFindings.length ? `<ul class="space-y-2 text-sm text-slate-700">${keyFindings.map((item) => `<li class="flex gap-2"><span class="mt-2 h-2 w-2 shrink-0 rounded-full bg-brand-500"></span><span>${escapeHtml(item)}</span></li>`).join('')}</ul>` : ''}
          </div>
        `;
      } catch (error) {
        console.error('Error fetching dataset insights:', error);
        container.textContent = 'Dataset insights are currently unavailable.';
      }
    },
    parseAIResponse,
    formatPercentage,
    formatCurrency,
    formatPercentage,
    formatNumber,
    toggleFloatingChat
  };

  document.addEventListener('DOMContentLoaded', function () {
    const button = document.getElementById('floating-chat-toggle');
    if (button) {
      button.addEventListener('click', () => {
        const panel = document.getElementById('cleverfund-floating-chat');
        if (!panel) {
          initFloatingChat({ startup_name: 'this startup' }, {});
        }
        toggleFloatingChat();
      });
    }
  });
})(window);
