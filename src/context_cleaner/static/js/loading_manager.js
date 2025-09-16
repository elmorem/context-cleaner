/**
 * Centralized Loading State Manager
 * Prevents infinite loading states and provides user feedback
 */
class LoadingManager {
    constructor() {
        this.loadingStates = new Map();
        this.timeouts = new Map();
        this.maxLoadingTime = 30000; // 30 seconds max loading time
    }

    /**
     * Start loading state for an element
     */
    startLoading(elementId, options = {}) {
        const config = {
            message: 'Loading...',
            progressiveTimeout: 3000, // Show progressive feedback after 3s
            defaultTimeout: 15000,    // Show timeout warning after 15s
            showSpinner: true,
            ...options
        };

        const element = document.getElementById(elementId);
        if (!element) {
            console.warn(`Element ${elementId} not found for loading state`);
            return;
        }

        // Clear any existing timeouts for this element
        this._clearTimeouts(elementId);

        // Store original content
        if (!this.loadingStates.has(elementId)) {
            this.loadingStates.set(elementId, {
                originalContent: element.innerHTML,
                startTime: Date.now(),
                config
            });
        }

        // Set initial loading UI
        this._setLoadingUI(elementId, config.message, config.showSpinner);

        // Set progressive feedback timeout
        const progressiveTimeoutId = setTimeout(() => {
            this._showProgressiveFeedback(elementId);
        }, config.progressiveTimeout);

        // Set warning timeout
        const warningTimeoutId = setTimeout(() => {
            this._showTimeoutWarning(elementId);
        }, config.defaultTimeout);

        // Set maximum timeout
        const maxTimeoutId = setTimeout(() => {
            this._handleTimeout(elementId);
        }, this.maxLoadingTime);

        this.timeouts.set(elementId, {
            progressive: progressiveTimeoutId,
            warning: warningTimeoutId,
            max: maxTimeoutId
        });
    }

    /**
     * Complete loading state successfully
     */
    completeLoading(elementId, content = null) {
        const element = document.getElementById(elementId);
        if (!element) return;

        this._clearTimeouts(elementId);

        if (content) {
            element.innerHTML = content;
        } else if (this.loadingStates.has(elementId)) {
            // Restore original content if no new content provided
            const state = this.loadingStates.get(elementId);
            element.innerHTML = state.originalContent;
        }

        // Add success flash
        element.classList.add('loading-success');
        setTimeout(() => {
            element.classList.remove('loading-success');
        }, 500);

        this.loadingStates.delete(elementId);
    }

    /**
     * Fail loading state with error
     */
    failLoading(elementId, error, options = {}) {
        const config = {
            retryable: true,
            retryCallback: null,
            showDetails: false,
            ...options
        };

        const element = document.getElementById(elementId);
        if (!element) return;

        this._clearTimeouts(elementId);

        const errorMessage = this._getErrorMessage(error);
        this._setErrorUI(elementId, errorMessage, config);

        // Add error flash
        element.classList.add('loading-error');
        setTimeout(() => {
            element.classList.remove('loading-error');
        }, 500);

        this.loadingStates.delete(elementId);
    }

    /**
     * Set loading UI
     */
    _setLoadingUI(elementId, message, showSpinner) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const spinnerHTML = showSpinner ? `
            <div class="loading-spinner">
                <div class="spinner"></div>
            </div>
        ` : '';

        element.innerHTML = `
            <div class="loading-container" data-element-id="${elementId}">
                ${spinnerHTML}
                <div class="loading-message">${message}</div>
                <div class="loading-progress" style="display: none;">
                    <div class="progress-bar">
                        <div class="progress-fill"></div>
                    </div>
                </div>
            </div>
        `;

