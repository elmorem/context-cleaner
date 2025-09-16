/**
 * Enhanced API Client with Retry Logic and Error Handling
 * Browser-compatible HTTP client for dashboard API calls
 */
class EnhancedAPIClient {
    constructor(options = {}) {
        this.baseURL = options.baseURL || '';
        this.timeout = options.timeout || 15000;
        this.maxRetries = options.maxRetries || 3;
        this.retryDelay = options.retryDelay || 1000;
        this.activeRequests = new Map();
        this.requestCounter = 0;
    }

    /**
     * Perform GET request with retry logic
     */
    async get(endpoint, params = {}, retryConfig = {}) {
        return this.request('GET', endpoint, null, params, retryConfig);
    }

    /**
     * Perform POST request with retry logic
     */
    async post(endpoint, data = null, params = {}, retryConfig = {}) {
        return this.request('POST', endpoint, data, params, retryConfig);
    }

    /**
     * Perform PUT request with retry logic
     */
    async put(endpoint, data = null, params = {}, retryConfig = {}) {
        return this.request('PUT', endpoint, data, params, retryConfig);
    }

    /**
     * Perform DELETE request with retry logic
     */
    async delete(endpoint, params = {}, retryConfig = {}) {
        return this.request('DELETE', endpoint, null, params, retryConfig);
    }

    /**
     * Generic request method with built-in retry logic
     */
    async request(method, endpoint, data = null, params = {}, retryConfig = {}) {
        const requestId = `req_${++this.requestCounter}`;
        const config = {
            timeout: retryConfig.timeout || this.timeout,
            retries: retryConfig.retries || this.maxRetries,
            retryDelay: retryConfig.retryDelay || this.retryDelay
        };

        // Build URL with query parameters
        const url = this.buildUrl(endpoint, params);
        
        let lastError;
        for (let attempt = 0; attempt <= config.retries; attempt++) {
            try {
                const response = await this.makeRequest(requestId, method, url, data, config.timeout);
                this.activeRequests.delete(requestId);
                return response;
            } catch (error) {
                lastError = error;
                console.warn(`Request attempt ${attempt + 1} failed:`, error.message);
                
                // Don't retry on certain errors
                if (this.isNonRetryableError(error)) {
                    break;
                }
                
                // Wait before retrying (exponential backoff)
                if (attempt < config.retries) {
                    const delay = config.retryDelay * Math.pow(2, attempt);
                    await this.sleep(delay);
                }
            }
        }

        this.activeRequests.delete(requestId);
        throw lastError;
    }

    /**
     * Make the actual HTTP request
     */
    async makeRequest(requestId, method, url, data, timeout) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            // Store request for potential cancellation
            this.activeRequests.set(requestId, xhr);
            
            // Set up timeout
            const timeoutId = setTimeout(() => {
                xhr.abort();
                reject(new Error(`Request timeout after ${timeout}ms`));
            }, timeout);
            
            xhr.onreadystatechange = () => {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    clearTimeout(timeoutId);
                    
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            const response = {
                                data: xhr.responseText ? JSON.parse(xhr.responseText) : null,
                                status: xhr.status,
                                statusText: xhr.statusText,
                                headers: this.parseHeaders(xhr.getAllResponseHeaders())
                            };
                            resolve(response);
                        } catch (parseError) {
                            reject(new Error(`Failed to parse response: ${parseError.message}`));
                        }
                    } else {
                        const error = new Error(`HTTP ${xhr.status}: ${xhr.statusText}`);
                        error.status = xhr.status;
                        error.response = xhr.responseText;
                        reject(error);
                    }
                }
            };
            
            xhr.onerror = () => {
                clearTimeout(timeoutId);
                reject(new Error('Network error occurred'));
            };
            
            xhr.onabort = () => {
                clearTimeout(timeoutId);
                reject(new Error('Request was aborted'));
            };
            
            // Open and send request
            xhr.open(method, url, true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('Accept', 'application/json');
            
            if (data) {
                xhr.send(JSON.stringify(data));
            } else {
                xhr.send();
            }
        });
    }

    /**
     * Build URL with query parameters
     */
    buildUrl(endpoint, params = {}) {
        let url = this.baseURL + endpoint;
        
        const queryParams = Object.entries(params)
            .filter(([key, value]) => value !== null && value !== undefined)
            .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
            .join('&');
            
        if (queryParams) {
            url += (url.includes('?') ? '&' : '?') + queryParams;
        }
        
        return url;
    }

    /**
     * Parse response headers from string
     */
    parseHeaders(headerString) {
        const headers = {};
        if (headerString) {
            headerString.split('\r\n').forEach(line => {
                const parts = line.split(': ');
                if (parts.length === 2) {
                    headers[parts[0].toLowerCase()] = parts[1];
                }
            });
        }
        return headers;
    }

    /**
     * Check if error should not be retried
     */
    isNonRetryableError(error) {
        // Don't retry client errors (4xx) except for specific cases
        if (error.status >= 400 && error.status < 500) {
            // Retry on 408 (timeout), 429 (rate limit)
            return ![408, 429].includes(error.status);
        }
        return false;
    }

    /**
     * Health check endpoint
     */
    async healthCheck() {
        try {
            const response = await this.get('/api/health', {}, { retries: 1, timeout: 5000 });
            return {
                status: 'healthy',
                data: response.data,
                timestamp: Date.now()
            };
        } catch (error) {
            return {
                status: 'error',
                message: error.message,
                timestamp: Date.now()
            };
        }
    }

    /**
     * Cancel all active requests
     */
    cancelAllRequests() {
        for (const [requestId, xhr] of this.activeRequests) {
            try {
                xhr.abort();
            } catch (error) {
                console.warn(`Failed to cancel request ${requestId}:`, error);
            }
        }
        this.activeRequests.clear();
    }

    /**
     * Cancel specific request
     */
    cancelRequest(requestId) {
        const xhr = this.activeRequests.get(requestId);
        if (xhr) {
            xhr.abort();
            this.activeRequests.delete(requestId);
            return true;
        }
        return false;
    }

    /**
     * Sleep utility for retry delays
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Get active request count
     */
    getActiveRequestCount() {
        return this.activeRequests.size;
    }
}

