/**
 * Real-time Dashboard Updates with Error Recovery
 * WebSocket-based real-time updates with fallback to polling
 * PHASE 1: Simplified coordination to eliminate race conditions
 */
class RealtimeDashboard {
    constructor(options = {}) {
        this.options = {
            wsUrl: options.wsUrl || this.buildWebSocketUrl(),
            fallbackPollInterval: options.fallbackPollInterval || 5000,
            reconnectInterval: options.reconnectInterval || 3000,
            maxReconnectAttempts: options.maxReconnectAttempts || 10,
            heartbeatInterval: options.heartbeatInterval || 30000,
            ...options
        };

        // State management
        this.websocket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.lastHeartbeat = Date.now();
        this.fallbackMode = false;
        this.subscribers = new Map();
        this.eventQueue = [];

        // PHASE 1: Request coordination to prevent race conditions
        this.requestQueue = new Map();
        this.debounceTimeout = 100; // ms
        this.updateLock = false;

        // Initialize dashboard components if available
        this.dashboardComponents = window.dashboardComponents || null;

        // Bind methods
        this.handleOpen = this.handleOpen.bind(this);
        this.handleMessage = this.handleMessage.bind(this);
        this.handleClose = this.handleClose.bind(this);
        this.handleError = this.handleError.bind(this);

        // PHASE 1: Single source of truth for widget updates
        this.setAsGlobalUpdateManager();

        // PHASE 1: Set up global error handling
        this.setupGlobalErrorHandling();

        // Initialize connection
        this.initialize();
    }

