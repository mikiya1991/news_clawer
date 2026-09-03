/**
 * Tweet Dashboard - Frontend Application
 */

// State management
const state = {
    currentPage: 1,
    limit: 50,
    totalPages: 1,
    totalTweets: 0,
    sortBy: 'time',
    sortOrder: 'desc',
    searchQuery: '',
    usernameFilter: '',
    isLoading: false
};

// Format numbers with commas
function formatNumber(num) {
    if (!num || isNaN(num)) return '0';
    return parseInt(num).toLocaleString('en-US');
}

// Format relative time
function formatRelativeTime(dateString) {
    const date = new Date(dateString);
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

// Fetch tweets from API
async function fetchTweets() {
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
        
        if (state.searchQuery) {
            params.append('search', state.searchQuery);
        }
        
        if (state.usernameFilter) {
            params.append('username', state.usernameFilter);
        }
        
        const response = await fetch(`/api/tweets?${params}`);
        const data = await response.json();
        
        if (data.success) {
            renderTweets(data.tweets);
            updatePagination(data.pagination);
        } else {
            showError(data.error || '加载失败');
        }
    } catch (error) {
        console.error('Error fetching tweets:', error);
        showError('网络错误，请稍后重试');
    } finally {
        state.isLoading = false;
    }
}

// Fetch statistics
async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('stat-total').textContent = formatNumber(data.stats.total_tweets);
            document.getElementById('stat-users').textContent = formatNumber(data.stats.unique_users);
            document.getElementById('stat-likes').textContent = formatNumber(data.stats.total_likes);
        }
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
}

// Fetch users for filter dropdown
async function fetchUsers() {
    try {
        const response = await fetch('/api/users');
        const data = await response.json();
        
        if (data.success) {
            const select = document.getElementById('user-filter');
            const currentValue = select.value;
            
            // Keep the first option (All users)
            select.innerHTML = '<option value="">所有用户</option>';
            
            data.users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.username;
                option.textContent = `${user.username} (${user.tweet_count})`;
                select.appendChild(option);
            });
            
            select.value = currentValue;
        }
    } catch (error) {
        console.error('Error fetching users:', error);
    }
}

// Render tweets
function renderTweets(tweets) {
    const container = document.getElementById('tweets-container');
    
    if (tweets.length === 0) {
        container.innerHTML = `
            <div class="md:col-span-2 xl:col-span-3 text-center py-12">
                <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <p class="mt-4 text-gray-500">没有找到匹配的推文</p>
            </div>
        `;
        return;
    }

    container.innerHTML = tweets.map(tweet => {
        const band = scoreBand(tweet.ai_score || 0);
        return `
        <div class="tweet-card ${band.card} border border-gray-200 border-l-4 rounded-lg p-3 hover:shadow-md transition-shadow flex flex-col">
            <div class="flex items-center gap-2">
                <div class="h-7 w-7 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold text-xs flex-shrink-0">
                    ${tweet.username.charAt(0).toUpperCase()}
                </div>
                <span class="font-medium text-gray-900 text-sm truncate">@${tweet.username}</span>
                <div class="ml-auto flex items-center gap-1.5 flex-shrink-0">
                    ${tweet.ai_score > 0 ? `<span class="inline-flex items-center justify-center h-5 px-1.5 rounded font-bold text-[11px] ${band.badge}">${tweet.ai_score}</span>` : ''}
                    <span class="text-gray-400 text-xs whitespace-nowrap">${formatRelativeTime(tweet.collected_at)}</span>
                </div>
            </div>
            <div class="mt-2 tweet-content text-gray-800 text-sm leading-relaxed line-clamp-3">
                ${escapeHtml(tweet.text)}
            </div>
            ${tweet.ai_summary ? `
            <div class="mt-1.5 text-xs text-gray-600 bg-gray-50 border border-gray-100 rounded p-1.5 leading-relaxed line-clamp-2">
                <span title="AI 注释">🤖</span> ${escapeHtml(tweet.ai_summary)}
            </div>
            ` : ''}
            <div class="mt-2 pt-2 border-t border-gray-100 flex items-center gap-3 text-xs text-gray-500">
                <span class="flex items-center gap-0.5 text-pink-500">♥ <span class="text-gray-500">${formatNumber(tweet.like_count)}</span></span>
                <span class="flex items-center gap-0.5 text-green-600">↻ <span class="text-gray-500">${formatNumber(tweet.retweet_count)}</span></span>
                <span class="flex items-center gap-0.5 text-blue-500">👁 <span class="text-gray-500">${formatNumber(tweet.view_count)}</span></span>
                ${tweet.url ? `<a href="${tweet.url}" target="_blank" class="ml-auto text-blue-500 hover:text-blue-600 whitespace-nowrap">原文</a>` : ''}
            </div>
        </div>
    `;
    }).join('');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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

// Show loading state
function showLoading() {
    const container = document.getElementById('tweets-container');
    container.innerHTML = `
        <div class="md:col-span-2 xl:col-span-3 text-center py-12">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
            <p class="mt-4 text-gray-500">加载中...</p>
        </div>
    `;
}

// Show error
function showError(message) {
    const container = document.getElementById('tweets-container');
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
    state.totalTweets = pagination.total;
    
    const start = (pagination.page - 1) * pagination.limit + 1;
    const end = Math.min(pagination.page * pagination.limit, pagination.total);
    
    document.getElementById('page-start').textContent = start;
    document.getElementById('page-end').textContent = end;
    document.getElementById('page-total').textContent = formatNumber(pagination.total);
    document.getElementById('page-info').textContent = `第 ${pagination.page} 页 / 共 ${pagination.pages} 页`;
    
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    
    prevBtn.disabled = pagination.page <= 1;
    nextBtn.disabled = pagination.page >= pagination.pages;
    
    document.getElementById('pagination').classList.remove('hidden');
}

// Event Listeners
function setupEventListeners() {
    // Search input with debounce
    let searchTimeout;
    document.getElementById('search-input').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            state.searchQuery = e.target.value.trim();
            state.currentPage = 1;
            fetchTweets();
        }, 500);
    });
    
    // User filter
    document.getElementById('user-filter').addEventListener('change', (e) => {
        state.usernameFilter = e.target.value;
        state.currentPage = 1;
        fetchTweets();
    });
    
    // Sort by
    document.getElementById('sort-by').addEventListener('change', (e) => {
        state.sortBy = e.target.value;
        state.currentPage = 1;
        fetchTweets();
    });
    
    // Sort order toggle
    document.getElementById('sort-order').addEventListener('click', () => {
        state.sortOrder = state.sortOrder === 'desc' ? 'asc' : 'desc';
        updateSortIcon();
        fetchTweets();
    });
    
    // Pagination
    document.getElementById('prev-page').addEventListener('click', () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            fetchTweets();
        }
    });
    
    document.getElementById('next-page').addEventListener('click', () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            fetchTweets();
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
    fetchUsers();
    fetchTweets();
    
    // Refresh stats every 30 seconds
    setInterval(fetchStats, 30000);
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);