/**
 * Loading Manager for UI loading states
 */
class LoadingManager {
    constructor() {
        this.loadingStates = new Map();
    }

    /**
     * Start loading state
     */
    startLoading(loadingId, options = {}) {
        const state = {
            id: loadingId,
            startTime: Date.now(),
            message: options.message || 'Loading...',
            showSpinner: options.showSpinner !== false,
            element: options.element || null
        };

        this.loadingStates.set(loadingId, state);
        this.updateUI(loadingId, true);
    }

    /**
     * Stop loading state
     */
    stopLoading(loadingId) {
        const state = this.loadingStates.get(loadingId);
        if (state) {
            this.updateUI(loadingId, false);
            this.loadingStates.delete(loadingId);
        }
    }

    /**
     * Stop all loading states
     */
    stopAllLoading() {
        for (const loadingId of this.loadingStates.keys()) {
            this.stopLoading(loadingId);
        }
    }

    /**
     * Check if specific loading state is active
     */
    isLoading(loadingId) {
        return this.loadingStates.has(loadingId);
    }

    /**
     * Get all active loading states
     */
    getActiveLoadingStates() {
        return Array.from(this.loadingStates.values());
    }

    /**
     * Update UI based on loading state
     */
    updateUI(loadingId, isLoading) {
        const state = this.loadingStates.get(loadingId);
        if (!state) return;

        // Try to find element by ID or use provided element
        const element = state.element || document.getElementById(loadingId.replace('loading-', ''));
        if (!element) return;

        if (isLoading) {
            this.showLoadingState(element, state);
        } else {
            this.hideLoadingState(element);
        }
    }

    /**
     * Show loading state on element
     */
    showLoadingState(element, state) {
        // Add loading class
        element.classList.add('loading');

        // Create or update loading overlay
        let overlay = element.querySelector('.loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            element.appendChild(overlay);
        }

        // Set loading content
        const spinner = state.showSpinner ? '<div class="loading-spinner"></div>' : '';
        overlay.innerHTML = `
            <div class="loading-content">
                ${spinner}
                <div class="loading-message">${state.message}</div>
            </div>
        `;

        // Add CSS if not already present
        this.ensureLoadingStyles();
    }

    /**
     * Hide loading state from element
     */
    hideLoadingState(element) {
        element.classList.remove('loading');
        const overlay = element.querySelector('.loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }

    /**
     * Ensure loading styles are present
     */
    ensureLoadingStyles() {
        if (document.getElementById('loading-manager-styles')) return;

        const style = document.createElement('style');
        style.id = 'loading-manager-styles';
        style.textContent = `
            .loading {
                position: relative;
                pointer-events: none;
                opacity: 0.7;
            }
            
            .loading-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(255, 255, 255, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
            }
            
            .loading-content {
                text-align: center;
                color: #64748b;
            }
            
            .loading-spinner {
                width: 20px;
                height: 20px;
                border: 2px solid #e2e8f0;
                border-top: 2px solid #2563eb;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 0.5rem;
            }
            
            .loading-message {
                font-size: 0.875rem;
                font-weight: 500;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
}

// Make classes available globally
window.EnhancedAPIClient = EnhancedAPIClient;
window.LoadingManager = LoadingManager;