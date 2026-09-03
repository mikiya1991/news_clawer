/**
 * News Radar Dashboard - Frontend Application
 */

// State management
const state = {
    currentPage: 1,
    limit: 50,
    totalPages: 1,
    totalItems: 0,
    sortBy: 'score',
    sortOrder: 'desc',
    sourceFilter: '',
    minScoreFilter: '',
    pushedFilter: false,
    isLoading: false
};

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format relative time
function formatRelativeTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString.replace(' ', 'T'));
    const now = new Date();
    const diff = now - date;

    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 30) {
        return date.toLocaleDateString('zh-CN');
    } else if (days > 0) {
        return `${days}天前`;
    } else if (hours > 0) {
        return `${hours}小时前`;
    } else if (minutes > 0) {
        return `${minutes}分钟前`;
    } else {
        return '刚刚';
    }
}

// Score badge color classes
function scoreBadgeClass(score) {
    if (score >= 80) return 'bg-green-100 text-green-800';
    if (score >= 60) return 'bg-amber-100 text-amber-800';
    return 'bg-red-100 text-red-800';
}

// Fetch news items from API
async function fetchNews() {
    if (state.isLoading) return;

    state.isLoading = true;
    showLoading();

    try {
        const params = new URLSearchParams({
            page: state.currentPage,
            limit: state.limit,
            sort: state.sortBy,
            order: state.sortOrder
        });

        if (state.sourceFilter) {
            params.append('source', state.sourceFilter);
        }

        if (state.minScoreFilter) {
            params.append('min_score', state.minScoreFilter);
        }

        if (state.pushedFilter) {
            params.append('pushed', '1');
        }

        const response = await fetch(`/api/news?${params}`);
        const data = await response.json();

        if (data.success) {
            renderNews(data.items);
            updatePagination(data.pagination);
        } else {
            showError(data.error || '加载失败');
        }
    } catch (error) {
        console.error('Error fetching news:', error);
        showError('网络错误，请稍后重试');
    } finally {
        state.isLoading = false;
    }
}

// Fetch statistics
async function fetchStats() {
    try {
        const response = await fetch('/api/news/stats');
        const data = await response.json();

        if (data.success) {
            document.getElementById('stat-total').textContent = data.stats.total;
            document.getElementById('stat-avg').textContent = data.stats.avg_score;
            document.getElementById('stat-pushed').textContent = data.stats.pushed_count;
        }
    } catch (error) {
        console.error('Error fetching news stats:', error);
    }
}

// Render news items
function renderNews(items) {
    const container = document.getElementById('news-container');

    if (items.length === 0) {
        container.innerHTML = `
            <div class="md:col-span-2 xl:col-span-3 text-center py-12">
                <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <p class="mt-4 text-gray-500">暂无新闻记录，等待首次采集评分...</p>
            </div>
        `;
        return;
    }

    container.innerHTML = items.map(item => {
        const sourceBadge = item.source === 'x'
            ? '<span class="text-sky-600">X</span>'
            : '<span class="text-purple-600">RSS</span>';
        const reasonsText = Array.isArray(item.reasons) && item.reasons.length
            ? item.reasons.join('；')
            : '';

        return `
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 hover:shadow-md transition-shadow flex flex-col">
            <div class="flex items-start gap-2">
                <span class="flex-shrink-0 inline-flex items-center justify-center h-8 w-8 rounded-md font-bold text-sm ${scoreBadgeClass(item.score)}">
                    ${item.score}
                </span>
                <h2 class="flex-1 text-sm font-medium text-gray-900 leading-snug line-clamp-2">
                    ${item.url && item.url.startsWith('http')
                        ? `<a href="${escapeHtml(item.url)}" target="_blank" class="hover:text-blue-600">${escapeHtml(item.title)}</a>`
                        : escapeHtml(item.title)}
                </h2>
            </div>
            ${item.summary ? `
                <p class="mt-1.5 text-xs text-gray-500 leading-relaxed line-clamp-2">${escapeHtml(item.summary)}</p>
            ` : ''}
            ${reasonsText ? `
                <p class="mt-1 text-[11px] text-gray-400 truncate" title="${escapeHtml(reasonsText)}">${escapeHtml(reasonsText)}</p>
            ` : ''}
            <div class="mt-2 pt-2 border-t border-gray-100 flex items-center flex-wrap gap-x-1.5 text-[11px] text-gray-400">
                ${sourceBadge}
                <span class="truncate">${escapeHtml(item.source_name || '')}</span>
                ${item.pushed ? '<span class="text-pink-500">已推送</span>' : ''}
                <span class="ml-auto whitespace-nowrap">${formatRelativeTime(item.created_at)}</span>
            </div>
        </div>
        `;
    }).join('');
}

// Show loading state
function showLoading() {
    const container = document.getElementById('news-container');
    container.innerHTML = `
        <div class="md:col-span-2 xl:col-span-3 text-center py-12">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
            <p class="mt-4 text-gray-500">加载中...</p>
        </div>
    `;
}

// Show error
function showError(message) {
    const container = document.getElementById('news-container');
    container.innerHTML = `
        <div class="md:col-span-2 xl:col-span-3 text-center py-12">
            <svg class="mx-auto h-12 w-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <p class="mt-4 text-gray-500">${message}</p>
        </div>
    `;
}

// Update pagination UI
function updatePagination(pagination) {
    state.totalPages = pagination.pages;
    state.totalItems = pagination.total;

    const start = (pagination.page - 1) * pagination.limit + 1;
    const end = Math.min(pagination.page * pagination.limit, pagination.total);

    document.getElementById('page-start').textContent = start;
    document.getElementById('page-end').textContent = end;
    document.getElementById('page-total').textContent = pagination.total;
    document.getElementById('page-info').textContent = `第 ${pagination.page} 页 / 共 ${pagination.pages} 页`;

    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');

    prevBtn.disabled = pagination.page <= 1;
    nextBtn.disabled = pagination.page >= pagination.pages;

    document.getElementById('pagination').classList.remove('hidden');
}

// Event Listeners
function setupEventListeners() {
    // Source filter
    document.getElementById('source-filter').addEventListener('change', (e) => {
        state.sourceFilter = e.target.value;
        state.currentPage = 1;
        fetchNews();
    });

    // Min score filter
    document.getElementById('min-score-filter').addEventListener('change', (e) => {
        state.minScoreFilter = e.target.value;
        state.currentPage = 1;
        fetchNews();
    });

    // Pushed filter
    document.getElementById('pushed-filter').addEventListener('change', (e) => {
        state.pushedFilter = e.target.checked;
        state.currentPage = 1;
        fetchNews();
    });

    // Sort by
    document.getElementById('sort-by').addEventListener('change', (e) => {
        state.sortBy = e.target.value;
        state.currentPage = 1;
        fetchNews();
    });

    // Sort order toggle
    document.getElementById('sort-order').addEventListener('click', () => {
        state.sortOrder = state.sortOrder === 'desc' ? 'asc' : 'desc';
        updateSortIcon();
        fetchNews();
    });

    // Pagination
    document.getElementById('prev-page').addEventListener('click', () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            fetchNews();
        }
    });

    document.getElementById('next-page').addEventListener('click', () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            fetchNews();
        }
    });
}

// Update sort icon based on direction
function updateSortIcon() {
    const icon = document.getElementById('sort-icon');
    if (state.sortOrder === 'asc') {
        icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4"></path>';
    } else {
        icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12"></path>';
    }
}

// Initialize
function init() {
    setupEventListeners();
    fetchStats();
    fetchNews();

    // Refresh stats every 30 seconds
    setInterval(fetchStats, 30000);
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);
