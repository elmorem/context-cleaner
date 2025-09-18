/**
 * WebSocket Streaming Client for Real-time Dashboard Updates
 * Implements efficient batching, reconnection, and channel subscriptions
 */

class WebSocketStreamingClient {
    constructor(options = {}) {
        this.options = {
            url: options.url || this.getWebSocketURL(),
            reconnectInterval: options.reconnectInterval || 3000,
            maxReconnectAttempts: options.maxReconnectAttempts || 10,
            heartbeatInterval: options.heartbeatInterval || 30000,
            batchUpdateDelay: options.batchUpdateDelay || 100,
            enableCompression: options.enableCompression || true,
            ...options
        };

        // Connection state
        this.websocket = null;
        this.connectionId = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;

        // Subscription management
        this.subscriptions = new Set();
        this.messageHandlers = new Map();
        this.batchedUpdates = new Map();
        this.batchTimer = null;

        // Performance tracking
        this.metrics = {
            messagesReceived: 0,
            bytesReceived: 0,
            reconnections: 0,
            averageLatency: 0,
            lastLatency: 0,
            connectionUptime: 0,
            batchedUpdates: 0
        };

        this.connectionStartTime = null;
        this.latencyMeasurements = [];

        this.initializeConnection();

        console.log('WebSocketStreamingClient initialized');
    }

