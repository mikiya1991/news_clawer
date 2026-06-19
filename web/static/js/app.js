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
            <div class="text-center py-12">
                <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <p class="mt-4 text-gray-500">没有找到匹配的推文</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = tweets.map(tweet => `
        <div class="tweet-card bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
            <div class="flex items-start space-x-3">
                <div class="flex-shrink-0">
                    <div class="h-10 w-10 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold text-lg">
                        ${tweet.username.charAt(0).toUpperCase()}
                    </div>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-2">
                            <span class="font-semibold text-gray-900">@${tweet.username}</span>
                            <span class="text-gray-500 text-sm">${formatRelativeTime(tweet.collected_at)}</span>
                        </div>
                        ${tweet.url ? `
                            <a href="${tweet.url}" target="_blank" class="text-blue-500 hover:text-blue-600 text-sm">
                                查看原文
                                <svg class="inline h-4 w-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                                </svg>
                            </a>
                        ` : ''}
                    </div>
                    <div class="mt-2 tweet-content text-gray-800 text-base leading-relaxed">
                        ${escapeHtml(tweet.text)}
                    </div>
                    <div class="mt-3 flex items-center space-x-6 text-sm text-gray-500">
                        <div class="flex items-center space-x-1">
                            <svg class="h-4 w-4 text-pink-500" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                            </svg>
                            <span>${formatNumber(tweet.like_count)}</span>
                        </div>
                        <div class="flex items-center space-x-1">
                            <svg class="h-4 w-4 text-green-500" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M23.77 15.67c-.07-.26-.27-.43-.53-.43h-3.13v-9.3c0-.35-.28-.63-.63-.63h-8.8V1.77c0-.26-.17-.46-.43-.53-.26-.07-.53.03-.69.23l-10 12.5c-.13.17-.15.39-.05.59.1.19.29.31.5.31h3.13v9.3c0 .35.28.63.63.63h8.8v3.57c0 .26.17.46.43.53.08.02.16.03.24.03.19 0 .37-.09.46-.26l10-12.5c.13-.17.15-.39.05-.59z"/>
                            </svg>
                            <span>${formatNumber(tweet.retweet_count)}</span>
                        </div>
                        <div class="flex items-center space-x-1">
                            <svg class="h-4 w-4 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
                            </svg>
                            <span>${formatNumber(tweet.view_count)}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Show loading state
function showLoading() {
    const container = document.getElementById('tweets-container');
    container.innerHTML = `
        <div class="text-center py-12">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
            <p class="mt-4 text-gray-500">加载中...</p>
        </div>
    `;
}

// Show error
function showError(message) {
    const container = document.getElementById('tweets-container');
    container.innerHTML = `
        <div class="text-center py-12">
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
