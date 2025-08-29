/**
 * Interactive Heatmaps for Productivity Analysis
 * 
 * Provides advanced heatmap visualizations with interactive features,
 * drill-down capabilities, and customizable display options.
 */

class InteractiveHeatmaps {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            colorScheme: 'default', // default, blue, green, red, custom
            showLabels: true,
            showTooltips: true,
            enableZoom: true,
            enableDrillDown: true,
            animationDuration: 500,
            cellSize: 'auto', // auto, small, medium, large, or number
            showColorScale: true,
            allowSelection: true,
            ...options
        };
        
        this.heatmaps = new Map();
        this.selectedCells = new Set();
        this.zoomLevel = 1;
        this.currentData = null;
        this.colorScales = this.initializeColorScales();
        
        this.setupContainer();
        this.setupEventHandlers();
    }

    /**
     * Initialize color scales for different visualization types
     */
    initializeColorScales() {
        return {
            default: {
                colors: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b'],
                domain: [0, 100]
            },
            productivity: {
                colors: ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#a50f15', '#67000d'],
                domain: [0, 100]
            },
            focus: {
                colors: ['#f7fcf0', '#e0f3db', '#ccebc5', '#a8ddb5', '#7bccc4', '#4eb3d3', '#2b8cbe', '#0868ac', '#084081'],
                domain: [0, 100]
            },
            temperature: {
                colors: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
                domain: [0, 100]
            },
            diverging: {
                colors: ['#d73027', '#f46d43', '#fdae61', '#fee090', '#ffffbf', '#e0f3f8', '#abd9e9', '#74add1', '#4575b4', '#313695'],
                domain: [-50, 50]
            }
        };
    }

    /**
     * Setup container structure
     */
    setupContainer() {
        this.container.innerHTML = '';
        this.container.className = 'interactive-heatmap-container';
        
        // Create control panel
        this.controlPanel = document.createElement('div');
        this.controlPanel.className = 'heatmap-controls';
        this.container.appendChild(this.controlPanel);
        
        // Create main heatmap area
        this.heatmapArea = document.createElement('div');
        this.heatmapArea.className = 'heatmap-area';
        this.container.appendChild(this.heatmapArea);
        
        // Create color scale legend
        if (this.options.showColorScale) {
            this.colorScaleLegend = document.createElement('div');
            this.colorScaleLegend.className = 'color-scale-legend';
            this.container.appendChild(this.colorScaleLegend);
        }
        
        this.setupControls();
    }

    /**
     * Setup control panel
     */
    setupControls() {
        this.controlPanel.innerHTML = `
            <div class="control-group">
                <label for="colorSchemeSelect">Color Scheme:</label>
                <select id="colorSchemeSelect">
                    <option value="default">Default</option>
                    <option value="productivity">Productivity</option>
                    <option value="focus">Focus</option>
                    <option value="temperature">Temperature</option>
                    <option value="diverging">Diverging</option>
                </select>
            </div>
            
            <div class="control-group">
                <label for="cellSizeRange">Cell Size:</label>
                <input type="range" id="cellSizeRange" min="10" max="50" value="25" />
                <span id="cellSizeValue">25px</span>
            </div>
            
            <div class="control-group">
                <label for="showLabelsCheck">
                    <input type="checkbox" id="showLabelsCheck" ${this.options.showLabels ? 'checked' : ''} />
                    Show Labels
                </label>
            </div>
            
            <div class="control-group">
                <label for="showTooltipsCheck">
                    <input type="checkbox" id="showTooltipsCheck" ${this.options.showTooltips ? 'checked' : ''} />
                    Show Tooltips
                </label>
            </div>
            
            <div class="control-group">
                <button id="resetZoomBtn">Reset Zoom</button>
                <button id="exportHeatmapBtn">Export</button>
            </div>
        `;
        
        // Add event listeners to controls
        this.setupControlListeners();
    }

    /**
     * Setup control event listeners
     */
    setupControlListeners() {
        const colorSchemeSelect = this.controlPanel.querySelector('#colorSchemeSelect');
        colorSchemeSelect.addEventListener('change', (e) => {
            this.options.colorScheme = e.target.value;
            this.updateColorScale();
            this.refreshAllHeatmaps();
        });
        
        const cellSizeRange = this.controlPanel.querySelector('#cellSizeRange');
        const cellSizeValue = this.controlPanel.querySelector('#cellSizeValue');
        cellSizeRange.addEventListener('input', (e) => {
            this.options.cellSize = parseInt(e.target.value);
            cellSizeValue.textContent = e.target.value + 'px';
            this.refreshAllHeatmaps();
        });
        
        const showLabelsCheck = this.controlPanel.querySelector('#showLabelsCheck');
        showLabelsCheck.addEventListener('change', (e) => {
            this.options.showLabels = e.target.checked;
            this.refreshAllHeatmaps();
        });
        
        const showTooltipsCheck = this.controlPanel.querySelector('#showTooltipsCheck');
        showTooltipsCheck.addEventListener('change', (e) => {
            this.options.showTooltips = e.target.checked;
        });
        
        const resetZoomBtn = this.controlPanel.querySelector('#resetZoomBtn');
        resetZoomBtn.addEventListener('click', () => {
            this.resetZoom();
        });
        
        const exportBtn = this.controlPanel.querySelector('#exportHeatmapBtn');
        exportBtn.addEventListener('click', () => {
            this.showExportOptions();
        });
    }

    /**
     * Setup event handlers
     */
    setupEventHandlers() {
        // Window resize handler
        window.addEventListener('resize', () => {
            this.handleResize();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (this.container.contains(e.target) || e.target === document.body) {
                this.handleKeyboardShortcuts(e);
            }
        });
    }

    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(event) {
        if (event.ctrlKey || event.metaKey) {
            switch (event.key) {
                case '=':
                case '+':
                    event.preventDefault();
                    this.zoomIn();
                    break;
                case '-':
                    event.preventDefault();
                    this.zoomOut();
                    break;
                case '0':
                    event.preventDefault();
                    this.resetZoom();
                    break;
                case 's':
                    event.preventDefault();
                    this.showExportOptions();
                    break;
            }
        }
        
        // Escape to clear selection
        if (event.key === 'Escape') {
            this.clearSelection();
        }
    }

    /**
     * Create weekly productivity heatmap
     */
    createWeeklyProductivityHeatmap(data, options = {}) {
        const config = {
            id: 'weeklyProductivity',
            title: 'Weekly Productivity Patterns',
            data: data.weeklyData || this.generateMockWeeklyData(),
            dimensions: {
                rows: 7, // Days of week
                cols: 24 // Hours of day
            },
            labels: {
                rows: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                cols: Array.from({length: 24}, (_, i) => `${i}:00`)
            },
            valueFormat: (value) => `${Math.round(value)}%`,
            ...options
        };
        
        return this.createHeatmap(config);
    }

    /**
     * Create monthly activity heatmap
     */
    createMonthlyActivityHeatmap(data, options = {}) {
        const config = {
            id: 'monthlyActivity',
            title: 'Monthly Activity Distribution',
            data: data.monthlyData || this.generateMockMonthlyData(),
            dimensions: {
                rows: 6, // Weeks (max 6 weeks in a month view)
                cols: 7  // Days of week
            },
            labels: {
                rows: Array.from({length: 6}, (_, i) => `Week ${i + 1}`),
                cols: ['S', 'M', 'T', 'W', 'T', 'F', 'S']
            },
            valueFormat: (value) => `${Math.round(value)} tasks`,
            cellShapes: 'rounded',
            ...options
        };
        
        return this.createHeatmap(config);
    }

    /**
     * Create skill development heatmap
     */
    createSkillDevelopmentHeatmap(data, options = {}) {
        const skills = data.skills || ['JavaScript', 'Python', 'React', 'Node.js', 'SQL', 'Docker', 'AWS', 'Git'];
        const timeframes = data.timeframes || ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'];
        
        const config = {
            id: 'skillDevelopment',
            title: 'Skill Development Progress',
            data: data.skillData || this.generateMockSkillData(skills.length, timeframes.length),
            dimensions: {
                rows: skills.length,
                cols: timeframes.length
            },
            labels: {
                rows: skills,
                cols: timeframes
            },
            valueFormat: (value) => `${Math.round(value)}h`,
            colorScheme: 'focus',
            ...options
        };
        
        return this.createHeatmap(config);
    }

    /**
     * Create performance correlation heatmap
     */
    createPerformanceCorrelationHeatmap(data, options = {}) {
        const metrics = data.metrics || [
            'Productivity', 'Focus Time', 'Tasks Completed', 'Code Quality', 
            'Collaboration', 'Learning', 'Innovation', 'Efficiency'
        ];
        
        const config = {
            id: 'performanceCorrelation',
            title: 'Performance Metrics Correlation',
            data: data.correlationMatrix || this.generateMockCorrelationData(metrics.length),
            dimensions: {
                rows: metrics.length,
                cols: metrics.length
            },
            labels: {
                rows: metrics,
                cols: metrics
            },
            valueFormat: (value) => `${(value / 100).toFixed(2)}`,
            colorScheme: 'diverging',
            symmetric: true,
            showDiagonal: false,
            ...options
        };
        
        return this.createHeatmap(config);
    }

    /**
     * Create generic heatmap
     */
    createHeatmap(config) {
        const heatmapContainer = document.createElement('div');
        heatmapContainer.className = 'heatmap-instance';
        heatmapContainer.id = `heatmap-${config.id}`;
        
        // Create title
        const title = document.createElement('h3');
        title.textContent = config.title;
        title.className = 'heatmap-title';
        heatmapContainer.appendChild(title);
        
        // Create SVG container
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.className = 'heatmap-svg';
        heatmapContainer.appendChild(svg);
        
        this.heatmapArea.appendChild(heatmapContainer);
        
        // Render heatmap
        const heatmapInstance = this.renderHeatmap(svg, config);
        this.heatmaps.set(config.id, { element: heatmapContainer, config, instance: heatmapInstance });
        
        // Update color scale legend
        this.updateColorScaleLegend(config);
        
        return heatmapInstance;
    }

    /**
     * Render heatmap to SVG
     */
    renderHeatmap(svg, config) {
        const { dimensions, data, labels } = config;
        const cellSize = this.calculateCellSize(dimensions);
        const margin = { top: 40, right: 40, bottom: 40, left: 100 };
        
        const width = dimensions.cols * cellSize + margin.left + margin.right;
        const height = dimensions.rows * cellSize + margin.top + margin.bottom;
        
        svg.setAttribute('width', width);
        svg.setAttribute('height', height);
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
        
        // Clear existing content
        svg.innerHTML = '';
        
        // Create main group
        const mainGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        mainGroup.setAttribute('transform', `translate(${margin.left}, ${margin.top})`);
        svg.appendChild(mainGroup);
        
        // Get color scale
        const colorScale = this.getColorScale(config.colorScheme || this.options.colorScheme);
        
        // Create cells
        const cells = [];
        for (let row = 0; row < dimensions.rows; row++) {
            for (let col = 0; col < dimensions.cols; col++) {
                const value = data[row] && data[row][col] !== undefined ? data[row][col] : 0;
                const cell = this.createHeatmapCell(mainGroup, {
                    row,
                    col,
                    value,
                    x: col * cellSize,
                    y: row * cellSize,
                    width: cellSize - 1,
                    height: cellSize - 1,
                    color: this.getColorFromScale(value, colorScale),
                    config
                });
                cells.push(cell);
            }
        }
        
        // Add row labels
        if (this.options.showLabels && labels.rows) {
            this.addRowLabels(svg, labels.rows, cellSize, margin);
        }
        
        // Add column labels  
        if (this.options.showLabels && labels.cols) {
            this.addColumnLabels(svg, labels.cols, cellSize, margin, dimensions);
        }
        
        return {
            svg,
            cells,
            config,
            update: (newData) => this.updateHeatmapData(svg, config, newData),
            destroy: () => svg.remove()
        };
    }

    /**
     * Create individual heatmap cell
     */
    createHeatmapCell(parent, cellData) {
        const { x, y, width, height, color, value, row, col, config } = cellData;
        
        // Skip diagonal cells for symmetric matrices if specified
        if (config.symmetric && config.showDiagonal === false && row === col) {
            return null;
        }
        
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', width);
        rect.setAttribute('height', height);
        rect.setAttribute('fill', color);
        rect.setAttribute('stroke', '#ffffff');
        rect.setAttribute('stroke-width', '1');
        rect.setAttribute('data-row', row);
        rect.setAttribute('data-col', col);
        rect.setAttribute('data-value', value);
        rect.className.baseVal = 'heatmap-cell';
        
        // Add rounded corners if specified
        if (config.cellShapes === 'rounded') {
            rect.setAttribute('rx', '3');
            rect.setAttribute('ry', '3');
        }
        
        // Add interactivity
        this.addCellInteractivity(rect, cellData);
        
        // Add animation
        if (this.options.animationDuration > 0) {
            rect.style.opacity = '0';
            setTimeout(() => {
                rect.style.transition = `opacity ${this.options.animationDuration}ms ease-in-out`;
                rect.style.opacity = '1';
            }, (row * config.dimensions.cols + col) * 10);
        }
        
        parent.appendChild(rect);
        return rect;
    }

    /**
     * Add cell interactivity (hover, click, selection)
     */
    addCellInteractivity(rect, cellData) {
        const { value, row, col, config } = cellData;
        
        // Hover effects
        rect.addEventListener('mouseenter', (e) => {
            rect.setAttribute('stroke-width', '3');
            rect.setAttribute('stroke', '#333333');
            
            if (this.options.showTooltips) {
                this.showTooltip(e, {
                    title: this.getCellTitle(row, col, config),
                    value: config.valueFormat ? config.valueFormat(value) : value,
                    coordinates: `(${row}, ${col})`
                });
            }
        });
        
        rect.addEventListener('mouseleave', (e) => {
            if (!this.selectedCells.has(`${row}-${col}`)) {
                rect.setAttribute('stroke-width', '1');
                rect.setAttribute('stroke', '#ffffff');
            }
            this.hideTooltip();
        });
        
        // Click for selection
        if (this.options.allowSelection) {
            rect.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleCellSelection(rect, row, col);
            });
        }
        
        // Double-click for drill-down
        if (this.options.enableDrillDown) {
            rect.addEventListener('dblclick', (e) => {
                e.stopPropagation();
                this.handleCellDrillDown(row, col, value, config);
            });
        }
    }

    /**
     * Get cell title for tooltip
     */
    getCellTitle(row, col, config) {
        const rowLabel = (config.labels.rows && config.labels.rows[row]) || `Row ${row}`;
        const colLabel = (config.labels.cols && config.labels.cols[col]) || `Col ${col}`;
        return `${rowLabel} - ${colLabel}`;
    }

    /**
     * Toggle cell selection
     */
    toggleCellSelection(rect, row, col) {
        const cellKey = `${row}-${col}`;
        
        if (this.selectedCells.has(cellKey)) {
            this.selectedCells.delete(cellKey);
            rect.setAttribute('stroke-width', '1');
            rect.setAttribute('stroke', '#ffffff');
        } else {
            this.selectedCells.add(cellKey);
            rect.setAttribute('stroke-width', '3');
            rect.setAttribute('stroke', '#ff6b6b');
        }
        
        // Dispatch selection change event
        const event = new CustomEvent('heatmapSelectionChange', {
            detail: { selectedCells: Array.from(this.selectedCells) }
        });
        this.container.dispatchEvent(event);
    }

    /**
     * Clear all selections
     */
    clearSelection() {
        this.selectedCells.clear();
        this.container.querySelectorAll('.heatmap-cell').forEach(cell => {
            cell.setAttribute('stroke-width', '1');
            cell.setAttribute('stroke', '#ffffff');
        });
    }

    /**
     * Handle drill-down functionality
     */
    handleCellDrillDown(row, col, value, config) {
        const drillDownData = {
            heatmapId: config.id,
            row,
            col,
            value,
            rowLabel: (config.labels.rows && config.labels.rows[row]) || `Row ${row}`,
            colLabel: (config.labels.cols && config.labels.cols[col]) || `Col ${col}`
        };
        
        // Dispatch drill-down event
        const event = new CustomEvent('heatmapDrillDown', { detail: drillDownData });
        this.container.dispatchEvent(event);
        
        // Show drill-down modal
        this.showDrillDownModal(drillDownData);
    }

    /**
     * Show drill-down modal with detailed data
     */
    showDrillDownModal(drillDownData) {
        const modal = document.createElement('div');
        modal.className = 'heatmap-drill-down-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Detailed View: ${drillDownData.rowLabel} - ${drillDownData.colLabel}</h3>
                    <button class="close-btn" onclick="this.closest('.heatmap-drill-down-modal').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="drill-down-summary">
                        <div class="summary-card">
                            <h4>Value</h4>
                            <div class="value-display">${drillDownData.value}</div>
                        </div>
                        <div class="summary-card">
                            <h4>Position</h4>
                            <div class="position-display">Row ${drillDownData.row}, Col ${drillDownData.col}</div>
                        </div>
                    </div>
                    <div class="drill-down-chart">
                        <div id="drillDownChart"></div>
                    </div>
                    <div class="drill-down-actions">
                        <button class="export-detail-btn">Export Details</button>
                        <button class="compare-btn">Compare with Others</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Load and display detailed data
        this.loadDrillDownData(drillDownData).then(detailData => {
            this.renderDrillDownChart('drillDownChart', detailData);
        });
        
        // Add action handlers
        modal.querySelector('.export-detail-btn').addEventListener('click', () => {
            this.exportDrillDownData(drillDownData);
        });
        
        modal.querySelector('.compare-btn').addEventListener('click', () => {
            this.showComparisonView(drillDownData);
        });
    }

    /**
     * Add row labels to heatmap
     */
    addRowLabels(svg, labels, cellSize, margin) {
        const labelGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        labelGroup.className.baseVal = 'row-labels';
        
        labels.forEach((label, i) => {
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', margin.left - 10);
            text.setAttribute('y', margin.top + i * cellSize + cellSize / 2);
            text.setAttribute('text-anchor', 'end');
            text.setAttribute('dominant-baseline', 'middle');
            text.setAttribute('class', 'heatmap-label');
            text.textContent = label;
            labelGroup.appendChild(text);
        });
        
        svg.appendChild(labelGroup);
    }

    /**
     * Add column labels to heatmap
     */
    addColumnLabels(svg, labels, cellSize, margin, dimensions) {
        const labelGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        labelGroup.className.baseVal = 'col-labels';
        
        labels.forEach((label, i) => {
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', margin.left + i * cellSize + cellSize / 2);
            text.setAttribute('y', margin.top - 10);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('dominant-baseline', 'baseline');
            text.setAttribute('class', 'heatmap-label');
            
            // Rotate long labels
            if (label.length > 3) {
                text.setAttribute('transform', 
                    `rotate(-45, ${margin.left + i * cellSize + cellSize / 2}, ${margin.top - 10})`);
                text.setAttribute('text-anchor', 'end');
            }
            
            text.textContent = label;
            labelGroup.appendChild(text);
        });
        
        svg.appendChild(labelGroup);
    }

    /**
     * Calculate appropriate cell size
     */
    calculateCellSize(dimensions) {
        if (typeof this.options.cellSize === 'number') {
            return this.options.cellSize;
        }
        
        const containerWidth = this.heatmapArea.offsetWidth - 200; // Account for margins
        const containerHeight = this.heatmapArea.offsetHeight - 200;
        
        const maxCellWidth = containerWidth / dimensions.cols;
        const maxCellHeight = containerHeight / dimensions.rows;
        
        const optimalSize = Math.min(maxCellWidth, maxCellHeight, 50);
        return Math.max(optimalSize, 15); // Minimum 15px
    }

    /**
     * Get color scale configuration
     */
    getColorScale(schemeName) {
        return this.colorScales[schemeName] || this.colorScales.default;
    }

    /**
     * Get color from scale based on value
     */
    getColorFromScale(value, colorScale) {
        const { colors, domain } = colorScale;
        const normalizedValue = (value - domain[0]) / (domain[1] - domain[0]);
        const clampedValue = Math.max(0, Math.min(1, normalizedValue));
        
        const colorIndex = Math.floor(clampedValue * (colors.length - 1));
        const nextColorIndex = Math.min(colorIndex + 1, colors.length - 1);
        
        if (colorIndex === nextColorIndex) {
            return colors[colorIndex];
        }
        
        // Interpolate between colors
        const ratio = (clampedValue * (colors.length - 1)) - colorIndex;
        return this.interpolateColors(colors[colorIndex], colors[nextColorIndex], ratio);
    }

    /**
     * Interpolate between two hex colors
     */
    interpolateColors(color1, color2, ratio) {
        const hex1 = color1.replace('#', '');
        const hex2 = color2.replace('#', '');
        
        const r1 = parseInt(hex1.substr(0, 2), 16);
        const g1 = parseInt(hex1.substr(2, 2), 16);
        const b1 = parseInt(hex1.substr(4, 2), 16);
        
        const r2 = parseInt(hex2.substr(0, 2), 16);
        const g2 = parseInt(hex2.substr(2, 2), 16);
        const b2 = parseInt(hex2.substr(4, 2), 16);
        
        const r = Math.round(r1 + (r2 - r1) * ratio);
        const g = Math.round(g1 + (g2 - g1) * ratio);
        const b = Math.round(b1 + (b2 - b1) * ratio);
        
        return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    }

    /**
     * Update color scale legend
     */
    updateColorScaleLegend(config) {
        if (!this.colorScaleLegend) return;
        
        const colorScale = this.getColorScale(config.colorScheme || this.options.colorScheme);
        const { colors, domain } = colorScale;
        
        this.colorScaleLegend.innerHTML = '';
        
        const legend = document.createElement('div');
        legend.className = 'color-scale';
        
        const title = document.createElement('div');
        title.className = 'legend-title';
        title.textContent = 'Value Scale';
        legend.appendChild(title);
        
        const scaleContainer = document.createElement('div');
        scaleContainer.className = 'scale-container';
        
        // Create gradient bar
        const gradientBar = document.createElement('div');
        gradientBar.className = 'gradient-bar';
        gradientBar.style.background = `linear-gradient(to right, ${colors.join(', ')})`;
        scaleContainer.appendChild(gradientBar);
        
        // Add scale labels
        const labelsContainer = document.createElement('div');
        labelsContainer.className = 'scale-labels';
        
        const minLabel = document.createElement('span');
        minLabel.textContent = domain[0];
        labelsContainer.appendChild(minLabel);
        
        const maxLabel = document.createElement('span');
        maxLabel.textContent = domain[1];
        labelsContainer.appendChild(maxLabel);
        
        scaleContainer.appendChild(labelsContainer);
        legend.appendChild(scaleContainer);
        
        this.colorScaleLegend.appendChild(legend);
    }

    /**
     * Show tooltip
     */
    showTooltip(event, data) {
        let tooltip = document.getElementById('heatmap-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'heatmap-tooltip';
            tooltip.className = 'heatmap-tooltip';
            document.body.appendChild(tooltip);
        }
        
        tooltip.innerHTML = `
            <div class="tooltip-title">${data.title}</div>
            <div class="tooltip-value">Value: ${data.value}</div>
            <div class="tooltip-coords">Position: ${data.coordinates}</div>
        `;
        
        tooltip.style.left = (event.pageX + 10) + 'px';
        tooltip.style.top = (event.pageY - 10) + 'px';
        tooltip.style.display = 'block';
    }

    /**
     * Hide tooltip
     */
    hideTooltip() {
        const tooltip = document.getElementById('heatmap-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }

    /**
     * Update color scale
     */
    updateColorScale() {
        this.heatmaps.forEach((heatmap) => {
            this.refreshHeatmap(heatmap.config.id);
        });
    }

    /**
     * Refresh all heatmaps
     */
    refreshAllHeatmaps() {
        this.heatmaps.forEach((heatmap, id) => {
            this.refreshHeatmap(id);
        });
    }

    /**
     * Refresh specific heatmap
     */
    refreshHeatmap(heatmapId) {
        const heatmap = this.heatmaps.get(heatmapId);
        if (heatmap) {
            const svg = heatmap.element.querySelector('.heatmap-svg');
            this.renderHeatmap(svg, heatmap.config);
        }
    }

    /**
     * Zoom functionality
     */
    zoomIn() {
        this.zoomLevel = Math.min(this.zoomLevel * 1.2, 3);
        this.applyZoom();
    }

    zoomOut() {
        this.zoomLevel = Math.max(this.zoomLevel / 1.2, 0.5);
        this.applyZoom();
    }

    resetZoom() {
        this.zoomLevel = 1;
        this.applyZoom();
    }

    applyZoom() {
        this.heatmapArea.style.transform = `scale(${this.zoomLevel})`;
        this.heatmapArea.style.transformOrigin = 'top left';
    }

    /**
     * Handle window resize
     */
    handleResize() {
        // Recalculate cell sizes and refresh heatmaps
        setTimeout(() => {
            this.refreshAllHeatmaps();
        }, 100);
    }

    /**
     * Show export options
     */
    showExportOptions() {
        const modal = document.createElement('div');
        modal.className = 'export-options-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Export Heatmaps</h3>
                    <button class="close-btn" onclick="this.closest('.export-options-modal').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="export-format-options">
                        <button class="export-btn" data-format="svg">Export as SVG</button>
                        <button class="export-btn" data-format="png">Export as PNG</button>
                        <button class="export-btn" data-format="pdf">Export as PDF</button>
                        <button class="export-btn" data-format="json">Export Data as JSON</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        modal.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.exportHeatmaps(e.target.dataset.format);
                modal.remove();
            });
        });
    }

    /**
     * Export heatmaps in specified format
     */
    exportHeatmaps(format) {
        const timestamp = new Date().toISOString().split('T')[0];
        const filename = `heatmaps_${timestamp}`;
        
        switch (format) {
            case 'svg':
                this.exportAsSVG(filename + '.svg');
                break;
            case 'png':
                this.exportAsPNG(filename + '.png');
                break;
            case 'pdf':
                this.exportAsPDF(filename + '.pdf');
                break;
            case 'json':
                this.exportAsJSON(filename + '.json');
                break;
        }
    }

    /**
     * Export as SVG
     */
    exportAsSVG(filename) {
        const svgElements = this.container.querySelectorAll('.heatmap-svg');
        if (svgElements.length === 0) return;
        
        // For single heatmap, export directly
        if (svgElements.length === 1) {
            const svgData = new XMLSerializer().serializeToString(svgElements[0]);
            const blob = new Blob([svgData], { type: 'image/svg+xml' });
            const link = document.createElement('a');
            link.download = filename;
            link.href = URL.createObjectURL(blob);
            link.click();
        } else {
            // For multiple heatmaps, combine them
            this.combineSVGsForExport(svgElements, filename);
        }
    }

    /**
     * Export as PNG
     */
    exportAsPNG(filename) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        // Set canvas size
        canvas.width = this.heatmapArea.offsetWidth;
        canvas.height = this.heatmapArea.offsetHeight;
        
        // Convert SVGs to canvas
        this.renderHeatmapsToCanvas(ctx).then(() => {
            const link = document.createElement('a');
            link.download = filename;
            link.href = canvas.toDataURL('image/png');
            link.click();
        });
    }

    /**
     * Export data as JSON
     */
    exportAsJSON(filename) {
        const exportData = {
            heatmaps: [],
            options: this.options,
            colorScales: this.colorScales,
            exportDate: new Date().toISOString()
        };
        
        this.heatmaps.forEach((heatmap, id) => {
            exportData.heatmaps.push({
                id,
                title: heatmap.config.title,
                data: heatmap.config.data,
                dimensions: heatmap.config.dimensions,
                labels: heatmap.config.labels
            });
        });
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const link = document.createElement('a');
        link.download = filename;
        link.href = URL.createObjectURL(blob);
        link.click();
    }

    /**
     * Generate mock data for demonstrations
     */
    generateMockWeeklyData() {
        return Array.from({length: 7}, () => 
            Array.from({length: 24}, () => Math.floor(Math.random() * 100))
        );
    }

    generateMockMonthlyData() {
        return Array.from({length: 6}, () => 
            Array.from({length: 7}, () => Math.floor(Math.random() * 20))
        );
    }

    generateMockSkillData(rows, cols) {
        return Array.from({length: rows}, () => 
            Array.from({length: cols}, () => Math.floor(Math.random() * 40))
        );
    }

    generateMockCorrelationData(size) {
        const data = Array.from({length: size}, () => Array(size).fill(0));
        for (let i = 0; i < size; i++) {
            for (let j = 0; j < size; j++) {
                if (i === j) {
                    data[i][j] = 100; // Perfect correlation with self
                } else {
                    // Generate symmetric correlation matrix
                    if (i < j) {
                        data[i][j] = Math.floor((Math.random() - 0.5) * 200); // -100 to 100
                        data[j][i] = data[i][j]; // Make symmetric
                    }
                }
            }
        }
        return data;
    }

    /**
     * Load drill-down data (placeholder for API integration)
     */
    async loadDrillDownData(drillDownData) {
        // Simulate API call
        return new Promise(resolve => {
            setTimeout(() => {
                resolve({
                    timeSeriesData: Array.from({length: 30}, (_, i) => ({
                        date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
                        value: Math.floor(Math.random() * 100)
                    })),
                    comparativeData: {
                        average: 65,
                        median: 68,
                        percentile: 75
                    },
                    metadata: {
                        lastUpdated: new Date().toISOString(),
                        dataPoints: 30,
                        reliability: 'High'
                    }
                });
            }, 500);
        });
    }

    /**
     * Render drill-down chart
     */
    renderDrillDownChart(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        // Create simple line chart for drill-down data
        container.innerHTML = `
            <div class="drill-down-chart-placeholder">
                <h4>Historical Trend</h4>
                <div class="chart-area">
                    <!-- This would be replaced with actual charting library -->
                    <div class="trend-line">Trend visualization would appear here</div>
                    <div class="stats">
                        <div class="stat">
                            <label>Average:</label>
                            <span>${data.comparativeData.average}</span>
                        </div>
                        <div class="stat">
                            <label>Median:</label>
                            <span>${data.comparativeData.median}</span>
                        </div>
                        <div class="stat">
                            <label>Percentile:</label>
                            <span>${data.comparativeData.percentile}th</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Initialize with default heatmaps
     */
    initializeDefault() {
        // Create a sample dashboard with multiple heatmaps
        const mockData = {
            weeklyData: this.generateMockWeeklyData(),
            monthlyData: this.generateMockMonthlyData(),
            skillData: this.generateMockSkillData(8, 6),
            correlationMatrix: this.generateMockCorrelationData(8)
        };
        
        this.createWeeklyProductivityHeatmap(mockData);
        this.createSkillDevelopmentHeatmap(mockData);
        this.createPerformanceCorrelationHeatmap(mockData);
    }

    /**
     * Destroy heatmaps and cleanup
     */
    destroy() {
        this.heatmaps.forEach(heatmap => {
            heatmap.instance.destroy();
        });
        this.heatmaps.clear();
        
        window.removeEventListener('resize', this.handleResize);
        this.container.innerHTML = '';
    }
}

// CSS Styles for Interactive Heatmaps
const heatmapStyles = `
.interactive-heatmap-container {
    background: #ffffff;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    overflow: hidden;
}

.heatmap-controls {
    background: #f8f9fa;
    padding: 20px;
    border-bottom: 1px solid #dee2e6;
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    align-items: center;
}

.control-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.control-group label {
    font-weight: 500;
    color: #495057;
    white-space: nowrap;
}

.control-group select, .control-group input[type="range"] {
    padding: 4px 8px;
    border: 1px solid #ced4da;
    border-radius: 4px;
}

.control-group button {
    padding: 8px 16px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
}

.control-group button:hover {
    background: #0056b3;
}

.heatmap-area {
    padding: 20px;
    overflow: auto;
    transform-origin: top left;
    transition: transform 0.3s ease;
}

.heatmap-instance {
    margin-bottom: 40px;
}

.heatmap-title {
    margin: 0 0 20px 0;
    font-size: 18px;
    font-weight: 600;
    color: #333333;
}

.heatmap-svg {
    border: 1px solid #e9ecef;
    border-radius: 4px;
    background: #ffffff;
}

.heatmap-cell {
    cursor: pointer;
    transition: stroke-width 0.2s, stroke 0.2s;
}

.heatmap-cell:hover {
    stroke-width: 3 !important;
    stroke: #333333 !important;
}

.heatmap-label {
    font-size: 12px;
    fill: #495057;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.color-scale-legend {
    background: #f8f9fa;
    padding: 20px;
    border-top: 1px solid #dee2e6;
}

.color-scale {
    max-width: 300px;
}

.legend-title {
    font-weight: 600;
    margin-bottom: 10px;
    color: #495057;
}

.scale-container {
    position: relative;
}

.gradient-bar {
    height: 20px;
    border-radius: 4px;
    border: 1px solid #dee2e6;
}

.scale-labels {
    display: flex;
    justify-content: space-between;
    margin-top: 5px;
    font-size: 12px;
    color: #6c757d;
}

.heatmap-tooltip {
    position: absolute;
    background: #333333;
    color: #ffffff;
    padding: 10px;
    border-radius: 6px;
    font-size: 12px;
    pointer-events: none;
    z-index: 1000;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    max-width: 200px;
}

.tooltip-title {
    font-weight: 600;
    margin-bottom: 4px;
}

.tooltip-value, .tooltip-coords {
    font-size: 11px;
    opacity: 0.9;
}

.heatmap-drill-down-modal, .export-options-modal {
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

.modal-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
}

.modal-content {
    background: #ffffff;
    border-radius: 8px;
    max-width: 90vw;
    max-height: 90vh;
    overflow: auto;
    position: relative;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
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

.close-btn {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #6c757d;
    padding: 0;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.close-btn:hover {
    color: #333333;
}

.modal-body {
    padding: 20px;
}

.drill-down-summary {
    display: flex;
    gap: 20px;
    margin-bottom: 20px;
}

.summary-card {
    flex: 1;
    background: #f8f9fa;
    padding: 15px;
    border-radius: 6px;
    text-align: center;
}

.summary-card h4 {
    margin: 0 0 8px 0;
    color: #6c757d;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.value-display, .position-display {
    font-size: 24px;
    font-weight: 600;
    color: #333333;
}

.drill-down-chart {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    min-height: 300px;
    margin-bottom: 20px;
    padding: 20px;
}

.drill-down-chart-placeholder {
    height: 100%;
    display: flex;
    flex-direction: column;
}

.chart-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}

.trend-line {
    color: #6c757d;
    font-style: italic;
    margin-bottom: 20px;
}

.stats {
    display: flex;
    gap: 20px;
}

.stat {
    text-align: center;
}

.stat label {
    display: block;
    font-size: 12px;
    color: #6c757d;
    margin-bottom: 4px;
}

.stat span {
    font-size: 18px;
    font-weight: 600;
    color: #333333;
}

.drill-down-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}

.drill-down-actions button {
    padding: 8px 16px;
    border: 1px solid #dee2e6;
    background: #ffffff;
    color: #495057;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
}

.drill-down-actions button:hover {
    background: #f8f9fa;
    border-color: #adb5bd;
}

.export-format-options {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    min-width: 300px;
}

.export-btn {
    padding: 12px 16px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
}

.export-btn:hover {
    background: #0056b3;
}

@media (max-width: 768px) {
    .heatmap-controls {
        flex-direction: column;
        align-items: stretch;
    }
    
    .control-group {
        justify-content: space-between;
    }
    
    .drill-down-summary {
        flex-direction: column;
    }
    
    .export-format-options {
        grid-template-columns: 1fr;
    }
    
    .stats {
        flex-direction: column;
        gap: 10px;
    }
}
`;

// Auto-inject styles
if (!document.getElementById('interactive-heatmaps-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'interactive-heatmaps-styles';
    styleSheet.textContent = heatmapStyles;
    document.head.appendChild(styleSheet);
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = InteractiveHeatmaps;
} else if (typeof window !== 'undefined') {
    window.InteractiveHeatmaps = InteractiveHeatmaps;
}