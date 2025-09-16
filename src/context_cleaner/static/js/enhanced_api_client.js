/**
 * Enhanced API Client with timeout management, retry logic, and error recovery
 */
class EnhancedAPIClient {
    constructor(options = {}) {
        this.baseURL = options.baseURL || '';
        this.defaultTimeout = options.timeout || 15000; // 15 seconds
        this.maxRetries = options.maxRetries || 3;
        this.retryDelay = options.retryDelay || 1000; // 1 second
        this.activeRequests = new Map();
        
        // Request interceptors
        this.requestInterceptors = [];
        this.responseInterceptors = [];
    }

    /**
     * Make HTTP request with timeout and retry logic
     */
    async request(url, options = {}) {
        const requestConfig = {
            timeout: options.timeout || this.defaultTimeout,
            retries: options.retries !== undefined ? options.retries : this.maxRetries,
            ...options
        };

        const requestKey = `${options.method || 'GET'}_${url}`;
        
        // Cancel existing request if duplicate
        if (this.activeRequests.has(requestKey)) {
            this.activeRequests.get(requestKey).abort();
        }

        const controller = new AbortController();
        this.activeRequests.set(requestKey, controller);

        try {
            const result = await this._makeRequestWithRetry(url, requestConfig, controller);
            this.activeRequests.delete(requestKey);
            return result;
        } catch (error) {
            this.activeRequests.delete(requestKey);
            throw error;
        }
    }

    /**
     * Internal method to handle request with retry logic
     */
    async _makeRequestWithRetry(url, config, controller, attempt = 1) {
        try {
            return await this._executeRequest(url, config, controller);
        } catch (error) {
            // Don't retry if request was cancelled
            if (error.name === 'AbortError') {
                throw error;
            }

            // Don't retry client errors (4xx)
            if (error.status >= 400 && error.status < 500) {
                throw error;
            }

            // Retry server errors and network issues
            if (attempt < config.retries && this._shouldRetry(error)) {
                console.warn(`Request failed (attempt ${attempt}/${config.retries}):`, error.message);
                
                // Exponential backoff
                const delay = this.retryDelay * Math.pow(2, attempt - 1);
                await this._sleep(delay);
                
                return this._makeRequestWithRetry(url, config, controller, attempt + 1);
            }

            throw error;
        }
    }

    /**
     * Execute the actual HTTP request
     */
    async _executeRequest(url, config, controller) {
        const timeoutId = setTimeout(() => controller.abort(), config.timeout);

        try {
            // Apply request interceptors
            const finalConfig = await this._applyRequestInterceptors(config);

            const response = await fetch(url, {
                ...finalConfig,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new APIError(`HTTP ${response.status}: ${response.statusText}`, response.status, url);
            }

            const data = await response.json();
            
            // Apply response interceptors
            return await this._applyResponseInterceptors(data);

        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new APIError('Request timeout', 408, url);
            }
            
            throw error;
        }
    }

    /**
     * Convenience methods for different HTTP verbs
     */
    async get(url, params = {}, options = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${url}?${queryString}` : url;
        
        return this.request(fullUrl, {
            method: 'GET',
            ...options
        });
    }

    async post(url, data, options = {}) {
        return this.request(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        });
    }

    async put(url, data, options = {}) {
        return this.request(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        });
    }

    async delete(url, options = {}) {
        return this.request(url, {
            method: 'DELETE',
            ...options
        });
    }

    /**
     * Batch multiple requests
     */
    async batch(requests) {
        const promises = requests.map(req => 
            this.request(req.url, req.options).catch(error => ({ error, request: req }))
        );
        
        return Promise.all(promises);
    }

    /**
     * Health check endpoint
     */
    async healthCheck() {
        try {
            return await this.get('/api/health', {}, { timeout: 5000, retries: 1 });
        } catch (error) {
            return { status: 'error', message: error.message };
        }
    }

    /**
     * Add request interceptor
     */
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    }

    /**
     * Add response interceptor
     */
    addResponseInterceptor(interceptor) {
        this.responseInterceptors.push(interceptor);
    }

    /**
     * Cancel all active requests
     */
    cancelAllRequests() {
        for (const [key, controller] of this.activeRequests) {
            controller.abort();
        }
        this.activeRequests.clear();
    }

    /**
     * Utility methods
     */
    _shouldRetry(error) {
        // Retry on network errors and 5xx server errors
        return !error.status || error.status >= 500;
    }

    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async _applyRequestInterceptors(config) {
        let finalConfig = { ...config };
        
        for (const interceptor of this.requestInterceptors) {
            finalConfig = await interceptor(finalConfig);
        }
        
        return finalConfig;
    }

    async _applyResponseInterceptors(data) {
        let finalData = data;
        
        for (const interceptor of this.responseInterceptors) {
            finalData = await interceptor(finalData);
        }
        
        return finalData;
    }
}

/**
 * Custom API Error class
 */
class APIError extends Error {
    constructor(message, status, url) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.url = url;
    }
}

// Export for use
window.EnhancedAPIClient = EnhancedAPIClient;
window.APIError = APIError;