        element.classList.add('loading-state');
    }

    /**
     * Show progressive feedback for long-running operations
     */
    _showProgressiveFeedback(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const progressElement = element.querySelector('.loading-progress');
        const messageElement = element.querySelector('.loading-message');

        if (progressElement && messageElement) {
            progressElement.style.display = 'block';
            messageElement.textContent = 'Loading is taking longer than usual...';
            
            // Animate progress bar
            const progressFill = element.querySelector('.progress-fill');
            if (progressFill) {
                progressFill.style.animation = 'loading-progress 10s linear infinite';
            }
        }
    }

    /**
     * Show timeout warning
     */
    _showTimeoutWarning(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const messageElement = element.querySelector('.loading-message');
        if (messageElement) {
            messageElement.innerHTML = `
                <div class="timeout-warning">
                    ⚠️ This is taking longer than expected
                    <button onclick="window.loadingManager.retryLoading('${elementId}')" 
                            class="retry-button">Retry</button>
                </div>
            `;
        }
    }

    /**
     * Handle maximum timeout
     */
    _handleTimeout(elementId) {
        const error = new Error('Operation timed out');
        this.failLoading(elementId, error, {
            retryable: true,
            retryCallback: () => this.retryLoading(elementId)
        });
    }

    /**
     * Set error UI
     */
    _setErrorUI(elementId, errorMessage, config) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const retryButton = config.retryable ? `
            <button onclick="window.loadingManager.retryLoading('${elementId}')" 
                    class="retry-button">Retry</button>
        ` : '';

        const detailsButton = config.showDetails ? `
            <button onclick="window.loadingManager.toggleErrorDetails('${elementId}')" 
                    class="details-button">Details</button>
        ` : '';

        element.innerHTML = `
            <div class="error-container">
                <div class="error-icon">❌</div>
                <div class="error-message">${errorMessage}</div>
                <div class="error-actions">
                    ${retryButton}
                    ${detailsButton}
                </div>
                <div class="error-details" style="display: none;">
                    <pre>${JSON.stringify(config.error || {}, null, 2)}</pre>
                </div>
            </div>
        `;

        element.classList.remove('loading-state');
        element.classList.add('error-state');
    }

    /**
     * Retry loading operation
     */
    retryLoading(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        // Dispatch retry event
        const event = new CustomEvent('retryLoading', {
            detail: { elementId }
        });
        document.dispatchEvent(event);

        // Reset element state
        element.classList.remove('error-state');
        this.startLoading(elementId, { message: 'Retrying...' });
    }

    /**
     * Toggle error details
     */
    toggleErrorDetails(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const detailsElement = element.querySelector('.error-details');
        if (detailsElement) {
            const isVisible = detailsElement.style.display !== 'none';
            detailsElement.style.display = isVisible ? 'none' : 'block';
        }
    }

    /**
     * Check if element is currently loading
     */
    isLoading(elementId) {
        return this.loadingStates.has(elementId);
    }

    /**
     * Get loading duration for element
     */
    getLoadingDuration(elementId) {
        const state = this.loadingStates.get(elementId);
        return state ? Date.now() - state.startTime : 0;
    }

    /**
     * Clear all timeouts for element
     */
    _clearTimeouts(elementId) {
        const timeouts = this.timeouts.get(elementId);
        if (timeouts) {
            clearTimeout(timeouts.progressive);
            clearTimeout(timeouts.warning);
            clearTimeout(timeouts.max);
            this.timeouts.delete(elementId);
        }
    }

    /**
     * Extract user-friendly error message
     */
    _getErrorMessage(error) {
        if (typeof error === 'string') return error;
        if (error?.message) return error.message;
        if (error?.status) return `Server error (${error.status})`;
        return 'An unexpected error occurred';
    }

    /**
     * Clear all loading states
     */
    clearAll() {
        for (const elementId of this.loadingStates.keys()) {
            this._clearTimeouts(elementId);
        }
        this.loadingStates.clear();
        this.timeouts.clear();
    }
}

// Create global instance
window.loadingManager = new LoadingManager();

// Add CSS styles
const style = document.createElement('style');
style.textContent = `
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2rem;
        min-height: 100px;
    }

    .loading-spinner .spinner {
        width: 32px;
        height: 32px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid #3498db;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 1rem;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .loading-message {
        color: #666;
        font-size: 14px;
        text-align: center;
        margin-bottom: 1rem;
    }

    .loading-progress {
        width: 100%;
        max-width: 200px;
    }

    .progress-bar {
        width: 100%;
        height: 4px;
        background-color: #f0f0f0;
        border-radius: 2px;
        overflow: hidden;
    }

    .progress-fill {
        height: 100%;
        background-color: #3498db;
        width: 30%;
        border-radius: 2px;
    }

    @keyframes loading-progress {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(300%); }
    }

    .timeout-warning {
        color: #f39c12;
        text-align: center;
    }

    .error-container {
        text-align: center;
        padding: 2rem;
        color: #e74c3c;
    }

    .error-icon {
        font-size: 2rem;
        margin-bottom: 1rem;
    }

    .error-message {
        margin-bottom: 1rem;
        font-weight: 500;
    }

    .error-actions {
        margin-bottom: 1rem;
    }

    .retry-button, .details-button {
        background: #3498db;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        margin: 0 4px;
        font-size: 14px;
    }

    .retry-button:hover, .details-button:hover {
        background: #2980b9;
    }

    .error-details {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 1rem;
        margin-top: 1rem;
        text-align: left;
        font-size: 12px;
        max-height: 200px;
        overflow-y: auto;
    }

    .loading-success {
        animation: success-flash 0.5s ease-in-out;
    }

    .loading-error {
        animation: error-flash 0.5s ease-in-out;
    }

    @keyframes success-flash {
        0% { background-color: transparent; }
        50% { background-color: rgba(46, 204, 113, 0.2); }
        100% { background-color: transparent; }
    }

    @keyframes error-flash {
        0% { background-color: transparent; }
        50% { background-color: rgba(231, 76, 60, 0.2); }
        100% { background-color: transparent; }
    }
`;
document.head.appendChild(style);