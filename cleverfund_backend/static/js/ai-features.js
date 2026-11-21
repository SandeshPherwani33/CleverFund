/**
 * CleverFund AI Features Module
 * Handles: AI Startup Advisor, Ask CleverFund AI Chat, Dataset Insights
 */

(function(window) {
  'use strict';

  const AI = {
    // State management
    _conversationHistory: [],
    _isLoadingQuestion: false,
    
    /**
     * Initialize AI Advisor display for a prediction
     */
    async initAIAdvisor(container, startupData, mlResult) {
      if (!container) return;
      
      container.classList.remove('hidden');
      container.innerHTML = `
        <div class="mt-6 p-6 rounded-2xl border border-blue-200 bg-blue-50">
          <div class="flex items-center gap-2 mb-4">
            <span class="text-2xl">🤖</span>
            <h3 class="text-lg font-semibold text-slate-900">AI Startup Advisor</h3>
          </div>
          <div class="animate-pulse flex gap-4">
            <div class="h-4 bg-slate-300 rounded w-3/4"></div>
            <div class="h-4 bg-slate-300 rounded w-1/4"></div>
          </div>
          <p class="mt-2 text-sm text-slate-600">Generating AI analysis...</p>
        </div>
      `;
      
      try {
        const response = await fetch('/api/ai-analysis', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            startup_name: startupData.startup_name || startupData.name || '',
            industry: startupData.industry || '',
            location: startupData.location || '',
            funding_amount: startupData.funding_amount || startupData.funding || 0,
            revenue: startupData.revenue || 0,
            employees: startupData.employees || startupData.num_employees || 0,
            funding_round: startupData.funding_round || null,
            years_operation: startupData.years_operation || null,
            ml_result: mlResult
          })
        });
        
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || data.message || 'AI analysis unavailable');
        }
        if (data.ai_analysis) {
          AI._renderAIAdvisor(container, data.ai_analysis, startupData, mlResult);
        } else {
          container.innerHTML = `
            <div class="mt-6 p-6 rounded-2xl border border-amber-200 bg-amber-50">
              <p class="text-sm text-amber-800">
                AI analysis temporarily unavailable. Your ML prediction is still valid.
              </p>
            </div>
          `;
        }
      } catch (error) {
        console.error('Error fetching AI analysis:', error);
        container.innerHTML = `
          <div class="mt-6 p-6 rounded-2xl border border-rose-200 bg-rose-50">
            <p class="text-sm text-rose-800">
              Error generating AI analysis. Please try again.
            </p>
          </div>
        `;
      }
    },

    /**
     * Render structured AI Advisor output
     */
    _renderAIAdvisor(container, analysis, startupData, mlResult) {
      const h = (text) => {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
      };
      
      const sections = [
        {
          title: 'Overall Assessment',
          content: analysis.summary || 'Assessment in progress...',
          icon: '📊'
        },
        {
          title: 'Why This Prediction',
          content: analysis.prediction_explanation || 'Explanation pending...',
          icon: '💡'
        }
      ];
      
      if (analysis.strengths && analysis.strengths.length > 0) {
        sections.push({
          title: 'Key Strengths',
          content: `<ul class="list-disc pl-5 space-y-1">${analysis.strengths.map(s => `<li>${h(s)}</li>`).join('')}</ul>`,
          icon: '✅'
        });
      }
      
      if (analysis.risks && analysis.risks.length > 0) {
        sections.push({
          title: 'Key Risks',
          content: `<ul class="list-disc pl-5 space-y-1">${analysis.risks.map(r => `<li>${h(r)}</li>`).join('')}</ul>`,
          icon: '⚠️'
        });
      }
      
      if (analysis.recommendations && analysis.recommendations.length > 0) {
        const recs = analysis.recommendations.map(r => {
          if (typeof r === 'string') return `<li>${h(r)}</li>`;
          return `<li><strong>${h(r.priority || 'Action')}:</strong> ${h(r.title || '')} — ${h(r.description || '')}</li>`;
        }).join('');
        sections.push({
          title: 'Recommended Actions',
          content: `<ol class="list-decimal pl-5 space-y-1">${recs}</ol>`,
          icon: '🎯'
        });
      }
      
      if (analysis.next_steps && analysis.next_steps.length > 0) {
        sections.push({
          title: 'Next Steps',
          content: `<ol class="list-decimal pl-5 space-y-1">${analysis.next_steps.map(s => `<li>${h(s)}</li>`).join('')}</ol>`,
          icon: '🚀'
        });
      }
      
      if (analysis.dataset_insight) {
        sections.push({
          title: 'Dataset Comparison',
          content: analysis.dataset_insight,
          icon: '📈'
        });
      }
      
      // Build HTML
      let html = `
        <div class="mt-6 space-y-4">
          <div class="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-blue-100 p-6">
            <div class="flex items-start gap-3">
              <span class="text-3xl">🤖</span>
              <div class="flex-1">
                <h3 class="text-lg font-semibold text-slate-900">AI Startup Advisor</h3>
                <p class="mt-1 text-sm text-slate-600">ML Prediction: <strong>${h(mlResult.prediction || 'Pending')}</strong> (${mlResult.success_probability || '?'}% confidence)</p>
              </div>
            </div>
          </div>
      `;
      
      sections.forEach(section => {
        html += `
          <div class="ai-analysis-card rounded-xl border border-slate-200 bg-white p-5 hover:shadow-md transition">
            <h4 class="ai-analysis-title flex items-center gap-2 text-sm font-semibold text-slate-900 mb-3">
              <span>${section.icon}</span>
              ${section.title}
            </h4>
            <div class="ai-analysis-content text-sm text-slate-700 space-y-2">
              ${typeof section.content === 'string' ? `<p>${section.content}</p>` : section.content}
            </div>
          </div>
        `;
      });
      
      // Ask follow-up question section
      html += `
        <div class="rounded-xl border border-slate-200 bg-slate-50 p-5">
          <h4 class="text-sm font-semibold text-slate-900 mb-3">💬 Ask a Follow-up Question</h4>
          <div class="flex gap-2">
            <input type="text" placeholder="E.g., What should I focus on first?" 
              class="ai-follow-up-input flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              id="ai-follow-up-input">
            <button class="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50"
              id="ai-follow-up-btn">Ask</button>
          </div>
          <div id="ai-follow-up-response" class="ai-follow-up-response mt-3 hidden p-3 rounded-lg bg-white border border-slate-200 text-sm text-slate-700"></div>
        </div>
      `;
      
      if (analysis.disclaimer) {
        html += `
          <p class="text-xs text-slate-500 mt-4 italic">${h(analysis.disclaimer)}</p>
        `;
      }
      
      html += '</div>';
      
      container.innerHTML = html;
      container.classList.remove('hidden');
      
      // Attach event handlers
      const input = container.querySelector('#ai-follow-up-input');
      const btn = container.querySelector('#ai-follow-up-btn');
      const response = container.querySelector('#ai-follow-up-response');
      
      btn.addEventListener('click', () => AI._handleFollowUpQuestion(
        input, btn, response, startupData, mlResult
      ));
      
      input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          AI._handleFollowUpQuestion(input, btn, response, startupData, mlResult);
        }
      });
    },

    /**
     * Handle follow-up questions in AI Advisor
     */
    async _handleFollowUpQuestion(input, btn, response, startupData, mlResult) {
      const question = input.value.trim();
      if (!question) return;
      
      btn.disabled = true;
      input.disabled = true;
      response.textContent = '🤔 Thinking...';
      response.classList.remove('hidden');
      
      try {
        const payload = {
          question: question,
          startup_data: startupData,
          ml_result: mlResult,
          conversation_history: AI._conversationHistory
        };
        
        const resp = await fetch('/api/ai-question', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        
        const data = await resp.json();
        
        if (data.answer) {
          const h = (text) => {
            const d = document.createElement('div');
            d.textContent = text;
            return d.innerHTML;
          };
          response.innerHTML = `<p>${h(data.answer)}</p>`;
          
          // Store in conversation history
          AI._conversationHistory.push({role: 'user', content: question});
          AI._conversationHistory.push({role: 'assistant', content: data.answer});
          
          input.value = '';
        } else {
          response.textContent = 'AI could not generate a response. Please try again.';
        }
      } catch (error) {
        console.error('Error:', error);
        response.textContent = 'Error communicating with AI. Please check your connection.';
      } finally {
        btn.disabled = false;
        input.disabled = false;
      }
    },

    /**
     * Load and display Dataset Insights
     */
    async initDatasetInsights(container) {
      if (!container) return;
      
      container.innerHTML = `
        <div class="p-6 rounded-2xl border border-blue-200 bg-blue-50">
          <div class="animate-pulse">
            <div class="h-4 bg-slate-300 rounded w-1/2 mb-3"></div>
            <div class="h-4 bg-slate-300 rounded w-3/4"></div>
          </div>
          <p class="mt-2 text-sm text-slate-600">Analyzing startup dataset...</p>
        </div>
      `;
      
      try {
        const response = await fetch('/api/ai-dataset-insights', {
          credentials: 'same-origin'
        });
        
        const data = await response.json();
        AI._renderDatasetInsights(container, data);
      } catch (error) {
        console.error('Error fetching dataset insights:', error);
        container.innerHTML = `
          <div class="p-6 rounded-2xl border border-rose-200 bg-rose-50">
            <p class="text-sm text-rose-800">Failed to load dataset insights.</p>
          </div>
        `;
      }
    },

    /**
     * Render Dataset Insights with stats and AI interpretation
     */
    _renderDatasetInsights(container, data) {
      const h = (text) => {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
      };
      
      const stats = data.stats || {};
      const insights = data.ai_insights || {};
      
      let html = `
        <div class="space-y-6">
          <div class="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-blue-100 p-6">
            <h3 class="flex items-center gap-2 text-xl font-semibold text-slate-900">
              <span>📊</span> CleverFund Dataset Insights
            </h3>
          </div>
      `;
      
      // Statistics Grid
      if (Object.keys(stats).length > 0 && stats.error === undefined) {
        html += '<div class="grid gap-4 md:grid-cols-3">';
        
        if (stats.total_startups !== undefined) {
          html += `
            <div class="p-4 rounded-xl border border-slate-200 bg-white">
              <p class="text-sm text-slate-600">Total Startups</p>
              <p class="mt-2 text-2xl font-bold text-slate-900">${stats.total_startups}</p>
            </div>
          `;
        }
        
        if (stats.overall_success_rate !== undefined) {
          html += `
            <div class="p-4 rounded-xl border border-slate-200 bg-white">
              <p class="text-sm text-slate-600">Overall Success Rate</p>
              <p class="mt-2 text-2xl font-bold text-emerald-600">${Number(stats.overall_success_rate).toFixed(1)}%</p>
            </div>
          `;
        }
        
        if (stats.successful_startups !== undefined && stats.failed_startups !== undefined) {
          html += `
            <div class="p-4 rounded-xl border border-slate-200 bg-white">
              <p class="text-sm text-slate-600">Success / Failure</p>
              <p class="mt-2 text-lg font-bold text-slate-900">
                <span class="text-emerald-600">${stats.successful_startups}</span> / 
                <span class="text-rose-600">${stats.failed_startups}</span>
              </p>
            </div>
          `;
        }
        
        html += '</div>';
        
        // Additional stats in expandable section
        html += `
          <div class="rounded-xl border border-slate-200 bg-white p-5">
            <h4 class="font-semibold text-slate-900 mb-3">📈 Key Metrics</h4>
            <div class="grid gap-4 md:grid-cols-2">
        `;
        
        const metricLabels = {
          'median_funding_overall': 'Median Funding (Overall)',
          'median_funding_successful': 'Median Funding (Successful)',
          'median_revenue_successful': 'Median Revenue (Successful)',
          'median_employees_overall': 'Median Employees (Overall)',
          'median_employees_successful': 'Median Employees (Successful)'
        };
        
        Object.entries(metricLabels).forEach(([key, label]) => {
          if (stats[key] !== undefined && stats[key] !== null) {
            const value = key.includes('funding') || key.includes('revenue') 
              ? `₹${(stats[key] / 1000000).toFixed(2)}M`
              : stats[key].toFixed(1);
            html += `
              <div class="flex justify-between items-center p-2 border-b border-slate-100">
                <span class="text-sm text-slate-600">${label}</span>
                <span class="font-semibold text-slate-900">${value}</span>
              </div>
            `;
          }
        });
        
        html += '</div></div>';
      }
      
      // AI Insights
      if (insights && typeof insights === 'object' && insights.summary !== undefined) {
        html += `
          <div class="rounded-xl border border-slate-200 bg-white p-5">
            <h4 class="flex items-center gap-2 font-semibold text-slate-900 mb-3">
              <span>💡</span> AI Interpretation
            </h4>
            <p class="text-sm text-slate-700 mb-4">${h(insights.summary)}</p>
        `;
        
        if (insights.key_findings && insights.key_findings.length > 0) {
          html += `
            <div class="mt-4">
              <h5 class="text-sm font-semibold text-slate-900 mb-2">Key Findings</h5>
              <ul class="list-disc pl-5 space-y-1 text-sm text-slate-700">
                ${insights.key_findings.map(f => `<li>${h(f)}</li>`).join('')}
              </ul>
            </div>
          `;
        }
        
        if (insights.industry_insights && insights.industry_insights.length > 0) {
          html += `
            <div class="mt-4">
              <h5 class="text-sm font-semibold text-slate-900 mb-2">Industry Insights</h5>
              <ul class="list-disc pl-5 space-y-1 text-sm text-slate-700">
                ${insights.industry_insights.map(i => `<li>${h(i)}</li>`).join('')}
              </ul>
            </div>
          `;
        }
        
        if (insights.recommendations && insights.recommendations.length > 0) {
          html += `
            <div class="mt-4">
              <h5 class="text-sm font-semibold text-slate-900 mb-2">Recommendations</h5>
              <ul class="list-disc pl-5 space-y-1 text-sm text-slate-700">
                ${insights.recommendations.map(r => `<li>${h(r)}</li>`).join('')}
              </ul>
            </div>
          `;
        }
        
        if (insights.disclaimer) {
          html += `<p class="mt-4 text-xs text-slate-500 italic">${h(insights.disclaimer)}</p>`;
        }
        
        html += '</div>';
      }
      
      html += '</div>';
      
      container.innerHTML = html;
    },

    /**
     * Initialize Ask CleverFund AI chat modal/panel
     */
    initChatPanel(container, startupData, mlResult) {
      if (!container) return;
      
      // Reset conversation for new context
      AI._conversationHistory = [];
      
      container.innerHTML = `
        <div class="flex flex-col h-full bg-white rounded-2xl border border-slate-200">
          <!-- Header -->
          <div class="flex items-center justify-between border-b border-slate-200 p-4 bg-gradient-to-r from-blue-50 to-slate-50">
            <h3 class="font-semibold text-slate-900 flex items-center gap-2">
              <span>💬</span> Ask CleverFund AI
            </h3>
            <button class="text-slate-500 hover:text-slate-700" aria-label="Close" onclick="this.closest('[data-chat-panel]').classList.add('hidden')">
              ✕
            </button>
          </div>
          
          <!-- Messages -->
          <div class="flex-1 overflow-y-auto p-4 space-y-4" id="chat-messages">
            <div class="p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-slate-700">
              <p><strong>CleverFund AI:</strong> Hello! I'm ready to answer questions about this startup based on the ML prediction and historical data. What would you like to know?</p>
            </div>
          </div>
          
          <!-- Input -->
          <div class="border-t border-slate-200 p-4 bg-slate-50">
            <div class="flex gap-2 mb-2">
              <input type="text" placeholder="Ask a question..." 
                class="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                id="chat-input">
              <button class="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50"
                id="chat-send-btn">Send</button>
            </div>
            <button class="text-xs text-slate-500 hover:text-slate-700" id="chat-clear-btn">
              🗑️ Clear Conversation
            </button>
          </div>
        </div>
      `;
      
      container.setAttribute('data-chat-panel', 'true');
      
      const input = container.querySelector('#chat-input');
      const sendBtn = container.querySelector('#chat-send-btn');
      const clearBtn = container.querySelector('#chat-clear-btn');
      const messagesDiv = container.querySelector('#chat-messages');
      
      const handleSend = async () => {
        const question = input.value.trim();
        if (!question) return;
        
        // Add user message to UI
        const userMsg = document.createElement('div');
        userMsg.className = 'p-3 rounded-lg bg-slate-100 text-sm text-slate-900 text-right';
        userMsg.innerHTML = `<p><strong>You:</strong> ${AI._escapeHtml(question)}</p>`;
        messagesDiv.appendChild(userMsg);
        
        input.value = '';
        sendBtn.disabled = true;
        input.disabled = true;
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        try {
          const payload = {
            question: question,
            startup_data: startupData,
            ml_result: mlResult,
            conversation_history: AI._conversationHistory
          };
          
          const resp = await fetch('/api/ai-question', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          
          const data = await resp.json();
          
          if (data.answer) {
            const aiMsg = document.createElement('div');
            aiMsg.className = 'p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-slate-700';
            aiMsg.innerHTML = `<p><strong>CleverFund AI:</strong> ${AI._escapeHtml(data.answer)}</p>`;
            messagesDiv.appendChild(aiMsg);
            
            // Store in history
            AI._conversationHistory.push({role: 'user', content: question});
            AI._conversationHistory.push({role: 'assistant', content: data.answer});
          } else {
            const errorMsg = document.createElement('div');
            errorMsg.className = 'p-3 rounded-lg bg-rose-50 border border-rose-200 text-sm text-rose-700';
            errorMsg.innerHTML = '<p>Sorry, I could not generate a response. Please try again.</p>';
            messagesDiv.appendChild(errorMsg);
          }
        } catch (error) {
          console.error('Error:', error);
          const errorMsg = document.createElement('div');
          errorMsg.className = 'p-3 rounded-lg bg-rose-50 border border-rose-200 text-sm text-rose-700';
          errorMsg.innerHTML = '<p>Connection error. Please check your network.</p>';
          messagesDiv.appendChild(errorMsg);
        } finally {
          sendBtn.disabled = false;
          input.disabled = false;
          messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
      };
      
      sendBtn.addEventListener('click', handleSend);
      input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
      });
      
      clearBtn.addEventListener('click', async () => {
        if (!confirm('Clear this conversation?')) return;
        
        try {
          await fetch('/api/conversation/clear', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ startup_data: startupData })
          });
          
          AI._conversationHistory = [];
          messagesDiv.innerHTML = `
            <div class="p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-slate-700">
              <p><strong>CleverFund AI:</strong> Conversation cleared. What would you like to know?</p>
            </div>
          `;
        } catch (error) {
          console.error('Error clearing conversation:', error);
        }
      });
    },

    /**
     * Escape HTML for safe display
     */
    _escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  };

  // Export to global scope
  window.CleverFundAI = AI;
})(window);
