"""
Testes para o exportador de métricas Prometheus
"""

import pytest
import time
from unittest.mock import patch, MagicMock, call
import threading

from src.core.metrics_exporter import MetricsExporter, AlertManager

class TestMetricsExporter:
    """Testes para o MetricsExporter"""
    
    def test_init(self):
        """Teste de inicialização"""
        exporter = MetricsExporter(port=8000, prefix='test')
        
        assert exporter.port == 8000
        assert exporter.prefix == 'test'
        assert exporter._server_started is False
    
    @patch('prometheus_client.start_http_server')
    def test_start_server(self, mock_start_server):
        """Teste de start_server"""
        exporter = MetricsExporter(port=8000)
        exporter.start_server()
        
        mock_start_server.assert_called_once_with(8000)
        assert exporter._server_started is True
    
    @patch('prometheus_client.push_to_gateway')
    def test_push_metrics(self, mock_push):
        """Teste de push_metrics"""
        exporter = MetricsExporter(
            port=8000,
            enable_pushgateway=True,
            pushgateway_url='localhost:9091',
            pushgateway_job='test_job'
        )
        
        exporter.push_metrics()
        
        mock_push.assert_called_once()
    
    def test_update_pnl(self):
        """Teste de update_pnl"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.pnl_gauge = MagicMock()
        exporter.daily_pnl_gauge = MagicMock()
        
        exporter.update_pnl(100.0, 10.0)
        
        exporter.pnl_gauge.set.assert_called_once_with(100.0)
        exporter.daily_pnl_gauge.set.assert_called_once_with(10.0)
    
    def test_update_drawdown(self):
        """Teste de update_drawdown"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.drawdown_gauge = MagicMock()
        exporter.max_drawdown_gauge = MagicMock()
        
        exporter.update_drawdown(5.0, 10.0)
        
        exporter.drawdown_gauge.set.assert_called_once_with(5.0)
        exporter.max_drawdown_gauge.set.assert_called_once_with(10.0)
    
    def test_update_sharpe(self):
        """Teste de update_sharpe"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.sharpe_gauge = MagicMock()
        
        exporter.update_sharpe(2.5)
        
        exporter.sharpe_gauge.set.assert_called_once_with(2.5)
    
    def test_record_trade(self):
        """Teste de record_trade"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.trades_counter = MagicMock()
        exporter.trades_counter.labels.return_value = MagicMock()
        exporter.trade_volume_counter = MagicMock()
        exporter.trade_volume_counter.labels.return_value = MagicMock()
        
        exporter.record_trade('win', 'funding_arbitrage', 1000.0)
        
        exporter.trades_counter.labels.assert_called_once_with(result='win', strategy='funding_arbitrage')
        exporter.trades_counter.labels.return_value.inc.assert_called_once()
        exporter.trade_volume_counter.labels.assert_called_once_with(strategy='funding_arbitrage')
        exporter.trade_volume_counter.labels.return_value.inc.assert_called_once_with(1000.0)
    
    def test_update_position(self):
        """Teste de update_position"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.position_gauge = MagicMock()
        exporter.position_gauge.labels.return_value = MagicMock()
        
        exporter.update_position('BTCUSDT', 'long', 500.0)
        
        exporter.position_gauge.labels.assert_called_once_with(symbol='BTCUSDT', direction='long')
        exporter.position_gauge.labels.return_value.set.assert_called_once_with(500.0)
    
    def test_update_funding_rate(self):
        """Teste de update_funding_rate"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.funding_rate_gauge = MagicMock()
        exporter.funding_rate_gauge.labels.return_value = MagicMock()
        
        exporter.update_funding_rate('BTCUSDT', 0.01)
        
        exporter.funding_rate_gauge.labels.assert_called_once_with(symbol='BTCUSDT')
        exporter.funding_rate_gauge.labels.return_value.set.assert_called_once_with(0.01)
    
    def test_update_capital(self):
        """Teste de update_capital"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.capital_gauge = MagicMock()
        
        exporter.update_capital(10000.0)
        
        exporter.capital_gauge.set.assert_called_once_with(10000.0)
    
    def test_update_win_rate(self):
        """Teste de update_win_rate"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.win_rate_gauge = MagicMock()
        
        exporter.update_win_rate(65.0)
        
        exporter.win_rate_gauge.set.assert_called_once_with(65.0)
    
    def test_record_error(self):
        """Teste de record_error"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.error_counter = MagicMock()
        exporter.error_counter.labels.return_value = MagicMock()
        
        exporter.record_error('ConnectionError', 'api')
        
        exporter.error_counter.labels.assert_called_once_with(type='ConnectionError', component='api')
        exporter.error_counter.labels.return_value.inc.assert_called_once()
    
    def test_record_api_call(self):
        """Teste de record_api_call"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.api_call_counter = MagicMock()
        exporter.api_call_counter.labels.return_value = MagicMock()
        
        exporter.record_api_call('order', 'POST')
        
        exporter.api_call_counter.labels.assert_called_once_with(endpoint='order', method='POST')
        exporter.api_call_counter.labels.return_value.inc.assert_called_once()
    
    def test_update_rate_limit(self):
        """Teste de update_rate_limit"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.rate_limit_gauge = MagicMock()
        exporter.rate_limit_gauge.labels.return_value = MagicMock()
        
        exporter.update_rate_limit('weight', 50.0)
        
        exporter.rate_limit_gauge.labels.assert_called_once_with(type='weight')
        exporter.rate_limit_gauge.labels.return_value.set.assert_called_once_with(50.0)
    
    def test_update_system_state(self):
        """Teste de update_system_state"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.system_state = MagicMock()
        
        exporter.update_system_state('running')
        
        exporter.system_state.state.assert_called_once_with('running')
    
    def test_record_alert(self):
        """Teste de record_alert"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.alert_counter = MagicMock()
        exporter.alert_counter.labels.return_value = MagicMock()
        
        exporter.record_alert('critical', 'drawdown')
        
        exporter.alert_counter.labels.assert_called_once_with(severity='critical', type='drawdown')
        exporter.alert_counter.labels.return_value.inc.assert_called_once()
    
    def test_record_latency(self):
        """Teste de record_latency"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.latency_histogram = MagicMock()
        exporter.latency_histogram.labels.return_value = MagicMock()
        
        exporter.record_latency('api_call', 0.1)
        
        exporter.latency_histogram.labels.assert_called_once_with(operation='api_call')
        exporter.latency_histogram.labels.return_value.observe.assert_called_once_with(0.1)
    
    def test_record_execution_time(self):
        """Teste de record_execution_time"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.execution_time_summary = MagicMock()
        exporter.execution_time_summary.labels.return_value = MagicMock()
        
        exporter.record_execution_time('strategy_update', 0.5)
        
        exporter.execution_time_summary.labels.assert_called_once_with(operation='strategy_update')
        exporter.execution_time_summary.labels.return_value.observe.assert_called_once_with(0.5)
    
    def test_update_memory_usage(self):
        """Teste de update_memory_usage"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.memory_usage_gauge = MagicMock()
        
        exporter.update_memory_usage(1024 * 1024 * 100)  # 100 MB
        
        exporter.memory_usage_gauge.set.assert_called_once_with(1024 * 1024 * 100)
    
    def test_update_cpu_usage(self):
        """Teste de update_cpu_usage"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.cpu_usage_gauge = MagicMock()
        
        exporter.update_cpu_usage(50.0)
        
        exporter.cpu_usage_gauge.set.assert_called_once_with(50.0)
    
    def test_time_operation(self):
        """Teste de time_operation"""
        exporter = MetricsExporter(port=8000)
        
        # Mock dos métodos
        exporter.record_execution_time = MagicMock()
        
        # Função decorada
        @exporter.time_operation('test_op')
        def test_func():
            return "success"
        
        # Chamar função
        result = test_func()
        
        # Verificar resultado
        assert result == "success"
        assert exporter.record_execution_time.call_count == 1
        assert exporter.record_execution_time.call_args[0][0] == 'test_op'


class TestAlertManager:
    """Testes para o AlertManager"""
    
    def test_init(self):
        """Teste de inicialização"""
        metrics = MagicMock()
        alerts = AlertManager(
            metrics_exporter=metrics,
            drawdown_threshold=15.0,
            daily_loss_threshold=5.0,
            error_rate_threshold=10,
            latency_threshold=1.0
        )
        
        assert alerts.metrics == metrics
        assert alerts.drawdown_threshold == 15.0
        assert alerts.daily_loss_threshold == 5.0
        assert alerts.error_rate_threshold == 10
        assert alerts.latency_threshold == 1.0
        assert alerts.error_count == 0
        assert isinstance(alerts.active_alerts, dict)
    
    def test_check_drawdown_no_alert(self):
        """Teste de check_drawdown sem alerta"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics, drawdown_threshold=15.0)
        
        # Drawdown abaixo do threshold
        alerts.check_drawdown(10.0)
        
        # Não deve criar alerta
        assert len(alerts.active_alerts) == 0
    
    def test_check_drawdown_with_alert(self):
        """Teste de check_drawdown com alerta"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics, drawdown_threshold=15.0)
        
        # Drawdown acima do threshold
        alerts.check_drawdown(20.0)
        
        # Deve criar alerta
        assert len(alerts.active_alerts) == 1
        assert 'drawdown' in alerts.active_alerts
        assert alerts.active_alerts['drawdown']['severity'] == 'critical'
        
        # Metrics deve registrar alerta
        metrics.record_alert.assert_called_once_with('critical', 'drawdown')
    
    def test_check_drawdown_resolve_alert(self):
        """Teste de check_drawdown resolvendo alerta"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics, drawdown_threshold=15.0)
        
        # Criar alerta
        alerts.check_drawdown(20.0)
        assert len(alerts.active_alerts) == 1
        
        # Resolver alerta
        alerts.check_drawdown(10.0)
        assert len(alerts.active_alerts) == 0
    
    def test_check_daily_loss_no_alert(self):
        """Teste de check_daily_loss sem alerta"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics, daily_loss_threshold=5.0)
        
        # Perda diária abaixo do threshold
        alerts.check_daily_loss(-100.0, 10000.0)  # 1% de perda
        
        # Não deve criar alerta
        assert len(alerts.active_alerts) == 0
    
    def test_check_daily_loss_with_alert(self):
        """Teste de check_daily_loss com alerta"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics, daily_loss_threshold=5.0)
        
        # Perda diária acima do threshold
        alerts.check_daily_loss(-1000.0, 10000.0)  # 10% de perda
        
        # Deve criar alerta
        assert len(alerts.active_alerts) == 1
        assert 'daily_loss' in alerts.active_alerts
        assert alerts.active_alerts['daily_loss']['severity'] == 'critical'
        
        # Metrics deve registrar alerta
        metrics.record_alert.assert_called_once_with('critical', 'pnl')
    
    def test_check_error_rate(self):
        """Teste de check_error_rate"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics, error_rate_threshold=10)
        
        # Simular erros
        alerts.error_count = 20
        alerts.last_error_check = time.time() - 60  # 1 minuto atrás
        
        # Verificar taxa de erros
        alerts.check_error_rate()
        
        # Deve criar alerta
        assert len(alerts.active_alerts) == 1
        assert 'error_rate' in alerts.active_alerts
        assert alerts.active_alerts['error_rate']['severity'] == 'critical'
        
        # Metrics deve registrar alerta
        metrics.record_alert.assert_called_once_with('critical', 'errors')
    
    def test_check_latency(self):
        """Teste de check_latency"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics, latency_threshold=1.0)
        
        # Latência acima do threshold
        alerts.check_latency('api_call', 2.0)
        
        # Deve criar alerta
        assert len(alerts.active_alerts) == 1
        assert 'latency_api_call' in alerts.active_alerts
        assert alerts.active_alerts['latency_api_call']['severity'] == 'critical'
        
        # Metrics deve registrar alerta
        metrics.record_alert.assert_called_once_with('critical', 'latency')
    
    def test_record_error(self):
        """Teste de record_error"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics)
        
        # Registrar erro
        alerts.record_error('ConnectionError', 'api')
        
        # Deve incrementar contador
        assert alerts.error_count == 1
        
        # Metrics deve registrar erro
        metrics.record_error.assert_called_once_with('ConnectionError', 'api')
    
    def test_get_active_alerts(self):
        """Teste de get_active_alerts"""
        metrics = MagicMock()
        alerts = AlertManager(metrics_exporter=metrics, drawdown_threshold=15.0)
        
        # Criar alerta
        alerts.check_drawdown(20.0)
        
        # Obter alertas ativos
        active_alerts = alerts.get_active_alerts()
        
        # Deve retornar cópia dos alertas
        assert len(active_alerts) == 1
        assert 'drawdown' in active_alerts
        assert active_alerts is not alerts.active_alerts

