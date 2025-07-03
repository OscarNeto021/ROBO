"""
Dashboard Server - Servidor web para monitoramento em tempo real
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import threading
import psutil

from ..core.logger import get_trading_logger
from ..core.metrics_exporter import MetricsExporter, AlertManager

logger = get_trading_logger(__name__)

class DashboardServer:
    """
    Servidor web para dashboard de monitoramento
    
    Funcionalidades:
    - Dashboard em tempo real
    - Métricas de performance
    - Gráficos interativos
    - Controle de estratégias
    - Logs em tempo real
    - WebSocket para atualizações
    - Exportação de métricas para Prometheus/Grafana
    """
    
    def __init__(self, system_manager, port: int = 8080, metrics_port: int = 8000):
        """
        Inicializa o servidor do dashboard
        
        Args:
            system_manager: Gerenciador do sistema
            port: Porta do servidor
            metrics_port: Porta para exportação de métricas Prometheus
        """
        self.system_manager = system_manager
        self.port = port
        self.metrics_port = metrics_port
        
        # Inicializar exportador de métricas
        self.metrics_exporter = MetricsExporter(port=metrics_port)
        
        # Inicializar gerenciador de alertas
        self.alert_manager = AlertManager(
            metrics_exporter=self.metrics_exporter,
            drawdown_threshold=15.0,
            daily_loss_threshold=5.0,
            error_rate_threshold=10,
            latency_threshold=1.0
        )
        
        # Criar aplicação Flask
        self.app = Flask(
            __name__,
            template_folder='../../dashboard/templates',
            static_folder='../../dashboard/static'
        )
        
        # Configurar CORS
        CORS(self.app, origins="*")
        
        # Configurar SocketIO
        self.socketio = SocketIO(
            self.app, 
            cors_allowed_origins="*",
            async_mode='threading'
        )
        
        # Estado do servidor
        self.is_running = False
        self.server_thread: Optional[threading.Thread] = None
        
        # Cache de dados
        self.data_cache: Dict[str, Any] = {}
        self.last_update = datetime.now()
        
        # Configurar rotas
        self._setup_routes()
        self._setup_websocket_events()
        
        logger.info(f"Dashboard Server configurado na porta {port} (métricas na porta {metrics_port})")
    
    def _setup_routes(self):
        """
        Configura rotas da aplicação
        """
        
        @self.app.route('/')
        def dashboard():
            """Página principal do dashboard"""
            return render_template('dashboard.html')
        
        @self.app.route('/api/status')
        def get_status():
            """API para status do sistema"""
            try:
                if self.system_manager:
                    status = self.system_manager.get_status()
                    return jsonify({
                        'success': True,
                        'data': {
                            'running': status.running,
                            'uptime': str(status.uptime),
                            'total_trades': status.total_trades,
                            'active_positions': status.active_positions,
                            'current_balance': status.current_balance,
                            'total_pnl': status.total_pnl,
                            'daily_pnl': status.daily_pnl,
                            'max_drawdown': status.max_drawdown,
                            'sharpe_ratio': status.sharpe_ratio
                        }
                    })
                else:
                    return jsonify({'success': False, 'error': 'Sistema não inicializado'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/metrics')
        def get_metrics():
            """API para métricas do sistema"""
            try:
                if self.system_manager:
                    metrics = asyncio.run(self.system_manager.get_system_metrics())
                    return jsonify({'success': True, 'data': metrics})
                else:
                    return jsonify({'success': False, 'error': 'Sistema não inicializado'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/prometheus')
        def get_prometheus_info():
            """API para informações do Prometheus"""
            try:
                return jsonify({
                    'success': True, 
                    'data': {
                        'metrics_url': f'http://localhost:{self.metrics_port}/metrics',
                        'grafana_setup': {
                            'datasource': {
                                'name': 'BTC Elite Prometheus',
                                'type': 'prometheus',
                                'url': f'http://localhost:{self.metrics_port}'
                            },
                            'dashboard_import': 'https://grafana.com/grafana/dashboards/1860'
                        }
                    }
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/alerts')
        def get_alerts():
            """API para alertas ativos"""
            try:
                alerts = self.alert_manager.get_active_alerts()
                return jsonify({'success': True, 'data': alerts})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/strategies')
        def get_strategies():
            """API para status das estratégias"""
            try:
                if self.system_manager and self.system_manager.strategy_manager:
                    strategies = self.system_manager.strategy_manager.get_all_strategies_status()
                    return jsonify({'success': True, 'data': strategies})
                else:
                    return jsonify({'success': False, 'error': 'Strategy Manager não disponível'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/performance')
        def get_performance():
            """API para dados de performance"""
            try:
                if self.system_manager and self.system_manager.strategy_manager:
                    performance = asyncio.run(self.system_manager.strategy_manager.get_performance_metrics())
                    return jsonify({'success': True, 'data': performance})
                else:
                    return jsonify({'success': False, 'error': 'Dados não disponíveis'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/trades')
        def get_trades():
            """API para histórico de trades"""
            try:
                # Implementar obtenção de trades
                trades = []  # Placeholder
                return jsonify({'success': True, 'data': trades})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/positions')
        def get_positions():
            """API para posições ativas"""
            try:
                if self.system_manager and self.system_manager.execution_engine:
                    positions = asyncio.run(self.system_manager.execution_engine.get_positions())
                    return jsonify({'success': True, 'data': positions})
                else:
                    return jsonify({'success': False, 'error': 'Execution Engine não disponível'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/control/start', methods=['POST'])
        def start_trading():
            """API para iniciar trading"""
            try:
                if self.system_manager and self.system_manager.strategy_manager:
                    asyncio.run(self.system_manager.strategy_manager.resume_trading())
                    return jsonify({'success': True, 'message': 'Trading iniciado'})
                else:
                    return jsonify({'success': False, 'error': 'Sistema não disponível'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/control/stop', methods=['POST'])
        def stop_trading():
            """API para parar trading"""
            try:
                if self.system_manager and self.system_manager.strategy_manager:
                    asyncio.run(self.system_manager.strategy_manager.pause_trading())
                    return jsonify({'success': True, 'message': 'Trading pausado'})
                else:
                    return jsonify({'success': False, 'error': 'Sistema não disponível'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/control/strategy/<strategy_name>/<action>', methods=['POST'])
        def control_strategy(strategy_name: str, action: str):
            """API para controlar estratégias individuais"""
            try:
                if not self.system_manager or not self.system_manager.strategy_manager:
                    return jsonify({'success': False, 'error': 'Sistema não disponível'})
                
                strategy_manager = self.system_manager.strategy_manager
                
                if action == 'start':
                    # Implementar start de estratégia específica
                    return jsonify({'success': True, 'message': f'Estratégia {strategy_name} iniciada'})
                elif action == 'stop':
                    # Implementar stop de estratégia específica
                    return jsonify({'success': True, 'message': f'Estratégia {strategy_name} parada'})
                else:
                    return jsonify({'success': False, 'error': 'Ação inválida'})
                    
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
    
    def _setup_websocket_events(self):
        """
        Configura eventos WebSocket
        """
        
        @self.socketio.on('connect')
        def handle_connect():
            """Cliente conectado"""
            logger.info("📡 Cliente conectado ao dashboard")
            emit('connected', {'message': 'Conectado ao dashboard'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Cliente desconectado"""
            logger.info("📡 Cliente desconectado do dashboard")
        
        @self.socketio.on('request_update')
        def handle_request_update():
            """Cliente solicitou atualização"""
            try:
                data = self._get_dashboard_data()
                emit('dashboard_update', data)
            except Exception as e:
                emit('error', {'message': str(e)})
    
    async def start(self):
        """
        Inicia o servidor do dashboard
        """
        try:
            logger.info(f"🚀 Iniciando Dashboard Server na porta {self.port}...")
            
            # Iniciar exportador de métricas Prometheus
            self.metrics_exporter.start_server()
            logger.info(f"📊 Métricas Prometheus disponíveis em http://localhost:{self.metrics_port}/metrics")
            
            # Iniciar servidor em thread separada
            self.server_thread = threading.Thread(
                target=self._run_server,
                daemon=True
            )
            self.server_thread.start()
            
            # Iniciar task de atualização
            asyncio.create_task(self._update_loop())
            
            self.is_running = True
            logger.info(f"✅ Dashboard disponível em http://localhost:{self.port}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar dashboard: {e}")
    
    async def stop(self):
        """
        Para o servidor do dashboard
        """
        try:
            logger.info("🛑 Parando Dashboard Server...")
            
            self.is_running = False
            
            # Parar SocketIO
            if self.socketio:
                self.socketio.stop()
            
            logger.info("✅ Dashboard Server parado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar dashboard: {e}")
    
    def _run_server(self):
        """
        Executa servidor Flask
        """
        try:
            self.socketio.run(
                self.app,
                host='0.0.0.0',
                port=self.port,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"❌ Erro no servidor: {e}")
    
    async def _update_loop(self):
        """
        Loop de atualização de dados
        """
        while self.is_running:
            try:
                # Atualizar dados do dashboard
                data = self._get_dashboard_data()
                self.data_cache = data
                self.last_update = datetime.now()
                
                # Enviar atualização via WebSocket
                self.socketio.emit('dashboard_update', data)
                
                # Atualizar métricas Prometheus
                self._update_prometheus_metrics(data)
                
                # Verificar alertas
                self._check_alerts(data)
                
                # Enviar métricas para Pushgateway (se configurado)
                self.metrics_exporter.push_metrics()
                
                # Aguardar próxima atualização
                await asyncio.sleep(1)  # Atualizar a cada segundo
                
            except Exception as e:
                logger.error(f"❌ Erro no loop de atualização: {e}")
                await asyncio.sleep(5)
    
    def _get_dashboard_data(self) -> Dict[str, Any]:
        """
        Obtém dados para o dashboard
        
        Returns:
            Dict: Dados do dashboard
        """
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'system_status': {},
                'metrics': {},
                'strategies': {},
                'performance': {},
                'positions': [],
                'recent_trades': []
            }
            
            if self.system_manager:
                # Status do sistema
                status = self.system_manager.get_status()
                data['system_status'] = {
                    'running': status.running,
                    'uptime': str(status.uptime),
                    'total_trades': status.total_trades,
                    'active_positions': status.active_positions,
                    'current_balance': status.current_balance,
                    'total_pnl': status.total_pnl,
                    'daily_pnl': status.daily_pnl,
                    'max_drawdown': status.max_drawdown,
                    'sharpe_ratio': status.sharpe_ratio
                }
                
                # Métricas do sistema
                try:
                    metrics = asyncio.run(self.system_manager.get_system_metrics())
                    data['metrics'] = metrics
                except:
                    pass
                
                # Status das estratégias
                if self.system_manager.strategy_manager:
                    try:
                        strategies = self.system_manager.strategy_manager.get_all_strategies_status()
                        data['strategies'] = strategies
                    except:
                        pass
                
                # Performance
                if self.system_manager.strategy_manager:
                    try:
                        performance = asyncio.run(self.system_manager.strategy_manager.get_performance_metrics())
                        data['performance'] = performance
                    except:
                        pass
            
            # Adicionar métricas do sistema
            data['system_metrics'] = {
                'cpu_usage': psutil.cpu_percent(),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent
            }
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter dados do dashboard: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _update_prometheus_metrics(self, data: Dict[str, Any]) -> None:
        """
        Atualiza métricas Prometheus com dados do dashboard
        
        Args:
            data: Dados do dashboard
        """
        try:
            # Atualizar métricas de sistema
            if 'system_metrics' in data:
                metrics = data['system_metrics']
                self.metrics_exporter.update_cpu_usage(metrics.get('cpu_usage', 0))
                self.metrics_exporter.update_memory_usage(metrics.get('memory_usage', 0) * 1024 * 1024)  # Converter para bytes
            
            # Atualizar métricas de trading
            if 'system_status' in data:
                status = data['system_status']
                
                # PnL
                self.metrics_exporter.update_pnl(
                    status.get('total_pnl', 0),
                    status.get('daily_pnl', 0)
                )
                
                # Drawdown
                self.metrics_exporter.update_drawdown(
                    status.get('drawdown', 0),
                    status.get('max_drawdown', 0)
                )
                
                # Sharpe
                if 'sharpe_ratio' in status:
                    self.metrics_exporter.update_sharpe(status['sharpe_ratio'])
                
                # Capital
                if 'current_balance' in status:
                    self.metrics_exporter.update_capital(status['current_balance'])
            
            # Atualizar métricas de estratégias
            if 'strategies' in data and isinstance(data['strategies'], dict):
                for strategy_name, strategy_data in data['strategies'].items():
                    if isinstance(strategy_data, dict) and 'win_rate' in strategy_data:
                        self.metrics_exporter.update_win_rate(strategy_data['win_rate'])
            
            # Atualizar estado do sistema
            if 'system_status' in data and 'running' in data['system_status']:
                state = 'running' if data['system_status']['running'] else 'paused'
                self.metrics_exporter.update_system_state(state)
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar métricas Prometheus: {e}")
    
    def _check_alerts(self, data: Dict[str, Any]) -> None:
        """
        Verifica alertas com base nos dados do dashboard
        
        Args:
            data: Dados do dashboard
        """
        try:
            if 'system_status' in data:
                status = data['system_status']
                
                # Verificar drawdown
                if 'drawdown' in status:
                    self.alert_manager.check_drawdown(status['drawdown'])
                
                # Verificar perda diária
                if 'daily_pnl' in status and 'current_balance' in status:
                    self.alert_manager.check_daily_loss(
                        status['daily_pnl'],
                        status['current_balance']
                    )
            
            # Verificar taxa de erros
            self.alert_manager.check_error_rate()
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar alertas: {e}")
    
    def get_cached_data(self) -> Dict[str, Any]:
        """
        Retorna dados em cache
        
        Returns:
            Dict: Dados em cache
        """
        return self.data_cache.copy()
    
    def is_server_running(self) -> bool:
        """
        Verifica se servidor está rodando
        
        Returns:
            bool: True se rodando
        """
        return self.is_running

