/**
 * BTC Perpetual Elite Trader - Dashboard JavaScript
 * Sistema de monitoramento em tempo real
 */

class TradingDashboard {
    constructor() {
        this.socket = null;
        this.charts = {};
        this.isConnected = false;
        this.lastUpdate = null;
        this.data = {};
        
        // Configurações
        this.updateInterval = 1000; // 1 segundo
        this.maxDataPoints = 100;
        
        // Inicializar
        this.init();
    }
    
    init() {
        console.log('🚀 Inicializando Dashboard...');
        
        // Conectar WebSocket
        this.connectWebSocket();
        
        // Configurar event listeners
        this.setupEventListeners();
        
        // Inicializar gráficos
        this.initializeCharts();
        
        // Carregar dados iniciais
        this.loadInitialData();
        
        console.log('✅ Dashboard inicializado');
    }
    
    connectWebSocket() {
        try {
            this.socket = io();
            
            this.socket.on('connect', () => {
                console.log('📡 Conectado ao servidor');
                this.isConnected = true;
                this.updateConnectionStatus('connected');
                this.socket.emit('request_update');
            });
            
            this.socket.on('disconnect', () => {
                console.log('📡 Desconectado do servidor');
                this.isConnected = false;
                this.updateConnectionStatus('disconnected');
            });
            
            this.socket.on('dashboard_update', (data) => {
                this.handleDataUpdate(data);
            });
            
            this.socket.on('error', (error) => {
                console.error('❌ Erro WebSocket:', error);
                this.showNotification('Erro de conexão', 'error');
            });
            
        } catch (error) {
            console.error('❌ Erro ao conectar WebSocket:', error);
            this.updateConnectionStatus('error');
        }
    }
    
    setupEventListeners() {
        // Botões de controle
        document.getElementById('start-trading')?.addEventListener('click', () => {
            this.startTrading();
        });
        
        document.getElementById('stop-trading')?.addEventListener('click', () => {
            this.stopTrading();
        });
        
        // Atualização manual
        document.addEventListener('keydown', (e) => {
            if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
                e.preventDefault();
                this.refreshData();
            }
        });
        
