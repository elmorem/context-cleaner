/**
 * Trend Visualizations for Productivity Analysis
 * 
 * Provides sophisticated trend visualization components with interactive features,
 * forecasting capabilities, and advanced statistical analysis.
 */

class TrendVisualizations {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            theme: 'light',
            showTrendLines: true,
            showConfidenceIntervals: true,
            enableForecasting: true,
            enableAnnotations: true,
            smoothingFactor: 0.3,
            forecastPeriods: 7,
            confidenceLevel: 95,
            animationDuration: 800,
            interactionMode: 'auto', // auto, manual, none
            ...options
        };
        
        this.charts = new Map();
        this.trendData = new Map();
        this.forecasts = new Map();
        this.annotations = [];
        this.selectedTimeRange = this.getDefaultTimeRange();
        
        this.statisticalMethods = this.initializeStatisticalMethods();
        this.setupContainer();
        this.setupEventHandlers();
    }

    /**
     * Initialize statistical methods for trend analysis
     */
    initializeStatisticalMethods() {
        return {
            movingAverage: this.calculateMovingAverage.bind(this),
            exponentialSmoothing: this.calculateExponentialSmoothing.bind(this),
            linearRegression: this.calculateLinearRegression.bind(this),
            polynomialRegression: this.calculatePolynomialRegression.bind(this),
            seasonalDecomposition: this.calculateSeasonalDecomposition.bind(this),
            confidenceIntervals: this.calculateConfidenceIntervals.bind(this)
        };
    }

    /**
     * Get default time range (last 30 days)
     */
    getDefaultTimeRange() {
        const end = new Date();
        const start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);
        return { start, end };
    }

    /**
     * Setup container structure
     */
    setupContainer() {
        this.container.innerHTML = '';
        this.container.className = 'trend-visualizations-container';
        
        // Create toolbar
        this.toolbar = document.createElement('div');
        this.toolbar.className = 'trend-toolbar';
        this.container.appendChild(this.toolbar);
        
        // Create main visualization area
        this.visualizationArea = document.createElement('div');
        this.visualizationArea.className = 'trend-visualization-area';
        this.container.appendChild(this.visualizationArea);
        
        // Create analysis panel
        this.analysisPanel = document.createElement('div');
        this.analysisPanel.className = 'trend-analysis-panel';
        this.container.appendChild(this.analysisPanel);
        
        this.setupToolbar();
        this.setupAnalysisPanel();
    }

    /**
     * Setup toolbar with controls
     */
    setupToolbar() {
        this.toolbar.innerHTML = `
            <div class="toolbar-section">
                <label for="timeRangeSelect">Time Range:</label>
                <select id="timeRangeSelect">
                    <option value="7">Last 7 Days</option>
                    <option value="30" selected>Last 30 Days</option>
                    <option value="90">Last 90 Days</option>
                    <option value="365">Last Year</option>
                    <option value="custom">Custom Range</option>
                </select>
            </div>
            
            <div class="toolbar-section">
                <label for="trendMethodSelect">Trend Method:</label>
                <select id="trendMethodSelect">
                    <option value="movingAverage" selected>Moving Average</option>
                    <option value="exponentialSmoothing">Exponential Smoothing</option>
                    <option value="linearRegression">Linear Regression</option>
                    <option value="polynomialRegression">Polynomial Regression</option>
                </select>
            </div>
            
            <div class="toolbar-section">
                <label for="smoothingRange">Smoothing:</label>
                <input type="range" id="smoothingRange" min="0.1" max="1.0" step="0.1" value="${this.options.smoothingFactor}" />
                <span id="smoothingValue">${this.options.smoothingFactor}</span>
            </div>
            
            <div class="toolbar-section">
                <button id="toggleForecastBtn" class="toggle-btn ${this.options.enableForecasting ? 'active' : ''}">
                    Forecast
                </button>
                <button id="toggleConfidenceBtn" class="toggle-btn ${this.options.showConfidenceIntervals ? 'active' : ''}">
                    Confidence
                </button>
                <button id="addAnnotationBtn">Add Note</button>
            </div>
            
            <div class="toolbar-section">
                <button id="exportTrendsBtn">Export</button>
                <button id="comparePeriodsBtn">Compare</button>
            </div>
        `;
        
        this.setupToolbarListeners();
    }

    /**
     * Setup toolbar event listeners
     */
    setupToolbarListeners() {
        // Time range selector
        const timeRangeSelect = this.toolbar.querySelector('#timeRangeSelect');
        timeRangeSelect.addEventListener('change', (e) => {
            this.handleTimeRangeChange(e.target.value);
        });
        
        // Trend method selector
        const trendMethodSelect = this.toolbar.querySelector('#trendMethodSelect');
        trendMethodSelect.addEventListener('change', (e) => {
            this.currentTrendMethod = e.target.value;
            this.recalculateTrends();
        });
        
        // Smoothing factor
        const smoothingRange = this.toolbar.querySelector('#smoothingRange');
        const smoothingValue = this.toolbar.querySelector('#smoothingValue');
        smoothingRange.addEventListener('input', (e) => {
            this.options.smoothingFactor = parseFloat(e.target.value);
            smoothingValue.textContent = e.target.value;
            this.recalculateTrends();
        });
        
        // Toggle buttons
        this.toolbar.querySelector('#toggleForecastBtn').addEventListener('click', (e) => {
            this.options.enableForecasting = !this.options.enableForecasting;
            e.target.classList.toggle('active', this.options.enableForecasting);
            this.refreshVisualizations();
        });
        
        this.toolbar.querySelector('#toggleConfidenceBtn').addEventListener('click', (e) => {
            this.options.showConfidenceIntervals = !this.options.showConfidenceIntervals;
            e.target.classList.toggle('active', this.options.showConfidenceIntervals);
            this.refreshVisualizations();
        });
        
        // Action buttons
        this.toolbar.querySelector('#addAnnotationBtn').addEventListener('click', () => {
            this.showAnnotationDialog();
        });
        
        this.toolbar.querySelector('#exportTrendsBtn').addEventListener('click', () => {
            this.showExportOptions();
        });
        
        this.toolbar.querySelector('#comparePeriodsBtn').addEventListener('click', () => {
            this.showComparisonDialog();
        });
    }

    /**
     * Setup analysis panel
     */
    setupAnalysisPanel() {
        this.analysisPanel.innerHTML = `
            <div class="analysis-header">
                <h3>Trend Analysis</h3>
                <button id="toggleAnalysisBtn" class="collapse-btn">−</button>
            </div>
            <div class="analysis-content">
                <div class="analysis-section">
                    <h4>Key Metrics</h4>
                    <div class="metrics-grid" id="keyMetrics">
                        <!-- Metrics will be populated dynamically -->
                    </div>
                </div>
                
                <div class="analysis-section">
                    <h4>Trend Insights</h4>
                    <div class="insights-list" id="trendInsights">
                        <!-- Insights will be populated dynamically -->
                    </div>
                </div>
                
                <div class="analysis-section">
                    <h4>Statistical Summary</h4>
                    <div class="statistics-table" id="statisticsSummary">
                        <!-- Statistics will be populated dynamically -->
                    </div>
                </div>
            </div>
        `;
        
        // Toggle analysis panel
        this.analysisPanel.querySelector('#toggleAnalysisBtn').addEventListener('click', (e) => {
            const content = this.analysisPanel.querySelector('.analysis-content');
            const isVisible = content.style.display !== 'none';
            content.style.display = isVisible ? 'none' : 'block';
            e.target.textContent = isVisible ? '+' : '−';
        });
    }

    /**
     * Setup event handlers
     */
    setupEventHandlers() {
        // Window resize
        window.addEventListener('resize', () => {
            this.handleResize();
        });
        
        // Custom events
        this.container.addEventListener('trendDataUpdate', (e) => {
            this.handleTrendDataUpdate(e.detail);
        });
        
        this.container.addEventListener('annotationAdded', (e) => {
            this.handleAnnotationAdded(e.detail);
        });
    }

    /**
     * Create productivity trend visualization
     */
    createProductivityTrend(data, options = {}) {
        const config = {
            id: 'productivityTrend',
            title: 'Productivity Trend Analysis',
            data: this.preprocessData(data.productivityData || this.generateMockProductivityData()),
            yAxisLabel: 'Productivity Score (%)',
            color: '#4CAF50',
            showDataPoints: true,
            enableZoom: true,
            ...options
        };
        
        return this.createTrendVisualization(config);
    }

    /**
     * Create focus time trend visualization
     */
    createFocusTimeTrend(data, options = {}) {
        const config = {
            id: 'focusTimeTrend',
            title: 'Focus Time Patterns',
            data: this.preprocessData(data.focusTimeData || this.generateMockFocusTimeData()),
            yAxisLabel: 'Focus Time (hours)',
            color: '#2196F3',
            showDataPoints: true,
            enableZoom: true,
            ...options
        };
        
        return this.createTrendVisualization(config);
    }

    /**
     * Create task completion trend
     */
    createTaskCompletionTrend(data, options = {}) {
        const config = {
            id: 'taskCompletionTrend',
            title: 'Task Completion Velocity',
            data: this.preprocessData(data.taskCompletionData || this.generateMockTaskCompletionData()),
            yAxisLabel: 'Tasks Completed',
            color: '#FF9800',
            showDataPoints: true,
            enableZoom: true,
            ...options
        };
        
        return this.createTrendVisualization(config);
    }

    /**
     * Create multi-metric trend comparison
     */
    createMultiMetricTrend(data, options = {}) {
        const config = {
            id: 'multiMetricTrend',
            title: 'Multi-Metric Trend Comparison',
            multiSeries: true,
            series: [
                {
                    name: 'Productivity',
                    data: this.preprocessData(data.productivityData || this.generateMockProductivityData()),
                    color: '#4CAF50',
                    yAxis: 'left'
                },
                {
                    name: 'Focus Time',
                    data: this.preprocessData(data.focusTimeData || this.generateMockFocusTimeData()),
                    color: '#2196F3',
                    yAxis: 'right',
                    transform: 'normalize' // Normalize to 0-100 scale for comparison
                },
                {
                    name: 'Tasks Completed',
                    data: this.preprocessData(data.taskCompletionData || this.generateMockTaskCompletionData()),
                    color: '#FF9800',
                    yAxis: 'left',
                    transform: 'normalize'
                }
            ],
            showLegend: true,
            enableCrosshair: true,
            ...options
        };
        
        return this.createTrendVisualization(config);
    }

    /**
     * Create generic trend visualization
     */
    createTrendVisualization(config) {
        const container = document.createElement('div');
        container.className = 'trend-chart-container';
        container.id = `trend-${config.id}`;
        
        // Create chart title
        const title = document.createElement('h3');
        title.className = 'trend-chart-title';
        title.textContent = config.title;
        container.appendChild(title);
        
        // Create chart canvas
        const canvas = document.createElement('canvas');
        canvas.className = 'trend-chart-canvas';
        container.appendChild(canvas);
        
        // Create chart overlay for interactions
        const overlay = document.createElement('div');
        overlay.className = 'trend-chart-overlay';
        container.appendChild(overlay);
        
        this.visualizationArea.appendChild(container);
        
        // Initialize chart
        const chart = this.initializeTrendChart(canvas, config);
        this.charts.set(config.id, { chart, config, container });
        
        // Calculate and display trends
        this.calculateTrendAnalysis(config);
        
        // Update analysis panel
        this.updateAnalysisPanel();
        
        return chart;
    }

    /**
     * Initialize trend chart with Chart.js
     */
    initializeTrendChart(canvas, config) {
        const ctx = canvas.getContext('2d');
        
        const chartConfig = {
            type: 'line',
            data: this.buildChartData(config),
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: this.options.animationDuration
                },
                scales: this.buildScalesConfig(config),
                plugins: {
                    title: {
                        display: false // We handle title separately
                    },
                    legend: {
                        display: config.showLegend || false,
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: (tooltipItems) => {
                                return this.formatTooltipTitle(tooltipItems[0].label);
                            },
                            label: (context) => {
                                return this.formatTooltipLabel(context, config);
                            },
                            afterBody: (tooltipItems) => {
                                return this.getTooltipInsights(tooltipItems, config);
                            }
                        }
                    }
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                onHover: (event, elements) => {
                    this.handleChartHover(event, elements, config);
                },
                onClick: (event, elements) => {
                    this.handleChartClick(event, elements, config);
                }
            }
        };
        
        const chart = new Chart(ctx, chartConfig);
        
        // Add zoom/pan functionality if enabled
        if (config.enableZoom) {
            this.addZoomFunctionality(chart, config);
        }
        
        return chart;
    }

    /**
     * Build chart data structure
     */
    buildChartData(config) {
        const datasets = [];
        
        if (config.multiSeries) {
            // Multi-series chart
            config.series.forEach(series => {
                const processedData = this.applyDataTransform(series.data, series.transform);
                const trendData = this.calculateTrend(processedData, this.currentTrendMethod);
                
                // Original data series
                datasets.push({
                    label: series.name,
                    data: processedData.map(point => ({ x: point.date, y: point.value })),
                    borderColor: series.color,
                    backgroundColor: series.color + '20',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1,
                    pointRadius: config.showDataPoints ? 3 : 0,
                    pointHoverRadius: 5
                });
                
                // Trend line
                if (this.options.showTrendLines) {
                    datasets.push({
                        label: `${series.name} Trend`,
                        data: trendData.map(point => ({ x: point.date, y: point.value })),
                        borderColor: series.color,
                        backgroundColor: 'transparent',
                        borderWidth: 3,
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0,
                        pointRadius: 0,
                        pointHoverRadius: 0
                    });
                }
                
                // Confidence intervals
                if (this.options.showConfidenceIntervals) {
                    const confidence = this.calculateConfidenceIntervals(processedData, trendData);
                    datasets.push({
                        label: `${series.name} Confidence`,
                        data: confidence.upper.map(point => ({ x: point.date, y: point.value })),
                        borderColor: 'transparent',
                        backgroundColor: series.color + '10',
                        fill: '+1',
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 0
                    });
                    datasets.push({
                        label: `${series.name} Confidence Lower`,
                        data: confidence.lower.map(point => ({ x: point.date, y: point.value })),
                        borderColor: 'transparent',
                        backgroundColor: series.color + '10',
                        fill: false,
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 0
                    });
                }
                
                // Forecast data
                if (this.options.enableForecasting) {
                    const forecast = this.generateForecast(processedData, this.options.forecastPeriods);
                    datasets.push({
                        label: `${series.name} Forecast`,
                        data: forecast.map(point => ({ x: point.date, y: point.value })),
                        borderColor: series.color,
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [10, 5],
                        fill: false,
                        tension: 0.1,
                        pointRadius: 0,
                        pointHoverRadius: 0
                    });
                }
            });
        } else {
            // Single series chart
            const processedData = this.applyDataTransform(config.data);
            const trendData = this.calculateTrend(processedData, this.currentTrendMethod);
            
            // Original data
            datasets.push({
                label: 'Data',
                data: processedData.map(point => ({ x: point.date, y: point.value })),
                borderColor: config.color,
                backgroundColor: config.color + '20',
                borderWidth: 2,
                fill: false,
                tension: 0.1,
                pointRadius: config.showDataPoints ? 3 : 0,
                pointHoverRadius: 5
            });
            
            // Trend line
            if (this.options.showTrendLines) {
                datasets.push({
                    label: 'Trend',
                    data: trendData.map(point => ({ x: point.date, y: point.value })),
                    borderColor: config.color,
                    backgroundColor: 'transparent',
                    borderWidth: 3,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0,
                    pointRadius: 0,
                    pointHoverRadius: 0
                });
            }
            
            // Confidence intervals
            if (this.options.showConfidenceIntervals) {
                const confidence = this.calculateConfidenceIntervals(processedData, trendData);
                datasets.push({
                    label: 'Upper Confidence',
                    data: confidence.upper.map(point => ({ x: point.date, y: point.value })),
                    borderColor: 'transparent',
                    backgroundColor: config.color + '15',
                    fill: '+1',
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 0
                });
                datasets.push({
                    label: 'Lower Confidence',
                    data: confidence.lower.map(point => ({ x: point.date, y: point.value })),
                    borderColor: 'transparent',
                    backgroundColor: config.color + '15',
                    fill: false,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 0
                });
            }
            
            // Forecast
            if (this.options.enableForecasting) {
                const forecast = this.generateForecast(processedData, this.options.forecastPeriods);
                datasets.push({
                    label: 'Forecast',
                    data: forecast.map(point => ({ x: point.date, y: point.value })),
                    borderColor: config.color,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [10, 5],
                    fill: false,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 0
                });
            }
        }
        
        return { datasets };
    }

    /**
     * Build scales configuration
     */
    buildScalesConfig(config) {
        const scales = {
            x: {
                type: 'time',
                time: {
                    displayFormats: {
                        day: 'MMM dd',
                        week: 'MMM dd',
                        month: 'MMM yyyy'
                    }
                },
                title: {
                    display: true,
                    text: 'Date'
                }
            }
        };
        
        if (config.multiSeries) {
            // Dual y-axes for multi-series
            scales.y = {
                type: 'linear',
                display: true,
                position: 'left',
                title: {
                    display: true,
                    text: 'Primary Metrics'
                }
            };
            scales.y1 = {
                type: 'linear',
                display: true,
                position: 'right',
                title: {
                    display: true,
                    text: 'Secondary Metrics'
                },
                grid: {
                    drawOnChartArea: false
                }
            };
        } else {
            scales.y = {
                title: {
                    display: true,
                    text: config.yAxisLabel || 'Value'
                }
            };
        }
        
        return scales;
    }

    /**
     * Preprocess raw data into standard format
     */
    preprocessData(rawData) {
        return rawData.map(point => ({
            date: new Date(point.date),
            value: parseFloat(point.value),
            metadata: point.metadata || {}
        })).sort((a, b) => a.date - b.date);
    }

    /**
     * Apply data transformation
     */
    applyDataTransform(data, transform = null) {
        if (!transform) return data;
        
        switch (transform) {
            case 'normalize':
                return this.normalizeData(data);
            case 'percentage':
                return this.convertToPercentage(data);
            case 'logarithmic':
                return this.applyLogarithmicTransform(data);
            default:
                return data;
        }
    }

    /**
     * Normalize data to 0-100 scale
     */
    normalizeData(data) {
        const values = data.map(d => d.value);
        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min;
        
        return data.map(point => ({
            ...point,
            value: range === 0 ? 50 : ((point.value - min) / range) * 100
        }));
    }

    /**
     * Calculate moving average trend
     */
    calculateMovingAverage(data, windowSize = 7) {
        const result = [];
        
        for (let i = 0; i < data.length; i++) {
            const start = Math.max(0, i - Math.floor(windowSize / 2));
            const end = Math.min(data.length, start + windowSize);
            const window = data.slice(start, end);
            const average = window.reduce((sum, point) => sum + point.value, 0) / window.length;
            
            result.push({
                date: data[i].date,
                value: average,
                confidence: this.calculateMovingAverageConfidence(window)
            });
        }
        
        return result;
    }

    /**
     * Calculate exponential smoothing trend
     */
    calculateExponentialSmoothing(data, alpha = null) {
        if (alpha === null) alpha = this.options.smoothingFactor;
        
        const result = [];
        let smoothedValue = data[0].value;
        
        for (let i = 0; i < data.length; i++) {
            if (i > 0) {
                smoothedValue = alpha * data[i].value + (1 - alpha) * smoothedValue;
            }
            
            result.push({
                date: data[i].date,
                value: smoothedValue,
                confidence: this.calculateSmoothingConfidence(data, i, alpha)
            });
        }
        
        return result;
    }

    /**
     * Calculate linear regression trend
     */
    calculateLinearRegression(data) {
        const n = data.length;
        const x = data.map((_, i) => i);
        const y = data.map(point => point.value);
        
        const sumX = x.reduce((a, b) => a + b, 0);
        const sumY = y.reduce((a, b) => a + b, 0);
        const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
        const sumXX = x.reduce((sum, xi) => sum + xi * xi, 0);
        
        const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
        const intercept = (sumY - slope * sumX) / n;
        
        const result = data.map((point, i) => ({
            date: point.date,
            value: slope * i + intercept,
            confidence: this.calculateRegressionConfidence(data, slope, intercept, i)
        }));
        
        return result;
    }

    /**
     * Calculate polynomial regression trend (degree 2)
     */
    calculatePolynomialRegression(data, degree = 2) {
        const n = data.length;
        const x = data.map((_, i) => i);
        const y = data.map(point => point.value);
        
        // For simplicity, implementing degree 2 polynomial
        if (degree === 2) {
            const sumX = x.reduce((a, b) => a + b, 0);
            const sumX2 = x.reduce((sum, xi) => sum + xi * xi, 0);
            const sumX3 = x.reduce((sum, xi) => sum + xi * xi * xi, 0);
            const sumX4 = x.reduce((sum, xi) => sum + xi * xi * xi * xi, 0);
            const sumY = y.reduce((a, b) => a + b, 0);
            const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
            const sumX2Y = x.reduce((sum, xi, i) => sum + xi * xi * y[i], 0);
            
            // Solve system of equations using matrix operations (simplified)
            const A = [
                [n, sumX, sumX2],
                [sumX, sumX2, sumX3],
                [sumX2, sumX3, sumX4]
            ];
            const B = [sumY, sumXY, sumX2Y];
            
            const coeffs = this.solveLinearSystem(A, B);
            const [a0, a1, a2] = coeffs;
            
            return data.map((point, i) => ({
                date: point.date,
                value: a0 + a1 * i + a2 * i * i,
                confidence: this.calculatePolynomialConfidence(data, coeffs, i)
            }));
        }
        
        // Fallback to linear regression for other degrees
        return this.calculateLinearRegression(data);
    }

    /**
     * Solve linear system (simplified Gaussian elimination)
     */
    solveLinearSystem(A, B) {
        const n = A.length;
        
        // Forward elimination
        for (let i = 0; i < n; i++) {
            // Find pivot
            let maxRow = i;
            for (let k = i + 1; k < n; k++) {
                if (Math.abs(A[k][i]) > Math.abs(A[maxRow][i])) {
                    maxRow = k;
                }
            }
            
            // Swap rows
            [A[i], A[maxRow]] = [A[maxRow], A[i]];
            [B[i], B[maxRow]] = [B[maxRow], B[i]];
            
            // Make all rows below this one 0 in current column
            for (let k = i + 1; k < n; k++) {
                const factor = A[k][i] / A[i][i];
                for (let j = i; j < n; j++) {
                    A[k][j] -= factor * A[i][j];
                }
                B[k] -= factor * B[i];
            }
        }
        
        // Back substitution
        const x = new Array(n);
        for (let i = n - 1; i >= 0; i--) {
            x[i] = B[i];
            for (let j = i + 1; j < n; j++) {
                x[i] -= A[i][j] * x[j];
            }
            x[i] /= A[i][i];
        }
        
        return x;
    }

    /**
     * Calculate confidence intervals for trends
     */
    calculateConfidenceIntervals(originalData, trendData) {
        const residuals = originalData.map((point, i) => 
            Math.abs(point.value - trendData[i].value)
        );
        
        const standardError = Math.sqrt(
            residuals.reduce((sum, r) => sum + r * r, 0) / (residuals.length - 1)
        );
        
        const confidenceMultiplier = this.getConfidenceMultiplier(this.options.confidenceLevel);
        const margin = standardError * confidenceMultiplier;
        
        return {
            upper: trendData.map(point => ({
                date: point.date,
                value: point.value + margin
            })),
            lower: trendData.map(point => ({
                date: point.date,
                value: Math.max(0, point.value - margin)
            }))
        };
    }

    /**
     * Get confidence multiplier based on confidence level
     */
    getConfidenceMultiplier(confidenceLevel) {
        const multipliers = {
            90: 1.645,
            95: 1.960,
            99: 2.576
        };
        return multipliers[confidenceLevel] || 1.960;
    }

    /**
     * Generate forecast data
     */
    generateForecast(data, periods) {
        const trend = this.calculateTrend(data, this.currentTrendMethod || 'exponentialSmoothing');
        const lastPoint = data[data.length - 1];
        const forecast = [];
        
        // Calculate trend velocity
        const recentTrend = trend.slice(-Math.min(7, trend.length));
        const trendVelocity = recentTrend.length > 1 ? 
            (recentTrend[recentTrend.length - 1].value - recentTrend[0].value) / (recentTrend.length - 1) : 0;
        
        // Generate future points
        for (let i = 1; i <= periods; i++) {
            const forecastDate = new Date(lastPoint.date.getTime() + i * 24 * 60 * 60 * 1000);
            const forecastValue = trend[trend.length - 1].value + (trendVelocity * i);
            
            forecast.push({
                date: forecastDate,
                value: Math.max(0, forecastValue),
                confidence: Math.max(0.1, 1 - (i / periods) * 0.5) // Decreasing confidence
            });
        }
        
        return forecast;
    }

    /**
     * Calculate trend using specified method
     */
    calculateTrend(data, method) {
        switch (method) {
            case 'movingAverage':
                return this.statisticalMethods.movingAverage(data);
            case 'exponentialSmoothing':
                return this.statisticalMethods.exponentialSmoothing(data);
            case 'linearRegression':
                return this.statisticalMethods.linearRegression(data);
            case 'polynomialRegression':
                return this.statisticalMethods.polynomialRegression(data);
            default:
                return this.statisticalMethods.movingAverage(data);
        }
    }

    /**
     * Calculate trend analysis metrics
     */
    calculateTrendAnalysis(config) {
        const data = config.multiSeries ? config.series[0].data : config.data;
        const trend = this.calculateTrend(data, this.currentTrendMethod || 'movingAverage');
        
        const analysis = {
            direction: this.calculateTrendDirection(trend),
            strength: this.calculateTrendStrength(data, trend),
            volatility: this.calculateVolatility(data),
            correlation: this.calculateAutocorrelation(data),
            seasonality: this.detectSeasonality(data),
            outliers: this.detectOutliers(data),
            changePoints: this.detectChangePoints(data),
            forecast: this.options.enableForecasting ? this.generateForecast(data, this.options.forecastPeriods) : null
        };
        
        this.trendData.set(config.id, analysis);
        return analysis;
    }

    /**
     * Calculate trend direction (upward, downward, stable)
     */
    calculateTrendDirection(trendData) {
        if (trendData.length < 2) return 'insufficient_data';
        
        const start = trendData[0].value;
        const end = trendData[trendData.length - 1].value;
        const percentChange = ((end - start) / start) * 100;
        
        if (Math.abs(percentChange) < 5) {
            return { direction: 'stable', change: percentChange };
        } else if (percentChange > 0) {
            return { direction: 'upward', change: percentChange };
        } else {
            return { direction: 'downward', change: percentChange };
        }
    }

    /**
     * Calculate trend strength (R-squared)
     */
    calculateTrendStrength(originalData, trendData) {
        const actualValues = originalData.map(d => d.value);
        const trendValues = trendData.map(d => d.value);
        
        const actualMean = actualValues.reduce((a, b) => a + b, 0) / actualValues.length;
        
        const totalSumSquares = actualValues.reduce((sum, value) => 
            sum + Math.pow(value - actualMean, 2), 0);
        
        const residualSumSquares = actualValues.reduce((sum, value, i) => 
            sum + Math.pow(value - trendValues[i], 2), 0);
        
        const rSquared = 1 - (residualSumSquares / totalSumSquares);
        return Math.max(0, Math.min(1, rSquared));
    }

    /**
     * Calculate data volatility
     */
    calculateVolatility(data) {
        if (data.length < 2) return 0;
        
        const returns = [];
        for (let i = 1; i < data.length; i++) {
            const returnValue = (data[i].value - data[i-1].value) / data[i-1].value;
            returns.push(returnValue);
        }
        
        const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - meanReturn, 2), 0) / (returns.length - 1);
        
        return Math.sqrt(variance);
    }

    /**
     * Detect seasonal patterns
     */
    detectSeasonality(data) {
        if (data.length < 14) return { hasSeasonality: false };
        
        // Simple weekly seasonality detection
        const weeklyAvg = new Array(7).fill(0);
        const weeklyCount = new Array(7).fill(0);
        
        data.forEach(point => {
            const dayOfWeek = point.date.getDay();
            weeklyAvg[dayOfWeek] += point.value;
            weeklyCount[dayOfWeek]++;
        });
        
        for (let i = 0; i < 7; i++) {
            weeklyAvg[i] = weeklyCount[i] > 0 ? weeklyAvg[i] / weeklyCount[i] : 0;
        }
        
        const overallAvg = weeklyAvg.reduce((a, b) => a + b, 0) / 7;
        const weeklyVariation = weeklyAvg.map(avg => Math.abs(avg - overallAvg) / overallAvg);
        const maxVariation = Math.max(...weeklyVariation);
        
        return {
            hasSeasonality: maxVariation > 0.1,
            weeklyPattern: weeklyAvg,
            seasonalStrength: maxVariation,
            peakDay: weeklyAvg.indexOf(Math.max(...weeklyAvg)),
            lowDay: weeklyAvg.indexOf(Math.min(...weeklyAvg))
        };
    }

    /**
     * Detect outliers using IQR method
     */
    detectOutliers(data) {
        const values = data.map(d => d.value).sort((a, b) => a - b);
        const n = values.length;
        
        const q1Index = Math.floor(n * 0.25);
        const q3Index = Math.floor(n * 0.75);
        const q1 = values[q1Index];
        const q3 = values[q3Index];
        const iqr = q3 - q1;
        
        const lowerBound = q1 - 1.5 * iqr;
        const upperBound = q3 + 1.5 * iqr;
        
        const outliers = data.filter(point => 
            point.value < lowerBound || point.value > upperBound
        );
        
        return {
            outliers,
            count: outliers.length,
            percentage: (outliers.length / data.length) * 100,
            bounds: { lower: lowerBound, upper: upperBound }
        };
    }

    /**
     * Detect change points in the data
     */
    detectChangePoints(data) {
        if (data.length < 10) return [];
        
        const changePoints = [];
        const windowSize = Math.max(5, Math.floor(data.length / 10));
        
        for (let i = windowSize; i < data.length - windowSize; i++) {
            const before = data.slice(i - windowSize, i);
            const after = data.slice(i, i + windowSize);
            
            const beforeMean = before.reduce((sum, d) => sum + d.value, 0) / before.length;
            const afterMean = after.reduce((sum, d) => sum + d.value, 0) / after.length;
            
            const changePercentage = Math.abs((afterMean - beforeMean) / beforeMean) * 100;
            
            if (changePercentage > 20) { // 20% change threshold
                changePoints.push({
                    index: i,
                    date: data[i].date,
                    value: data[i].value,
                    changePercentage,
                    beforeMean,
                    afterMean
                });
            }
        }
        
        return changePoints;
    }

    /**
     * Update analysis panel with calculated insights
     */
    updateAnalysisPanel() {
        const keyMetrics = this.analysisPanel.querySelector('#keyMetrics');
        const trendInsights = this.analysisPanel.querySelector('#trendInsights');
        const statisticsSummary = this.analysisPanel.querySelector('#statisticsSummary');
        
        // Clear existing content
        keyMetrics.innerHTML = '';
        trendInsights.innerHTML = '';
        statisticsSummary.innerHTML = '';
        
        // Aggregate metrics from all trends
        let allAnalyses = Array.from(this.trendData.values());
        
        if (allAnalyses.length === 0) return;
        
        // Key metrics
        const avgVolatility = allAnalyses.reduce((sum, a) => sum + (a.volatility || 0), 0) / allAnalyses.length;
        const avgTrendStrength = allAnalyses.reduce((sum, a) => sum + (a.strength || 0), 0) / allAnalyses.length;
        const totalOutliers = allAnalyses.reduce((sum, a) => sum + (a.outliers?.count || 0), 0);
        
        keyMetrics.innerHTML = `
            <div class="metric-card">
                <div class="metric-value">${(avgTrendStrength * 100).toFixed(1)}%</div>
                <div class="metric-label">Trend Strength</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${(avgVolatility * 100).toFixed(1)}%</div>
                <div class="metric-label">Volatility</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${totalOutliers}</div>
                <div class="metric-label">Outliers</div>
            </div>
        `;
        
        // Trend insights
        const insights = [];
        allAnalyses.forEach((analysis, index) => {
            if (analysis.direction) {
                const direction = analysis.direction.direction;
                const change = Math.abs(analysis.direction.change).toFixed(1);
                insights.push(`Trend ${index + 1} is ${direction} with ${change}% change`);
            }
            
            if (analysis.seasonality?.hasSeasonality) {
                const peakDays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
                insights.push(`Weekly pattern detected with peak on ${peakDays[analysis.seasonality.peakDay]}`);
            }
            
            if (analysis.changePoints?.length > 0) {
                insights.push(`${analysis.changePoints.length} significant change points detected`);
            }
        });
        
        trendInsights.innerHTML = insights.map(insight => 
            `<div class="insight-item">• ${insight}</div>`
        ).join('');
        
        // Statistics summary
        statisticsSummary.innerHTML = `
            <table class="stats-table">
                <tr><td>Average Trend Strength</td><td>${(avgTrendStrength * 100).toFixed(2)}%</td></tr>
                <tr><td>Average Volatility</td><td>${(avgVolatility * 100).toFixed(2)}%</td></tr>
                <tr><td>Total Data Points</td><td>${allAnalyses.reduce((sum, a) => sum + (a.dataPoints || 0), 0)}</td></tr>
                <tr><td>Confidence Level</td><td>${this.options.confidenceLevel}%</td></tr>
                <tr><td>Forecast Periods</td><td>${this.options.forecastPeriods}</td></tr>
            </table>
        `;
    }

    /**
     * Handle time range changes
     */
    handleTimeRangeChange(range) {
        if (range === 'custom') {
            this.showCustomRangeDialog();
            return;
        }
        
        const days = parseInt(range);
        const end = new Date();
        const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
        
        this.selectedTimeRange = { start, end };
        this.refreshAllVisualizations();
    }

    /**
     * Show custom range selection dialog
     */
    showCustomRangeDialog() {
        const dialog = document.createElement('div');
        dialog.className = 'custom-range-dialog';
        dialog.innerHTML = `
            <div class="dialog-overlay" onclick="this.parentElement.remove()"></div>
            <div class="dialog-content">
                <h3>Select Custom Date Range</h3>
                <div class="date-inputs">
                    <label>Start Date: <input type="date" id="customStartDate" /></label>
                    <label>End Date: <input type="date" id="customEndDate" /></label>
                </div>
                <div class="dialog-actions">
                    <button id="applyCustomRange">Apply</button>
                    <button onclick="this.closest('.custom-range-dialog').remove()">Cancel</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        // Set default values
        dialog.querySelector('#customStartDate').value = this.selectedTimeRange.start.toISOString().split('T')[0];
        dialog.querySelector('#customEndDate').value = this.selectedTimeRange.end.toISOString().split('T')[0];
        
        dialog.querySelector('#applyCustomRange').addEventListener('click', () => {
            const start = new Date(dialog.querySelector('#customStartDate').value);
            const end = new Date(dialog.querySelector('#customEndDate').value);
            
            if (start <= end) {
                this.selectedTimeRange = { start, end };
                this.refreshAllVisualizations();
                dialog.remove();
            } else {
                alert('End date must be after start date');
            }
        });
    }

    /**
     * Recalculate trends with current method
     */
    recalculateTrends() {
        this.charts.forEach((chart, id) => {
            this.calculateTrendAnalysis(chart.config);
        });
        
        this.refreshAllVisualizations();
        this.updateAnalysisPanel();
    }

    /**
     * Refresh all visualizations
     */
    refreshAllVisualizations() {
        this.charts.forEach((chartData, id) => {
            const newData = this.buildChartData(chartData.config);
            chartData.chart.data = newData;
            chartData.chart.update();
        });
    }

    /**
     * Generate mock data for demonstrations
     */
    generateMockProductivityData() {
        const data = [];
        const baseDate = new Date(this.selectedTimeRange.start);
        const endDate = new Date(this.selectedTimeRange.end);
        
        while (baseDate <= endDate) {
            const dayOfWeek = baseDate.getDay();
            const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
            
            let baseValue = isWeekend ? 30 + Math.random() * 40 : 60 + Math.random() * 35;
            baseValue += Math.sin((baseDate.getTime() / (7 * 24 * 60 * 60 * 1000)) * Math.PI * 2) * 10;
            baseValue += (Math.random() - 0.5) * 20; // Random noise
            
            data.push({
                date: new Date(baseDate),
                value: Math.max(0, Math.min(100, baseValue))
            });
            
            baseDate.setDate(baseDate.getDate() + 1);
        }
        
        return data;
    }

    generateMockFocusTimeData() {
        const data = [];
        const baseDate = new Date(this.selectedTimeRange.start);
        const endDate = new Date(this.selectedTimeRange.end);
        
        while (baseDate <= endDate) {
            const dayOfWeek = baseDate.getDay();
            const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
            
            let baseValue = isWeekend ? 1 + Math.random() * 2 : 4 + Math.random() * 4;
            baseValue += (Math.random() - 0.5) * 1.5; // Random noise
            
            data.push({
                date: new Date(baseDate),
                value: Math.max(0, baseValue)
            });
            
            baseDate.setDate(baseDate.getDate() + 1);
        }
        
        return data;
    }

    generateMockTaskCompletionData() {
        const data = [];
        const baseDate = new Date(this.selectedTimeRange.start);
        const endDate = new Date(this.selectedTimeRange.end);
        
        while (baseDate <= endDate) {
            const dayOfWeek = baseDate.getDay();
            const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
            
            let baseValue = isWeekend ? Math.floor(Math.random() * 3) : 3 + Math.floor(Math.random() * 8);
            
            data.push({
                date: new Date(baseDate),
                value: baseValue
            });
            
            baseDate.setDate(baseDate.getDate() + 1);
        }
        
        return data;
    }

    /**
     * Handle window resize
     */
    handleResize() {
        this.charts.forEach(chartData => {
            chartData.chart.resize();
        });
    }

    /**
     * Show export options
     */
    showExportOptions() {
        const dialog = document.createElement('div');
        dialog.className = 'export-dialog';
        dialog.innerHTML = `
            <div class="dialog-overlay" onclick="this.parentElement.remove()"></div>
            <div class="dialog-content">
                <h3>Export Trend Analysis</h3>
                <div class="export-options">
                    <button class="export-btn" data-format="png">Export Charts as PNG</button>
                    <button class="export-btn" data-format="svg">Export Charts as SVG</button>
                    <button class="export-btn" data-format="csv">Export Data as CSV</button>
                    <button class="export-btn" data-format="json">Export Analysis as JSON</button>
                    <button class="export-btn" data-format="report">Generate PDF Report</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        dialog.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.exportData(e.target.dataset.format);
                dialog.remove();
            });
        });
    }

    /**
     * Export data in specified format
     */
    exportData(format) {
        const timestamp = new Date().toISOString().split('T')[0];
        const filename = `trend_analysis_${timestamp}`;
        
        switch (format) {
            case 'csv':
                this.exportAsCSV(filename + '.csv');
                break;
            case 'json':
                this.exportAsJSON(filename + '.json');
                break;
            case 'png':
                this.exportChartsAsPNG(filename + '.png');
                break;
            case 'svg':
                this.exportChartsAsSVG(filename + '.svg');
                break;
            case 'report':
                this.generatePDFReport(filename + '.pdf');
                break;
        }
    }

    /**
     * Export as CSV
     */
    exportAsCSV(filename) {
        let csvContent = 'Date,Chart,Value,Trend,Confidence\n';
        
        this.charts.forEach((chartData, chartId) => {
            const data = chartData.config.multiSeries ? 
                chartData.config.series[0].data : chartData.config.data;
            const trend = this.calculateTrend(data, this.currentTrendMethod);
            
            data.forEach((point, i) => {
                csvContent += `${point.date.toISOString().split('T')[0]},${chartId},${point.value},${trend[i]?.value || ''},${trend[i]?.confidence || ''}\n`;
            });
        });
        
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const link = document.createElement('a');
        link.download = filename;
        link.href = URL.createObjectURL(blob);
        link.click();
    }

    /**
     * Export as JSON
     */
    exportAsJSON(filename) {
        const exportData = {
            timeRange: this.selectedTimeRange,
            options: this.options,
            charts: {},
            analysis: {},
            exportDate: new Date().toISOString()
        };
        
        this.charts.forEach((chartData, chartId) => {
            exportData.charts[chartId] = {
                config: chartData.config,
                data: chartData.config.multiSeries ? chartData.config.series : chartData.config.data
            };
        });
        
        this.trendData.forEach((analysis, chartId) => {
            exportData.analysis[chartId] = analysis;
        });
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const link = document.createElement('a');
        link.download = filename;
        link.href = URL.createObjectURL(blob);
        link.click();
    }

    /**
     * Initialize default dashboard
     */
    initializeDefaultDashboard() {
        const mockData = {
            productivityData: this.generateMockProductivityData(),
            focusTimeData: this.generateMockFocusTimeData(),
            taskCompletionData: this.generateMockTaskCompletionData()
        };
        
        this.createProductivityTrend(mockData);
        this.createFocusTimeTrend(mockData);
        this.createMultiMetricTrend(mockData);
        
        this.currentTrendMethod = 'movingAverage';
    }

    /**
     * Destroy visualizations and cleanup
     */
    destroy() {
        this.charts.forEach(chartData => {
            chartData.chart.destroy();
        });
        
        this.charts.clear();
        this.trendData.clear();
        this.forecasts.clear();
        
        window.removeEventListener('resize', this.handleResize);
        this.container.innerHTML = '';
    }
}

