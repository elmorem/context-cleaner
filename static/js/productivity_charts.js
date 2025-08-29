/**
 * Interactive Productivity Charts
 * 
 * Provides sophisticated chart visualizations for productivity analysis
 * with drill-down capabilities, custom time ranges, and export functionality.
 */

class ProductivityCharts {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            theme: 'light',
            responsive: true,
            animations: true,
            showTooltips: true,
            allowDrillDown: true,
            exportFormats: ['png', 'svg', 'json'],
            ...options
        };
        
        this.charts = new Map();
        this.currentData = null;
        this.selectedTimeRange = {
            start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
            end: new Date()
        };
        
        this.initializeChartLibrary();
        this.setupEventHandlers();
    }

    /**
     * Initialize chart library (using Chart.js as base)
     */
    initializeChartLibrary() {
        if (typeof Chart === 'undefined') {
            console.error('Chart.js library not loaded');
            return;
        }
        
        // Configure Chart.js defaults
        Chart.defaults.responsive = true;
        Chart.defaults.maintainAspectRatio = false;
        Chart.defaults.plugins.legend.position = 'top';
        Chart.defaults.plugins.tooltip.mode = 'index';
        Chart.defaults.plugins.tooltip.intersect = false;
        
        // Custom color schemes
        this.colorSchemes = {
            productivity: [
                '#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B',
                '#FFC107', '#FF9800', '#FF5722', '#F44336'
            ],
            focus: [
                '#2196F3', '#03A9F4', '#00BCD4', '#009688',
                '#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B'
            ],
            health: [
                '#E91E63', '#9C27B0', '#673AB7', '#3F51B5',
                '#2196F3', '#03A9F4', '#00BCD4', '#009688'
            ]
        };
    }

    /**
     * Setup event handlers for interactivity
     */
    setupEventHandlers() {
        // Time range selector
        this.setupTimeRangeSelector();
        
        // Export functionality
        this.setupExportHandlers();
        
        // Chart interaction handlers
        this.setupChartInteractions();
        
        // Window resize handler
        window.addEventListener('resize', () => {
            this.resizeCharts();
        });
    }

    /**
     * Create productivity overview chart
     */
    createProductivityOverview(data, chartConfig = {}) {
        const config = {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [{
                    label: 'Productivity Score',
                    data: data.productivityScores || [],
                    borderColor: this.colorSchemes.productivity[0],
                    backgroundColor: this.colorSchemes.productivity[0] + '20',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Focus Level',
                    data: data.focusLevels || [],
                    borderColor: this.colorSchemes.focus[0],
                    backgroundColor: this.colorSchemes.focus[0] + '20',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4
                }]
            },
            options: {
                ...this.getBaseChartOptions(),
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Score (%)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time Period'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Productivity Overview',
                        font: { size: 16, weight: 'bold' }
                    },
                    zoom: {
                        zoom: {
                            wheel: { enabled: true },
                            pinch: { enabled: true },
                            mode: 'x'
                        },
                        pan: {
                            enabled: true,
                            mode: 'x'
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && this.options.allowDrillDown) {
                        this.handleDrillDown('productivity', elements[0].index);
                    }
                }
            }
        };

        return this.createChart('productivityOverview', config);
    }

    /**
     * Create activity distribution chart
     */
    createActivityDistribution(data, chartConfig = {}) {
        const config = {
            type: 'doughnut',
            data: {
                labels: data.activities || [],
                datasets: [{
                    data: data.timeSpent || [],
                    backgroundColor: this.colorSchemes.productivity,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                ...this.getBaseChartOptions(),
                plugins: {
                    title: {
                        display: true,
                        text: 'Activity Distribution',
                        font: { size: 16, weight: 'bold' }
                    },
                    legend: {
                        position: 'right'
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value}h (${percentage}%)`;
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && this.options.allowDrillDown) {
                        this.handleDrillDown('activity', elements[0].index);
                    }
                }
            }
        };

        return this.createChart('activityDistribution', config);
    }

    /**
     * Create performance trends chart
     */
    createPerformanceTrends(data, chartConfig = {}) {
        const config = {
            type: 'bar',
            data: {
                labels: data.periods || [],
                datasets: [{
                    label: 'Tasks Completed',
                    data: data.tasksCompleted || [],
                    backgroundColor: this.colorSchemes.productivity[1],
                    borderColor: this.colorSchemes.productivity[1],
                    borderWidth: 1,
                    yAxisID: 'y'
                }, {
                    label: 'Average Focus Time',
                    data: data.averageFocusTime || [],
                    type: 'line',
                    borderColor: this.colorSchemes.focus[2],
                    backgroundColor: this.colorSchemes.focus[2] + '20',
                    borderWidth: 2,
                    fill: false,
                    yAxisID: 'y1'
                }]
            },
            options: {
                ...this.getBaseChartOptions(),
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Tasks Completed'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Focus Time (hours)'
                        },
                        grid: {
                            drawOnChartArea: false,
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Performance Trends',
                        font: { size: 16, weight: 'bold' }
                    }
                }
            }
        };

        return this.createChart('performanceTrends', config);
    }

    /**
     * Create focus pattern heatmap
     */
    createFocusHeatmap(data, chartConfig = {}) {
        // Create custom heatmap using canvas
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        const heatmapContainer = document.createElement('div');
        heatmapContainer.className = 'heatmap-container';
        heatmapContainer.style.position = 'relative';
        heatmapContainer.style.height = '300px';
        
        this.renderHeatmap(ctx, data, heatmapContainer);
        
        return {
            element: heatmapContainer,
            update: (newData) => this.updateHeatmap(ctx, newData, heatmapContainer),
            destroy: () => heatmapContainer.remove()
        };
    }

    /**
     * Render custom heatmap visualization
     */
    renderHeatmap(ctx, data, container) {
        const canvas = ctx.canvas;
        const width = container.offsetWidth || 800;
        const height = container.offsetHeight || 300;
        
        canvas.width = width;
        canvas.height = height;
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        
        const cellWidth = width / 24; // 24 hours
        const cellHeight = height / 7; // 7 days
        
        // Draw heatmap cells
        for (let day = 0; day < 7; day++) {
            for (let hour = 0; hour < 24; hour++) {
                const value = (data.heatmapData && data.heatmapData[day] && data.heatmapData[day][hour]) || 0;
                const intensity = Math.min(value / 100, 1); // Normalize to 0-1
                
                // Color interpolation based on intensity
                const red = Math.round(255 * (1 - intensity));
                const green = Math.round(255 * intensity);
                const blue = 0;
                
                ctx.fillStyle = `rgb(${red}, ${green}, ${blue})`;
                ctx.fillRect(hour * cellWidth, day * cellHeight, cellWidth - 1, cellHeight - 1);
                
                // Add value text for high intensity cells
                if (intensity > 0.3) {
                    ctx.fillStyle = '#ffffff';
                    ctx.font = '10px Arial';
                    ctx.textAlign = 'center';
                    ctx.fillText(
                        Math.round(value),
                        hour * cellWidth + cellWidth / 2,
                        day * cellHeight + cellHeight / 2 + 3
                    );
                }
            }
        }
        
        // Add labels
        this.addHeatmapLabels(ctx, cellWidth, cellHeight, width, height);
        
        container.appendChild(canvas);
        
        // Add interactivity
        canvas.addEventListener('mousemove', (e) => {
            this.handleHeatmapHover(e, canvas, cellWidth, cellHeight, data);
        });
        
        canvas.addEventListener('click', (e) => {
            this.handleHeatmapClick(e, canvas, cellWidth, cellHeight, data);
        });
    }

    /**
     * Add labels to heatmap
     */
    addHeatmapLabels(ctx, cellWidth, cellHeight, width, height) {
        const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const hours = Array.from({length: 24}, (_, i) => `${i}:00`);
        
        ctx.fillStyle = '#333333';
        ctx.font = '12px Arial';
        ctx.textAlign = 'center';
        
        // Hour labels
        for (let i = 0; i < 24; i += 3) {
            ctx.fillText(hours[i], i * cellWidth + cellWidth / 2, height + 20);
        }
        
        // Day labels
        ctx.textAlign = 'right';
        for (let i = 0; i < 7; i++) {
            ctx.fillText(days[i], -10, i * cellHeight + cellHeight / 2 + 4);
        }
    }

    /**
     * Handle heatmap hover for tooltips
     */
    handleHeatmapHover(event, canvas, cellWidth, cellHeight, data) {
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        const hour = Math.floor(x / cellWidth);
        const day = Math.floor(y / cellHeight);
        
        if (hour >= 0 && hour < 24 && day >= 0 && day < 7) {
            const value = (data.heatmapData && data.heatmapData[day] && data.heatmapData[day][hour]) || 0;
            const dayName = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][day];
            
            this.showTooltip(event.clientX, event.clientY, {
                title: `${dayName} ${hour}:00`,
                content: `Focus Score: ${Math.round(value)}%`
            });
        }
    }

    /**
     * Handle drill-down functionality
     */
    handleDrillDown(chartType, index) {
        const drillDownData = {
            chartType,
            index,
            timestamp: Date.now()
        };
        
        // Dispatch custom event for drill-down
        const event = new CustomEvent('chartDrillDown', { detail: drillDownData });
        this.container.dispatchEvent(event);
        
        // Show detailed view
        this.showDrillDownView(chartType, index);
    }

    /**
     * Show detailed drill-down view
     */
    showDrillDownView(chartType, index) {
        // Create modal or slide-out panel for detailed view
        const modal = document.createElement('div');
        modal.className = 'chart-drill-down-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Detailed View: ${chartType}</h3>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="drillDownChart"></div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Add close functionality
        modal.querySelector('.close-modal').addEventListener('click', () => {
            modal.remove();
        });
        
        // Load detailed data and create drill-down chart
        this.loadDrillDownData(chartType, index).then(detailData => {
            this.createDrillDownChart('drillDownChart', detailData);
        });
    }

    /**
     * Load drill-down data (placeholder - would connect to API)
     */
    async loadDrillDownData(chartType, index) {
        // Simulate API call
        return new Promise(resolve => {
            setTimeout(() => {
                resolve({
                    chartType,
                    index,
                    detailedData: this.generateMockDetailData(chartType, index)
                });
            }, 500);
        });
    }

    /**
     * Generate mock detail data for drill-down
     */
    generateMockDetailData(chartType, index) {
        const baseData = {
            labels: [],
            datasets: []
        };
        
        switch (chartType) {
            case 'productivity':
                return {
                    ...baseData,
                    labels: ['Hour 1', 'Hour 2', 'Hour 3', 'Hour 4', 'Hour 5', 'Hour 6'],
                    datasets: [{
                        label: 'Detailed Productivity',
                        data: [65, 75, 80, 85, 90, 85],
                        borderColor: this.colorSchemes.productivity[0],
                        backgroundColor: this.colorSchemes.productivity[0] + '20'
                    }]
                };
            case 'activity':
                return {
                    ...baseData,
                    labels: ['Subtask 1', 'Subtask 2', 'Subtask 3', 'Subtask 4'],
                    datasets: [{
                        label: 'Time Distribution',
                        data: [2.5, 1.8, 3.2, 1.5],
                        backgroundColor: this.colorSchemes.productivity.slice(0, 4)
                    }]
                };
            default:
                return baseData;
        }
    }

    /**
     * Create drill-down chart
     */
    createDrillDownChart(containerId, data) {
        const config = {
            type: 'line',
            data: data,
            options: {
                ...this.getBaseChartOptions(),
                plugins: {
                    title: {
                        display: true,
                        text: 'Detailed Analysis'
                    }
                }
            }
        };
        
        return this.createChart(containerId, config);
    }

    /**
     * Setup time range selector
     */
    setupTimeRangeSelector() {
        const selector = document.createElement('div');
        selector.className = 'time-range-selector';
        selector.innerHTML = `
            <div class="time-range-controls">
                <button class="time-btn active" data-range="7">7D</button>
                <button class="time-btn" data-range="30">30D</button>
                <button class="time-btn" data-range="90">90D</button>
                <button class="time-btn" data-range="365">1Y</button>
                <button class="time-btn" data-range="custom">Custom</button>
            </div>
            <div class="custom-range" style="display: none;">
                <input type="date" id="startDate" />
                <input type="date" id="endDate" />
                <button id="applyRange">Apply</button>
            </div>
        `;
        
        this.container.insertBefore(selector, this.container.firstChild);
        
        // Add event listeners
        selector.querySelectorAll('.time-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.handleTimeRangeChange(e.target.dataset.range);
                selector.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
            });
        });
        
        selector.querySelector('#applyRange').addEventListener('click', () => {
            const startDate = new Date(selector.querySelector('#startDate').value);
            const endDate = new Date(selector.querySelector('#endDate').value);
            this.setCustomTimeRange(startDate, endDate);
        });
    }

    /**
     * Handle time range changes
     */
    handleTimeRangeChange(range) {
        const now = new Date();
        let startDate;
        
        switch (range) {
            case '7':
                startDate = new Date(now - 7 * 24 * 60 * 60 * 1000);
                break;
            case '30':
                startDate = new Date(now - 30 * 24 * 60 * 60 * 1000);
                break;
            case '90':
                startDate = new Date(now - 90 * 24 * 60 * 60 * 1000);
                break;
            case '365':
                startDate = new Date(now - 365 * 24 * 60 * 60 * 1000);
                break;
            case 'custom':
                document.querySelector('.custom-range').style.display = 'block';
                return;
            default:
                startDate = new Date(now - 30 * 24 * 60 * 60 * 1000);
        }
        
        this.selectedTimeRange = { start: startDate, end: now };
        this.refreshCharts();
    }

    /**
     * Set custom time range
     */
    setCustomTimeRange(startDate, endDate) {
        if (startDate && endDate && startDate <= endDate) {
            this.selectedTimeRange = { start: startDate, end: endDate };
            this.refreshCharts();
            document.querySelector('.custom-range').style.display = 'none';
        }
    }

    /**
     * Setup export handlers
     */
    setupExportHandlers() {
        const exportBtn = document.createElement('button');
        exportBtn.className = 'export-charts-btn';
        exportBtn.textContent = 'Export Charts';
        exportBtn.addEventListener('click', () => this.showExportMenu());
        
        this.container.insertBefore(exportBtn, this.container.firstChild);
    }

    /**
     * Show export menu
     */
    showExportMenu() {
        const menu = document.createElement('div');
        menu.className = 'export-menu';
        menu.innerHTML = `
            <div class="export-options">
                <button data-format="png">Export as PNG</button>
                <button data-format="svg">Export as SVG</button>
                <button data-format="json">Export as JSON</button>
                <button data-format="csv">Export as CSV</button>
            </div>
        `;
        
        menu.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.exportCharts(e.target.dataset.format);
                menu.remove();
            });
        });
        
        document.body.appendChild(menu);
        
        // Remove menu on outside click
        setTimeout(() => {
            document.addEventListener('click', (e) => {
                if (!menu.contains(e.target)) {
                    menu.remove();
                }
            }, { once: true });
        }, 100);
    }

    /**
     * Export charts in specified format
     */
    exportCharts(format) {
        const timestamp = new Date().toISOString().split('T')[0];
        
        switch (format) {
            case 'png':
                this.exportAsPNG(`productivity_charts_${timestamp}.png`);
                break;
            case 'svg':
                this.exportAsSVG(`productivity_charts_${timestamp}.svg`);
                break;
            case 'json':
                this.exportAsJSON(`productivity_data_${timestamp}.json`);
                break;
            case 'csv':
                this.exportAsCSV(`productivity_data_${timestamp}.csv`);
                break;
        }
    }

    /**
     * Export as PNG
     */
    exportAsPNG(filename) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 1200;
        canvas.height = 800;
        
        // Render all charts to single canvas
        this.renderChartsToCanvas(ctx).then(() => {
            const link = document.createElement('a');
            link.download = filename;
            link.href = canvas.toDataURL();
            link.click();
        });
    }

    /**
     * Export as JSON
     */
    exportAsJSON(filename) {
        const exportData = {
            timeRange: this.selectedTimeRange,
            charts: Array.from(this.charts.keys()),
            data: this.currentData,
            exportTimestamp: new Date().toISOString()
        };
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const link = document.createElement('a');
        link.download = filename;
        link.href = URL.createObjectURL(blob);
        link.click();
    }

    /**
     * Get base chart options
     */
    getBaseChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: this.options.animations ? 750 : 0
            },
            plugins: {
                tooltip: {
                    enabled: this.options.showTooltips,
                    mode: 'index',
                    intersect: false
                }
            }
        };
    }

    /**
     * Create chart instance
     */
    createChart(id, config) {
        const existingChart = this.charts.get(id);
        if (existingChart) {
            existingChart.destroy();
        }
        
        const canvas = document.createElement('canvas');
        canvas.id = id;
        
        const chartContainer = document.createElement('div');
        chartContainer.className = 'chart-container';
        chartContainer.appendChild(canvas);
        
        this.container.appendChild(chartContainer);
        
        const chart = new Chart(canvas.getContext('2d'), config);
        this.charts.set(id, chart);
        
        return chart;
    }

    /**
     * Update chart data
     */
    updateChart(id, newData) {
        const chart = this.charts.get(id);
        if (chart) {
            chart.data = newData;
            chart.update();
        }
    }

    /**
     * Refresh all charts
     */
    refreshCharts() {
        // Would typically fetch new data based on selected time range
        this.loadProductivityData(this.selectedTimeRange).then(data => {
            this.currentData = data;
            this.updateAllCharts(data);
        });
    }

    /**
     * Load productivity data (placeholder - would connect to API)
     */
    async loadProductivityData(timeRange) {
        // Simulate API call
        return new Promise(resolve => {
            setTimeout(() => {
                resolve(this.generateMockProductivityData(timeRange));
            }, 500);
        });
    }

    /**
     * Generate mock productivity data
     */
    generateMockProductivityData(timeRange) {
        const days = Math.ceil((timeRange.end - timeRange.start) / (24 * 60 * 60 * 1000));
        
        return {
            labels: Array.from({length: days}, (_, i) => {
                const date = new Date(timeRange.start.getTime() + i * 24 * 60 * 60 * 1000);
                return date.toLocaleDateString();
            }),
            productivityScores: Array.from({length: days}, () => Math.floor(Math.random() * 40) + 60),
            focusLevels: Array.from({length: days}, () => Math.floor(Math.random() * 50) + 50),
            activities: ['Coding', 'Meetings', 'Research', 'Documentation', 'Communication'],
            timeSpent: [6.5, 2.3, 1.8, 1.2, 0.7],
            tasksCompleted: Array.from({length: days}, () => Math.floor(Math.random() * 10) + 5),
            averageFocusTime: Array.from({length: days}, () => Math.random() * 3 + 2),
            heatmapData: Array.from({length: 7}, () => 
                Array.from({length: 24}, () => Math.floor(Math.random() * 100))
            )
        };
    }

    /**
     * Update all charts with new data
     */
    updateAllCharts(data) {
        this.charts.forEach((chart, id) => {
            switch (id) {
                case 'productivityOverview':
                    this.updateProductivityOverview(chart, data);
                    break;
                case 'activityDistribution':
                    this.updateActivityDistribution(chart, data);
                    break;
                case 'performanceTrends':
                    this.updatePerformanceTrends(chart, data);
                    break;
            }
        });
    }

    /**
     * Update productivity overview chart
     */
    updateProductivityOverview(chart, data) {
        chart.data.labels = data.labels;
        chart.data.datasets[0].data = data.productivityScores;
        chart.data.datasets[1].data = data.focusLevels;
        chart.update();
    }

    /**
     * Update activity distribution chart
     */
    updateActivityDistribution(chart, data) {
        chart.data.labels = data.activities;
        chart.data.datasets[0].data = data.timeSpent;
        chart.update();
    }

    /**
     * Update performance trends chart
     */
    updatePerformanceTrends(chart, data) {
        chart.data.labels = data.labels;
        chart.data.datasets[0].data = data.tasksCompleted;
        chart.data.datasets[1].data = data.averageFocusTime;
        chart.update();
    }

    /**
     * Show tooltip
     */
    showTooltip(x, y, content) {
        let tooltip = document.getElementById('chart-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'chart-tooltip';
            tooltip.className = 'chart-tooltip';
            document.body.appendChild(tooltip);
        }
        
        tooltip.innerHTML = `
            <div class="tooltip-title">${content.title}</div>
            <div class="tooltip-content">${content.content}</div>
        `;
        
        tooltip.style.left = x + 10 + 'px';
        tooltip.style.top = y - 10 + 'px';
        tooltip.style.display = 'block';
        
        // Hide after delay
        setTimeout(() => {
            if (tooltip) tooltip.style.display = 'none';
        }, 3000);
    }

    /**
     * Resize charts on window resize
     */
    resizeCharts() {
        this.charts.forEach(chart => {
            chart.resize();
        });
    }

    /**
     * Destroy all charts and cleanup
     */
    destroy() {
        this.charts.forEach(chart => {
            chart.destroy();
        });
        this.charts.clear();
        
        // Remove event listeners
        window.removeEventListener('resize', this.resizeCharts);
        
        // Clear container
        this.container.innerHTML = '';
    }

    /**
     * Initialize default dashboard
     */
    initializeDefaultDashboard(data = null) {
        if (!data) {
            this.loadProductivityData(this.selectedTimeRange).then(loadedData => {
                this.currentData = loadedData;
                this.createDefaultCharts(loadedData);
            });
        } else {
            this.currentData = data;
            this.createDefaultCharts(data);
        }
    }

    /**
     * Create default set of charts
     */
    createDefaultCharts(data) {
        // Create layout containers
        const mainRow = document.createElement('div');
        mainRow.className = 'charts-main-row';
        
        const secondRow = document.createElement('div');
        secondRow.className = 'charts-second-row';
        
        this.container.appendChild(mainRow);
        this.container.appendChild(secondRow);
        
        // Create overview chart (takes full width)
        const overviewContainer = document.createElement('div');
        overviewContainer.className = 'chart-full-width';
        overviewContainer.id = 'overview-container';
        mainRow.appendChild(overviewContainer);
        
        // Create side-by-side charts
        const leftChart = document.createElement('div');
        leftChart.className = 'chart-half-width';
        leftChart.id = 'activity-container';
        
        const rightChart = document.createElement('div');
        rightChart.className = 'chart-half-width';
        rightChart.id = 'trends-container';
        
        secondRow.appendChild(leftChart);
        secondRow.appendChild(rightChart);
        
        // Initialize charts
        this.createProductivityOverview(data);
        this.createActivityDistribution(data);
        this.createPerformanceTrends(data);
        
        // Create heatmap in separate section
        const heatmapSection = document.createElement('div');
        heatmapSection.className = 'heatmap-section';
        heatmapSection.innerHTML = '<h3>Focus Patterns</h3>';
        this.container.appendChild(heatmapSection);
        
        const heatmap = this.createFocusHeatmap(data);
        heatmapSection.appendChild(heatmap.element);
    }
}

// CSS styles (to be included separately or injected)
const chartStyles = `
.chart-container {
    position: relative;
    height: 400px;
    margin: 20px 0;
    padding: 15px;
    background: #ffffff;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.charts-main-row, .charts-second-row {
    display: flex;
    gap: 20px;
    margin: 20px 0;
}

.chart-full-width {
    flex: 1;
    height: 400px;
}

.chart-half-width {
    flex: 1;
    height: 350px;
}

.time-range-selector {
    margin-bottom: 20px;
    padding: 15px;
    background: #f8f9fa;
    border-radius: 8px;
}

.time-range-controls {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}

.time-btn {
    padding: 8px 16px;
    border: 1px solid #dee2e6;
    background: #ffffff;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
}

.time-btn:hover {
    background: #e9ecef;
}

.time-btn.active {
    background: #007bff;
    color: #ffffff;
    border-color: #007bff;
}

.export-charts-btn {
    padding: 10px 20px;
    background: #28a745;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    margin-bottom: 20px;
}

.export-menu {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: #ffffff;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 1000;
}

.export-options {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.export-options button {
    padding: 10px 15px;
    border: 1px solid #dee2e6;
    background: #ffffff;
    border-radius: 4px;
    cursor: pointer;
}

.export-options button:hover {
    background: #f8f9fa;
}

.heatmap-container {
    background: #ffffff;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.heatmap-section h3 {
    margin: 0 0 15px 0;
    font-size: 18px;
    color: #333333;
}

.chart-tooltip {
    position: absolute;
    background: #333333;
    color: #ffffff;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 12px;
    pointer-events: none;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.tooltip-title {
    font-weight: bold;
    margin-bottom: 4px;
}

.chart-drill-down-modal {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
}

.modal-content {
    background: #ffffff;
    border-radius: 8px;
    width: 90%;
    max-width: 800px;
    max-height: 90vh;
    overflow: auto;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid #dee2e6;
}

.modal-header h3 {
    margin: 0;
    color: #333333;
}

.close-modal {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #666666;
}

.modal-body {
    padding: 20px;
    height: 400px;
}

@media (max-width: 768px) {
    .charts-main-row, .charts-second-row {
        flex-direction: column;
    }
    
    .time-range-controls {
        flex-wrap: wrap;
    }
    
    .export-menu {
        width: 90%;
        max-width: 300px;
    }
}
`;

// Auto-inject styles if not already present
if (!document.getElementById('productivity-charts-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'productivity-charts-styles';
    styleSheet.textContent = chartStyles;
    document.head.appendChild(styleSheet);
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProductivityCharts;
} else if (typeof window !== 'undefined') {
    window.ProductivityCharts = ProductivityCharts;
}