        // Resize dos gráficos
        window.addEventListener('resize', () => {
            this.resizeCharts();
        });
    }
    
    initializeCharts() {
        // Configuração padrão dos gráficos
        Chart.defaults.color = '#9ca3af';
        Chart.defaults.borderColor = '#374151';
        Chart.defaults.backgroundColor = '#1f2937';
        
        // Gráfico de PnL
        this.initializePnLChart();
        
        // Gráfico de Saldo
        this.initializeBalanceChart();
    }
    
    initializePnLChart() {
        const ctx = document.getElementById('pnl-chart');
        if (!ctx) return;
        
        this.charts.pnl = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'PnL Acumulado',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute'
                        },
                        grid: {
                            color: '#374151'
                        }
                    },
                    y: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }
    
    initializeBalanceChart() {
        const ctx = document.getElementById('balance-chart');
        if (!ctx) return;
        
        this.charts.balance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Saldo',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute'
                        },
                        grid: {
                            color: '#374151'
                        }
                    },
                    y: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    }
    
    async loadInitialData() {
        try {
            // Carregar status
            const statusResponse = await fetch('/api/status');
            const statusData = await statusResponse.json();
            
            if (statusData.success) {
                this.updateSystemStatus(statusData.data);
            }
            
            // Carregar métricas
            const metricsResponse = await fetch('/api/metrics');
            const metricsData = await metricsResponse.json();
            
            if (metricsData.success) {
                this.updateMetrics(metricsData.data);
            }
            
            // Carregar estratégias
            const strategiesResponse = await fetch('/api/strategies');
            const strategiesData = await strategiesResponse.json();
            
            if (strategiesData.success) {
                this.updateStrategies(strategiesData.data);
            }
            
        } catch (error) {
            console.error('❌ Erro ao carregar dados iniciais:', error);
        }
    }
    
    handleDataUpdate(data) {
        console.log('📊 Dados atualizados:', data);
        
        this.data = data;
        this.lastUpdate = new Date();
        
        // Atualizar interface
        if (data.system_status) {
            this.updateSystemStatus(data.system_status);
        }
        
        if (data.metrics) {
            this.updateMetrics(data.metrics);
        }
        
        if (data.strategies) {
            this.updateStrategies(data.strategies);
        }
        
        if (data.positions) {
            this.updatePositions(data.positions);
        }
        
        if (data.performance) {
            this.updatePerformance(data.performance);
        }
        
        // Atualizar timestamp
        this.updateLastUpdateTime();
    }
    
    updateSystemStatus(status) {
        // Status indicator
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        
        if (status.running) {
            statusIndicator?.classList.remove('bg-gray-500', 'bg-red-500');
            statusIndicator?.classList.add('bg-green-500', 'status-online');
            if (statusText) statusText.textContent = 'Online';
        } else {
            statusIndicator?.classList.remove('bg-green-500', 'bg-gray-500');
            statusIndicator?.classList.add('bg-red-500', 'status-offline');
            if (statusText) statusText.textContent = 'Offline';
        }
        
        // Saldo atual
        const balanceElement = document.getElementById('current-balance');
        if (balanceElement) {
            balanceElement.textContent = this.formatCurrency(status.current_balance || 0);
        }
        
        // PnL Total
        const pnlElement = document.getElementById('total-pnl');
        if (pnlElement) {
            const pnl = status.total_pnl || 0;
            pnlElement.textContent = this.formatCurrency(pnl);
            pnlElement.className = pnl >= 0 ? 'text-2xl font-bold text-green-400' : 'text-2xl font-bold text-red-400';
        }
        
        // Posições ativas
        const positionsElement = document.getElementById('active-positions');
        if (positionsElement) {
            positionsElement.textContent = status.active_positions || 0;
        }
        
        // Total de trades
        const tradesElement = document.getElementById('total-trades');
        if (tradesElement) {
            tradesElement.textContent = status.total_trades || 0;
        }
        
        // Sharpe Ratio
        const sharpeElement = document.getElementById('sharpe-ratio');
        if (sharpeElement) {
            sharpeElement.textContent = (status.sharpe_ratio || 0).toFixed(2);
        }
        
        // Drawdown
        const drawdownElement = document.getElementById('drawdown');
        if (drawdownElement) {
            const drawdown = (status.max_drawdown || 0) * 100;
            drawdownElement.innerHTML = `<i class="fas fa-arrow-down mr-1"></i>${drawdown.toFixed(2)}% drawdown`;
        }
        
        // Atualizar gráficos
        this.updateCharts(status);
    }
    
    updateMetrics(metrics) {
        // Implementar atualização de métricas detalhadas
        console.log('📈 Métricas atualizadas:', metrics);
    }
    
    updateStrategies(strategies) {
        const strategiesList = document.getElementById('strategies-list');
        if (!strategiesList) return;
        
        strategiesList.innerHTML = '';
        
        Object.entries(strategies).forEach(([name, strategy]) => {
            const strategyElement = this.createStrategyElement(name, strategy);
            strategiesList.appendChild(strategyElement);
        });
    }
    
    createStrategyElement(name, strategy) {
        const div = document.createElement('div');
        div.className = 'flex items-center justify-between p-3 bg-gray-700 rounded-lg';
        
        const statusClass = strategy.running ? 'strategy-active' : 'strategy-inactive';
        const statusIcon = strategy.running ? 'fa-play' : 'fa-pause';
        
        div.innerHTML = `
            <div class="flex items-center space-x-3">
                <div class="w-3 h-3 rounded-full ${statusClass}"></div>
                <div>
                    <div class="font-medium">${this.formatStrategyName(name)}</div>
                    <div class="text-sm text-gray-400">
                        Alocação: ${(strategy.allocation * 100).toFixed(1)}% | 
                        PnL: ${this.formatCurrency(strategy.metrics?.total_pnl || 0)}
                    </div>
                </div>
            </div>
            <div class="flex items-center space-x-2">
                <span class="text-sm ${strategy.metrics?.win_rate >= 0.6 ? 'text-green-400' : 'text-yellow-400'}">
                    ${((strategy.metrics?.win_rate || 0) * 100).toFixed(1)}%
                </span>
                <button class="text-gray-400 hover:text-white" onclick="dashboard.toggleStrategy('${name}')">
                    <i class="fas ${statusIcon}"></i>
                </button>
            </div>
        `;
        
        return div;
    }
    
    updatePositions(positions) {
        const positionsList = document.getElementById('positions-list');
        if (!positionsList) return;
        
        positionsList.innerHTML = '';
        
        if (!positions || positions.length === 0) {
            positionsList.innerHTML = '<div class="text-gray-400 text-center py-4">Nenhuma posição ativa</div>';
            return;
        }
        
        positions.forEach(position => {
            const positionElement = this.createPositionElement(position);
            positionsList.appendChild(positionElement);
        });
    }
    
    createPositionElement(position) {
        const div = document.createElement('div');
        div.className = 'flex items-center justify-between p-3 bg-gray-700 rounded-lg';
        
        const sideClass = position.side === 'long' ? 'text-green-400' : 'text-red-400';
        const sideIcon = position.side === 'long' ? 'fa-arrow-up' : 'fa-arrow-down';
        
        div.innerHTML = `
            <div class="flex items-center space-x-3">
                <i class="fas ${sideIcon} ${sideClass}"></i>
                <div>
                    <div class="font-medium">${position.symbol}</div>
                    <div class="text-sm text-gray-400">
                        ${position.quantity} @ ${this.formatCurrency(position.entry_price)}
                    </div>
                </div>
            </div>
            <div class="text-right">
                <div class="font-medium ${position.pnl >= 0 ? 'text-green-400' : 'text-red-400'}">
                    ${this.formatCurrency(position.pnl)}
                </div>
                <div class="text-sm text-gray-400">
                    ${((position.pnl / (position.quantity * position.entry_price)) * 100).toFixed(2)}%
                </div>
            </div>
        `;
        
        return div;
    }
    
    updatePerformance(performance) {
        // Implementar atualização de performance
        console.log('🎯 Performance atualizada:', performance);
    }
    
    updateCharts(status) {
        const now = new Date();
        
        // Atualizar gráfico de PnL
        if (this.charts.pnl) {
            const pnlData = this.charts.pnl.data;
            pnlData.labels.push(now);
            pnlData.datasets[0].data.push(status.total_pnl || 0);
            
            // Manter apenas os últimos pontos
            if (pnlData.labels.length > this.maxDataPoints) {
                pnlData.labels.shift();
                pnlData.datasets[0].data.shift();
            }
            
            this.charts.pnl.update('none');
        }
        
        // Atualizar gráfico de saldo
        if (this.charts.balance) {
            const balanceData = this.charts.balance.data;
            balanceData.labels.push(now);
            balanceData.datasets[0].data.push(status.current_balance || 0);
            
            // Manter apenas os últimos pontos
            if (balanceData.labels.length > this.maxDataPoints) {
                balanceData.labels.shift();
                balanceData.datasets[0].data.shift();
            }
            
            this.charts.balance.update('none');
        }
    }
    
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('status-indicator');
        const textElement = document.getElementById('status-text');
        
        if (!statusElement || !textElement) return;
        
        statusElement.className = 'w-3 h-3 rounded-full';
        
        switch (status) {
            case 'connected':
                statusElement.classList.add('bg-green-500', 'status-online');
                textElement.textContent = 'Conectado';
                break;
            case 'disconnected':
                statusElement.classList.add('bg-red-500', 'status-offline');
                textElement.textContent = 'Desconectado';
                break;
            case 'connecting':
                statusElement.classList.add('bg-yellow-500', 'status-warning');
                textElement.textContent = 'Conectando...';
                break;
            default:
                statusElement.classList.add('bg-gray-500');
                textElement.textContent = 'Erro';
        }
    }
    
    updateLastUpdateTime() {
        const element = document.getElementById('last-update');
        if (element && this.lastUpdate) {
            element.textContent = this.lastUpdate.toLocaleTimeString();
        }
    }
    
    async startTrading() {
        try {
            const response = await fetch('/api/control/start', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Trading iniciado', 'success');
            } else {
                this.showNotification('Erro ao iniciar trading: ' + data.error, 'error');
            }
        } catch (error) {
            this.showNotification('Erro de conexão', 'error');
        }
    }
    
    async stopTrading() {
        try {
            const response = await fetch('/api/control/stop', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Trading pausado', 'warning');
            } else {
                this.showNotification('Erro ao parar trading: ' + data.error, 'error');
            }
        } catch (error) {
            this.showNotification('Erro de conexão', 'error');
        }
    }
    
    async toggleStrategy(strategyName) {
        // Implementar toggle de estratégia
        console.log('🔄 Toggle estratégia:', strategyName);
    }
    
    refreshData() {
        if (this.socket && this.isConnected) {
            this.socket.emit('request_update');
            this.showNotification('Dados atualizados', 'info');
        } else {
            this.loadInitialData();
        }
    }
    
    resizeCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.resize();
            }
        });
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'USD'
        }).format(value);
    }
    
    formatStrategyName(name) {
        return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    formatPercentage(value) {
        return (value * 100).toFixed(2) + '%';
    }
}

// Inicializar dashboard quando página carregar
let dashboard;

document.addEventListener('DOMContentLoaded', () => {
    dashboard = new TradingDashboard();
});

// Expor dashboard globalmente para debugging
window.dashboard = dashboard;