// CSS Styles for Trend Visualizations
const trendStyles = `
.trend-visualizations-container {
    background: #ffffff;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    overflow: hidden;
}

.trend-toolbar {
    background: #f8f9fa;
    padding: 15px 20px;
    border-bottom: 1px solid #dee2e6;
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    align-items: center;
}

.toolbar-section {
    display: flex;
    align-items: center;
    gap: 8px;
}

.toolbar-section label {
    font-weight: 500;
    color: #495057;
    white-space: nowrap;
}

.toolbar-section select,
.toolbar-section input[type="range"] {
    padding: 4px 8px;
    border: 1px solid #ced4da;
    border-radius: 4px;
    font-size: 14px;
}

.toggle-btn {
    padding: 6px 12px;
    border: 1px solid #007bff;
    background: #ffffff;
    color: #007bff;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

.toggle-btn:hover {
    background: #f8f9fa;
}

.toggle-btn.active {
    background: #007bff;
    color: #ffffff;
}

.toolbar-section button {
    padding: 6px 12px;
    background: #28a745;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    transition: background-color 0.2s;
}

.toolbar-section button:hover {
    background: #218838;
}

.trend-visualization-area {
    padding: 20px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 30px;
}

.trend-chart-container {
    background: #ffffff;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    overflow: hidden;
    position: relative;
}

.trend-chart-title {
    margin: 0;
    padding: 15px 20px;
    background: #f8f9fa;
    border-bottom: 1px solid #dee2e6;
    font-size: 16px;
    font-weight: 600;
    color: #333333;
}

.trend-chart-canvas {
    display: block;
    height: 400px;
    padding: 20px;
}

.trend-chart-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    pointer-events: none;
    z-index: 1;
}

.trend-analysis-panel {
    background: #f8f9fa;
    border-top: 1px solid #dee2e6;
}

.analysis-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 20px;
    background: #e9ecef;
}

.analysis-header h3 {
    margin: 0;
    font-size: 16px;
    color: #333333;
}

.collapse-btn {
    background: none;
    border: none;
    font-size: 18px;
    cursor: pointer;
    color: #6c757d;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.analysis-content {
    padding: 20px;
}

.analysis-section {
    margin-bottom: 25px;
}

.analysis-section h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 600;
    color: #495057;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 15px;
}

.metric-card {
    background: #ffffff;
    padding: 15px;
    border-radius: 6px;
    text-align: center;
    border: 1px solid #dee2e6;
}

.metric-value {
    font-size: 24px;
    font-weight: 700;
    color: #007bff;
    margin-bottom: 4px;
}

.metric-label {
    font-size: 12px;
    color: #6c757d;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.insights-list {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 15px;
    max-height: 200px;
    overflow-y: auto;
}

.insight-item {
    margin-bottom: 8px;
    color: #495057;
    font-size: 14px;
    line-height: 1.4;
}

.insight-item:last-child {
    margin-bottom: 0;
}

.statistics-table {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    overflow: hidden;
}

.stats-table {
    width: 100%;
    border-collapse: collapse;
}

.stats-table td {
    padding: 10px 15px;
    border-bottom: 1px solid #f1f3f4;
    font-size: 14px;
}

.stats-table td:first-child {
    font-weight: 500;
    color: #495057;
}

.stats-table td:last-child {
    text-align: right;
    font-weight: 600;
    color: #007bff;
}

.stats-table tr:last-child td {
    border-bottom: none;
}

.custom-range-dialog,
.export-dialog {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 2000;
    display: flex;
    align-items: center;
    justify-content: center;
}

.dialog-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
}

.dialog-content {
    background: #ffffff;
    border-radius: 8px;
    padding: 20px;
    max-width: 90vw;
    max-height: 90vh;
    overflow: auto;
    position: relative;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    min-width: 300px;
}

.dialog-content h3 {
    margin: 0 0 20px 0;
    color: #333333;
}

.date-inputs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    margin-bottom: 20px;
}

.date-inputs label {
    display: flex;
    flex-direction: column;
    gap: 5px;
    font-weight: 500;
    color: #495057;
}

.date-inputs input {
    padding: 8px;
    border: 1px solid #ced4da;
    border-radius: 4px;
}

.dialog-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}

.dialog-actions button {
    padding: 8px 16px;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
}

.dialog-actions button:first-child {
    background: #007bff;
    color: #ffffff;
    border-color: #007bff;
}

.dialog-actions button:first-child:hover {
    background: #0056b3;
    border-color: #0056b3;
}

.dialog-actions button:not(:first-child) {
    background: #ffffff;
    color: #495057;
}

.dialog-actions button:not(:first-child):hover {
    background: #f8f9fa;
}

.export-options {
    display: grid;
    grid-template-columns: 1fr;
    gap: 10px;
    min-width: 250px;
}

.export-btn {
    padding: 12px 16px;
    background: #007bff;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: background-color 0.2s;
    text-align: left;
}

.export-btn:hover {
    background: #0056b3;
}

@media (max-width: 768px) {
    .trend-toolbar {
        flex-direction: column;
        align-items: stretch;
    }
    
    .toolbar-section {
        justify-content: space-between;
        flex-wrap: wrap;
    }
    
    .metrics-grid {
        grid-template-columns: 1fr 1fr;
    }
    
    .date-inputs {
        grid-template-columns: 1fr;
    }
    
    .dialog-actions {
        flex-direction: column;
    }
}

@media (max-width: 480px) {
    .metrics-grid {
        grid-template-columns: 1fr;
    }
}
`;

// Auto-inject styles
if (!document.getElementById('trend-visualizations-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'trend-visualizations-styles';
    styleSheet.textContent = trendStyles;
    document.head.appendChild(styleSheet);
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TrendVisualizations;
} else if (typeof window !== 'undefined') {
    window.TrendVisualizations = TrendVisualizations;
}