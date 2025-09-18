/**
 * UI Responsiveness Optimization System
 * Implements virtual scrolling, debouncing, and performance enhancements
 */

class UIPerformanceOptimizer {
    constructor(options = {}) {
        this.options = {
            debounceDelay: options.debounceDelay || 150,
            throttleDelay: options.throttleDelay || 16, // ~60fps
            virtualScrollBuffer: options.virtualScrollBuffer || 5,
            maxRenderBatch: options.maxRenderBatch || 20,
            enableVirtualScrolling: options.enableVirtualScrolling !== false,
            enableSmartRendering: options.enableSmartRendering !== false,
            enablePerformanceMonitoring: options.enablePerformanceMonitoring !== false,
            ...options
        };

        // Performance tracking
        this.performanceMetrics = {
            frameDrops: 0,
            renderOperations: 0,
            averageRenderTime: 0,
            virtualScrollSaves: 0,
            debouncedOperations: 0,
            currentFPS: 0
        };

        // Virtual scrolling instances
        this.virtualScrollers = new Map();
        this.intersectionObserver = null;

        // Debounced/throttled functions cache
        this.debouncedFunctions = new Map();
        this.throttledFunctions = new Map();

        // Animation frame management
        this.frameCallbacks = new Set();
        this.rafId = null;

        // Performance monitoring
        this.frameTimestamps = [];
        this.renderTimestamps = [];

        this.initializeOptimizations();

        console.log('UI Performance Optimizer initialized');
    }

    initializeOptimizations() {
        this.setupFrameMonitoring();
        this.setupIntersectionObserver();
        this.optimizeExistingElements();
        this.setupEventOptimizations();
    }

    setupFrameMonitoring() {
        if (!this.options.enablePerformanceMonitoring) return;

        let lastFrameTime = performance.now();

        const frameLoop = (currentTime) => {
            // Calculate FPS
            const frameDelta = currentTime - lastFrameTime;
            lastFrameTime = currentTime;

            this.frameTimestamps.push(currentTime);
            if (this.frameTimestamps.length > 60) {
                this.frameTimestamps.shift();
            }

            // Calculate current FPS
            if (this.frameTimestamps.length > 1) {
                const timeSpan = this.frameTimestamps[this.frameTimestamps.length - 1] - this.frameTimestamps[0];
                this.performanceMetrics.currentFPS = (this.frameTimestamps.length - 1) / (timeSpan / 1000);
            }

            // Detect frame drops (> 20ms = below 50fps)
            if (frameDelta > 20) {
                this.performanceMetrics.frameDrops++;
            }

            // Process queued frame callbacks
            const callbacks = Array.from(this.frameCallbacks);
            this.frameCallbacks.clear();

            callbacks.forEach(callback => {
                try {
                    callback(currentTime);
                } catch (error) {
                    console.error('Error in frame callback:', error);
                }
            });

            this.rafId = requestAnimationFrame(frameLoop);
        };

        this.rafId = requestAnimationFrame(frameLoop);
    }

