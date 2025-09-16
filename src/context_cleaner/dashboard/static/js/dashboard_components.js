/**
 * Enhanced Dashboard Components with Resilient API Integration
 * Integrates Phase 1-3 infrastructure for robust real-time dashboard functionality
 */
class DashboardComponents {
    constructor(options = {}) {
        // Initialize API client with resilient configuration
        this.apiClient = new EnhancedAPIClient({
            baseURL: options.baseURL || '',
            timeout: options.timeout || 15000,
            maxRetries: options.maxRetries || 3,
            retryDelay: options.retryDelay || 1000
        });

        // Initialize loading manager
        this.loadingManager = new LoadingManager();

        // Dashboard state
        this.components = new Map();
        this.updateIntervals = new Map();
        this.errorStates = new Map();
        
        // Configuration
        this.refreshInterval = options.refreshInterval || 30000; // 30 seconds
        this.healthCheckInterval = options.healthCheckInterval || 10000; // 10 seconds
        this.maxErrorCount = options.maxErrorCount || 3;
        
        // Initialize health monitoring
        this.initializeHealthMonitoring();
    }

    /**
     * Initialize health monitoring for the dashboard
     */
    initializeHealthMonitoring() {
        // Regular health checks
        setInterval(() => {
            this.performHealthCheck();
        }, this.healthCheckInterval);

        // Initial health check
        this.performHealthCheck();
    }

    /**
     * Perform system health check
     */
    async performHealthCheck() {
        try {
            const healthData = await this.apiClient.healthCheck();
            this.updateHealthIndicator(healthData);
        } catch (error) {
            console.warn('Health check failed:', error.message);
            this.updateHealthIndicator({ status: 'error', message: error.message });
        }
    }

    /**
     * Update health indicator in the UI
     */
    updateHealthIndicator(healthData) {
        const indicator = document.getElementById('system-health-indicator');
        if (indicator) {
            indicator.className = `health-indicator health-${healthData.status}`;
            indicator.textContent = healthData.status.toUpperCase();
            indicator.title = healthData.message || '';
        }
    }

    /**
     * Register a dashboard component for automatic updates
     */
    registerComponent(componentId, config) {
        this.components.set(componentId, {
            endpoint: config.endpoint,
            updateInterval: config.updateInterval || this.refreshInterval,
            transform: config.transform || (data => data),
            render: config.render,
            errorHandler: config.errorHandler || this.defaultErrorHandler.bind(this),
            retryConfig: config.retryConfig || {}
        });

        this.errorStates.set(componentId, { count: 0, lastError: null });
        
        // Start automatic updates
        this.startComponentUpdates(componentId);
    }

    /**
     * Start automatic updates for a component
     */
    startComponentUpdates(componentId) {
        const component = this.components.get(componentId);
        if (!component) return;

        // Initial load
        this.updateComponent(componentId);

        // Set up interval
        const intervalId = setInterval(() => {
            this.updateComponent(componentId);
        }, component.updateInterval);

        this.updateIntervals.set(componentId, intervalId);
    }

    /**
     * Update a specific component
     */
    async updateComponent(componentId) {
        const component = this.components.get(componentId);
        if (!component) return;

        const loadingId = `loading-${componentId}`;
        
        try {
            // Start loading state
            this.loadingManager.startLoading(loadingId, {
                message: 'Updating...',
                showSpinner: true
            });

            // Fetch data
            const response = await this.apiClient.get(component.endpoint, {}, component.retryConfig);
            
            // Transform data
            const transformedData = component.transform(response.data || response);
            
            // Render component
            component.render(transformedData);
            
            // Clear error state
            this.clearErrorState(componentId);
            
            // Stop loading
            this.loadingManager.stopLoading(loadingId);

        } catch (error) {
            this.handleComponentError(componentId, error);
        }
    }

    /**
     * Handle component errors with retry logic
     */
    async handleComponentError(componentId, error) {
        const component = this.components.get(componentId);
        const errorState = this.errorStates.get(componentId);
        
        errorState.count++;
        errorState.lastError = error;

        // Stop loading with error state
        this.loadingManager.stopLoading(`loading-${componentId}`);

        if (errorState.count >= this.maxErrorCount) {
            // Too many errors, show error state
            component.errorHandler(error, componentId, 'max_errors_reached');
            this.pauseComponentUpdates(componentId);
        } else {
            // Show degraded state but continue trying
            component.errorHandler(error, componentId, 'retry_pending');
        }
    }

    /**
     * Default error handler
     */
    defaultErrorHandler(error, componentId, errorType) {
        const container = document.getElementById(componentId);
        if (!container) return;

        const errorMessage = error.message || 'Unknown error occurred';
        
        if (errorType === 'max_errors_reached') {
            container.innerHTML = `
                <div class="component-error">
                    <div class="error-icon">⚠️</div>
                    <div class="error-message">
                        <h4>Component Unavailable</h4>
                        <p>${errorMessage}</p>
                        <button onclick="dashboardComponents.retryComponent('${componentId}')" class="retry-btn">
                            Retry
                        </button>
                    </div>
                </div>
            `;
        } else {
            container.classList.add('component-degraded');
            const statusBar = container.querySelector('.component-status') || this.createStatusBar(container);
            statusBar.textContent = `Warning: ${errorMessage}`;
            statusBar.className = 'component-status warning';
        }
    }