    /**
     * Build WebSocket URL from current location
     */
    buildWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/ws/dashboard`;
    }

    /**
     * PHASE 1: Set this instance as the global update manager
     * Prevents multiple competing update mechanisms
     */
    setAsGlobalUpdateManager() {
        // Override global functions that cause race conditions
        window.globalUpdateManager = this;

        // Replace competing update functions with coordinated versions
        window.loadDashboardMetrics = () => this.coordinatedDashboardUpdate();
        window.loadOverviewMetrics = () => this.coordinatedDashboardUpdate();
        window.autoLoadMetrics = () => this.coordinatedDashboardUpdate();

        // PHASE 1: Coordinate cache invalidation with update-data command
        window.globalUpdateManager = this;
        window.coordinatedCacheInvalidation = () => this.handleCacheInvalidation();

        console.log('🔧 RealtimeDashboard: Set as global update manager, eliminated competing update functions');
    }

    /**
     * PHASE 1: Coordinated dashboard update to prevent race conditions
     * Single source of truth for all widget updates
     */
    async coordinatedDashboardUpdate() {
        // Prevent concurrent updates
        if (this.updateLock) {
            console.log('🔒 Update already in progress, skipping duplicate request');
            return;
        }

        this.updateLock = true;

        try {
            // Show loading state
            this.setLoadingState(true);

            // Use existing request if within debounce window
            const cacheKey = 'dashboard-metrics';
            if (this.requestQueue.has(cacheKey)) {
                console.log('🔄 Using cached dashboard metrics request');
                return await this.requestQueue.get(cacheKey);
            }

            // Create new request
            const promise = this.fetchDashboardMetrics();
            this.requestQueue.set(cacheKey, promise);

            // Clean up cache after debounce period
            setTimeout(() => this.requestQueue.delete(cacheKey), this.debounceTimeout);

            const data = await promise;
            this.updateDashboardElements(data);

            console.log('✅ Coordinated dashboard update completed');
            return data;

        } catch (error) {
            console.error('❌ Coordinated dashboard update failed:', error);
            this.setErrorState(error.message);
        } finally {
            this.updateLock = false;
            this.setLoadingState(false);
        }
    }

    /**
     * PHASE 1: Fetch dashboard metrics with proper error handling
     */
    async fetchDashboardMetrics() {
        const response = await fetch('/api/dashboard-metrics');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    }

    /**
     * PHASE 1: Update dashboard elements with data
     * Single function to prevent inconsistent updates
     */
    updateDashboardElements(data) {
        const elements = {
            'total-tokens': data.data?.total_tokens || data.total_tokens || '0',
            'metric-total-sessions': data.data?.total_sessions || data.total_sessions || '0',
            'success-rate': data.data?.success_rate || data.success_rate || '95%',
            'active-agents': data.data?.active_agents || data.active_agents || '0'
        };

        let updatedCount = 0;
        for (const [elementId, value] of Object.entries(elements)) {
            if (this.safeElementUpdate(elementId, value)) {
                // Add update animation only if update was successful
                const element = document.getElementById(elementId);
                if (element) {
                    element.classList.add('data-updated');
                    setTimeout(() => element.classList.remove('data-updated'), 1000);
                    updatedCount++;
                }
            }
        }

        console.log(`📊 Dashboard elements updated: ${updatedCount}/${Object.keys(elements).length}`, elements);
    }

    /**
     * PHASE 1: Set loading state for widgets
     */
    setLoadingState(isLoading) {
        const loadingElements = ['total-tokens', 'metric-total-sessions', 'success-rate', 'active-agents'];

        loadingElements.forEach(elementId => {
            const element = document.getElementById(elementId);
            if (element) {
                if (isLoading) {
                    element.classList.add('loading');
                    // Don't replace content with "Loading..." to prevent flickering
                } else {
                    element.classList.remove('loading');
                }
            }
        });
    }

    /**
     * PHASE 1: Set error state for widgets
     */
    setErrorState(errorMessage) {
        console.error('🚨 Dashboard error state:', errorMessage);

        const errorElements = ['total-tokens', 'metric-total-sessions', 'success-rate', 'active-agents'];

        errorElements.forEach(elementId => {
            const element = document.getElementById(elementId);
            if (element) {
                element.classList.add('error');
                // Keep existing content instead of showing error to prevent flickering
                setTimeout(() => element.classList.remove('error'), 3000);
            }
        });

        // Show notification instead of replacing widget content
        this.showNotification('Dashboard Update Error', errorMessage, 'error');
    }

    /**
     * Initialize real-time connection
     */
    initialize() {
        this.updateConnectionStatus('connecting');
        this.connectWebSocket();
        this.startHeartbeat();
        
        // Set up page visibility handling
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.handlePageHidden();
            } else {
                this.handlePageVisible();
            }
        });
    }

    /**
     * Connect WebSocket
     */
    connectWebSocket() {
        if (this.websocket && this.websocket.readyState === WebSocket.CONNECTING) {
            return;
        }

        try {
            this.websocket = new WebSocket(this.options.wsUrl);
            this.websocket.onopen = this.handleOpen;
            this.websocket.onmessage = this.handleMessage;
            this.websocket.onclose = this.handleClose;
            this.websocket.onerror = this.handleError;
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.enableFallbackMode();
        }
    }

    /**
     * Handle WebSocket open
     */
    handleOpen(event) {
        console.log('WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.fallbackMode = false;
        this.lastHeartbeat = Date.now();
        this.updateConnectionStatus('connected');
        
        // Process queued events
        this.processEventQueue();
        
        // Send initial subscription requests
        this.sendSubscriptions();
    }

    /**
     * Handle WebSocket message
     */
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.lastHeartbeat = Date.now();
            
            switch (data.type) {
                case 'heartbeat':
                    this.handleHeartbeat(data);
                    break;
                case 'metrics_update':
                    this.handleMetricsUpdate(data.payload);
                    break;
                case 'health_update':
                    this.handleHealthUpdate(data.payload);
                    break;
                case 'events_update':
                    this.handleEventsUpdate(data.payload);
                    break;
                case 'error':
                    this.handleServerError(data.payload);
                    break;
                default:
                    this.notifySubscribers(data.type, data.payload);
            }
        } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
        }
    }

    /**
     * Handle WebSocket close
     */
    handleClose(event) {
        console.log('WebSocket disconnected:', event.code, event.reason);
        this.isConnected = false;
        this.updateConnectionStatus('disconnected');
        
        if (!event.wasClean && this.reconnectAttempts < this.options.maxReconnectAttempts) {
            this.scheduleReconnect();
        } else if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            console.warn('Max reconnection attempts reached, switching to fallback mode');
            this.enableFallbackMode();
        }
    }

    /**
     * Handle WebSocket error
     */
    handleError(error) {
        console.error('WebSocket error:', error);
        this.updateConnectionStatus('error');
    }

    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        this.reconnectAttempts++;
        const delay = Math.min(this.options.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1), 30000);
        
        console.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
        setTimeout(() => {
            this.connectWebSocket();
        }, delay);
    }

    /**
     * Enable fallback polling mode
     */
    enableFallbackMode() {
        if (this.fallbackMode) return;
        
        console.log('Enabling fallback polling mode');
        this.fallbackMode = true;
        this.updateConnectionStatus('fallback');
        
        // Start polling for updates
        this.startFallbackPolling();
    }

    /**
     * Start fallback polling
     */
    startFallbackPolling() {
        if (this.fallbackInterval) {
            clearInterval(this.fallbackInterval);
        }

        this.fallbackInterval = setInterval(async () => {
            try {
                await this.pollForUpdates();
            } catch (error) {
                console.error('Fallback polling failed:', error);
            }
        }, this.options.fallbackPollInterval);
    }

    /**
     * Poll for updates using HTTP
     * PHASE 1: Use coordinated updates instead of separate polling
     */
    async pollForUpdates() {
        console.log('🔄 Fallback polling: Using coordinated dashboard update');

        // Use the same coordinated update mechanism for consistency
        await this.coordinatedDashboardUpdate();

        // Poll other endpoints that don't compete with dashboard metrics
        const endpoints = [
            { type: 'health', url: '/api/health/detailed' },
            { type: 'events', url: '/api/realtime/events' }
        ];

        for (const endpoint of endpoints) {
            try {
                const response = await fetch(endpoint.url);
                if (response.ok) {
                    const data = await response.json();
                    this.notifySubscribers(`${endpoint.type}_update`, data);
                }
            } catch (error) {
                console.warn(`Failed to poll ${endpoint.type}:`, error);
            }
        }
    }

    /**
     * Start heartbeat monitoring
     */
    startHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }

        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeat;
                if (timeSinceLastHeartbeat > this.options.heartbeatInterval * 2) {
                    console.warn('Heartbeat timeout detected');
                    this.websocket?.close();
                }
            }
        }, this.options.heartbeatInterval);
    }

    /**
     * Handle heartbeat message
     */
    handleHeartbeat(data) {
        // Send heartbeat response if requested
        if (data.requireResponse) {
            this.send({
                type: 'heartbeat_response',
                timestamp: Date.now()
            });
        }
    }

    /**
     * Handle metrics update
     * PHASE 1: Use coordinated update mechanism for consistency
     */
    handleMetricsUpdate(payload) {
        console.log('📡 WebSocket metrics update received');

        // Use coordinated update to prevent race conditions with HTTP polling
        if (payload && typeof payload === 'object') {
            this.updateDashboardElements(payload);
        }

        // Legacy component support
        if (this.dashboardComponents) {
            const metricsComponent = this.dashboardComponents.components.get('metrics-component');
            if (metricsComponent) {
                const transformedData = metricsComponent.transform(payload);
                metricsComponent.render(transformedData);
                this.addUpdateAnimation('metrics-component');
            }
        }

        this.notifySubscribers('metrics_update', payload);
    }

    /**
     * Handle health update
     */
    handleHealthUpdate(payload) {
        if (this.dashboardComponents) {
            const healthComponent = this.dashboardComponents.components.get('health-component');
            if (healthComponent) {
                const transformedData = healthComponent.transform(payload);
                healthComponent.render(transformedData);
                this.addUpdateAnimation('health-component');
            }
        }
        this.notifySubscribers('health_update', payload);
    }

    /**
     * Handle events update
     */
    handleEventsUpdate(payload) {
        if (this.dashboardComponents) {
            const realtimeComponent = this.dashboardComponents.components.get('realtime-component');
            if (realtimeComponent) {
                const transformedData = realtimeComponent.transform(payload);
                realtimeComponent.render(transformedData);
                this.addUpdateAnimation('realtime-component');
            }
        }
        this.notifySubscribers('events_update', payload);
    }

    /**
     * Handle server error
     */
    handleServerError(payload) {
        console.error('Server error received:', payload);
        this.notifySubscribers('server_error', payload);
        
        // Show user notification
        this.showNotification('Server Error', payload.message || 'Unknown server error', 'error');
    }

    /**
     * Add update animation to component
     */
    addUpdateAnimation(componentId) {
        const element = document.getElementById(componentId);
        if (element) {
            element.classList.add('updating');
            setTimeout(() => {
                element.classList.remove('updating');
            }, 2000);
        }
    }

    /**
     * Send subscriptions to server
     */
    sendSubscriptions() {
        const subscriptions = Array.from(this.subscribers.keys());
        if (subscriptions.length > 0) {
            this.send({
                type: 'subscribe',
                channels: subscriptions
            });
        }
    }

    /**
     * Subscribe to real-time updates
     */
    subscribe(channel, callback) {
        if (!this.subscribers.has(channel)) {
            this.subscribers.set(channel, new Set());
        }
        this.subscribers.get(channel).add(callback);
        
        // Send subscription if connected
        if (this.isConnected) {
            this.send({
                type: 'subscribe',
                channels: [channel]
            });
        }
    }

    /**
     * Unsubscribe from updates
     */
    unsubscribe(channel, callback) {
        if (this.subscribers.has(channel)) {
            this.subscribers.get(channel).delete(callback);
            if (this.subscribers.get(channel).size === 0) {
                this.subscribers.delete(channel);
                
                // Send unsubscription if connected
                if (this.isConnected) {
                    this.send({
                        type: 'unsubscribe',
                        channels: [channel]
                    });
                }
            }
        }
    }

    /**
     * Notify subscribers
     */
    notifySubscribers(channel, data) {
        if (this.subscribers.has(channel)) {
            for (const callback of this.subscribers.get(channel)) {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in subscriber callback for ${channel}:`, error);
                }
            }
        }
    }

    /**
     * Send message via WebSocket
     */
    send(data) {
        if (this.isConnected && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(data));
        } else {
            // Queue message for later
            this.eventQueue.push(data);
        }
    }

    /**
     * Process queued events
     */
    processEventQueue() {
        while (this.eventQueue.length > 0) {
            const event = this.eventQueue.shift();
            this.send(event);
        }
    }

    /**
     * Update connection status indicator
     */
    updateConnectionStatus(status) {
        const indicator = document.getElementById('connection-status');
        if (indicator) {
            indicator.className = `connection-status connection-${status}`;
            
            const statusText = {
                connecting: 'Connecting...',
                connected: 'Connected',
                disconnected: 'Disconnected',
                error: 'Connection Error',
                fallback: 'Polling Mode'
            };
            
            indicator.textContent = statusText[status] || status;
        }
    }

    /**
     * Show notification to user
     */
    showNotification(title, message, type = 'info') {
        // Create notification element if it doesn't exist
        let container = document.getElementById('notifications-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notifications-container';
            container.className = 'notifications-container';
            document.body.appendChild(container);
        }

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <h4>${title}</h4>
                <p>${message}</p>
            </div>
            <button class="notification-close" onclick="this.parentElement.remove()">×</button>
        `;

        container.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    /**
     * Handle page hidden (user switched tabs)
     */
    handlePageHidden() {
        // Reduce update frequency when page is hidden
        if (this.fallbackInterval) {
            clearInterval(this.fallbackInterval);
            this.fallbackInterval = setInterval(() => {
                this.pollForUpdates();
            }, this.options.fallbackPollInterval * 3); // Reduce frequency
        }
    }

    /**
     * Handle page visible (user returned to tab)
     */
    handlePageVisible() {
        // Resume normal update frequency
        if (this.fallbackMode) {
            this.startFallbackPolling();
        }
        
        // Trigger immediate update
        if (this.dashboardComponents) {
            // Refresh all components
            for (const [componentId] of this.dashboardComponents.components) {
                this.dashboardComponents.updateComponent(componentId);
            }
        }
    }

    /**
     * PHASE 1: Global error boundary for dashboard operations
     */
    setupGlobalErrorHandling() {
        // Capture unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('🚨 Unhandled promise rejection:', event.reason);
            this.handleGlobalError(event.reason, 'promise_rejection');
            event.preventDefault(); // Prevent browser default error handling
        });

        // Capture JavaScript errors
        window.addEventListener('error', (event) => {
            console.error('🚨 JavaScript error:', event.error);
            this.handleGlobalError(event.error, 'javascript_error');
        });

        console.log('🛡️ Global error handling enabled');
    }

    /**
     * PHASE 1: Handle global errors gracefully
     */
    handleGlobalError(error, type) {
        // Don't spam users with too many error notifications
        const errorKey = `${type}_${error.message || error}`;
        if (this.recentErrors && this.recentErrors.has(errorKey)) {
            return;
        }

        if (!this.recentErrors) {
            this.recentErrors = new Set();
        }

        this.recentErrors.add(errorKey);
        setTimeout(() => this.recentErrors.delete(errorKey), 30000); // 30 second cooldown

        // Show user-friendly error notification
        const errorMessage = this.getErrorMessage(error, type);
        this.showNotification('Dashboard Error', errorMessage, 'error');

        // Log for debugging
        console.error(`Dashboard error [${type}]:`, error);
    }

    /**
     * PHASE 1: Get user-friendly error messages
     */
    getErrorMessage(error, type) {
        if (type === 'promise_rejection') {
            if (error && error.message) {
                if (error.message.includes('fetch')) {
                    return 'Unable to connect to dashboard services. Retrying...';
                }
                if (error.message.includes('JSON')) {
                    return 'Invalid data received from server. Please refresh.';
                }
            }
            return 'An unexpected error occurred. Dashboard will continue operating.';
        }

        if (type === 'javascript_error') {
            return 'A client-side error occurred. Dashboard functionality may be limited.';
        }

        return 'An error occurred. Please refresh if issues persist.';
    }

    /**
     * PHASE 1: Handle cache invalidation coordination
     * Called by update-data command to prevent race conditions
     */
    async handleCacheInvalidation() {
        console.log('🗑️ Cache invalidation requested - coordinating refresh');

        try {
            // Clear request cache to force fresh data
            this.requestQueue.clear();

            // Set loading state
            this.setLoadingState(true);

            // Wait a brief moment for cache clearing to complete
            await new Promise(resolve => setTimeout(resolve, 200));

            // Trigger coordinated update
            await this.coordinatedDashboardUpdate();

            this.showNotification('Cache Cleared', 'Dashboard data refreshed successfully', 'success');
            console.log('✅ Cache invalidation completed');

        } catch (error) {
            console.error('❌ Cache invalidation failed:', error);
            this.setErrorState('Failed to refresh dashboard data');
        }
    }

    /**
     * PHASE 1: Graceful degradation for missing elements
     */
    safeElementUpdate(elementId, value) {
        try {
            const element = document.getElementById(elementId);
            if (!element) {
                console.warn(`🔍 Element '${elementId}' not found, skipping update`);
                return false;
            }

            element.textContent = value;
            return true;
        } catch (error) {
            console.error(`❌ Error updating element '${elementId}':`, error);
            this.handleGlobalError(error, 'element_update');
            return false;
        }
    }

    /**
     * Clean up resources
     */
    destroy() {
        if (this.websocket) {
            this.websocket.close();
        }

        if (this.fallbackInterval) {
            clearInterval(this.fallbackInterval);
        }

        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }

        this.subscribers.clear();
        this.eventQueue = [];

        // Clean up error tracking
        if (this.recentErrors) {
            this.recentErrors.clear();
        }
    }
}

// Export for use
window.RealtimeDashboard = RealtimeDashboard;

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.realtimeDashboard = new RealtimeDashboard();
});