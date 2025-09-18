/**
 * Lazy Loading and Performance Optimization for Dashboard Components
 * Implements intersection observer, virtual scrolling, and predictive loading
 */

class LazyLoadingController {
    constructor(options = {}) {
        this.options = {
            rootMargin: '200px',
            threshold: 0.1,
            batchSize: 5,
            maxConcurrentLoads: 3,
            enablePredictiveLoading: true,
            cacheEnabled: true,
            cacheTTL: 300000, // 5 minutes
            ...options
        };

        // Component tracking
        this.registeredComponents = new Map();
        this.loadingQueue = [];
        this.activeLoaders = 0;
        this.componentCache = new Map();
        this.cacheTimestamps = new Map();

        // Performance tracking
        this.metrics = {
            totalComponents: 0,
            loadedComponents: 0,
            cacheHits: 0,
            cacheMisses: 0,
            averageLoadTime: 0,
            loadErrors: 0
        };

        // Scroll prediction
        this.scrollHistory = [];
        this.lastScrollTime = 0;
        this.scrollVelocity = 0;

        this.initializeIntersectionObserver();
        this.initializeScrollTracking();

        console.log('LazyLoadingController initialized with advanced optimization');
    }

    initializeIntersectionObserver() {
        if (!window.IntersectionObserver) {
            console.warn('IntersectionObserver not supported, falling back to scroll-based loading');
            this.initializeFallbackScrollLoading();
            return;
        }

        this.observer = new IntersectionObserver((entries) => {
            this.handleIntersectionChanges(entries);
        }, {
            rootMargin: this.options.rootMargin,
            threshold: this.options.threshold
        });

        // Observe existing components
        document.querySelectorAll('[data-lazy-component]').forEach(element => {
            this.registerComponent(element);
        });
    }

