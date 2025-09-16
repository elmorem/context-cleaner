/**
 * Real-time Dashboard Updates with Error Recovery
 * WebSocket-based real-time updates with fallback to polling
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
        
        // Initialize dashboard components if available
        this.dashboardComponents = window.dashboardComponents || null;
        
        // Bind methods
        this.handleOpen = this.handleOpen.bind(this);
        this.handleMessage = this.handleMessage.bind(this);
        this.handleClose = this.handleClose.bind(this);
        this.handleError = this.handleError.bind(this);
        
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
     */
    async pollForUpdates() {
        if (!this.dashboardComponents) return;

        const endpoints = [
            { type: 'metrics', url: '/api/dashboard/metrics' },
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
     */
    handleMetricsUpdate(payload) {
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
    }
}

// Export for use
window.RealtimeDashboard = RealtimeDashboard;

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.realtimeDashboard = new RealtimeDashboard();
});