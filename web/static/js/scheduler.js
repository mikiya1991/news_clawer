/**
 * Scheduler Control Panel - Frontend Application
 */

// State management
const state = {
    running: false,
    interval: 1,
    unit: 'hours',
    nextRun: null,
    busy: false,
    ready: false,   // true once the first status fetch has synced the form
    busyJob: null,  // manual/scheduled job currently running (collection|news|login)
    refreshInterval: null
};

// DOM Elements
const elements = {
    statusIndicator: document.getElementById('status-indicator'),
    statusText: document.getElementById('status-text'),
    nextRunText: document.getElementById('next-run-text'),
    intervalInput: document.getElementById('interval-input'),
    unitSelect: document.getElementById('unit-select'),
    toggleBtn: document.getElementById('toggle-btn'),
    loginBtn: document.getElementById('login-btn'),
    collectNowBtn: document.getElementById('collect-now-btn'),
    newsNowBtn: document.getElementById('news-now-btn'),
    scoreTweetsBtn: document.getElementById('score-tweets-btn'),
    scoreNewsBtn: document.getElementById('score-news-btn'),
    collectionsContainer: document.getElementById('collections-container'),
    unscoredContainer: document.getElementById('unscored-container'),
    unscoredCount: document.getElementById('unscored-count'),
    newsRunsContainer: document.getElementById('news-runs-container'),
    newsItemsContainer: document.getElementById('news-items-container'),
    envFilePath: document.getElementById('env-file-path'),
    apiKeyInput: document.getElementById('api-key-input'),
    apiKeyToggle: document.getElementById('api-key-toggle'),
    baseUrlInput: document.getElementById('base-url-input'),
    modelInput: document.getElementById('model-input'),
    pushProviderSelect: document.getElementById('push-provider-select'),
    pushTokenInput: document.getElementById('push-token-input'),
    rssFeedsInput: document.getElementById('rss-feeds-input'),
    aiFilterToggle: document.getElementById('ai-filter-toggle'),
    aiSummaryToggle: document.getElementById('ai-summary-toggle'),
    saveConfigBtn: document.getElementById('save-config-btn'),
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toast-message')
};

// Fetch scheduler status
async function fetchStatus() {
    try {
        const response = await fetch('/api/scheduler/status');
        const data = await response.json();

        state.running = data.running;
        state.interval = data.config?.interval || 1;
        state.unit = data.config?.unit || 'hours';
        state.nextRun = data.next_run;
        state.busyJob = data.busy_job || null;
        state.ready = true;

        updateUI(data);
    } catch (error) {
        console.error('Error fetching status:', error);
        showToast('获取状态失败', 'error');
    }
}

// Update UI based on status
function updateUI(data) {
    const running = data.running;
    const config = data.config || {};
    
    // Status indicator
    const statusColor = running ? 'bg-green-500' : 'bg-gray-400';
    const statusText = running ? '运行中' : '已停止';
    elements.statusIndicator.innerHTML = `
        <span class="w-3 h-3 rounded-full ${statusColor}"></span>
        <span class="text-sm ${running ? 'text-green-600' : 'text-gray-600'}">${statusText}</span>
    `;
    
    // Status text
    elements.statusText.textContent = running 
        ? `每 ${config.interval} ${translateUnit(config.unit)}采集一次`
        : '定时任务未运行';
    
    // Next run
    elements.nextRunText.textContent = data.next_run 
        ? `下次执行: ${data.next_run}`
        : '';
    
    // Single toggle button reflects running state (unless a request is in flight)
    if (!state.busy) {
        renderToggleButton(running ? 'stop' : 'start');
    }
    elements.intervalInput.disabled = running;
    elements.unitSelect.disabled = running;

    // Manual action buttons: disabled while any job is running
    renderManualButtons(data.busy_job || null);
    
    // Always reflect saved config in the form (inputs are disabled while
    // running, but should still display the actual configured values)
    elements.intervalInput.value = config.interval || 1;
    elements.unitSelect.value = config.unit || 'hours';
}