    setupIntersectionObserver() {
        if (!window.IntersectionObserver) return;

        this.intersectionObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const element = entry.target;

                if (entry.isIntersecting) {
                    this.onElementVisible(element);
                } else {
                    this.onElementHidden(element);
                }
            });
        }, {
            threshold: [0, 0.25, 0.5, 0.75, 1.0],
            rootMargin: '50px'
        });
    }

    onElementVisible(element) {
        // Resume animations and interactions for visible elements
        element.classList.remove('ui-optimized-hidden');

        // Enable hover effects
        element.style.pointerEvents = '';

        // Resume auto-refresh for widgets
        if (element.dataset.autoRefresh === 'paused') {
            element.dataset.autoRefresh = 'active';
            this.resumeElementUpdates(element);
        }
    }

    onElementHidden(element) {
        // Pause expensive operations for hidden elements
        element.classList.add('ui-optimized-hidden');

        // Disable hover effects to save CPU
        element.style.pointerEvents = 'none';

        // Pause auto-refresh for widgets
        if (element.dataset.autoRefresh === 'active') {
            element.dataset.autoRefresh = 'paused';
            this.pauseElementUpdates(element);
        }
    }

    optimizeExistingElements() {
        // Find and optimize large lists
        document.querySelectorAll('.large-list, [data-virtual-scroll]').forEach(element => {
            this.enableVirtualScrolling(element);
        });

        // Optimize heavy widgets
        document.querySelectorAll('.widget-card, .metric-card').forEach(element => {
            this.optimizeWidget(element);
        });

        // Monitor performance-critical elements
        document.querySelectorAll('[data-performance-critical]').forEach(element => {
            if (this.intersectionObserver) {
                this.intersectionObserver.observe(element);
            }
        });
    }

    setupEventOptimizations() {
        // Optimize scroll events
        this.optimizeScrollEvents();

        // Optimize resize events
        this.optimizeResizeEvents();

        // Optimize input events
        this.optimizeInputEvents();
    }

    optimizeScrollEvents() {
        const throttledScroll = this.throttle((event) => {
            // Update virtual scrollers
            this.virtualScrollers.forEach(scroller => {
                scroller.updateViewport();
            });

            // Emit optimized scroll event
            document.dispatchEvent(new CustomEvent('optimizedScroll', {
                detail: {
                    scrollY: window.scrollY,
                    scrollX: window.scrollX,
                    timestamp: performance.now()
                }
            }));
        }, this.options.throttleDelay);

        window.addEventListener('scroll', throttledScroll, { passive: true });
    }

    optimizeResizeEvents() {
        const debouncedResize = this.debounce(() => {
            // Update virtual scrollers
            this.virtualScrollers.forEach(scroller => {
                scroller.handleResize();
            });

            // Recalculate layout for critical elements
            document.querySelectorAll('[data-responsive]').forEach(element => {
                this.updateResponsiveElement(element);
            });

            // Emit optimized resize event
            document.dispatchEvent(new CustomEvent('optimizedResize', {
                detail: {
                    width: window.innerWidth,
                    height: window.innerHeight,
                    timestamp: performance.now()
                }
            }));
        }, 250);

        window.addEventListener('resize', debouncedResize);
    }

    optimizeInputEvents() {
        // Debounce search inputs
        document.addEventListener('input', (event) => {
            if (event.target.matches('.search-input, [data-search]')) {
                this.debounceSearchInput(event.target);
            }
        });

        // Throttle range inputs
        document.addEventListener('input', (event) => {
            if (event.target.type === 'range') {
                this.throttleRangeInput(event.target);
            }
        });
    }

    debounceSearchInput(input) {
        const debouncedSearch = this.debounce(() => {
            const searchEvent = new CustomEvent('debouncedSearch', {
                detail: {
                    value: input.value,
                    target: input
                }
            });
            input.dispatchEvent(searchEvent);
        }, this.options.debounceDelay);

        debouncedSearch();
    }

    throttleRangeInput(input) {
        const throttledRange = this.throttle(() => {
            const rangeEvent = new CustomEvent('throttledRange', {
                detail: {
                    value: input.value,
                    target: input
                }
            });
            input.dispatchEvent(rangeEvent);
        }, this.options.throttleDelay);

        throttledRange();
    }

    enableVirtualScrolling(container) {
        if (!this.options.enableVirtualScrolling) return;

        const virtualScroller = new VirtualScroller(container, {
            itemHeight: parseInt(container.dataset.itemHeight) || 50,
            buffer: this.options.virtualScrollBuffer,
            totalItems: parseInt(container.dataset.totalItems) || 0
        });

        this.virtualScrollers.set(container, virtualScroller);
        this.performanceMetrics.virtualScrollSaves++;

        console.debug('Virtual scrolling enabled for:', container);
    }

    optimizeWidget(widget) {
        // Add intersection observer for visibility optimization
        if (this.intersectionObserver) {
            this.intersectionObserver.observe(widget);
        }

        // Optimize animations
        this.optimizeWidgetAnimations(widget);

        // Setup smart updating
        this.setupSmartUpdating(widget);
    }

    optimizeWidgetAnimations(widget) {
        // Replace CSS transitions with optimized ones
        const style = window.getComputedStyle(widget);
        if (style.transition && style.transition !== 'none') {
            // Add will-change for better performance
            widget.style.willChange = 'transform, opacity';

            // Use transform instead of changing layout properties
            this.convertToTransformAnimations(widget);
        }
    }

    convertToTransformAnimations(element) {
        // Convert margin/padding animations to transform
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    this.optimizeInlineStyles(element);
                }
            });
        });

        observer.observe(element, { attributes: true, attributeFilter: ['style'] });
    }

    optimizeInlineStyles(element) {
        const style = element.style;

        // Convert margin changes to transforms where possible
        if (style.marginTop || style.marginLeft) {
            const translateY = parseInt(style.marginTop) || 0;
            const translateX = parseInt(style.marginLeft) || 0;

            if (translateX !== 0 || translateY !== 0) {
                style.transform = `translate(${translateX}px, ${translateY}px)`;
                style.marginTop = '';
                style.marginLeft = '';
            }
        }
    }

    setupSmartUpdating(widget) {
        if (!this.options.enableSmartRendering) return;

        const updateFunction = widget.updateData || widget.refresh;
        if (!updateFunction) return;

        // Wrap update function with smart timing
        const smartUpdate = this.createSmartUpdateFunction(updateFunction.bind(widget));
        widget.updateData = smartUpdate;
        widget.refresh = smartUpdate;
    }

    createSmartUpdateFunction(originalUpdate) {
        let lastUpdate = 0;
        let pendingUpdate = false;

        return (...args) => {
            const now = performance.now();

            // Prevent too frequent updates
            if (now - lastUpdate < 100) {
                if (!pendingUpdate) {
                    pendingUpdate = true;
                    this.scheduleFrameCallback(() => {
                        pendingUpdate = false;
                        lastUpdate = performance.now();
                        originalUpdate(...args);
                    });
                }
                return;
            }

            lastUpdate = now;
            originalUpdate(...args);
        };
    }

    updateResponsiveElement(element) {
        const breakpoints = {
            small: 576,
            medium: 768,
            large: 992,
            xlarge: 1200
        };

        const width = window.innerWidth;
        let currentBreakpoint = 'small';

        for (const [name, minWidth] of Object.entries(breakpoints)) {
            if (width >= minWidth) {
                currentBreakpoint = name;
            }
        }

        element.dataset.breakpoint = currentBreakpoint;
        element.className = element.className.replace(/\bbreakpoint-\w+/g, '') + ` breakpoint-${currentBreakpoint}`;
    }

    pauseElementUpdates(element) {
        // Pause timers and intervals associated with the element
        const timers = element._uiOptimizationTimers || [];
        timers.forEach(timer => clearInterval(timer));
    }

    resumeElementUpdates(element) {
        // Resume timers and intervals
        const timerConfigs = element._uiOptimizationTimerConfigs || [];
        const timers = timerConfigs.map(config => setInterval(config.callback, config.interval));
        element._uiOptimizationTimers = timers;
    }

    // Utility functions for debouncing and throttling
    debounce(func, delay) {
        const key = func.toString();

        if (!this.debouncedFunctions.has(key)) {
            let timeoutId;

            const debouncedFunc = (...args) => {
                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    func.apply(this, args);
                    this.performanceMetrics.debouncedOperations++;
                }, delay);
            };

            this.debouncedFunctions.set(key, debouncedFunc);
        }

        return this.debouncedFunctions.get(key);
    }

    throttle(func, delay) {
        const key = func.toString();

        if (!this.throttledFunctions.has(key)) {
            let lastCall = 0;

            const throttledFunc = (...args) => {
                const now = performance.now();

                if (now - lastCall >= delay) {
                    lastCall = now;
                    func.apply(this, args);
                }
            };

            this.throttledFunctions.set(key, throttledFunc);
        }

        return this.throttledFunctions.get(key);
    }

    scheduleFrameCallback(callback) {
        this.frameCallbacks.add(callback);
    }

    measureRenderTime(renderFunction) {
        const startTime = performance.now();

        const result = renderFunction();

        const endTime = performance.now();
        const renderTime = endTime - startTime;

        // Update metrics
        this.performanceMetrics.renderOperations++;
        const currentAvg = this.performanceMetrics.averageRenderTime;
        const operations = this.performanceMetrics.renderOperations;

        this.performanceMetrics.averageRenderTime = operations === 1
            ? renderTime
            : (currentAvg * (operations - 1) + renderTime) / operations;

        return result;
    }

    getPerformanceMetrics() {
        return {
            ...this.performanceMetrics,
            virtualScrollers: this.virtualScrollers.size,
            debouncedFunctions: this.debouncedFunctions.size,
            throttledFunctions: this.throttledFunctions.size,
            frameCallbacksQueued: this.frameCallbacks.size
        };
    }

    destroy() {
        // Clean up
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
        }

        if (this.intersectionObserver) {
            this.intersectionObserver.disconnect();
        }

        this.virtualScrollers.forEach(scroller => scroller.destroy());
        this.virtualScrollers.clear();

        this.debouncedFunctions.clear();
        this.throttledFunctions.clear();
        this.frameCallbacks.clear();
    }
}

