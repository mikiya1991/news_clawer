/**
 * News Timeline - Frontend Application
 * Center vertical line with two cards per row (left + right), grouped by date
 */

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format time HH:MM from a timestamp string
function formatTime(dateString) {
    if (!dateString) return '';
    const parts = String(dateString).replace('T', ' ').split(/[- :]/);
    if (parts.length < 5) return '';
    return `${parts[3]}:${parts[4]}`;
}

// Format date label with weekday
function formatDateLabel(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
    return `${dateStr} ${weekdays[d.getDay()]}`;
}

// Score-based card color scheme (green = high priority, red = low)
function scoreBand(score) {
    if (score >= 90) return { card: 'bg-emerald-50 border-l-emerald-500', badge: 'bg-emerald-600 text-white' };
    if (score >= 85) return { card: 'bg-green-50 border-l-green-500', badge: 'bg-green-600 text-white' };
    if (score >= 80) return { card: 'bg-teal-50 border-l-teal-400', badge: 'bg-teal-500 text-white' };
    if (score >= 75) return { card: 'bg-cyan-50 border-l-cyan-400', badge: 'bg-cyan-500 text-white' };
    if (score >= 70) return { card: 'bg-blue-50 border-l-blue-400', badge: 'bg-blue-500 text-white' };
    if (score >= 60) return { card: 'bg-amber-50 border-l-amber-400', badge: 'bg-amber-500 text-white' };
    return { card: 'bg-rose-50 border-l-rose-400', badge: 'bg-rose-500 text-white' };
}

// Render one item card
function itemCard(item) {
    const band = scoreBand(item.score);
    const sourceBadge = item.kind === 'tweet'
        ? '<span class="text-sky-600">推文</span>'
        : (item.source === 'x'
            ? '<span class="text-sky-600">X</span>'
            : '<span class="text-purple-600">RSS</span>');
    return `
    <div class="${band.card} border border-gray-200 border-l-4 rounded-lg p-3 hover:shadow-md transition-shadow">
        <div class="flex items-start gap-2">
            <span class="flex-shrink-0 inline-flex items-center justify-center h-7 w-7 rounded-md font-bold text-xs ${band.badge}">
                ${item.score}
            </span>
            <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between gap-2">
                    <h3 class="text-sm font-medium text-gray-900 leading-snug">
                        ${item.url && item.url.startsWith('http')
                            ? `<a href="${escapeHtml(item.url)}" target="_blank" class="hover:text-blue-600">${escapeHtml(item.title)}</a>`
                            : escapeHtml(item.title)}
                    </h3>
                    <span class="text-xs text-gray-400 whitespace-nowrap">${formatTime(item.published_at || item.created_at)}</span>
                </div>
                ${item.summary ? `
                    <p class="mt-1 text-xs text-gray-500 leading-relaxed">${escapeHtml(item.summary)}</p>
                ` : ''}
                <div class="mt-1.5 flex items-center gap-1.5 text-[11px] text-gray-400">
                    ${sourceBadge}
                    <span class="truncate">${escapeHtml(item.source_name || '')}</span>
                </div>
            </div>
        </div>
    </div>
    `;
}

// Fetch timeline data
async function fetchTimeline() {
    const container = document.getElementById('timeline-container');
    const minScore = document.getElementById('min-score-filter').value;
    const hint = document.getElementById('count-hint');

    container.innerHTML = `
        <div class="absolute left-1/2 top-0 bottom-0 w-0.5 bg-blue-200 -translate-x-1/2"></div>
        <div class="relative text-center py-12">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
            <p class="mt-4 text-gray-500">加载中...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/timeline?min_score=${minScore}`);
        const data = await response.json();

        if (!data.success) {
            showError(data.error || '加载失败');
            return;
        }

        if (data.groups.length === 0) {
            container.innerHTML = `
                <div class="absolute left-1/2 top-0 bottom-0 w-0.5 bg-blue-200 -translate-x-1/2"></div>
                <div class="relative text-center py-12">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <p class="mt-4 text-gray-500">暂无达到该重要度的新闻</p>
                </div>
            `;
            hint.textContent = '';
            return;
        }

        renderHint(data.groups);

        const sectionsHtml = data.groups.map(group => {
            // Pair items: [0,1] -> row 1 (left, right), [2,3] -> row 2, ...
            const rowsHtml = [];
            for (let i = 0; i < group.items.length; i += 2) {
                const left = group.items[i];
                const right = group.items[i + 1];
                rowsHtml.push(`
                <div class="relative grid grid-cols-2 gap-6 md:gap-10 items-center">
                    <span class="absolute left-1/2 -translate-x-1/2 h-2.5 w-2.5 rounded-full bg-blue-400 ring-4 ring-blue-100 z-10"></span>
                    <div class="min-w-0">${left ? itemCard(left) : ''}</div>
                    <div class="min-w-0">${right ? itemCard(right) : ''}</div>
                </div>
                `);
            }

            return `
            <section id="day-${group.date}" class="relative scroll-mt-24">
                <div class="relative flex justify-center mb-4">
                    <span class="relative z-10 bg-white border border-blue-200 rounded-full px-3 py-1 text-xs font-semibold text-gray-700 shadow-sm">
                        ${formatDateLabel(group.date)}
                        <span class="text-gray-400 font-normal">· ${group.items.length} 条</span>
                    </span>
                </div>
                <div class="space-y-5">
                    ${rowsHtml.join('')}
                </div>
            </section>
            `;
        }).join('');

        container.innerHTML = `
            <div class="absolute left-1/2 top-0 bottom-0 w-0.5 bg-blue-200 -translate-x-1/2"></div>
            <div class="relative space-y-10">
                ${sectionsHtml}
            </div>
        `;
    } catch (error) {
        console.error('Error fetching timeline:', error);
        showError('网络错误，请稍后重试');
    }
}

// Populate the hint line in the control bar
function renderHint(groups) {
    let total = 0, news = 0, tweets = 0, scoreSum = 0;
    groups.forEach(g => {
        g.items.forEach(i => {
            total++;
            if (i.kind === 'tweet') tweets++; else news++;
            if (i.score) scoreSum += i.score;
        });
    });
    const hint = document.getElementById('count-hint');
    hint.textContent = `共 ${groups.length} 天 · ${total} 条（新闻 ${news} / 推文 ${tweets}）· 平均 ${total ? (scoreSum / total).toFixed(1) : '-'} 分`;
}

// Show error
function showError(message) {
    const container = document.getElementById('timeline-container');
    container.innerHTML = `
        <div class="absolute left-1/2 top-0 bottom-0 w-0.5 bg-blue-200 -translate-x-1/2"></div>
        <div class="relative text-center py-12">
            <svg class="mx-auto h-12 w-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <p class="mt-4 text-gray-500">${message}</p>
        </div>
    `;
}

// Initialize
function init() {
    document.getElementById('min-score-filter').addEventListener('change', fetchTimeline);
    fetchTimeline();
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);
