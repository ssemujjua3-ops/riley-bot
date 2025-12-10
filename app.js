// app.js

class TradingBotApp {
    constructor() {
        this.updateInterval = null;
        this.chartData = null;
        this.modal = document.getElementById('tournament-modal');
        this.tournamentListBody = document.getElementById('tournament-list-body');
        this.init();
    }

    init() {
        this.bindEvents();
        this.startUpdates();
        this.initChart();
        // Event listeners for the new modal
        const closeBtn = this.modal ? this.modal.querySelector('.close-btn') : null;
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideTournamentModal());
        }
        window.addEventListener('click', (event) => {
            if (this.modal && event.target === this.modal) {
                this.hideTournamentModal();
            }
        });
    }

    bindEvents() {
        // Existing control buttons
        document.getElementById('btn-start').addEventListener('click', () => this.controlBot('start'));
        document.getElementById('btn-stop').addEventListener('click', () => this.controlBot('stop'));
        document.getElementById('btn-trade').addEventListener('click', () => this.controlBot('start_trading'));
        document.getElementById('btn-stop-trade').addEventListener('click', () => this.controlBot('stop_trading'));
        
        // NEW Tournament button
        document.getElementById('btn-show-tournaments').addEventListener('click', () => this.showTournamentModal());
        
        // Existing settings
        document.getElementById('asset-select').addEventListener('change', (e) => {
            this.setSetting('asset', e.target.value);
        });
        
        document.getElementById('timeframe-select').addEventListener('change', (e) => {
            this.setSetting('timeframe', e.target.value);
        });
        
        const slider = document.getElementById('confidence-slider');
        const confidenceValue = document.getElementById('confidence-value');
        slider.addEventListener('input', (e) => {
            confidenceValue.textContent = e.target.value + '%';
        });
        slider.addEventListener('change', (e) => {
            this.setSetting('min_confidence', e.target.value / 100);
        });

        // PDF upload logic (placeholder)
        document.getElementById('btn-upload-pdf').addEventListener('click', () => {
            document.getElementById('pdf-input').click();
        });
        document.getElementById('pdf-input').addEventListener('change', (e) => this.uploadPDF(e.target.files[0]));
    }

    startUpdates() {
        this.fetchStatus();
        this.fetchMarketAnalysis();
        this.updateInterval = setInterval(() => {
            this.fetchStatus();
            this.fetchMarketAnalysis();
        }, 3000);
    }

    // --- API CALLS ---

    async controlBot(action, payload = {}) {
        const response = await fetch('/api/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, ...payload })
        });
        const data = await response.json();
        alert(data.message);
        this.fetchStatus();
    }
    
    async setSetting(setting, value) {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ setting, value })
        });
        const data = await response.json();
        console.log(data.message);
        this.fetchStatus();
    }

    async fetchStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            this.updateDashboard(data);
            this.fetchTradeStats();
        } catch (error) {
            console.error('Error fetching status:', error);
        }
    }

    async fetchMarketAnalysis() {
        try {
            const response = await fetch('/api/market/analysis');
            const data = await response.json();
            this.updateMarketAnalysis(data);
            this.updateChart(data);
        } catch (error) {
            console.error('Error fetching market analysis:', error);
        }
    }
    
    async fetchTournaments() {
        const statusMessage = document.getElementById('tournament-status-message');
        if (statusMessage) statusMessage.textContent = 'Loading tournaments...';
        this.tournamentListBody.innerHTML = '';
        try {
            const response = await fetch('/api/tournaments/free');
            const tournaments = await response.json();
            if (statusMessage) statusMessage.textContent = '';
            this.renderTournamentList(tournaments);
        } catch (error) {
            console.error('Error fetching tournaments:', error);
            if (statusMessage) statusMessage.textContent = 'Failed to fetch tournaments. Check bot connection.';
        }
    }

    async joinTournament(tournamentId) {
        if (!confirm('Are you sure you want to join this tournament?')) return;
        
        const statusMessage = document.getElementById('tournament-status-message');
        if (statusMessage) statusMessage.textContent = `Attempting to join tournament ${tournamentId}...`;
        
        const joinButton = document.querySelector(`[data-tournament-id="${tournamentId}"]`);
        if (joinButton) {
            joinButton.disabled = true;
            joinButton.textContent = 'Joining...';
        }
        
        const response = await fetch('/api/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'join_tournament', id: tournamentId })
        });
        const data = await response.json();

        if (response.ok) {
            alert(data.message);
            this.fetchTournaments(); // Refresh the list
        } else {
            alert(`Error: ${data.message}`);
            if (joinButton) {
                joinButton.disabled = false;
                joinButton.textContent = 'Join';
            }
        }
        if (statusMessage) statusMessage.textContent = '';
    }

    async fetchTradeStats() {
        try {
            const response = await fetch('/api/trades/history');
            const data = await response.json();
            this.updateTradeStats(data);
        } catch (error) {
            console.error('Error fetching trade stats:', error);
        }
    }
    
    // --- UI UPDATES ---

    updateDashboard(data) {
        // Status Indicators
        document.getElementById('bot-status').className = `status-indicator ${data.is_running ? 'status-on' : 'status-off'}`;
        document.getElementById('bot-status').textContent = `Bot: ${data.is_running ? 'Running' : 'Stopped'}`;
        
        document.getElementById('conn-status').className = `status-indicator ${data.connected ? 'status-on' : 'status-off'}`;
        document.getElementById('conn-status').textContent = `Connection: ${data.connected ? (data.simulation_mode ? 'Simulated' : 'Live') : 'Disconnected'}`;
        
        document.getElementById('mode-status').className = `status-indicator ${data.simulation_mode ? 'status-sim' : 'status-live'}`;
        document.getElementById('mode-status').textContent = `Mode: ${data.simulation_mode ? 'Simulation' : 'Live'}`;
        
        // Stats Panel
        document.getElementById('stat-balance').textContent = `$${data.balance.toFixed(2)}`;
        document.getElementById('stat-total-trades').textContent = data.total_trades;
        
        // Agent Stats
        document.getElementById('stat-training-samples').textContent = data.agent_stats.total_experiences;
        document.getElementById('stat-agent-win-rate').textContent = `${(data.agent_stats.win_rate * 100).toFixed(2)}%`;
        document.getElementById('stat-learned-concepts').textContent = data.knowledge_stats.total_concepts;

        // Settings update (to reflect current bot state)
        document.getElementById('chart-asset').textContent = data.current_asset;
        document.getElementById('chart-timeframe').textContent = `${data.current_timeframe / 60} Min`;
    }
    
    updateTradeStats(data) {
        document.getElementById('stat-total-wins').textContent = data.total_wins;
        document.getElementById('stat-win-rate').textContent = `${(data.win_rate * 100).toFixed(2)}%`;
        document.getElementById('stat-pending-trades').textContent = data.pending_trades;
        
        // Update Recent Trades List
        const tbody = document.getElementById('trades-body');
        tbody.innerHTML = '';
        data.recent_trades.forEach(trade => {
            const row = tbody.insertRow();
            row.className = trade.outcome ? (trade.outcome === 'win' ? 'trade-win' : 'trade-loss') : '';
            row.insertCell().textContent = new Date(trade.created_at).toLocaleTimeString();
            row.insertCell().textContent = trade.asset;
            row.insertCell().textContent = `$${trade.amount.toFixed(2)}`;
            row.insertCell().textContent = trade.direction;
            row.insertCell().textContent = trade.outcome || 'Pending';
        });
    }

    updateMarketAnalysis(analysis) {
        document.getElementById('market-trend').textContent = analysis.trend.toUpperCase();
        document.getElementById('market-patterns').textContent = analysis.patterns.length;
        
        const support = analysis.levels.support ? analysis.levels.support.length : 0;
        const resistance = analysis.levels.resistance ? analysis.levels.resistance.length : 0;
        document.getElementById('market-levels').textContent = `${support} Support, ${resistance} Resistance`;

        const container = document.getElementById('market-data-container');
        container.innerHTML = '';
        
        // Add detailed patterns
        if (analysis.patterns.length > 0) {
            const p = document.createElement('p');
            p.innerHTML = `**Patterns (${analysis.patterns.length}):** ${analysis.patterns.map(p => `${p.pattern} (${p.signal}/${(p.strength*100).toFixed(0)}%)`).join(', ')}`;
            container.appendChild(p);
        }
        
        // Add detailed indicators (Example: RSI)
        if (analysis.indicators.rsi) {
            const p = document.createElement('p');
            p.innerHTML = `**RSI (14):** ${(analysis.indicators.rsi.value).toFixed(2)} (${analysis.indicators.rsi.signal || 'Neutral'})`;
            container.appendChild(p);
        }
        
        // Add detailed levels (Example: nearest support/resistance)
        if (support > 0 || resistance > 0) {
            const p = document.createElement('p');
            const nearestS = support > 0 ? `$${analysis.levels.support[0].price.toFixed(5)}` : 'None';
            const nearestR = resistance > 0 ? `$${analysis.levels.resistance[0].price.toFixed(5)}` : 'None';
            p.innerHTML = `**Nearest Levels:** S: ${nearestS}, R: ${nearestR}`;
            container.appendChild(p);
        }
    }

    // --- CHART LOGIC ---
    initChart() {
        const layout = {
            title: 'Candlestick Chart',
            xaxis: {
                title: 'Candle Index (Recent on Left)',
                type: 'category',
                rangeslider: { visible: false }
            },
            yaxis: {
                title: 'Price',
                autorange: true,
                fixedrange: false
            },
            autosize: true,
            plot_bgcolor: 'rgba(0,0,0,0.2)',
            paper_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#e4e4e4' },
            margin: { t: 30, r: 30, b: 30, l: 50 },
            xaxis: { showgrid: false, color: '#666' },
            yaxis: { showgrid: true, gridcolor: 'rgba(255,255,255,0.1)', color: '#666' }
        };

        Plotly.newPlot('market-chart', [], layout, { responsive: true });
    }

    updateChart(analysis) {
        if (!analysis.candles || analysis.candles.length === 0) return;

        // Use up to 50 candles, reverse order for display (most recent on the left index=0)
        const candles = analysis.candles.slice(0, 50).reverse();
        
        const trace = {
            x: candles.map((_, i) => i),
            open: candles.map(c => c.open),
            high: candles.map(c => c.high),
            low: candles.map(c => c.low),
            close: candles.map(c => c.close),
            type: 'candlestick',
            increasing: { line: { color: '#00ff88' } },
            decreasing: { line: { color: '#ff4444' } }
        };

        Plotly.react('market-chart', [trace], {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0.2)',
            font: { color: '#e4e4e4' },
            margin: { t: 30, r: 30, b: 30, l: 50 },
            xaxis: { showgrid: false, color: '#666', title: 'Candle Index' },
            yaxis: { showgrid: true, gridcolor: 'rgba(255,255,255,0.1)', color: '#666', title: 'Price' }
        });
    }
    
    // --- SETTINGS PLACEHOLDERS ---
    setAsset(asset) { this.setSetting('current_asset', asset); }
    setTimeframe(timeframe) { this.setSetting('current_timeframe', parseInt(timeframe)); }
    setConfidence(confidence) { this.setSetting('min_confidence', parseFloat(confidence)); }
    uploadPDF(file) { 
        document.getElementById('upload-status').textContent = `Uploading ${file.name}... (Processing not yet implemented)`;
        // Real implementation would use fetch API to POST the file to /api/learn/pdf
    }


    // --- NEW TOURNAMENT MODAL LOGIC ---

    showTournamentModal() {
        if (!this.modal) return;
        this.fetchTournaments();
        this.modal.style.display = 'flex';
    }

    hideTournamentModal() {
        if (!this.modal) return;
        this.modal.style.display = 'none';
    }

    renderTournamentList(tournaments) {
        if (!this.tournamentListBody) return;
        this.tournamentListBody.innerHTML = '';

        if (tournaments.length === 0) {
            this.tournamentListBody.innerHTML = '<tr><td colspan="5" class="no-data">No active free tournaments found.</td></tr>';
            return;
        }

        tournaments.forEach(t => {
            const row = this.tournamentListBody.insertRow();
            
            // Name
            row.insertCell().textContent = t.name;
            
            // Prize Pool
            row.insertCell().textContent = `$${t.prize_pool}`;
            
            // Participants
            row.insertCell().textContent = t.participants;
            
            // Status
            row.insertCell().textContent = t.status.charAt(0).toUpperCase() + t.status.slice(1).replace('_', ' ');
            
            // Action Button
            const actionCell = row.insertCell();
            const button = document.createElement('button');
            button.className = 'btn-join';
            button.textContent = 'Join';
            button.setAttribute('data-tournament-id', t.id); // Store ID for click handler
            button.onclick = () => this.joinTournament(t.id);
            actionCell.appendChild(button);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.tradingBotApp = new TradingBotApp();
});