class VirtualScroller {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            itemHeight: options.itemHeight || 50,
            buffer: options.buffer || 5,
            totalItems: options.totalItems || 0,
            ...options
        };

        this.scrollTop = 0;
        this.viewportHeight = 0;
        this.startIndex = 0;
        this.endIndex = 0;
        this.visibleItems = [];

        this.initialize();
    }

    initialize() {
        // Create virtual scroll wrapper
        this.wrapper = document.createElement('div');
        this.wrapper.className = 'virtual-scroll-wrapper';
        this.wrapper.style.cssText = `
            position: relative;
            overflow-y: auto;
            height: 100%;
        `;

        // Create content container
        this.content = document.createElement('div');
        this.content.className = 'virtual-scroll-content';
        this.content.style.cssText = `
            position: relative;
            height: ${this.options.totalItems * this.options.itemHeight}px;
        `;

        // Create viewport
        this.viewport = document.createElement('div');
        this.viewport.className = 'virtual-scroll-viewport';
        this.viewport.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
        `;

        this.content.appendChild(this.viewport);
        this.wrapper.appendChild(this.content);

        // Replace original container content
        const parent = this.container.parentNode;
        parent.insertBefore(this.wrapper, this.container);
        parent.removeChild(this.container);

        // Setup scroll listener
        this.wrapper.addEventListener('scroll', this.handleScroll.bind(this), { passive: true });

        // Initial render
        this.updateViewport();
    }

    handleScroll() {
        this.scrollTop = this.wrapper.scrollTop;
        this.updateViewport();
    }

    updateViewport() {
        this.viewportHeight = this.wrapper.clientHeight;

        // Calculate visible range
        const startIndex = Math.max(0, Math.floor(this.scrollTop / this.options.itemHeight) - this.options.buffer);
        const endIndex = Math.min(
            this.options.totalItems,
            Math.ceil((this.scrollTop + this.viewportHeight) / this.options.itemHeight) + this.options.buffer
        );

        if (startIndex !== this.startIndex || endIndex !== this.endIndex) {
            this.startIndex = startIndex;
            this.endIndex = endIndex;
            this.render();
        }
    }

    render() {
        // Clear viewport
        this.viewport.innerHTML = '';

        // Position viewport
        this.viewport.style.transform = `translateY(${this.startIndex * this.options.itemHeight}px)`;

        // Render visible items
        for (let i = this.startIndex; i < this.endIndex; i++) {
            const item = this.createItem(i);
            this.viewport.appendChild(item);
        }

        // Emit render event
        this.wrapper.dispatchEvent(new CustomEvent('virtualRender', {
            detail: {
                startIndex: this.startIndex,
                endIndex: this.endIndex,
                visibleCount: this.endIndex - this.startIndex
            }
        }));
    }

    createItem(index) {
        const item = document.createElement('div');
        item.className = 'virtual-scroll-item';
        item.style.cssText = `
            height: ${this.options.itemHeight}px;
            box-sizing: border-box;
        `;
        item.dataset.index = index;

        // Allow custom item renderer
        if (this.options.renderItem) {
            this.options.renderItem(item, index);
        } else {
            item.textContent = `Item ${index}`;
        }

        return item;
    }

    handleResize() {
        this.updateViewport();
    }

    updateTotalItems(newTotal) {
        this.options.totalItems = newTotal;
        this.content.style.height = `${newTotal * this.options.itemHeight}px`;
        this.updateViewport();
    }

    scrollToIndex(index) {
        const scrollTop = index * this.options.itemHeight;
        this.wrapper.scrollTop = scrollTop;
    }

    destroy() {
        if (this.wrapper && this.wrapper.parentNode) {
            this.wrapper.parentNode.removeChild(this.wrapper);
        }
    }
}

// Global instance
window.uiOptimizer = new UIPerformanceOptimizer();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('UI Performance Optimization system initialized');

    // Add performance monitoring to console
    if (window.uiOptimizer.options.enablePerformanceMonitoring) {
        setInterval(() => {
            const metrics = window.uiOptimizer.getPerformanceMetrics();
            if (metrics.currentFPS < 30) {
                console.warn('Low FPS detected:', metrics.currentFPS.toFixed(1));
            }
        }, 5000);
    }
});

// CSS for optimizations
const optimizationStyles = `
.ui-optimized-hidden {
    animation-play-state: paused !important;
}

.virtual-scroll-wrapper {
    contain: layout style paint;
}

.virtual-scroll-item {
    contain: layout style paint;
    will-change: transform;
}

.lazy-loading {
    opacity: 0.5;
    transition: opacity 0.3s ease;
}

.lazy-loaded {
    opacity: 1;
}

.performance-optimized {
    transform: translateZ(0);
    backface-visibility: hidden;
}

@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}
`;

// Inject optimization styles
const styleSheet = document.createElement('style');
styleSheet.textContent = optimizationStyles;
document.head.appendChild(styleSheet);

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { UIPerformanceOptimizer, VirtualScroller };
}