// Translate unit to Chinese
function translateUnit(unit) {
    const translations = {
        'minutes': '分钟',
        'hours': '小时',
        'days': '天'
    };
    return translations[unit] || unit;
}

// Toggle button appearance (single button: start when stopped, stop when running)
const TOGGLE_BUTTON_STYLES = {
    base: 'w-full text-white py-2 px-4 rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 flex items-center justify-center space-x-2',
    start: 'bg-green-600 hover:bg-green-700 focus:ring-green-500',
    stop: 'bg-red-600 hover:bg-red-700 focus:ring-red-500'
};

const TOGGLE_BUTTON_ICONS = {
    start: '<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
    stop: '<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path></svg>',
    spinner: '<svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">' +
        '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>' +
        '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>'
};

// Render the toggle button: 'start' | 'stop' | 'start-loading' | 'stop-loading'
function renderToggleButton(kind) {
    const btn = elements.toggleBtn;
    state.busy = kind === 'start-loading' || kind === 'stop-loading';

    if (state.busy) {
        btn.disabled = true;
        btn.innerHTML = TOGGLE_BUTTON_ICONS.spinner +
            `<span>${kind === 'start-loading' ? '启动中...' : '停止中...'}</span>`;
        return;
    }

    btn.disabled = false;
    btn.className = `${TOGGLE_BUTTON_STYLES.base} ${TOGGLE_BUTTON_STYLES[kind]}`;
    btn.innerHTML = TOGGLE_BUTTON_ICONS[kind] +
        `<span>${kind === 'start' ? '启动' : '停止'}</span>`;
}

// Manual action buttons: show spinner on the running job, disable all while busy
function renderManualButtons(busyJob) {
    const defs = [
        ['loginBtn', 'login', '🔑 登录 X'],
        ['collectNowBtn', 'collection', '📥 手动抓取Tweet'],
        ['scoreTweetsBtn', 'tweet-scoring', '🤖 AI评分Tweet'],
        ['newsNowBtn', 'news', '📡 手动抓取新闻'],
        ['scoreNewsBtn', 'news-scoring', '🤖 AI评分新闻']
    ];

    defs.forEach(([key, job, label]) => {
        const btn = elements[key];
        if (!btn) return;
        const isThis = busyJob === job;
        btn.disabled = !!busyJob;
        btn.classList.toggle('opacity-50', !!busyJob);
        btn.classList.toggle('cursor-not-allowed', !!busyJob);
        btn.innerHTML = isThis
            ? TOGGLE_BUTTON_ICONS.spinner + '<span>执行中...</span>'
            : label;
    });
}

// Fetch and render the .env configuration form
async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        if (!data.success) throw new Error(data.error || '加载失败');

        const v = data.values || {};
        elements.envFilePath.textContent = data.env_file || '.env';
        elements.apiKeyInput.value = v.DEEPSEEK_API_KEY || '';
        elements.baseUrlInput.value = v.DEEPSEEK_BASE_URL || 'https://api.deepseek.com';
        elements.modelInput.value = v.DEEPSEEK_MODEL || 'deepseek-v4-flash';
        elements.pushProviderSelect.value = v.PUSH_PROVIDER || '';
        elements.pushTokenInput.value = v.PUSH_TOKEN || '';
        elements.rssFeedsInput.value = v.RSS_FEEDS || '';
        elements.aiFilterToggle.checked = !!v.AI_FILTER_ENABLED;
        elements.aiSummaryToggle.checked = !!v.AI_SUMMARY_ENABLED;
    } catch (error) {
        console.error('Error fetching config:', error);
    }
}