    /**
     * Create status bar for components
     */
    createStatusBar(container) {
        const statusBar = document.createElement('div');
        statusBar.className = 'component-status';
        container.insertBefore(statusBar, container.firstChild);
        return statusBar;
    }

    /**
     * Clear error state for a component
     */
    clearErrorState(componentId) {
        const errorState = this.errorStates.get(componentId);
        errorState.count = 0;
        errorState.lastError = null;

        const container = document.getElementById(componentId);
        if (container) {
            container.classList.remove('component-degraded');
            const statusBar = container.querySelector('.component-status');
            if (statusBar) {
                statusBar.remove();
            }
        }
    }

    /**
     * Pause component updates
     */
    pauseComponentUpdates(componentId) {
        const intervalId = this.updateIntervals.get(componentId);
        if (intervalId) {
            clearInterval(intervalId);
            this.updateIntervals.delete(componentId);
        }
    }

    /**
     * Retry a failed component
     */
    retryComponent(componentId) {
        this.clearErrorState(componentId);
        this.startComponentUpdates(componentId);
    }

    /**
     * Metrics Dashboard Component
     */
    initializeMetricsComponent() {
        this.registerComponent('metrics-component', {
            endpoint: '/api/dashboard/metrics',
            updateInterval: 15000, // 15 seconds for metrics
            transform: (data) => {
                // Process metrics data
                return {
                    performance: data.performance || {},
                    errors: data.errors || {},
                    usage: data.usage || {}
                };
            },
            render: (data) => {
                this.renderMetricsChart(data);
            },
            retryConfig: { timeout: 10000, retries: 2 }
        });
    }

    /**
     * Render metrics chart
     */
    renderMetricsChart(data) {
        const container = document.getElementById('metrics-component');
        if (!container) return;

        const html = `
            <div class="metrics-grid">
                <div class="metric-card">
                    <h3>Performance</h3>
                    <div class="metric-value">${data.performance.avgResponseTime || 'N/A'}ms</div>
                    <div class="metric-label">Avg Response Time</div>
                </div>
                <div class="metric-card">
                    <h3>Errors</h3>
                    <div class="metric-value">${data.errors.count || 0}</div>
                    <div class="metric-label">Last 24h</div>
                </div>
                <div class="metric-card">
                    <h3>Usage</h3>
                    <div class="metric-value">${data.usage.requests || 0}</div>
                    <div class="metric-label">Total Requests</div>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
    }

    /**
     * Service Health Component
     */
    initializeHealthComponent() {
        this.registerComponent('health-component', {
            endpoint: '/api/health/detailed',
            updateInterval: 20000, // 20 seconds for health
            transform: (data) => {
                return data.services || {};
            },
            render: (services) => {
                this.renderHealthStatus(services);
            },
            retryConfig: { timeout: 8000, retries: 2 }
        });
    }

    /**
     * Render health status
     */
    renderHealthStatus(services) {
        const container = document.getElementById('health-component');
        if (!container) return;

        const serviceHtml = Object.entries(services).map(([name, health]) => {
            const statusClass = health.status === 'healthy' ? 'healthy' : 
                               health.status === 'degraded' ? 'degraded' : 'unhealthy';
            
            return `
                <div class="service-status ${statusClass}">
                    <div class="service-name">${name}</div>
                    <div class="service-indicator"></div>
                    <div class="service-response">${health.response_time_ms || 0}ms</div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div class="health-grid">
                ${serviceHtml}
            </div>
        `;
    }

    /**
     * Real-time Updates Component
     */
    initializeRealtimeComponent() {
        this.registerComponent('realtime-component', {
            endpoint: '/api/realtime/events',
            updateInterval: 5000, // 5 seconds for real-time
            transform: (data) => {
                return data.events || [];
            },
            render: (events) => {
                this.renderRealtimeEvents(events);
            },
            retryConfig: { timeout: 5000, retries: 1 }
        });
    }

    /**
     * Render real-time events
     */
    renderRealtimeEvents(events) {
        const container = document.getElementById('realtime-component');
        if (!container) return;

        const eventsHtml = events.slice(0, 10).map(event => `
            <div class="event-item">
                <div class="event-time">${new Date(event.timestamp).toLocaleTimeString()}</div>
                <div class="event-message">${event.message}</div>
                <div class="event-type ${event.type}">${event.type}</div>
            </div>
        `).join('');

        container.innerHTML = `
            <div class="events-list">
                ${eventsHtml}
            </div>
        `;
    }

    /**
     * Initialize all dashboard components
     */
    initializeAll() {
        this.initializeMetricsComponent();
        this.initializeHealthComponent();
        this.initializeRealtimeComponent();
    }

    /**
     * Cleanup method
     */
    destroy() {
        // Clear all intervals
        for (const intervalId of this.updateIntervals.values()) {
            clearInterval(intervalId);
        }
        
        // Cancel active requests
        this.apiClient.cancelAllRequests();
        
        // Clear loading states
        this.loadingManager.stopAllLoading();
    }
}

// Global instance
window.DashboardComponents = DashboardComponents;

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboardComponents = new DashboardComponents();
});