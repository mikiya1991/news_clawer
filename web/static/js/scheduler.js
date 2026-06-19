/**
 * Scheduler Control Panel - Frontend Application
 */

// State management
const state = {
    running: false,
    interval: 1,
    unit: 'hours',
    nextRun: null,
    refreshInterval: null
};

// DOM Elements
const elements = {
    statusIndicator: document.getElementById('status-indicator'),
    statusText: document.getElementById('status-text'),
    nextRunText: document.getElementById('next-run-text'),
    intervalInput: document.getElementById('interval-input'),
    unitSelect: document.getElementById('unit-select'),
    startBtn: document.getElementById('start-btn'),
    stopBtn: document.getElementById('stop-btn'),
    logContainer: document.getElementById('log-container'),
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
    
    // Button states
    elements.startBtn.disabled = running;
    elements.stopBtn.disabled = !running;
    elements.intervalInput.disabled = running;
    elements.unitSelect.disabled = running;
    
    // Update input values if not running
    if (!running) {
        elements.intervalInput.value = config.interval || 1;
        elements.unitSelect.value = config.unit || 'hours';
    }
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

// Fetch detailed logs from scraper.log
async function fetchLogs() {
    try {
        const response = await fetch('/api/scheduler/logs?lines=100');
        const data = await response.json();
        if (data.success) {
            renderLogs(data.logs);
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}

// Render log lines (raw strings from scraper.log)
function renderLogs(logLines) {
    if (!logLines || logLines.length === 0) {
        elements.logContainer.innerHTML = '<div class="text-center py-8 text-gray-500">暂无日志记录</div>';
        return;
    }

    const html = logLines.map(line => {
        let colorClass = 'text-gray-700';
        if (line.includes(' - ERROR - ')) colorClass = 'text-red-600';
        else if (line.includes(' - WARNING - ')) colorClass = 'text-amber-600';
        else if (line.includes(' - INFO - ')) colorClass = 'text-gray-700';
        else if (line.includes(' - DEBUG - ')) colorClass = 'text-gray-400';
        return `<div class="font-mono text-xs whitespace-pre-wrap break-all ${colorClass} py-0.5">${escapeHtml(line)}</div>`;
    }).join('');

    elements.logContainer.innerHTML = html;
    // Auto-scroll to bottom
    elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
}

// Start scheduler
async function startScheduler() {
    const interval = parseInt(elements.intervalInput.value) || 1;
    const unit = elements.unitSelect.value;
    
    try {
        elements.startBtn.disabled = true;
        elements.startBtn.innerHTML = `
            <svg class="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>启动中...</span>
        `;
        
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
    } finally {
        resetStartButton();
    }
}

// Stop scheduler
async function stopScheduler() {
    try {
        elements.stopBtn.disabled = true;
        elements.stopBtn.innerHTML = `
            <svg class="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>停止中...</span>
        `;
        
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
    } finally {
        resetStopButton();
    }
}

// Reset button states
function resetStartButton() {
    elements.startBtn.innerHTML = `
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <span>启动</span>
    `;
    elements.startBtn.disabled = state.running;
}

function resetStopButton() {
    elements.stopBtn.innerHTML = `
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path>
        </svg>
        <span>停止</span>
    `;
    elements.stopBtn.disabled = !state.running;
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
    // Start button
    elements.startBtn.addEventListener('click', startScheduler);
    
    // Stop button
    elements.stopBtn.addEventListener('click', stopScheduler);
    
    // Preset buttons
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (state.running) return;
            elements.intervalInput.value = btn.dataset.interval;
            elements.unitSelect.value = btn.dataset.unit;
        });
    });
}

// Initialize
function init() {
    setupEventListeners();
    fetchStatus();
    fetchLogs();

    // Refresh status every 10 seconds
    state.refreshInterval = setInterval(fetchStatus, 10000);
    // Refresh logs every 5 seconds
    state.logRefreshInterval = setInterval(fetchLogs, 5000);
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (state.refreshInterval) {
        clearInterval(state.refreshInterval);
    }
    if (state.logRefreshInterval) {
        clearInterval(state.logRefreshInterval);
    }
});

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);