    getWebSocketURL() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/ws/dashboard`;
    }

    initializeConnection() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            return;
        }

        try {
            console.log(`Connecting to WebSocket: ${this.options.url}`);
            this.websocket = new WebSocket(this.options.url);

            this.websocket.onopen = this.handleOpen.bind(this);
            this.websocket.onmessage = this.handleMessage.bind(this);
            this.websocket.onclose = this.handleClose.bind(this);
            this.websocket.onerror = this.handleError.bind(this);

        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }

    handleOpen(event) {
        console.log('WebSocket connected successfully');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.connectionStartTime = Date.now();

        // Clear any existing reconnect timer
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // Start heartbeat
        this.startHeartbeat();

        // Re-subscribe to channels
        this.resubscribeToChannels();

        // Notify connection established
        this.emit('connected', { connectionId: this.connectionId });
    }

    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.metrics.messagesReceived++;
            this.metrics.bytesReceived += event.data.length;

            // Handle different message types
            switch (data.type) {
                case 'connection_established':
                    this.connectionId = data.connection_id;
                    console.log(`Connection established with ID: ${this.connectionId}`);
                    break;

                case 'batch':
                    this.handleBatchMessage(data);
                    break;

                case 'component_update':
                    this.handleComponentUpdate(data);
                    break;

                case 'performance_update':
                    this.handlePerformanceUpdate(data);
                    break;

                case 'pong':
                    this.handlePong(data);
                    break;

                case 'error':
                    console.error('WebSocket error message:', data.message);
                    break;

                default:
                    this.handleGenericMessage(data);
            }

        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }

    handleClose(event) {
        console.log('WebSocket connection closed:', event.code, event.reason);
        this.isConnected = false;
        this.connectionId = null;

        // Stop heartbeat
        this.stopHeartbeat();

        // Update metrics
        if (this.connectionStartTime) {
            this.metrics.connectionUptime += Date.now() - this.connectionStartTime;
        }

        // Emit disconnected event
        this.emit('disconnected', { code: event.code, reason: event.reason });

        // Schedule reconnect unless it was intentional
        if (event.code !== 1000) { // 1000 = normal closure
            this.scheduleReconnect();
        }
    }

    handleError(event) {
        console.error('WebSocket error:', event);
        this.emit('error', event);
    }

    handleBatchMessage(data) {
        this.metrics.batchedUpdates++;

        if (data.messages && Array.isArray(data.messages)) {
            data.messages.forEach(message => {
                this.handleGenericMessage(message);
            });
        }
    }

    handleComponentUpdate(data) {
        const { component_id, data: componentData } = data;

        // Check if we should batch this update
        if (this.options.batchUpdateDelay > 0) {
            this.batchComponentUpdate(component_id, componentData);
        } else {
            this.applyComponentUpdate(component_id, componentData);
        }
    }

    batchComponentUpdate(componentId, data) {
        // Store update for batching
        this.batchedUpdates.set(componentId, {
            data,
            timestamp: Date.now()
        });

        // Clear existing batch timer and start new one
        if (this.batchTimer) {
            clearTimeout(this.batchTimer);
        }

        this.batchTimer = setTimeout(() => {
            this.processBatchedUpdates();
        }, this.options.batchUpdateDelay);
    }

    processBatchedUpdates() {
        const updates = new Map(this.batchedUpdates);
        this.batchedUpdates.clear();
        this.batchTimer = null;

        // Apply all batched updates
        for (const [componentId, updateInfo] of updates) {
            this.applyComponentUpdate(componentId, updateInfo.data);
        }

        console.debug(`Processed ${updates.size} batched component updates`);
    }

    applyComponentUpdate(componentId, data) {
        // Find component element
        const element = document.getElementById(componentId) ||
                       document.querySelector(`[data-component-id="${componentId}"]`) ||
                       document.querySelector(`[data-lazy-component="${componentId}"]`);

        if (!element) {
            console.warn(`Component element not found: ${componentId}`);
            return;
        }

        // Check if component has custom update handler
        const customHandler = this.messageHandlers.get(`component:${componentId}`);
        if (customHandler) {
            customHandler(data);
            return;
        }

        // Default update handling
        this.updateComponentElement(element, data);

        // Emit component updated event
        this.emit('componentUpdated', { componentId, data });
    }

    updateComponentElement(element, data) {
        // Update based on component type
        const componentType = element.dataset.componentType || 'default';

        switch (componentType) {
            case 'metric':
                this.updateMetricComponent(element, data);
                break;
            case 'chart':
                this.updateChartComponent(element, data);
                break;
            case 'status':
                this.updateStatusComponent(element, data);
                break;
            default:
                this.updateGenericComponent(element, data);
        }

        // Update timestamp
        element.setAttribute('data-last-updated', new Date().toISOString());
    }

    updateMetricComponent(element, data) {
        const valueElement = element.querySelector('.metric-value');
        const changeElement = element.querySelector('.metric-change');

        if (valueElement && data.value !== undefined) {
            valueElement.textContent = data.value;
        }

        if (changeElement && data.change !== undefined) {
            changeElement.textContent = data.change;
            changeElement.className = `metric-change ${data.changeType || 'neutral'}`;
        }
    }

    updateChartComponent(element, data) {
        // Trigger chart update event for chart libraries to handle
        element.dispatchEvent(new CustomEvent('chartUpdate', {
            detail: data
        }));
    }

    updateStatusComponent(element, data) {
        const statusIndicator = element.querySelector('.status-indicator');
        if (statusIndicator && data.status) {
            statusIndicator.className = `status-indicator status-${data.status}`;
        }

        const statusText = element.querySelector('.status-text');
        if (statusText && data.message) {
            statusText.textContent = data.message;
        }
    }

    updateGenericComponent(element, data) {
        // Generic update - replace content or merge data
        if (typeof data === 'string') {
            element.innerHTML = data;
        } else if (data.html) {
            element.innerHTML = data.html;
        } else {
            // Dispatch generic update event
            element.dispatchEvent(new CustomEvent('dataUpdate', {
                detail: data
            }));
        }
    }

    handlePerformanceUpdate(data) {
        this.emit('performanceUpdate', data);
    }

    handlePong(data) {
        if (data.timestamp) {
            const latency = Date.now() - data.timestamp;
            this.updateLatencyMetrics(latency);
        }
    }

    updateLatencyMetrics(latency) {
        this.metrics.lastLatency = latency;
        this.latencyMeasurements.push(latency);

        // Keep only last 10 measurements
        if (this.latencyMeasurements.length > 10) {
            this.latencyMeasurements.shift();
        }

        // Calculate average
        this.metrics.averageLatency = this.latencyMeasurements.reduce((sum, val) => sum + val, 0) / this.latencyMeasurements.length;
    }

    handleGenericMessage(data) {
        // Check for specific handler
        const handler = this.messageHandlers.get(data.type);
        if (handler) {
            handler(data);
        } else {
            // Emit generic message event
            this.emit('message', data);
        }
    }

    startHeartbeat() {
        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected) {
                this.send({
                    type: 'ping',
                    timestamp: Date.now()
                });
            }
        }, this.options.heartbeatInterval);
    }

    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached. Giving up.');
            this.emit('maxReconnectAttemptsReached');
            return;
        }

        this.reconnectAttempts++;
        this.metrics.reconnections++;

        const delay = Math.min(
            this.options.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
            30000 // Max 30 seconds
        );

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        this.reconnectTimer = setTimeout(() => {
            this.initializeConnection();
        }, delay);
    }

    subscribe(channels) {
        if (!Array.isArray(channels)) {
            channels = [channels];
        }

        channels.forEach(channel => {
            this.subscriptions.add(channel);
        });

        if (this.isConnected) {
            this.send({
                type: 'subscribe',
                channels: channels
            });
        }

        console.debug(`Subscribed to channels: ${channels.join(', ')}`);
    }

    unsubscribe(channels) {
        if (!Array.isArray(channels)) {
            channels = [channels];
        }

        channels.forEach(channel => {
            this.subscriptions.delete(channel);
        });

        if (this.isConnected) {
            this.send({
                type: 'unsubscribe',
                channels: channels
            });
        }

        console.debug(`Unsubscribed from channels: ${channels.join(', ')}`);
    }

    resubscribeToChannels() {
        if (this.subscriptions.size > 0) {
            const channels = Array.from(this.subscriptions);
            this.send({
                type: 'subscribe',
                channels: channels
            });
            console.debug(`Re-subscribed to ${channels.length} channels`);
        }
    }

    send(data) {
        if (!this.isConnected || !this.websocket) {
            console.warn('Cannot send message: WebSocket not connected');
            return false;
        }

        try {
            this.websocket.send(JSON.stringify(data));
            return true;
        } catch (error) {
            console.error('Error sending WebSocket message:', error);
            return false;
        }
    }

    registerMessageHandler(messageType, handler) {
        this.messageHandlers.set(messageType, handler);
    }

    unregisterMessageHandler(messageType) {
        this.messageHandlers.delete(messageType);
    }

    // Event emitter functionality
    emit(eventType, data) {
        const event = new CustomEvent(`ws:${eventType}`, {
            detail: data
        });
        document.dispatchEvent(event);
    }

    on(eventType, handler) {
        document.addEventListener(`ws:${eventType}`, handler);
    }

    off(eventType, handler) {
        document.removeEventListener(`ws:${eventType}`, handler);
    }

    getConnectionStatus() {
        return {
            isConnected: this.isConnected,
            connectionId: this.connectionId,
            reconnectAttempts: this.reconnectAttempts,
            subscriptions: Array.from(this.subscriptions),
            metrics: {
                ...this.metrics,
                connectionUptime: this.connectionStartTime
                    ? this.metrics.connectionUptime + (Date.now() - this.connectionStartTime)
                    : this.metrics.connectionUptime
            }
        };
    }

    disconnect() {
        console.log('Disconnecting WebSocket...');

        // Clear timers
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.batchTimer) {
            clearTimeout(this.batchTimer);
            this.batchTimer = null;
        }

        this.stopHeartbeat();

        // Close connection
        if (this.websocket) {
            this.websocket.close(1000, 'Client disconnect');
        }

        this.isConnected = false;
        this.connectionId = null;
    }

    reconnect() {
        console.log('Manual reconnection triggered');
        this.disconnect();
        setTimeout(() => {
            this.reconnectAttempts = 0;
            this.initializeConnection();
        }, 1000);
    }
}

// WebSocket connection manager for dashboard components
class DashboardWebSocketManager {
    constructor() {
        this.client = new WebSocketStreamingClient();
        this.componentSubscriptions = new Map();

        this.setupDefaultHandlers();
        this.setupDashboardIntegration();

        console.log('Dashboard WebSocket Manager initialized');
    }

    setupDefaultHandlers() {
        // Handle connection events
        this.client.on('connected', () => {
            this.showConnectionStatus('connected');
            this.subscribeToDefaultChannels();
        });

        this.client.on('disconnected', () => {
            this.showConnectionStatus('disconnected');
        });

        this.client.on('error', () => {
            this.showConnectionStatus('error');
        });

        // Handle component updates
        this.client.on('componentUpdated', (event) => {
            console.debug('Component updated:', event.detail);
        });

        // Handle performance updates
        this.client.on('performanceUpdate', (event) => {
            this.updatePerformanceMetrics(event.detail);
        });
    }

    setupDashboardIntegration() {
        // Subscribe components when they are registered with lazy loader
        document.addEventListener('componentRegistered', (event) => {
            const { componentId } = event.detail;
            this.subscribeToComponent(componentId);
        });

        // Auto-subscribe visible components
        if (window.lazyLoader) {
            this.subscribeVisibleComponents();
        }
    }

    subscribeToDefaultChannels() {
        const defaultChannels = [
            'performance',
            'system_health',
            'global_updates'
        ];

        this.client.subscribe(defaultChannels);
    }

    subscribeToComponent(componentId) {
        const channel = `component:${componentId}`;

        if (!this.componentSubscriptions.has(componentId)) {
            this.client.subscribe(channel);
            this.componentSubscriptions.set(componentId, channel);
            console.debug(`Subscribed to component updates: ${componentId}`);
        }
    }

    unsubscribeFromComponent(componentId) {
        const channel = this.componentSubscriptions.get(componentId);

        if (channel) {
            this.client.unsubscribe(channel);
            this.componentSubscriptions.delete(componentId);
            console.debug(`Unsubscribed from component updates: ${componentId}`);
        }
    }

    subscribeVisibleComponents() {
        // Subscribe to all currently visible components
        document.querySelectorAll('[data-lazy-component], [data-component-id]').forEach(element => {
            const componentId = element.dataset.lazyComponent ||
                               element.dataset.componentId ||
                               element.id;

            if (componentId) {
                this.subscribeToComponent(componentId);
            }
        });
    }

    showConnectionStatus(status) {
        const statusElement = document.getElementById('websocket-status');
        if (statusElement) {
            statusElement.className = `websocket-status ${status}`;
            statusElement.textContent = status.toUpperCase();
        }

        // Show toast notification
        this.showToast(`WebSocket ${status}`, status === 'connected' ? 'success' : 'warning');
    }

    updatePerformanceMetrics(data) {
        // Update global performance metrics display
        const metricsElement = document.getElementById('realtime-metrics');
        if (metricsElement) {
            metricsElement.innerHTML = `
                <div class="metric">
                    <span>Latency:</span>
                    <span>${data.latency || 0}ms</span>
                </div>
                <div class="metric">
                    <span>Updates/sec:</span>
                    <span>${data.updatesPerSecond || 0}</span>
                </div>
                <div class="metric">
                    <span>Connected:</span>
                    <span>${data.connections || 0}</span>
                </div>
            `;
        }
    }

    showToast(message, type = 'info') {
        // Simple toast notification system
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('show');
        }, 100);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 3000);
    }

    getStatus() {
        return this.client.getConnectionStatus();
    }

    disconnect() {
        this.client.disconnect();
    }

    reconnect() {
        this.client.reconnect();
    }
}

// Global instances
window.wsClient = new WebSocketStreamingClient();
window.dashboardWS = new DashboardWebSocketManager();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('WebSocket streaming system initialized');

    // Add reconnect button functionality
    const reconnectBtn = document.getElementById('ws-reconnect-btn');
    if (reconnectBtn) {
        reconnectBtn.addEventListener('click', () => {
            window.dashboardWS.reconnect();
        });
    }
});

// Handle page visibility changes to manage connections
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('Page hidden, reducing WebSocket activity');
        // Could implement reduced polling here
    } else {
        console.log('Page visible, resuming normal WebSocket activity');
        // Ensure connection is active
        if (!window.wsClient.isConnected) {
            window.wsClient.reconnect();
        }
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WebSocketStreamingClient, DashboardWebSocketManager };
}