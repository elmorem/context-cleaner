(() => {
    const STYLE_ID = 'data-explorer-standalone-styles';

    const DATA_EXPLORER_TEMPLATES = {
        apiErrors: `SELECT
    LogAttributes['status_code'] AS status_code,
    LogAttributes['model'] AS model,
    COUNT(*) AS error_count,
    MIN(Timestamp) AS first_occurrence,
    MAX(Timestamp) AS last_occurrence
FROM otel.otel_logs
WHERE Body = 'claude_code.api_error'
  AND Timestamp >= now() - INTERVAL 24 HOUR
GROUP BY status_code, model
ORDER BY error_count DESC
LIMIT 100`,
        toolUsage: `SELECT
    tool_name,
    COUNT() AS invocation_count,
    AVG(execution_time_ms) AS avg_execution_ms,
    countIf(success) AS successful_runs,
    countIf(NOT success) AS failed_runs
FROM otel.claude_tool_results
WHERE timestamp >= now() - INTERVAL 7 DAY
GROUP BY tool_name
ORDER BY invocation_count DESC
LIMIT 100`,
        contextRot: `SELECT
    toStartOfInterval(timestamp, INTERVAL 1 HOUR) AS window_start,
    AVG(rot_score) AS avg_rot_score,
    AVG(confidence_score) AS avg_confidence,
    COUNT() AS events
FROM otel.context_rot_metrics
WHERE timestamp >= now() - INTERVAL 24 HOUR
GROUP BY window_start
ORDER BY window_start DESC
LIMIT 200`,
        sessionDrilldown: `WITH target_session AS (
    SELECT session_id
    FROM otel.claude_message_content
    WHERE session_id != ''
    ORDER BY timestamp DESC
    LIMIT 1
)
SELECT
    timestamp,
    role,
    message_preview,
    input_tokens,
    output_tokens,
    cost_usd
FROM otel.claude_message_content
WHERE session_id IN (SELECT session_id FROM target_session)
ORDER BY timestamp ASC
LIMIT 200`,
        latencyHotspots: `SELECT
    tool_name,
    AVG(execution_time_ms) AS avg_execution_ms,
    quantile(0.9)(execution_time_ms) AS p90_execution_ms,
    COUNT() AS runs
FROM otel.claude_tool_results
WHERE timestamp >= now() - INTERVAL 4 HOUR
GROUP BY tool_name
ORDER BY avg_execution_ms DESC
LIMIT 25`,
        costTrend: `SELECT
    toStartOfInterval(timestamp, INTERVAL 15 MINUTE) AS window_start,
    SUM(cost_usd) AS total_cost_usd,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens
FROM otel.claude_message_content
WHERE timestamp >= now() - INTERVAL 48 HOUR
GROUP BY window_start
ORDER BY window_start`,
        activeSessions: `SELECT
    LogAttributes['session.id'] AS session_id,
    MIN(Timestamp) AS first_seen,
    MAX(Timestamp) AS last_seen,
    COUNT(*) AS event_count
FROM otel.otel_logs
WHERE Timestamp >= now() - INTERVAL 24 HOUR
  AND LogAttributes['session.id'] != ''
GROUP BY session_id
ORDER BY event_count DESC
LIMIT 50`,
        userJourney: `SELECT
    LogAttributes['user.email'] AS user_email,
    MIN(Timestamp) AS first_activity,
    MAX(Timestamp) AS last_activity,
    COUNT(*) AS total_events,
    COUNT(DISTINCT LogAttributes['session.id']) AS sessions_touched
FROM otel.otel_logs
WHERE Timestamp >= now() - INTERVAL 14 DAY
GROUP BY user_email
ORDER BY last_activity DESC
LIMIT 50`,
        errorSessions: `SELECT
    LogAttributes['session.id'] AS session_id,
    COUNT(*) AS error_events,
    MIN(Timestamp) AS first_error,
    MAX(Timestamp) AS last_error,
    any(LogAttributes['user.email']) AS user_email
FROM otel.otel_logs
WHERE Body = 'claude_code.api_error'
  AND Timestamp >= now() - INTERVAL 7 DAY
GROUP BY session_id
ORDER BY error_events DESC
LIMIT 50`
    };

    const DEFAULT_QUERY = `SELECT
    LogAttributes['session.id'] AS session_id,
    LogAttributes['tool_name'] AS tool,
    Timestamp,
    LogAttributes['cost_usd'] AS cost_usd
FROM otel.otel_logs
WHERE Timestamp >= now() - INTERVAL 1 HOUR
ORDER BY Timestamp DESC
LIMIT 50`;

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) {
            return;
        }
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = `
        #data-explorer-root {
            position: relative;
        }
        .data-explorer-layout {
            display: flex;
            gap: 1.5rem;
            align-items: flex-start;
            flex-wrap: nowrap;
        }
        .data-explorer-sidebar {
            flex: 0 0 320px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 1.25rem;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            position: sticky;
            top: 6.5rem;
            max-height: calc(100vh - 8rem);
            overflow-y: auto;
            min-width: 280px;
        }
        .data-explorer-main {
            flex: 1 1 520px;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            min-width: 0;
        }
        .de-sidebar-section {
            margin-bottom: 1.5rem;
        }
        .de-sidebar-section h4 {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            margin: 0 0 0.6rem 0;
            font-size: 0.9rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #0f172a;
        }
        .de-sidebar-section small {
            display: block;
            color: #64748b;
            font-size: 0.7rem;
            margin-bottom: 0.5rem;
        }
        .de-sidebar-list {
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
        }
        .de-sidebar-chip {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 0.7rem;
            border-radius: 10px;
            border: 1px solid rgba(148, 163, 184, 0.35);
            background: #fff;
            color: #1e293b;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.15s ease;
            text-align: left;
        }
        .de-sidebar-chip:hover {
            border-color: #2563eb;
            color: #2563eb;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.15);
        }
        .de-chip-hint {
            font-size: 0.65rem;
            color: #64748b;
        }
        .de-card {
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            background: #fff;
            padding: 1.25rem;
            box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
        }
        .de-toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }
        .de-toolbar-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        .de-btn {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            border-radius: 10px;
            padding: 0.55rem 0.9rem;
            font-size: 0.8rem;
            font-weight: 600;
            border: 1px solid rgba(148, 163, 184, 0.4);
            background: #fff;
            color: #1f2937;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .de-btn.primary {
            background: #2563eb;
            border-color: transparent;
            color: #fff;
        }
        .de-btn.secondary {
            background: #0f172a;
            border-color: transparent;
            color: #fff;
        }
        .de-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(15, 23, 42, 0.12);
        }
        .de-query-textarea {
            width: 100%;
            min-height: 160px;
            padding: 1rem;
            border-radius: 12px;
            border: 1.5px solid rgba(148, 163, 184, 0.5);
            font-family: 'Monaco', 'Fira Code', 'Menlo', monospace;
            font-size: 0.9rem;
            line-height: 1.55;
            resize: vertical;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .de-query-textarea:focus {
            border-color: #2563eb;
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
            outline: none;
        }
        .de-status-banner {
            margin-top: 0.6rem;
            font-size: 0.78rem;
            color: #475569;
        }
        .de-status-banner[data-tone="success"] { color: #047857; }
        .de-status-banner[data-tone="error"] { color: #dc2626; }
        .de-status-banner[data-tone="warning"] { color: #d97706; }
        .de-helper-banner {
            margin-top: 1rem;
            padding: 0.75rem 1rem;
            border-radius: 10px;
            background: #ecfdf5;
            border: 1px solid #34d399;
            color: #047857;
            font-size: 0.82rem;
        }
        .de-info-banner {
            border: 1px solid #bfdbfe;
            background: #eff6ff;
            color: #1d4ed8;
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin-bottom: 1.25rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }
        .de-info-banner button {
            border: 1px solid #2563eb;
            background: #2563eb;
            color: #fff;
            padding: 0.45rem 0.9rem;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .de-info-banner button:hover {
            background: #1d4ed8;
        }
        .de-assist-panel {
            position: absolute;
            top: 3.5rem;
            right: 1.35rem;
            width: min(440px, 90vw);
            max-height: 22rem;
            overflow-y: auto;
            background: #fff;
            border-radius: 14px;
            border: 1px solid rgba(148, 163, 184, 0.45);
            box-shadow: 0 22px 40px rgba(15, 23, 42, 0.18);
            padding: 1rem;
            z-index: 22;
        }
        .de-assist-panel.hidden { display: none; }
        .de-assist-header {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            margin-bottom: 0.8rem;
        }
        .de-assist-header input[type="search"] {
            flex: 1;
            border: 1px solid rgba(148, 163, 184, 0.45);
            border-radius: 8px;
            padding: 0.45rem 0.7rem;
            font-size: 0.8rem;
        }
        .de-assist-options {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .de-assist-chip-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
        }
        .de-assist-chip {
            display: inline-flex;
            align-items: center;
            border: 1px solid rgba(37, 99, 235, 0.3);
            border-radius: 9999px;
            padding: 0.3rem 0.75rem;
            font-size: 0.75rem;
            background: rgba(37, 99, 235, 0.08);
            color: #1d4ed8;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .de-assist-chip:hover {
            background: #2563eb;
            color: #fff;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.25);
        }
        .de-empty-state {
            text-align: center;
            color: #6b7280;
            font-size: 0.85rem;
            padding: 2rem;
        }
        .de-results-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 0.6rem;
            font-size: 0.82rem;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.6);
        }
        .de-results-table thead {
            background: #f8fafc;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.68rem;
            color: #475569;
        }
        .de-results-table th,
        .de-results-table td {
            padding: 0.65rem 0.85rem;
            border-bottom: 1px solid rgba(226, 232, 240, 0.6);
        }
        .de-results-table tbody tr:hover {
            background: rgba(37, 99, 235, 0.06);
        }
        @media (max-width: 1100px) {
            .data-explorer-layout {
                flex-direction: column;
                align-items: stretch;
            }
            .data-explorer-sidebar {
                position: relative;
                top: 0;
                max-height: none;
                width: 100%;
            }
        }
        `;
        document.head.appendChild(style);
    }

    function renderLayout(root) {
        root.innerHTML = `
            <div class="de-info-banner">
                <div>
                    📚 Need schema details or example queries? Open the Data Explorer reference guide.
                </div>
                <button type="button" id="de-open-reference">Open Reference</button>
            </div>
            <div class="data-explorer-layout">
                <aside class="data-explorer-sidebar" aria-label="Query building helpers">
                    <div class="de-sidebar-section">
                        <h4>🎯 Query Starters</h4>
                        <small>Load curated templates</small>
                        <div class="de-sidebar-list">
                            <button type="button" class="de-sidebar-chip" data-template="activeSessions">
                                Active Sessions (24h)
                                <span class="de-chip-hint">Top Activity</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-template="sessionDrilldown">
                                Session Drilldown
                                <span class="de-chip-hint">Recent history</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-template="contextRot">
                                Context Rot Pulse
                                <span class="de-chip-hint">Health</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-template="toolUsage">
                                Tool Usage Overview
                                <span class="de-chip-hint">7d</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-template="apiErrors">
                                API Error Monitor
                                <span class="de-chip-hint">24h</span>
                            </button>
                        </div>
                    </div>
                    <div class="de-sidebar-section">
                        <h4>📚 Data Sources</h4>
                        <small>Insert into FROM clauses</small>
                        <div class="de-sidebar-list">
                            <button type="button" class="de-sidebar-chip" data-snippet="FROM otel.otel_logs">
                                otel.otel_logs
                                <span class="de-chip-hint">Event Stream</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-snippet="FROM otel.claude_message_content">
                                otel.claude_message_content
                                <span class="de-chip-hint">Messages</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-snippet="FROM otel.claude_tool_results">
                                otel.claude_tool_results
                                <span class="de-chip-hint">Tool Runs</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-snippet="FROM otel.context_rot_metrics">
                                otel.context_rot_metrics
                                <span class="de-chip-hint">Context Rot</span>
                            </button>
                        </div>
                    </div>
                    <div class="de-sidebar-section">
                        <h4>🧱 Common Fields</h4>
                        <small>Tap to insert at cursor</small>
                        <div class="de-sidebar-list">
                            <button type="button" class="de-sidebar-chip" data-contextual="sessionId" data-label="Session ID">
                                Session ID
                                <span class="de-chip-hint">Context aware</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-contextual="userEmail" data-label="User Email">
                                User Email
                                <span class="de-chip-hint">Context aware</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-contextual="toolName" data-label="Tool Name">
                                Tool Name
                                <span class="de-chip-hint">Log / Tool Runs</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-contextual="modelName" data-label="Model Name">
                                Model Name
                                <span class="de-chip-hint">Message / Logs</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-contextual="timestampColumn" data-label="Timestamp">
                                Timestamp
                                <span class="de-chip-hint">Auto detects</span>
                            </button>
                        </div>
                    </div>
                    <div class="de-sidebar-section">
                        <h4>⏱️ Quick Time Ranges</h4>
                        <small>Append to WHERE clauses</small>
                        <div class="de-sidebar-list">
                            <button type="button" class="de-sidebar-chip" data-timerange="lastHour" data-label="Last hour">
                                Last hour
                                <span class="de-chip-hint">timestamp ≥ now()-1h</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-timerange="lastDay" data-label="Last 24 hours">
                                Last 24 hours
                                <span class="de-chip-hint">Daily window</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-timerange="today" data-label="Today">
                                Today
                                <span class="de-chip-hint">toDate()</span>
                            </button>
                            <button type="button" class="de-sidebar-chip" data-timerange="lastSevenDays" data-label="Last 7 days">
                                Last 7 days
                                <span class="de-chip-hint">Rolling week</span>
                            </button>
                        </div>
                    </div>
                </aside>
                <div class="data-explorer-main">
                    <div class="de-card" style="position: relative;">
                        <div class="de-toolbar">
                            <div class="de-toolbar-group">
                                <button type="button" class="de-btn primary" id="de-run">▶️ Run Query</button>
                                <button type="button" class="de-btn" id="de-reset">🧹 Reset Editor</button>
                                <button type="button" class="de-btn" id="de-clear">🗑️ Clear Results</button>
                            </div>
                            <div class="de-toolbar-group">
                                <button type="button" class="de-btn" id="de-export">📁 Export CSV</button>
                                <button type="button" class="de-btn secondary" id="de-assist-toggle">✨ Query Assist</button>
                            </div>
                        </div>
                        <textarea id="de-query" class="de-query-textarea" spellcheck="false"></textarea>
                        <div id="de-status" class="de-status-banner" data-tone="info">Compose a query, then press ⌘⏎ / Ctrl+Enter to execute.</div>
                        <div class="de-helper-banner">
                            <strong>Tip:</strong> Use the sidebar chips or press ⌘+K / Ctrl+K to open Query Assist for guided query building.
                        </div>
                        <div id="de-assist-panel" class="de-assist-panel hidden" role="dialog" aria-labelledby="de-assist-heading">
                            <div class="de-assist-header">
                                <h5 id="de-assist-heading" style="margin:0; font-size:0.85rem; font-weight:700; color:#1f2937;">Query Assist</h5>
                                <input type="search" id="de-assist-search" placeholder="Search helpers" aria-label="Search query helpers" />
                                <button type="button" class="de-btn" id="de-assist-close">✕ Close</button>
                            </div>
                            <div class="de-assist-options">
                                <div class="de-assist-section" data-section="fields">
                                    <h5 style="margin:0 0 0.4rem 0; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.04em; color:#1f2937;">Common Fields</h5>
                                    <div class="de-assist-chip-grid">
                                        <span class="de-assist-chip" data-snippet="input_tokens">input_tokens</span>
                                        <span class="de-assist-chip" data-snippet="output_tokens">output_tokens</span>
                                        <span class="de-assist-chip" data-snippet="cost_usd">cost_usd</span>
                                        <span class="de-assist-chip" data-snippet="execution_time_ms">execution_time_ms</span>
                                        <span class="de-assist-chip" data-snippet="rot_score">rot_score</span>
                                    </div>
                                </div>
                                <div class="de-assist-section" data-section="filters">
                                    <h5 style="margin:0 0 0.4rem 0; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.04em; color:#1f2937;">Helpful Filters</h5>
                                    <div class="de-assist-chip-grid">
                                        <span class="de-assist-chip" data-snippet="WHERE LogAttributes['user.email'] = 'user@example.com'">Filter by user</span>
                                        <span class="de-assist-chip" data-snippet="AND LogAttributes['tool_name'] = 'cursor-search'">Limit to tool</span>
                                        <span class="de-assist-chip" data-snippet="AND LogAttributes['workspace.id'] = 'workspace-123'">Workspace scope</span>
                                        <span class="de-assist-chip" data-snippet="AND LogAttributes['session.id'] = 'session-id-here'">Specific session</span>
                                        <span class="de-assist-chip" data-snippet="AND LogAttributes['status'] = 'error'">Only errors</span>
                                        <span class="de-assist-chip" data-snippet="ORDER BY Timestamp DESC">Sort by newest</span>
                                    </div>
                                </div>
                                <div class="de-assist-section" data-section="aggregations">
                                    <h5 style="margin:0 0 0.4rem 0; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.04em; color:#1f2937;">Aggregations</h5>
                                    <div class="de-assist-chip-grid">
                                        <span class="de-assist-chip" data-snippet="COUNT(*) AS total_events">COUNT(*)</span>
                                        <span class="de-assist-chip" data-snippet="COUNT(DISTINCT LogAttributes['session.id']) AS unique_sessions">Distinct sessions</span>
                                        <span class="de-assist-chip" data-snippet="AVG(toFloat64OrNull(LogAttributes['duration_ms'])) AS avg_duration_ms">Avg duration</span>
                                        <span class="de-assist-chip" data-snippet="SUM(toInt64OrNull(LogAttributes['input_tokens'])) AS total_input_tokens">SUM input_tokens</span>
                                        <span class="de-assist-chip" data-snippet="toStartOfInterval(Timestamp, INTERVAL 5 MINUTE) AS window_start">toStartOfInterval(...)</span>
                                    </div>
                                </div>
                                <div class="de-assist-section" data-section="templates">
                                    <h5 style="margin:0 0 0.4rem 0; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.04em; color:#1f2937;">Curated Templates</h5>
                                    <div class="de-assist-chip-grid">
                                    <span class="de-assist-chip" data-template="latencyHotspots">Latency hotspots</span>
                                    <span class="de-assist-chip" data-template="costTrend">Cost trend</span>
                                    <span class="de-assist-chip" data-template="userJourney">User journey</span>
                                    <span class="de-assist-chip" data-template="errorSessions">Sessions with errors</span>
                                    <span class="de-assist-chip" data-template="activeSessions">Active Sessions</span>
                                </div>
                            </div>
                        </div>
                            <div id="de-assist-empty" class="de-empty-state hidden">No matching helpers. Try a different search.</div>
                        </div>
                    </div>
                    <div class="de-card">
                        <div style="display:flex; justify-content:space-between; align-items:center; gap:1rem;">
                            <h3 style="margin:0; font-size:1.05rem; color:#0f172a;">📊 Query Results</h3>
                            <div class="status-indicator" id="de-results-indicator"></div>
                        </div>
                        <div id="de-results" style="min-height:220px; margin-top:0.75rem; font-family:'Monaco','Menlo',monospace; font-size:0.875rem;">
                            <div class="de-empty-state">Execute a query or load a template to see rows here.</div>
                        </div>
                        <div id="de-meta" style="margin-top:0.75rem; font-size:0.75rem; color:#6b7280;"></div>
                    </div>
                    <div class="de-card">
                        <div style="display:flex; justify-content:space-between; align-items:center; gap:1rem;">
                            <h3 style="margin:0; font-size:1.05rem; color:#0f172a;">📈 Data Visualization</h3>
                            <div>
                                <select id="de-chart-type" style="padding:0.45rem 0.7rem; border:1px solid rgba(148, 163, 184, 0.7); border-radius:8px; font-size:0.8rem; margin-right:0.5rem;">
                                    <option value="table">Table View</option>
                                    <option value="bar">Bar Chart</option>
                                    <option value="line">Line Chart</option>
                                    <option value="pie">Pie Chart</option>
                                    <option value="scatter">Scatter Plot</option>
                                </select>
                                <button type="button" class="de-btn" id="de-generate-chart">📊 Generate Chart</button>
                            </div>
                        </div>
                        <div id="de-visualization" style="min-height:280px; margin-top:1rem;">
                            <div class="de-empty-state">Run a query and generate a visualization to see charts here.</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function initDataExplorer() {
        const root = document.getElementById('data-explorer-root');
        if (!root) {
            return;
        }

        try {
            injectStyles();
            renderLayout(root);
        } catch (error) {
            console.error('Data Explorer rendering failed:', error);
            return;
        }

        const queryTextarea = root.querySelector('#de-query');
        const runButton = root.querySelector('#de-run');
        const resetButton = root.querySelector('#de-reset');
        const clearButton = root.querySelector('#de-clear');
        const exportButton = root.querySelector('#de-export');
        const assistToggle = root.querySelector('#de-assist-toggle');
        const assistClose = root.querySelector('#de-assist-close');
        const assistPanel = root.querySelector('#de-assist-panel');
        const assistSearch = root.querySelector('#de-assist-search');
        const statusBanner = root.querySelector('#de-status');
        const resultsContainer = root.querySelector('#de-results');
        const metaContainer = root.querySelector('#de-meta');
        const resultsIndicator = root.querySelector('#de-results-indicator');
        const visualizationContainer = root.querySelector('#de-visualization');
        const chartTypeSelect = root.querySelector('#de-chart-type');
        const generateChartButton = root.querySelector('#de-generate-chart');
        const referenceButton = root.querySelector('#de-open-reference');

        queryTextarea.value = DEFAULT_QUERY;

        const state = {
            lastResults: null,
            lastColumns: null,
            chartInstance: null
        };

        function setStatus(message, tone = 'info') {
            if (!statusBanner) return;
            statusBanner.textContent = message;
            statusBanner.dataset.tone = tone;
        }

        function setIndicator(stateName) {
            if (!resultsIndicator) return;
            const base = 'status-indicator';
            const mapping = {
                success: 'status-healthy',
                error: 'status-critical',
                running: 'status-warning'
            };
            const modifier = mapping[stateName];
            resultsIndicator.className = modifier ? `${base} ${modifier}` : base;
        }

        const RESERVED_KEYWORDS = new Set([
            'WHERE', 'GROUP', 'ORDER', 'LIMIT', 'LEFT', 'RIGHT', 'FULL', 'INNER', 'OUTER',
            'JOIN', 'ON', 'USING', 'ARRAY', 'SAMPLE', 'PREWHERE', 'SETTINGS', 'FORMAT'
        ]);

        const TABLE_KEY_MAP = {
            'otel.otel_logs': 'otel_logs',
            'otel_logs': 'otel_logs',
            'otel.claude_message_content': 'message_content',
            'claude_message_content': 'message_content',
            'otel.claude_tool_results': 'tool_results',
            'claude_tool_results': 'tool_results',
            'otel.context_rot_metrics': 'context_rot',
            'context_rot_metrics': 'context_rot',
            'otel.context_rot_hourly': 'context_rot_hourly',
            'context_rot_hourly': 'context_rot_hourly'
        };

        const TABLE_LABELS = {
            otel_logs: 'otel.otel_logs',
            message_content: 'otel.claude_message_content',
            tool_results: 'otel.claude_tool_results',
            context_rot: 'otel.context_rot_metrics',
            context_rot_hourly: 'otel.context_rot_hourly'
        };

        const CONTEXTUAL_FIELD_SNIPPETS = {
            sessionId: [
                {
                    table: 'otel_logs',
                    resolver: ctx => `${ctx.aliasMap.otel_logs ? `${ctx.aliasMap.otel_logs}.` : ''}LogAttributes['session.id']`
                },
                {
                    table: 'message_content',
                    resolver: ctx => `${ctx.aliasMap.message_content ? `${ctx.aliasMap.message_content}.` : ''}session_id`
                },
                {
                    table: 'tool_results',
                    resolver: ctx => `${ctx.aliasMap.tool_results ? `${ctx.aliasMap.tool_results}.` : ''}session_id`
                },
                {
                    table: 'context_rot',
                    resolver: ctx => `${ctx.aliasMap.context_rot ? `${ctx.aliasMap.context_rot}.` : ''}session_id`
                }
            ],
            userEmail: [
                {
                    table: 'otel_logs',
                    resolver: ctx => `${ctx.aliasMap.otel_logs ? `${ctx.aliasMap.otel_logs}.` : ''}LogAttributes['user.email']`
                }
            ],
            toolName: [
                {
                    table: 'tool_results',
                    resolver: ctx => `${ctx.aliasMap.tool_results ? `${ctx.aliasMap.tool_results}.` : ''}tool_name`
                },
                {
                    table: 'otel_logs',
                    resolver: ctx => `${ctx.aliasMap.otel_logs ? `${ctx.aliasMap.otel_logs}.` : ''}LogAttributes['tool_name']`
                }
            ],
            modelName: [
                {
                    table: 'message_content',
                    resolver: ctx => `${ctx.aliasMap.message_content ? `${ctx.aliasMap.message_content}.` : ''}model_name`
                },
                {
                    table: 'otel_logs',
                    resolver: ctx => `${ctx.aliasMap.otel_logs ? `${ctx.aliasMap.otel_logs}.` : ''}LogAttributes['model']`
                }
            ],
            timestampColumn: [
                {
                    table: 'otel_logs',
                    resolver: ctx => `${ctx.aliasMap.otel_logs ? `${ctx.aliasMap.otel_logs}.` : ''}Timestamp`
                },
                {
                    table: 'message_content',
                    resolver: ctx => `${ctx.aliasMap.message_content ? `${ctx.aliasMap.message_content}.` : ''}timestamp`
                },
                {
                    table: 'tool_results',
                    resolver: ctx => `${ctx.aliasMap.tool_results ? `${ctx.aliasMap.tool_results}.` : ''}timestamp`
                },
                {
                    table: 'context_rot',
                    resolver: ctx => `${ctx.aliasMap.context_rot ? `${ctx.aliasMap.context_rot}.` : ''}timestamp`
                },
                {
                    table: 'context_rot_hourly',
                    resolver: ctx => `${ctx.aliasMap.context_rot_hourly ? `${ctx.aliasMap.context_rot_hourly}.` : ''}hour`
                }
            ]
        };

        const QUICK_TIME_RANGE_BUILDERS = {
            lastHour: column => `${column} >= now() - INTERVAL 1 HOUR`,
            lastDay: column => `${column} >= now() - INTERVAL 24 HOUR`,
            today: column => `toDate(${column}) = today()`,
            lastSevenDays: column => `${column} BETWEEN now() - INTERVAL 7 DAY AND now()`
        };

        function normalizeTableName(raw) {
            if (!raw) return null;
            const cleaned = raw.replace(/`/g, '').trim();
            const lower = cleaned.toLowerCase();
            return TABLE_KEY_MAP[cleaned] || TABLE_KEY_MAP[lower] || lower || null;
        }

        function getQueryContext() {
            const query = queryTextarea ? queryTextarea.value : '';
            const pattern = /\b(FROM|JOIN)\s+([`\w\.]+)(?:\s+(?:AS\s+)?([\w]+))?/gi;
            const aliasMap = {};
            const tables = new Set();
            let lastTable = null;
            let match;
            while ((match = pattern.exec(query)) !== null) {
                const tableName = normalizeTableName(match[2]);
                if (!tableName) {
                    continue;
                }
                tables.add(tableName);
                lastTable = tableName;
                const potentialAlias = match[3];
                if (potentialAlias) {
                    const keyword = potentialAlias.toUpperCase();
                    if (!RESERVED_KEYWORDS.has(keyword)) {
                        aliasMap[tableName] = potentialAlias;
                    }
                }
            }
            return { tables, aliasMap, lastTable };
        }

        function resolveContextualSnippet(key) {
            const definitions = CONTEXTUAL_FIELD_SNIPPETS[key];
            if (!definitions || !definitions.length) {
                setStatus('No contextual snippet found for this helper.', 'warning');
                return null;
            }
            const context = getQueryContext();
            for (const definition of definitions) {
                if (context.tables.has(definition.table)) {
                    const snippet = definition.resolver(context);
                    if (snippet) {
                        return { snippet, table: definition.table };
                    }
                }
            }
            setStatus('Add a FROM clause first so we can determine the right field for this data source.', 'warning');
            return null;
        }

        function detectTimestampIdentifier(context = getQueryContext()) {
            const priority = [context.lastTable, 'message_content', 'tool_results', 'context_rot', 'context_rot_hourly', 'otel_logs'];
            for (const tableKey of priority) {
                if (!tableKey) continue;
                if (!context.tables.has(tableKey)) continue;
                switch (tableKey) {
                    case 'otel_logs':
                        return `${context.aliasMap.otel_logs ? `${context.aliasMap.otel_logs}.` : ''}Timestamp`;
                    case 'context_rot_hourly':
                        return `${context.aliasMap.context_rot_hourly ? `${context.aliasMap.context_rot_hourly}.` : ''}hour`;
                    case 'message_content':
                        return `${context.aliasMap.message_content ? `${context.aliasMap.message_content}.` : ''}timestamp`;
                    case 'tool_results':
                        return `${context.aliasMap.tool_results ? `${context.aliasMap.tool_results}.` : ''}timestamp`;
                    case 'context_rot':
                        return `${context.aliasMap.context_rot ? `${context.aliasMap.context_rot}.` : ''}timestamp`;
                    default:
                        break;
                }
            }
            if (queryTextarea && /\btimestamp\b/i.test(queryTextarea.value)) {
                return 'timestamp';
            }
            if (queryTextarea && /\bTimestamp\b/.test(queryTextarea.value)) {
                return 'Timestamp';
            }
            return null;
        }

        function resolveTimeRangeSnippet(rangeKey) {
            const builder = QUICK_TIME_RANGE_BUILDERS[rangeKey];
            if (!builder) {
                setStatus('Unknown time range helper selected.', 'warning');
                return null;
            }
            const column = detectTimestampIdentifier();
            if (!column) {
                setStatus('Unable to determine a timestamp column. Insert one manually.', 'warning');
                return null;
            }
            return {
                snippet: builder(column),
                column
            };
        }

        function insertSnippet(snippet, options = {}) {
            if (!snippet || !queryTextarea) {
                return;
            }
            const { selectionStart, selectionEnd, value } = queryTextarea;
            const before = value.slice(0, selectionStart);
            const after = value.slice(selectionEnd);
            let insertion = snippet;
            const trimmed = snippet.trimStart();
            const blockKeywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING'];
            const precedingChar = before.slice(-1);
            if (blockKeywords.some(keyword => trimmed.toUpperCase().startsWith(keyword))) {
                if (precedingChar && precedingChar !== '\n') {
                    insertion = '\n' + insertion;
                }
            } else if (precedingChar && !/\s/.test(precedingChar)) {
                insertion = ' ' + insertion;
            }
            const followingChar = after.slice(0, 1);
            if (followingChar && !/\s/.test(followingChar)) {
                insertion = insertion + ' ';
            }
            queryTextarea.value = before + insertion + after;
            const cursor = before.length + insertion.length;
            queryTextarea.focus();
            queryTextarea.setSelectionRange(cursor, cursor);
            const message = options.message || 'Inserted snippet into the editor.';
            const tone = options.tone || 'info';
            setStatus(message, tone);
        }

        function insertFilterClause(clause, metadata = {}) {
            if (!clause || !queryTextarea) {
                return;
            }
            const label = metadata.label || 'Filter';
            const column = metadata.column || 'timestamp';
            const trimmed = clause.trim();
            if (!trimmed.length) {
                setStatus('Unable to insert an empty filter clause.', 'warning');
                return;
            }

            const clauseUpper = trimmed.toUpperCase();
            let insertion = trimmed;
            if (!/^(WHERE|AND|OR)\b/.test(clauseUpper)) {
                const { selectionStart } = queryTextarea;
                const before = queryTextarea.value.slice(0, selectionStart).toLowerCase();
                const lastWhere = before.lastIndexOf('where');
                const lastFrom = before.lastIndexOf('from');
                if (lastWhere === -1 || lastWhere < lastFrom) {
                    insertion = `WHERE ${trimmed}`;
                } else {
                    insertion = `AND ${trimmed}`;
                }
            }

            insertSnippet(insertion, {
                message: `Inserted ${label} filter using ${column}.`,
                tone: 'success'
            });
        }

        function loadTemplate(templateId) {
            const template = DATA_EXPLORER_TEMPLATES[templateId];
            if (!template) {
                setStatus(`Unknown template: ${templateId}`, 'warning');
                return;
            }
            queryTextarea.value = template;
            queryTextarea.focus();
            queryTextarea.setSelectionRange(queryTextarea.value.length, queryTextarea.value.length);
            clearResults(true);
            setStatus(`Loaded template: ${templateId}. Press ⌘⏎ / Ctrl+Enter to run.`, 'info');
            closeAssist();
        }

        function renderResultsTable(rows, columns) {
            if (!rows || rows.length === 0 || !columns || columns.length === 0) {
                return '<div class="de-empty-state">Query executed successfully but returned no rows.</div>';
            }
            const limitedRows = rows.slice(0, 250);
            const header = columns.map(col => `<th>${escapeHtml(col)}</th>`).join('');
            const body = limitedRows.map(row => {
                const cells = columns.map(col => {
                    let value = row[col];
                    if (value === null || value === undefined) {
                        value = '';
                    } else if (typeof value === 'object') {
                        value = JSON.stringify(value);
                    }
                    const stringValue = String(value);
                    const display = stringValue.length > 160 ? `${stringValue.substring(0, 160)}…` : stringValue;
                    const titleAttr = display !== stringValue ? ` title="${escapeHtml(stringValue)}"` : '';
                    return `<td${titleAttr}>${escapeHtml(display)}</td>`;
                }).join('');
                return `<tr>${cells}</tr>`;
            }).join('');
            return `
                <div style="overflow-x:auto; max-height:440px;">
                    <table class="de-results-table">
                        <thead><tr>${header}</tr></thead>
                        <tbody>${body}</tbody>
                    </table>
                </div>
            `;
        }

        function escapeHtml(value) {
            return value
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function clearResults(silent = false) {
            resultsContainer.innerHTML = '<div class="de-empty-state">No results to display. Execute a query to see rows here.</div>';
            metaContainer.textContent = '';
            if (state.chartInstance) {
                state.chartInstance.destroy();
                state.chartInstance = null;
            }
            visualizationContainer.innerHTML = '<div class="de-empty-state">Run a query and generate a visualization to see charts here.</div>';
            state.lastResults = null;
            state.lastColumns = null;
            setIndicator();
            if (!silent) {
                setStatus('Results cleared. Compose a new query and run it.', 'info');
            }
        }

        async function executeQuery() {
            if (!queryTextarea) return;
            const query = queryTextarea.value.trim();
            if (!query) {
                setStatus('Please enter a SQL query before executing.', 'warning');
                return;
            }

            setIndicator('running');
            setStatus('Executing query…', 'info');
            runButton.disabled = true;
            runButton.textContent = '⏳ Running…';
            resultsContainer.innerHTML = '<div class="de-empty-state">🔄 Executing query…</div>';
            metaContainer.textContent = '';

           try {
                const response = await fetch('/api/data-explorer/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ query })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const result = await response.json();
                console.log('[DataExplorer] Query response received:', result);

                if (result.error) {
                    setIndicator('error');
                    setStatus(`Query failed: ${result.error}`, 'error');
                    resultsContainer.innerHTML = `<div class="de-empty-state" style="color:#dc2626;">❌ Query Error: ${escapeHtml(result.error)}</div>`;
                    return;
                }

                const rows = Array.isArray(result.data) ? result.data : [];
                const columns = result.columns && result.columns.length ? result.columns : (rows[0] ? Object.keys(rows[0]) : []);
                console.log('[DataExplorer] Parsed rows/columns:', rows.length, columns);

                if (rows.length === 0 || columns.length === 0) {
                    clearResults(true);
                    setIndicator('success');
                    setStatus('Query completed with no rows returned.', 'warning');
                    return;
                }

                state.lastResults = rows;
                state.lastColumns = columns;
                resultsContainer.innerHTML = renderResultsTable(rows, columns);

                const executedAt = new Date();
                const parts = [];
                parts.push(`${rows.length.toLocaleString()} row${rows.length === 1 ? '' : 's'}`);
                if (rows.length > 250) {
                    parts.push('showing first 250');
                }
                if (result.execution_time_ms !== undefined) {
                    parts.push(`${result.execution_time_ms} ms`);
                }
                parts.push(`Ran at ${executedAt.toLocaleTimeString()}`);
                metaContainer.textContent = parts.join(' • ');

                visualizationContainer.innerHTML = '<div class="de-empty-state">Generate a visualization to explore this result set.</div>';
                if (state.chartInstance) {
                    state.chartInstance.destroy();
                    state.chartInstance = null;
                }

                setIndicator('success');
                setStatus(`Query completed. ${rows.length.toLocaleString()} row${rows.length === 1 ? '' : 's'} available for visualization.`, 'success');
            } catch (error) {
                console.error('Data Explorer query error:', error);
                setIndicator('error');
                setStatus(`Network error while executing query: ${error.message}`, 'error');
                resultsContainer.innerHTML = `<div class="de-empty-state" style="color:#dc2626;">❌ Network Error: ${escapeHtml(error.message)}</div>`;
            } finally {
                runButton.disabled = false;
                runButton.textContent = '▶️ Run Query';
            }
        }

        function exportResults() {
            if (!state.lastResults || !state.lastResults.length) {
                setStatus('No query results to export. Execute a query first.', 'warning');
                alert('No query results to export. Execute a query first.');
                return;
            }
            try {
                const columns = state.lastColumns && state.lastColumns.length ? state.lastColumns : Object.keys(state.lastResults[0]);
                let csvContent = columns.join(',') + '\n';
                state.lastResults.forEach(row => {
                    const values = columns.map(col => {
                        let value = row[col];
                        if (value === null || value === undefined) {
                            value = '';
                        } else if (typeof value === 'object') {
                            value = JSON.stringify(value);
                        }
                        let stringValue = String(value);
                        if (stringValue.includes(',')) {
                            stringValue = '"' + stringValue.replace(/"/g, '""') + '"';
                        }
                        return stringValue;
                    });
                    csvContent += values.join(',') + '\n';
                });
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                const url = URL.createObjectURL(blob);
                link.setAttribute('href', url);
                link.setAttribute('download', `query_results_${Date.now()}.csv`);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                setStatus('Exported results to CSV.', 'success');
            } catch (error) {
                console.error('Export error:', error);
                setStatus(`Failed to export results: ${error.message}`, 'error');
                alert('Failed to export results. Please try again.');
            }
        }

        function generateVisualization() {
            if (!state.lastResults || !state.lastResults.length) {
                setStatus('Run a query before generating a visualization.', 'warning');
                alert('No query results to visualize. Execute a query first.');
                return;
            }
            const data = state.lastResults;
            const columns = state.lastColumns && state.lastColumns.length ? state.lastColumns : Object.keys(data[0]);
            const type = chartTypeSelect ? chartTypeSelect.value : 'table';
            if (type === 'table') {
                visualizationContainer.innerHTML = renderResultsTable(data, columns);
                if (state.chartInstance) {
                    state.chartInstance.destroy();
                    state.chartInstance = null;
                }
                setStatus('Rendered table view in visualization pane.', 'success');
                return;
            }
            if (typeof Chart === 'undefined') {
                visualizationContainer.innerHTML = '<div class="de-empty-state" style="color:#d97706;">⚠️ Chart.js is unavailable for visualization.</div>';
                setStatus('Chart.js is unavailable. Unable to generate visualization.', 'warning');
                return;
            }
            const numericColumns = columns.filter(col => data.some(row => typeof row[col] === 'number' && !Number.isNaN(row[col])));
            if (!numericColumns.length) {
                visualizationContainer.innerHTML = '<div class="de-empty-state" style="color:#d97706;">⚠️ No numeric data found for visualization.</div>';
                setStatus('Unable to build chart because no numeric columns were returned.', 'warning');
                return;
            }
            const categoryColumns = columns.filter(col => data.some(row => typeof row[col] === 'string' && row[col]));
            const labels = data.map((row, index) => {
                if (categoryColumns.length) {
                    const value = row[categoryColumns[0]];
                    return value && String(value).length ? value : `Row ${index + 1}`;
                }
                return `Row ${index + 1}`;
            }).slice(0, 50);

            let chartConfig;
            if (type === 'pie') {
                const values = data.slice(0, 12).map(row => row[numericColumns[0]] || 0);
                chartConfig = {
                    type: 'pie',
                    data: {
                        labels: labels.slice(0, 12),
                        datasets: [{
                            label: numericColumns[0],
                            data: values,
                            backgroundColor: labels.slice(0, 12).map((_, idx) => `hsl(${(idx * 47) % 360} 85% 65%)`)
                        }]
                    }
                };
            } else if (type === 'scatter') {
                if (numericColumns.length < 2) {
                    visualizationContainer.innerHTML = '<div class="de-empty-state" style="color:#d97706;">⚠️ Scatter plots require at least two numeric columns.</div>';
                    setStatus('Scatter plot not generated. Select a dataset with two numeric columns.', 'warning');
                    return;
                }
                chartConfig = {
                    type: 'scatter',
                    data: {
                        datasets: [{
                            label: `${numericColumns[0]} vs ${numericColumns[1]}`,
                            data: data.slice(0, 200).map(row => ({
                                x: row[numericColumns[0]] || 0,
                                y: row[numericColumns[1]] || 0,
                                label: categoryColumns.length ? row[categoryColumns[0]] : undefined
                            })),
                            backgroundColor: 'rgba(37, 99, 235, 0.4)',
                            borderColor: '#2563eb'
                        }]
                    },
                    options: {
                        parsing: false,
                        scales: {
                            x: { title: { display: true, text: numericColumns[0] } },
                            y: { title: { display: true, text: numericColumns[1] } }
                        }
                    }
                };
            } else {
                const values = data.slice(0, 50).map(row => row[numericColumns[0]] || 0);
                chartConfig = {
                    type,
                    data: {
                        labels,
                        datasets: [{
                            label: numericColumns[0],
                            data: values,
                            backgroundColor: type === 'bar' ? 'rgba(16, 185, 129, 0.6)' : 'rgba(16, 185, 129, 0.3)',
                            borderColor: '#10b981',
                            borderWidth: 2,
                            fill: type === 'line'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: { display: true, text: numericColumns[0] }
                            },
                            x: {
                                title: { display: true, text: categoryColumns[0] || 'Data Points' }
                            }
                        }
                    }
                };
            }

            visualizationContainer.innerHTML = `
                <div style="margin-bottom:1rem; color:#059669; font-weight:600;">📊 Data Visualization (${type.toUpperCase()})</div>
                <div style="background:white; padding:1rem; border-radius:0.75rem; border:1px solid #e5e7eb; min-height:260px;">
                    <canvas id="de-chart" style="width:100%; height:320px;"></canvas>
                </div>
            `;
            const canvas = visualizationContainer.querySelector('#de-chart');
            if (!canvas) {
                return;
            }
            const ctx = canvas.getContext('2d');
            if (state.chartInstance) {
                state.chartInstance.destroy();
            }
            state.chartInstance = new Chart(ctx, chartConfig);
            setStatus(`Generated ${type.toUpperCase()} visualization using ${numericColumns[0]}.`, 'success');
        }

        function toggleAssist(forceOpen) {
            const shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : assistPanel.classList.contains('hidden');
            if (shouldOpen) {
                assistPanel.classList.remove('hidden');
                assistPanel.setAttribute('aria-hidden', 'false');
                if (assistToggle) assistToggle.setAttribute('aria-expanded', 'true');
                if (assistSearch) {
                    assistSearch.value = '';
                    filterAssist('');
                    setTimeout(() => assistSearch.focus(), 0);
                }
            } else {
                closeAssist();
            }
        }

        function closeAssist() {
            assistPanel.classList.add('hidden');
            assistPanel.setAttribute('aria-hidden', 'true');
            if (assistToggle) assistToggle.setAttribute('aria-expanded', 'false');
        }

        function filterAssist(term) {
            const chips = assistPanel.querySelectorAll('.de-assist-chip');
            const sections = assistPanel.querySelectorAll('.de-assist-section');
            const emptyState = assistPanel.querySelector('#de-assist-empty');
            const normalized = (term || '').toLowerCase();
            let visible = 0;
            chips.forEach(chip => {
                const searchable = `${chip.textContent} ${(chip.dataset.snippet || '')} ${(chip.dataset.template || '')}`.toLowerCase();
                const matches = !normalized || searchable.includes(normalized);
                chip.style.display = matches ? '' : 'none';
                if (matches) {
                    visible += 1;
                }
            });
            sections.forEach(section => {
                const hasVisible = Array.from(section.querySelectorAll('.de-assist-chip')).some(chip => chip.style.display !== 'none');
                section.style.display = hasVisible ? '' : 'none';
            });
            if (emptyState) {
                emptyState.classList.toggle('hidden', visible > 0);
            }
        }

        function handleShortcut(event) {
            const meta = event.metaKey || event.ctrlKey;
            if (meta && event.key === 'Enter') {
                if (document.activeElement === queryTextarea) {
                    event.preventDefault();
                    executeQuery();
                }
            }
            if (meta && (event.key === 'k' || event.key === 'K')) {
                event.preventDefault();
                toggleAssist();
            }
            if (event.key === 'Escape' && !assistPanel.classList.contains('hidden')) {
                event.preventDefault();
                closeAssist();
            }
        }

        function bindEvents() {
            root.querySelectorAll('.de-sidebar-chip[data-snippet]').forEach(button => {
                button.addEventListener('click', () => insertSnippet(button.dataset.snippet));
            });
            root.querySelectorAll('.de-sidebar-chip[data-contextual]').forEach(button => {
                button.addEventListener('click', () => {
                    const result = resolveContextualSnippet(button.dataset.contextual);
                    if (result && result.snippet) {
                        const label = button.dataset.label || 'Context helper';
                        const tableLabel = TABLE_LABELS[result.table] || result.table || 'current query';
                        insertSnippet(result.snippet, {
                            message: `Inserted ${label} using ${tableLabel}.`,
                            tone: 'success'
                        });
                    }
                });
            });
            root.querySelectorAll('.de-sidebar-chip[data-timerange]').forEach(button => {
                button.addEventListener('click', () => {
                    const result = resolveTimeRangeSnippet(button.dataset.timerange);
                    if (result && result.snippet) {
                        const label = button.dataset.label || 'time range';
                        insertFilterClause(result.snippet, {
                            label,
                            column: result.column
                        });
                    }
                });
            });
            root.querySelectorAll('.de-sidebar-chip[data-template]').forEach(button => {
                button.addEventListener('click', () => loadTemplate(button.dataset.template));
            });
            root.querySelectorAll('.de-assist-chip[data-snippet]').forEach(chip => {
                chip.addEventListener('click', () => insertSnippet(chip.dataset.snippet));
            });
            root.querySelectorAll('.de-assist-chip[data-template]').forEach(chip => {
                chip.addEventListener('click', () => loadTemplate(chip.dataset.template));
            });
            runButton.addEventListener('click', executeQuery);
            resetButton.addEventListener('click', () => {
                queryTextarea.value = DEFAULT_QUERY;
                queryTextarea.focus();
                queryTextarea.setSelectionRange(queryTextarea.value.length, queryTextarea.value.length);
                clearResults(true);
                setStatus('Editor reset to default query. Press ⌘⏎ / Ctrl+Enter to run.', 'info');
                closeAssist();
            });
            clearButton.addEventListener('click', () => clearResults());
            exportButton.addEventListener('click', exportResults);
            assistToggle.addEventListener('click', () => toggleAssist());
            assistClose.addEventListener('click', () => closeAssist());
            if (assistSearch) {
                assistSearch.addEventListener('input', event => filterAssist(event.target.value || ''));
            }
            generateChartButton.addEventListener('click', generateVisualization);
            if (referenceButton) {
                referenceButton.addEventListener('click', () => window.open('/docs/data-explorer-reference', '_blank'));
            }
            document.addEventListener('keydown', handleShortcut);
            document.addEventListener('click', event => {
                if (!assistPanel.contains(event.target) && event.target !== assistToggle && !assistPanel.classList.contains('hidden')) {
                    closeAssist();
                }
            });
        }

        bindEvents();
        setStatus('Compose a query, then press ⌘⏎ / Ctrl+Enter to execute.', 'info');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDataExplorer);
    } else {
        initDataExplorer();
    }
})();