    initializeScrollTracking() {
        let scrollTimeout;

        window.addEventListener('scroll', () => {
            const now = Date.now();
            const scrollY = window.scrollY;

            // Calculate scroll velocity
            if (this.scrollHistory.length > 0) {
                const lastEntry = this.scrollHistory[this.scrollHistory.length - 1];
                const timeDelta = now - lastEntry.time;
                const scrollDelta = scrollY - lastEntry.position;

                if (timeDelta > 0) {
                    this.scrollVelocity = Math.abs(scrollDelta) / timeDelta;
                }
            }

            // Track scroll history
            this.scrollHistory.push({ time: now, position: scrollY });
            if (this.scrollHistory.length > 10) {
                this.scrollHistory.shift();
            }

            // Predictive loading on fast scroll
            if (this.options.enablePredictiveLoading && this.scrollVelocity > 0.5) {
                clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    this.predictiveLoad();
                }, 100);
            }
        }, { passive: true });
    }

    initializeFallbackScrollLoading() {
        // Fallback for browsers without IntersectionObserver
        window.addEventListener('scroll', this.throttle(() => {
            this.checkVisibilityFallback();
        }, 100), { passive: true });
    }

    registerComponent(element, config = {}) {
        const componentId = element.dataset.lazyComponent ||
                           element.id ||
                           `lazy-component-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        const componentConfig = {
            element,
            id: componentId,
            priority: parseInt(element.dataset.priority) || 5,
            endpoint: element.dataset.endpoint,
            dependencies: element.dataset.dependencies ?
                         element.dataset.dependencies.split(',').map(s => s.trim()) : [],
            loadedCallback: config.loadedCallback,
            errorCallback: config.errorCallback,
            isLoaded: false,
            isLoading: false,
            loadAttempts: 0,
            ...config
        };

        this.registeredComponents.set(componentId, componentConfig);
        this.metrics.totalComponents++;

        // Start observing
        if (this.observer) {
            this.observer.observe(element);
        }

        // Mark critical components for immediate loading
        if (componentConfig.priority <= 2) {
            this.queueComponentLoad(componentId, true);
        }

        console.debug(`Registered component: ${componentId} with priority ${componentConfig.priority}`);
        return componentId;
    }

    handleIntersectionChanges(entries) {
        const visibleComponents = [];

        entries.forEach(entry => {
            const element = entry.target;
            const componentId = this.getComponentId(element);
            const component = this.registeredComponents.get(componentId);

            if (!component) return;

            if (entry.isIntersecting) {
                visibleComponents.push(componentId);

                // Queue for loading if not already loaded
                if (!component.isLoaded && !component.isLoading) {
                    this.queueComponentLoad(componentId);
                }
            }
        });

        // Process visible components in batches
        this.processLoadingQueue();
    }

    queueComponentLoad(componentId, highPriority = false) {
        const component = this.registeredComponents.get(componentId);
        if (!component || component.isLoaded || component.isLoading) {
            return;
        }

        // Check dependencies first
        const unloadedDeps = component.dependencies.filter(depId => {
            const dep = this.registeredComponents.get(depId);
            return dep && !dep.isLoaded;
        });

        if (unloadedDeps.length > 0) {
            // Load dependencies first
            unloadedDeps.forEach(depId => this.queueComponentLoad(depId, true));

            // Re-queue this component after a short delay
            setTimeout(() => this.queueComponentLoad(componentId, highPriority), 100);
            return;
        }

        // Add to queue with priority
        const queueItem = { componentId, priority: component.priority, timestamp: Date.now() };

        if (highPriority) {
            this.loadingQueue.unshift(queueItem);
        } else {
            this.loadingQueue.push(queueItem);
        }

        // Sort queue by priority
        this.loadingQueue.sort((a, b) => a.priority - b.priority);

        console.debug(`Queued component for loading: ${componentId}`);
    }

    async processLoadingQueue() {
        if (this.activeLoaders >= this.options.maxConcurrentLoads || this.loadingQueue.length === 0) {
            return;
        }

        // Process batch
        const batch = this.loadingQueue.splice(0, Math.min(
            this.options.batchSize,
            this.options.maxConcurrentLoads - this.activeLoaders
        ));

        const loadPromises = batch.map(item => this.loadComponent(item.componentId));

        try {
            await Promise.allSettled(loadPromises);
        } catch (error) {
            console.error('Error in batch loading:', error);
        }

        // Continue processing queue
        if (this.loadingQueue.length > 0) {
            setTimeout(() => this.processLoadingQueue(), 50);
        }
    }

    async loadComponent(componentId) {
        const component = this.registeredComponents.get(componentId);
        if (!component || component.isLoading || component.isLoaded) {
            return;
        }

        this.activeLoaders++;
        component.isLoading = true;
        component.loadAttempts++;

        const startTime = performance.now();

        try {
            // Check cache first
            if (this.options.cacheEnabled && this.checkCache(componentId)) {
                const cachedData = this.componentCache.get(componentId);
                await this.renderComponent(component, cachedData);
                this.metrics.cacheHits++;
                console.debug(`Loaded component ${componentId} from cache`);
                return;
            }

            this.metrics.cacheMisses++;

            // Show loading state
            this.showLoadingState(component.element);

            // Fetch component data
            const data = await this.fetchComponentData(component);

            // Cache the data
            if (this.options.cacheEnabled) {
                this.cacheComponent(componentId, data);
            }

            // Render component
            await this.renderComponent(component, data);

            // Update metrics
            const loadTime = performance.now() - startTime;
            this.updateLoadTimeMetrics(loadTime);

            component.isLoaded = true;
            this.metrics.loadedComponents++;

            // Call success callback
            if (component.loadedCallback) {
                component.loadedCallback(data);
            }

            console.debug(`Successfully loaded component ${componentId} in ${loadTime.toFixed(2)}ms`);

        } catch (error) {
            console.error(`Failed to load component ${componentId}:`, error);
            this.metrics.loadErrors++;

            // Show error state
            this.showErrorState(component.element, error);

            // Call error callback
            if (component.errorCallback) {
                component.errorCallback(error);
            }

            // Retry logic for failed loads
            if (component.loadAttempts < 3) {
                setTimeout(() => {
                    component.isLoading = false;
                    this.queueComponentLoad(componentId);
                }, 1000 * component.loadAttempts);
            }

        } finally {
            component.isLoading = false;
            this.activeLoaders--;
        }
    }

    async fetchComponentData(component) {
        if (!component.endpoint) {
            throw new Error('No endpoint specified for component');
        }

        const response = await fetch(component.endpoint, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    async renderComponent(component, data) {
        // Remove loading/error states
        component.element.classList.remove('lazy-loading', 'lazy-error');

        // Custom renderer if specified
        if (component.renderer) {
            await component.renderer(component.element, data);
            return;
        }

        // Default rendering based on component type
        const componentType = component.element.dataset.componentType || 'default';

        switch (componentType) {
            case 'widget':
                this.renderWidget(component.element, data);
                break;
            case 'chart':
                this.renderChart(component.element, data);
                break;
            case 'table':
                this.renderTable(component.element, data);
                break;
            default:
                this.renderDefault(component.element, data);
        }

        // Mark as rendered
        component.element.classList.add('lazy-loaded');
        component.element.setAttribute('data-loaded-at', new Date().toISOString());
    }

    renderWidget(element, data) {
        const template = `
            <div class="widget-content">
                <div class="widget-header">
                    <h3>${data.title || 'Widget'}</h3>
                    <div class="widget-status ${data.status || 'healthy'}"></div>
                </div>
                <div class="widget-body">
                    ${this.renderMetrics(data.metrics || {})}
                </div>
                <div class="widget-footer">
                    <small>Last updated: ${new Date(data.timestamp || Date.now()).toLocaleTimeString()}</small>
                </div>
            </div>
        `;
        element.innerHTML = template;
    }

    renderChart(element, data) {
        // Placeholder for chart rendering
        // In real implementation, would integrate with Chart.js, D3, etc.
        element.innerHTML = `
            <div class="chart-container">
                <canvas id="chart-${element.id}" width="400" height="200"></canvas>
                <div class="chart-legend">
                    <p>Chart: ${data.title || 'Data Visualization'}</p>
                    <p>Data points: ${data.dataPoints?.length || 0}</p>
                </div>
            </div>
        `;
    }

    renderTable(element, data) {
        const headers = data.headers || [];
        const rows = data.rows || [];

        const headerHtml = headers.map(h => `<th>${h}</th>`).join('');
        const rowsHtml = rows.map(row =>
            `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`
        ).join('');

        element.innerHTML = `
            <div class="table-container">
                <table class="lazy-table">
                    <thead><tr>${headerHtml}</tr></thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
            </div>
        `;
    }

    renderDefault(element, data) {
        if (typeof data === 'string') {
            element.innerHTML = data;
        } else {
            element.innerHTML = `
                <div class="component-data">
                    <pre>${JSON.stringify(data, null, 2)}</pre>
                </div>
            `;
        }
    }

    renderMetrics(metrics) {
        return Object.entries(metrics).map(([key, value]) => `
            <div class="metric-row">
                <span class="metric-label">${key}:</span>
                <span class="metric-value">${value}</span>
            </div>
        `).join('');
    }

    showLoadingState(element) {
        element.classList.add('lazy-loading');
        element.innerHTML = `
            <div class="loading-placeholder">
                <div class="loading-spinner"></div>
                <p>Loading component...</p>
            </div>
        `;
    }

    showErrorState(element, error) {
        element.classList.add('lazy-error');
        element.innerHTML = `
            <div class="error-placeholder">
                <div class="error-icon">⚠️</div>
                <p>Failed to load component</p>
                <small>${error.message}</small>
                <button onclick="lazyLoader.retryComponent('${this.getComponentId(element)}')">
                    Retry
                </button>
            </div>
        `;
    }

    checkCache(componentId) {
        if (!this.componentCache.has(componentId)) {
            return false;
        }

        const timestamp = this.cacheTimestamps.get(componentId);
        const isExpired = (Date.now() - timestamp) > this.options.cacheTTL;

        if (isExpired) {
            this.componentCache.delete(componentId);
            this.cacheTimestamps.delete(componentId);
            return false;
        }

        return true;
    }

    cacheComponent(componentId, data) {
        this.componentCache.set(componentId, data);
        this.cacheTimestamps.set(componentId, Date.now());

        // Cleanup old cache entries
        this.cleanupCache();
    }

    cleanupCache() {
        const now = Date.now();
        for (const [id, timestamp] of this.cacheTimestamps.entries()) {
            if ((now - timestamp) > this.options.cacheTTL) {
                this.componentCache.delete(id);
                this.cacheTimestamps.delete(id);
            }
        }
    }

    predictiveLoad() {
        if (!this.options.enablePredictiveLoading) return;

        // Predict scroll direction and preload components
        const scrollDirection = this.getScrollDirection();
        const currentViewport = this.getCurrentViewport();

        // Find components likely to become visible soon
        const predictedComponents = this.findComponentsInDirection(scrollDirection, currentViewport);

        predictedComponents.forEach(componentId => {
            this.queueComponentLoad(componentId);
        });
    }

    getScrollDirection() {
        if (this.scrollHistory.length < 2) return 'down';

        const recent = this.scrollHistory.slice(-3);
        const avgDirection = recent.reduce((sum, entry, index) => {
            if (index === 0) return 0;
            return sum + (entry.position - recent[index - 1].position);
        }, 0);

        return avgDirection > 0 ? 'down' : 'up';
    }

    getCurrentViewport() {
        return {
            top: window.scrollY,
            bottom: window.scrollY + window.innerHeight,
            height: window.innerHeight
        };
    }

    findComponentsInDirection(direction, viewport) {
        const buffer = 500; // pixels to look ahead
        const searchArea = direction === 'down'
            ? { top: viewport.bottom, bottom: viewport.bottom + buffer }
            : { top: viewport.top - buffer, bottom: viewport.top };

        const components = [];

        this.registeredComponents.forEach((component, id) => {
            if (component.isLoaded || component.isLoading) return;

            const rect = component.element.getBoundingClientRect();
            const elementTop = rect.top + window.scrollY;

            if (elementTop >= searchArea.top && elementTop <= searchArea.bottom) {
                components.push(id);
            }
        });

        return components;
    }

    retryComponent(componentId) {
        const component = this.registeredComponents.get(componentId);
        if (!component) return;

        component.isLoaded = false;
        component.isLoading = false;
        component.element.classList.remove('lazy-error');

        this.queueComponentLoad(componentId, true);
    }

    checkVisibilityFallback() {
        // Fallback visibility check for browsers without IntersectionObserver
        const viewport = this.getCurrentViewport();

        this.registeredComponents.forEach((component, id) => {
            if (component.isLoaded || component.isLoading) return;

            const rect = component.element.getBoundingClientRect();
            const isVisible = (
                rect.top >= -this.options.rootMargin &&
                rect.bottom <= window.innerHeight + this.options.rootMargin
            );

            if (isVisible) {
                this.queueComponentLoad(id);
            }
        });
    }

    getComponentId(element) {
        return element.dataset.lazyComponent ||
               element.id ||
               element.getAttribute('data-component-id');
    }

    updateLoadTimeMetrics(loadTime) {
        const currentAvg = this.metrics.averageLoadTime;
        const loadedCount = this.metrics.loadedComponents;

        this.metrics.averageLoadTime = loadedCount === 0
            ? loadTime
            : (currentAvg * (loadedCount - 1) + loadTime) / loadedCount;
    }

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    getPerformanceMetrics() {
        return {
            ...this.metrics,
            cacheSize: this.componentCache.size,
            queueLength: this.loadingQueue.length,
            activeLoaders: this.activeLoaders,
            scrollVelocity: this.scrollVelocity
        };
    }

    destroy() {
        if (this.observer) {
            this.observer.disconnect();
        }

        this.registeredComponents.clear();
        this.componentCache.clear();
        this.cacheTimestamps.clear();
        this.loadingQueue = [];
    }
}

// Global instance
window.lazyLoader = new LazyLoadingController();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('Lazy loading system initialized');

    // Initialize any existing components
    document.querySelectorAll('[data-lazy-component]').forEach(element => {
        if (!element.dataset.registered) {
            window.lazyLoader.registerComponent(element);
            element.dataset.registered = 'true';
        }
    });
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LazyLoadingController;
}