// Save the configuration form
async function saveConfig() {
    elements.saveConfigBtn.disabled = true;
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                DEEPSEEK_API_KEY: elements.apiKeyInput.value,
                DEEPSEEK_BASE_URL: elements.baseUrlInput.value,
                DEEPSEEK_MODEL: elements.modelInput.value,
                PUSH_PROVIDER: elements.pushProviderSelect.value,
                PUSH_TOKEN: elements.pushTokenInput.value,
                RSS_FEEDS: elements.rssFeedsInput.value,
                AI_FILTER_ENABLED: elements.aiFilterToggle.checked,
                AI_SUMMARY_ENABLED: elements.aiSummaryToggle.checked,
            })
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message || '配置已保存');
            await fetchConfig();
        } else {
            showToast(data.message || '保存失败', 'error');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showToast('保存失败: 网络错误', 'error');
    } finally {
        elements.saveConfigBtn.disabled = false;
    }
}

// Fetch overview data: collection results, unscored tweets, news cycle
async function fetchOverview() {
    try {
        const response = await fetch('/api/scheduler/overview');
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || '加载失败');
        }

        renderCollections(data.collections || []);
        renderUnscored(data.unscored_tweets || [], data.unscored_total || 0);
        renderNewsRuns(data.news_runs || []);
        renderNewsItems(data.news_items || []);
    } catch (error) {
        console.error('Error fetching overview:', error);
    }
}

// Format timestamp to "MM-DD HH:MM"
function formatTime(ts) {
    if (!ts) return '';
    const s = String(ts);
    return s.length >= 16 ? s.slice(5, 16) : s;
}

const COLLECTION_STATUS = {
    success: { label: '成功', badge: 'bg-green-100 text-green-700' },
    partial: { label: '部分', badge: 'bg-amber-100 text-amber-700' },
    error: { label: '失败', badge: 'bg-red-100 text-red-700' }
};

// Render recent tweet collection runs (time + count + status)
function renderCollections(collections) {
    if (!collections.length) {
        elements.collectionsContainer.innerHTML =
            '<div class="text-center py-4 text-gray-400">暂无采集记录</div>';
        return;
    }

    const rows = collections.map(c => {
        const st = COLLECTION_STATUS[c.status] || { label: c.status, badge: 'bg-gray-100 text-gray-600' };
        const note = c.error_message
            ? `<div class="text-xs text-red-500 truncate" title="${escapeHtml(c.error_message)}">${escapeHtml(String(c.error_message).slice(0, 40))}</div>`
            : '';
        return `
            <tr class="border-b border-gray-100 last:border-0">
                <td class="py-1.5 pr-2 whitespace-nowrap text-gray-600">${escapeHtml(formatTime(c.created_at || c.last_collection_time))}</td>
                <td class="py-1.5 pr-2"><span class="px-2 py-0.5 text-xs rounded-full ${st.badge}">${st.label}</span>${note}</td>
                <td class="py-1.5 text-right font-medium">${c.tweet_count_collected || 0} 条</td>
            </tr>`;
    }).join('');

    elements.collectionsContainer.innerHTML = `
        <table class="w-full text-sm">
            <thead>
                <tr class="text-left text-xs text-gray-400 border-b border-gray-200">
                    <th class="pb-1 pr-2 font-medium">时间</th>
                    <th class="pb-1 pr-2 font-medium">状态</th>
                    <th class="pb-1 text-right font-medium">条数</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;
}

// Render tweets that have not been AI-scored yet
function renderUnscored(tweets, total) {
    elements.unscoredCount.textContent = total;

    if (!tweets.length) {
        elements.unscoredContainer.innerHTML =
            '<div class="text-center py-3 text-gray-400">所有推文均已打分 ✓</div>';
        return;
    }

    const rows = tweets.map(t => `
        <div class="flex items-start py-1.5 border-b border-gray-100 last:border-0">
            <span class="text-xs text-gray-400 whitespace-nowrap pt-0.5 mr-2">${escapeHtml(formatTime(t.collected_at))}</span>
            <div class="min-w-0 flex-1">
                <span class="font-medium text-gray-700">@${escapeHtml(t.username)}</span>
                <span class="text-gray-600 break-words">: ${escapeHtml(String(t.text).slice(0, 60))}${String(t.text).length > 60 ? '…' : ''}</span>
            </div>
            <span class="text-xs text-gray-400 whitespace-nowrap ml-2 pt-0.5">♥ ${t.like_count || 0}</span>
        </div>`).join('');

    elements.unscoredContainer.innerHTML = rows;
}

// Render news cycle history (time + result summary)
function renderNewsRuns(runs) {
    if (!runs.length) {
        elements.newsRunsContainer.innerHTML =
            '<div class="text-center py-4 text-gray-400">暂无新闻采集记录</div>';
        return;
    }

    const rows = runs.map(r => {
        const color = r.status === 'error' ? 'bg-red-500' : 'bg-green-500';
        return `
            <div class="flex items-start py-1.5 border-b border-gray-100 last:border-0">
                <span class="w-2 h-2 rounded-full mt-1.5 mr-2 ${color}"></span>
                <span class="text-xs text-gray-400 whitespace-nowrap pt-0.5 mr-2">${escapeHtml(formatTime(r.timestamp))}</span>
                <span class="text-gray-600 break-words">${escapeHtml(r.message)}</span>
            </div>`;
    }).join('');

    elements.newsRunsContainer.innerHTML = rows;
}

// Render recent scored news items (time + score + title)
function renderNewsItems(items) {
    if (!items.length) {
        elements.newsItemsContainer.innerHTML =
            '<div class="text-center py-3 text-gray-400">暂无新闻条目</div>';
        return;
    }

    const rows = items.map(item => {
        const score = item.score || 0;
        const scoreBadge = score >= 80
            ? 'bg-red-100 text-red-700'
            : (score >= 70 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600');
        const sourceBadge = item.source === 'x'
            ? 'bg-sky-100 text-sky-700'
            : 'bg-purple-100 text-purple-700';
        const title = String(item.title || '').slice(0, 50);
        const url = item.url ? `href="${escapeHtml(item.url)}" target="_blank" rel="noopener"` : '';
        return `
            <div class="flex items-start py-1.5 border-b border-gray-100 last:border-0">
                <span class="text-xs text-gray-400 whitespace-nowrap pt-0.5 mr-2">${escapeHtml(formatTime(item.created_at || item.scored_at))}</span>
                <span class="px-1.5 py-0.5 text-xs rounded-full mr-2 ${scoreBadge}">${score}</span>
                <span class="px-1.5 py-0.5 text-xs rounded-full mr-2 ${sourceBadge}">${item.source === 'x' ? 'X' : 'RSS'}</span>
                <span class="text-gray-700 break-words min-w-0">
                    <a ${url} class="hover:text-blue-600">${escapeHtml(title)}${String(item.title || '').length > 50 ? '…' : ''}</a>
                </span>
            </div>`;
    }).join('');

    elements.newsItemsContainer.innerHTML = rows;
}

// Start scheduler
async function startScheduler() {
    const interval = parseInt(elements.intervalInput.value) || 1;
    const unit = elements.unitSelect.value;

    try {
        renderToggleButton('start-loading');

        const response = await fetch('/api/scheduler/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interval, unit })
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message);
            await fetchStatus();
        } else {
            showToast(data.message || '启动失败', 'error');
        }
    } catch (error) {
        console.error('Error starting scheduler:', error);
        showToast('启动失败: 网络错误', 'error');
    }

    // Re-render based on the latest known state
    renderToggleButton(state.running ? 'stop' : 'start');
}

// Trigger a manual job via the backend, then refresh status
async function manualAction(endpoint, successMsg) {
    try {
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showToast(successMsg);
        } else {
            showToast(data.message || '操作失败', 'error');
        }
    } catch (error) {
        console.error('Error triggering manual action:', error);
        showToast('操作失败: 网络错误', 'error');
    }
    await fetchStatus();
}

// Stop scheduler
async function stopScheduler() {
    try {
        renderToggleButton('stop-loading');

        const response = await fetch('/api/scheduler/stop', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message);
            await fetchStatus();
        } else {
            showToast(data.message || '停止失败', 'error');
        }
    } catch (error) {
        console.error('Error stopping scheduler:', error);
        showToast('停止失败: 网络错误', 'error');
    }

    // Re-render based on the latest known state
    renderToggleButton(state.running ? 'stop' : 'start');
}

// Show toast notification
function showToast(message, type = 'success') {
    elements.toastMessage.textContent = message;
    elements.toast.classList.remove('translate-y-20', 'opacity-0');
    
    setTimeout(() => {
        elements.toast.classList.add('translate-y-20', 'opacity-0');
    }, 3000);
}

// Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Setup event listeners
function setupEventListeners() {
    // Single toggle button: start when stopped, stop when running.
    // Ignore clicks until the first status fetch has synced the form,
    // otherwise the HTML default values (1 hour) could be submitted.
    elements.toggleBtn.addEventListener('click', () => {
        if (!state.ready) return;
        if (state.running) {
            stopScheduler();
        } else {
            startScheduler();
        }
    });

    // Sidebar tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Config form
    elements.saveConfigBtn.addEventListener('click', saveConfig);
    elements.apiKeyToggle.addEventListener('click', () => {
        const isPassword = elements.apiKeyInput.type === 'password';
        elements.apiKeyInput.type = isPassword ? 'text' : 'password';
        elements.apiKeyToggle.textContent = isPassword ? '隐藏' : '显示';
    });

    // Manual actions
    elements.loginBtn.addEventListener('click', () => {
        if (!confirm('将打开一个可见的浏览器窗口，请在窗口中完成 X 登录（自动检测，最长等待 5 分钟）。继续？')) return;
        manualAction('/api/scheduler/login', '已打开浏览器，请在窗口中登录 X');
    });
    elements.collectNowBtn.addEventListener('click', () => {
        manualAction('/api/scheduler/collect-now', '已开始手动抓取Tweet（可见浏览器）');
    });
    elements.scoreTweetsBtn.addEventListener('click', () => {
        manualAction('/api/scheduler/score-tweets', '已开始AI评分Tweet（未打分的推文）');
    });
    elements.newsNowBtn.addEventListener('click', () => {
        manualAction('/api/scheduler/news-now', '已开始新闻采集（抓取+评分+推送）');
    });
    elements.scoreNewsBtn.addEventListener('click', () => {
        manualAction('/api/scheduler/score-news', '已开始AI评分新闻（重新评分最近50条）');
    });
    
    // Preset buttons
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (state.running) return;
            elements.intervalInput.value = btn.dataset.interval;
            elements.unitSelect.value = btn.dataset.unit;
        });
    });
}

// Switch between sidebar tabs
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const isActive = btn.dataset.tab === tab;
        btn.classList.toggle('bg-blue-50', isActive);
        btn.classList.toggle('text-blue-700', isActive);
        btn.classList.toggle('text-gray-600', !isActive);
        btn.classList.toggle('hover:bg-gray-50', !isActive);
    });
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('hidden', panel.id !== 'tab-' + tab);
    });
}

// Initialize
function init() {
    setupEventListeners();
    fetchStatus();
    fetchOverview();
    fetchConfig();

    // Refresh status every 10 seconds
    state.refreshInterval = setInterval(fetchStatus, 10000);
    // Refresh overview (collection/news results) every 15 seconds
    state.overviewInterval = setInterval(fetchOverview, 15000);
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (state.refreshInterval) {
        clearInterval(state.refreshInterval);
    }
    if (state.overviewInterval) {
        clearInterval(state.overviewInterval);
    }
});

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);
