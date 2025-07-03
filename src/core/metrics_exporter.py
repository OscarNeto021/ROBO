"""
Metrics Exporter - Sistema de exportação de métricas para Prometheus/Grafana

Este módulo implementa um sistema de exportação de métricas para Prometheus,
permitindo o monitoramento em tempo real do sistema de trading através do Grafana.

Características:
- Thread dedicada para coleta e exportação de métricas
- Exportação de métricas via HTTP para Prometheus
- Suporte a métricas de trading (PnL, drawdown, etc.)
- Suporte a métricas de sistema (latência, erros, etc.)
- Suporte a métricas de performance (tempo de execução, etc.)
- Integração com Grafana para visualização
"""

import time
import threading
import logging
import queue
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
import os
import socket
from datetime import datetime
import concurrent.futures
import psutil

from prometheus_client import (
    start_http_server, 
    Counter, 
    Gauge, 
    Histogram, 
    Summary,
    Info,
    Enum,
    CollectorRegistry,
    push_to_gateway,
    REGISTRY
)

from ..core.logger import get_trading_logger

logger = get_trading_logger(__name__)

class MetricsExporter:
    """
    Exportador de métricas para Prometheus/Grafana com thread dedicada
    
    Características:
    - Thread dedicada para coleta e exportação de métricas
    - Exportação de métricas via HTTP para Prometheus
    - Suporte a métricas de trading (PnL, drawdown, etc.)
    - Suporte a métricas de sistema (latência, erros, etc.)
    - Suporte a métricas de performance (tempo de execução, etc.)
    - Integração com Grafana para visualização
    """
    
    def __init__(
        self,
        port: int = 8000,
        prefix: str = 'btc_elite',
        enable_pushgateway: bool = False,
        pushgateway_url: Optional[str] = None,
        pushgateway_job: str = 'btc_elite_trader',
        instance_name: Optional[str] = None,
        push_interval: int = 15,  # segundos
        system_metrics_interval: int = 5  # segundos
    ):
        """
        Inicializa o exportador de métricas
        
        Args:
            port: Porta para o servidor HTTP
            prefix: Prefixo para as métricas
            enable_pushgateway: Se deve enviar métricas para um Pushgateway
            pushgateway_url: URL do Pushgateway (ex: 'localhost:9091')
            pushgateway_job: Nome do job no Pushgateway
            instance_name: Nome da instância (default: hostname)
            push_interval: Intervalo em segundos para envio de métricas ao Pushgateway
            system_metrics_interval: Intervalo em segundos para coleta de métricas do sistema
        """
        self.port = port
        self.prefix = prefix
        self.enable_pushgateway = enable_pushgateway
        self.pushgateway_url = pushgateway_url
        self.pushgateway_job = pushgateway_job
        self.push_interval = push_interval
        self.system_metrics_interval = system_metrics_interval
        
        # Definir nome da instância
        if instance_name:
            self.instance_name = instance_name
        else:
            self.instance_name = socket.gethostname()
        
        # Inicializar servidor HTTP
        self._server_started = False
        
        # Inicializar registro separado para pushgateway
        if self.enable_pushgateway:
            self.push_registry = CollectorRegistry()
        else:
            self.push_registry = REGISTRY
        
        # Inicializar métricas de trading
        self._init_trading_metrics()
        
        # Inicializar métricas de sistema
        self._init_system_metrics()
        
        # Inicializar métricas de performance
        self._init_performance_metrics()
        
        # Inicializar informações do sistema
        self._init_system_info()
        
        # Fila de métricas para processamento assíncrono
        self._metrics_queue = queue.Queue()
        
        # Thread dedicada para processamento de métricas
        self._metrics_thread = None
        self._stop_event = threading.Event()
        
        # Executor para tarefas em segundo plano
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        # Locks para acesso concorrente
        self._metrics_lock = threading.RLock()
        
        logger.info(f"MetricsExporter inicializado (porta={port}, prefix={prefix})")
    
    def _init_trading_metrics(self) -> None:
        """
        Inicializa métricas de trading
        """
        # PnL
        self.pnl_gauge = Gauge(
            f'{self.prefix}_pnl_usd',
            'PnL acumulado em USD',
            registry=self.push_registry
        )
        
        self.daily_pnl_gauge = Gauge(
            f'{self.prefix}_daily_pnl_usd',
            'PnL diário em USD',
            registry=self.push_registry
        )
        
        # Drawdown
        self.drawdown_gauge = Gauge(
            f'{self.prefix}_drawdown_pct',
            'Drawdown atual em porcentagem',
            registry=self.push_registry
        )
        
        self.max_drawdown_gauge = Gauge(
            f'{self.prefix}_max_drawdown_pct',
            'Drawdown máximo em porcentagem',
            registry=self.push_registry
        )
        
        # Sharpe Ratio
        self.sharpe_gauge = Gauge(
            f'{self.prefix}_sharpe_ratio',
            'Sharpe Ratio',
            registry=self.push_registry
        )
        
        # Trades
        self.trades_counter = Counter(
            f'{self.prefix}_trades_total',
            'Número total de trades',
            ['result', 'strategy'],
            registry=self.push_registry
        )
        
        self.trade_volume_counter = Counter(
            f'{self.prefix}_trade_volume_usd',
            'Volume total negociado em USD',
            ['strategy'],
            registry=self.push_registry
        )
        
        # Posições
        self.position_gauge = Gauge(
            f'{self.prefix}_position_size_usd',
            'Tamanho da posição atual em USD',
            ['symbol', 'direction'],
            registry=self.push_registry
        )
        
        # Funding Rate
        self.funding_rate_gauge = Gauge(
            f'{self.prefix}_funding_rate_pct',
            'Funding Rate atual em porcentagem',
            ['symbol'],
            registry=self.push_registry
        )
        
        # Capital
        self.capital_gauge = Gauge(
            f'{self.prefix}_capital_usd',
            'Capital total em USD',
            registry=self.push_registry
        )
        
        # Win Rate
        self.win_rate_gauge = Gauge(
            f'{self.prefix}_win_rate_pct',
            'Win Rate em porcentagem',
            registry=self.push_registry
        )
    
    def _init_system_metrics(self) -> None:
        """
        Inicializa métricas de sistema
        """
        # Erros
        self.error_counter = Counter(
            f'{self.prefix}_errors_total',
            'Número total de erros',
            ['type', 'component'],
            registry=self.push_registry
        )
        
        # API Calls
        self.api_call_counter = Counter(
            f'{self.prefix}_api_calls_total',
            'Número total de chamadas de API',
            ['endpoint', 'method'],
            registry=self.push_registry
        )
        
        # Rate Limit
        self.rate_limit_gauge = Gauge(
            f'{self.prefix}_rate_limit_usage_pct',
            'Uso do rate limit em porcentagem',
            ['type'],
            registry=self.push_registry
        )
        
        # Estado do sistema
        self.system_state = Enum(
            f'{self.prefix}_system_state',
            'Estado atual do sistema',
            states=['running', 'paused', 'error', 'maintenance', 'emergency'],
            registry=self.push_registry
        )
        
        # Alertas
        self.alert_counter = Counter(
            f'{self.prefix}_alerts_total',
            'Número total de alertas',
            ['severity', 'type'],
            registry=self.push_registry
        )
    
    def _init_performance_metrics(self) -> None:
        """
        Inicializa métricas de performance
        """
        # Latência
        self.latency_histogram = Histogram(
            f'{self.prefix}_latency_seconds',
            'Latência em segundos',
            ['operation'],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.push_registry
        )
        
        # Tempo de execução
        self.execution_time_summary = Summary(
            f'{self.prefix}_execution_time_seconds',
            'Tempo de execução em segundos',
            ['operation'],
            registry=self.push_registry
        )
        
        # Uso de memória
        self.memory_usage_gauge = Gauge(
            f'{self.prefix}_memory_usage_bytes',
            'Uso de memória em bytes',
            registry=self.push_registry
        )
        
        # Uso de CPU
        self.cpu_usage_gauge = Gauge(
            f'{self.prefix}_cpu_usage_pct',
            'Uso de CPU em porcentagem',
            registry=self.push_registry
        )
        
        # Métricas da thread de métricas
        self.metrics_queue_size_gauge = Gauge(
            f'{self.prefix}_metrics_queue_size',
            'Tamanho da fila de métricas',
            registry=self.push_registry
        )
        
        self.metrics_processing_time_summary = Summary(
            f'{self.prefix}_metrics_processing_time_seconds',
            'Tempo de processamento de métricas em segundos',
            registry=self.push_registry
        )
    
    def _init_system_info(self) -> None:
        """
        Inicializa informações do sistema
        """
        # Informações do sistema
        self.system_info = Info(
            f'{self.prefix}_system_info',
            'Informações do sistema',
            registry=self.push_registry
        )
        
        # Preencher informações básicas
        self.system_info.info({
            'version': '1.0.0',
            'instance': self.instance_name,
            'start_time': datetime.now().isoformat(),
            'python_version': os.popen('python --version').read().strip(),
            'hostname': socket.gethostname()
        })
    
    def start_server(self) -> None:
        """
        Inicia o servidor HTTP para Prometheus
        """
        if not self._server_started:
            try:
                start_http_server(self.port)
                self._server_started = True
                logger.info(f"Servidor de métricas iniciado na porta {self.port}")
            except Exception as e:
                logger.error(f"Erro ao iniciar servidor de métricas: {e}")
    
    def start(self) -> None:
        """
        Inicia o exportador de métricas com thread dedicada
        """
        # Iniciar servidor HTTP
        self.start_server()
        
        # Iniciar thread de métricas
        if self._metrics_thread is None or not self._metrics_thread.is_alive():
            self._stop_event.clear()
            self._metrics_thread = threading.Thread(
                target=self._metrics_worker,
                daemon=True,
                name="MetricsThread"
            )
            self._metrics_thread.start()
            logger.info("Thread de métricas iniciada")
    
    def stop(self) -> None:
        """
        Para o exportador de métricas
        """
        if self._metrics_thread and self._metrics_thread.is_alive():
            self._stop_event.set()
            self._metrics_thread.join(timeout=5.0)
            logger.info("Thread de métricas parada")
        
        # Encerrar executor
        self._executor.shutdown(wait=False)
    
    def _metrics_worker(self) -> None:
        """
        Worker para processamento de métricas em thread dedicada
        """
        logger.info("Worker de métricas iniciado")
        
        last_push_time = 0
        last_system_metrics_time = 0
        
        while not self._stop_event.is_set():
            try:
                # Processar métricas na fila
                self._process_metrics_queue()
                
                # Atualizar métricas do sistema
                current_time = time.time()
                if current_time - last_system_metrics_time >= self.system_metrics_interval:
                    self._collect_system_metrics()
                    last_system_metrics_time = current_time
                
                # Enviar métricas para Pushgateway
                if self.enable_pushgateway and self.pushgateway_url:
                    if current_time - last_push_time >= self.push_interval:
                        self._push_metrics_to_gateway()
                        last_push_time = current_time
                
                # Atualizar métrica de tamanho da fila
                with self._metrics_lock:
                    self.metrics_queue_size_gauge.set(self._metrics_queue.qsize())
                
                # Dormir um pouco para não consumir CPU
                time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Erro no worker de métricas: {e}")
                time.sleep(1.0)  # Evitar loop infinito em caso de erro
    
    def _process_metrics_queue(self) -> None:
        """
        Processa métricas na fila
        """
        # Processar no máximo 100 métricas por vez para evitar bloqueio
        max_items = 100
        processed = 0
        
        while processed < max_items:
            try:
                # Tentar obter uma métrica da fila (não bloqueante)
                metric_item = self._metrics_queue.get_nowait()
                start_time = time.time()
                
                try:
                    # Processar métrica
                    metric_type, args, kwargs = metric_item
                    self._process_metric(metric_type, *args, **kwargs)
                except Exception as e:
                    logger.error(f"Erro ao processar métrica {metric_type}: {e}")
                finally:
                    # Marcar como concluída
                    self._metrics_queue.task_done()
                    processed += 1
                    
                    # Registrar tempo de processamento
                    with self._metrics_lock:
                        self.metrics_processing_time_summary.observe(time.time() - start_time)
            
            except queue.Empty:
                # Fila vazia, sair do loop
                break
    
    def _process_metric(self, metric_type: str, *args: Any, **kwargs: Any) -> None:
        """
        Processa uma métrica específica
        
        Args:
            metric_type: Tipo de métrica
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
        """
        with self._metrics_lock:
            if metric_type == 'pnl':
                self.pnl_gauge.set(args[0])
                if len(args) > 1 and args[1] is not None:
                    self.daily_pnl_gauge.set(args[1])
            
            elif metric_type == 'drawdown':
                self.drawdown_gauge.set(args[0])
                if len(args) > 1 and args[1] is not None:
                    self.max_drawdown_gauge.set(args[1])
            
            elif metric_type == 'sharpe':
                self.sharpe_gauge.set(args[0])
            
            elif metric_type == 'trade':
                self.trades_counter.labels(result=args[0], strategy=args[1]).inc()
                self.trade_volume_counter.labels(strategy=args[1]).inc(args[2])
            
            elif metric_type == 'position':
                self.position_gauge.labels(symbol=args[0], direction=args[1]).set(args[2])
            
            elif metric_type == 'funding_rate':
                self.funding_rate_gauge.labels(symbol=args[0]).set(args[1])
            
            elif metric_type == 'capital':
                self.capital_gauge.set(args[0])
            
            elif metric_type == 'win_rate':
                self.win_rate_gauge.set(args[0])
            
            elif metric_type == 'error':
                self.error_counter.labels(type=args[0], component=args[1]).inc()
            
            elif metric_type == 'api_call':
                self.api_call_counter.labels(endpoint=args[0], method=args[1]).inc()
            
            elif metric_type == 'rate_limit':
                self.rate_limit_gauge.labels(type=args[0]).set(args[1])
            
            elif metric_type == 'system_state':
                self.system_state.state(args[0])
            
            elif metric_type == 'alert':
                self.alert_counter.labels(severity=args[0], type=args[1]).inc()
            
            elif metric_type == 'latency':
                self.latency_histogram.labels(operation=args[0]).observe(args[1])
            
            elif metric_type == 'execution_time':
                self.execution_time_summary.labels(operation=args[0]).observe(args[1])
            
            elif metric_type == 'memory_usage':
                self.memory_usage_gauge.set(args[0])
            
            elif metric_type == 'cpu_usage':
                self.cpu_usage_gauge.set(args[0])
    
    def _collect_system_metrics(self) -> None:
        """
        Coleta métricas do sistema
        """
        try:
            # Uso de memória
            memory_info = psutil.Process(os.getpid()).memory_info()
            self._queue_metric('memory_usage', memory_info.rss)
            
            # Uso de CPU
            cpu_percent = psutil.Process(os.getpid()).cpu_percent(interval=0.1)
            self._queue_metric('cpu_usage', cpu_percent)
        except Exception as e:
            logger.warning(f"Erro ao coletar métricas do sistema: {e}")
    
    def _push_metrics_to_gateway(self) -> None:
        """
        Envia métricas para o Pushgateway
        """
        if not self.enable_pushgateway or not self.pushgateway_url:
            return
        
        try:
            # Enviar em uma thread separada para não bloquear
            self._executor.submit(
                push_to_gateway,
                self.pushgateway_url,
                job=self.pushgateway_job,
                registry=self.push_registry,
                grouping_key={'instance': self.instance_name}
            )
            logger.debug(f"Métricas enviadas para Pushgateway: {self.pushgateway_url}")
        except Exception as e:
            logger.error(f"Erro ao enviar métricas para Pushgateway: {e}")
    
    def _queue_metric(self, metric_type: str, *args: Any, **kwargs: Any) -> None:
        """
        Adiciona uma métrica à fila para processamento assíncrono
        
        Args:
            metric_type: Tipo de métrica
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
        """
        try:
            self._metrics_queue.put((metric_type, args, kwargs))
        except Exception as e:
            logger.error(f"Erro ao adicionar métrica à fila: {e}")
    
    def update_pnl(self, pnl: float, daily_pnl: Optional[float] = None) -> None:
        """
        Atualiza métricas de PnL
        
        Args:
            pnl: PnL acumulado em USD
            daily_pnl: PnL diário em USD
        """
        self._queue_metric('pnl', pnl, daily_pnl)
    
    def update_drawdown(self, drawdown: float, max_drawdown: Optional[float] = None) -> None:
        """
        Atualiza métricas de drawdown
        
        Args:
            drawdown: Drawdown atual em porcentagem
            max_drawdown: Drawdown máximo em porcentagem
        """
        self._queue_metric('drawdown', drawdown, max_drawdown)
    
    def update_sharpe(self, sharpe: float) -> None:
        """
        Atualiza métrica de Sharpe Ratio
        
        Args:
            sharpe: Sharpe Ratio
        """
        self._queue_metric('sharpe', sharpe)
    
    def record_trade(self, result: str, strategy: str, volume: float) -> None:
        """
        Registra um trade
        
        Args:
            result: Resultado do trade ('win', 'loss', 'breakeven')
            strategy: Nome da estratégia
            volume: Volume do trade em USD
        """
        self._queue_metric('trade', result, strategy, volume)
    
    def update_position(self, symbol: str, direction: str, size: float) -> None:
        """
        Atualiza posição
        
        Args:
            symbol: Símbolo do par
            direction: Direção ('long', 'short')
            size: Tamanho da posição em USD
        """
        self._queue_metric('position', symbol, direction, size)
    
    def update_funding_rate(self, symbol: str, rate: float) -> None:
        """
        Atualiza funding rate
        
        Args:
            symbol: Símbolo do par
            rate: Funding rate em porcentagem
        """
        self._queue_metric('funding_rate', symbol, rate)
    
    def update_capital(self, capital: float) -> None:
        """
        Atualiza capital
        
        Args:
            capital: Capital total em USD
        """
        self._queue_metric('capital', capital)
    
    def update_win_rate(self, win_rate: float) -> None:
        """
        Atualiza win rate
        
        Args:
            win_rate: Win rate em porcentagem
        """
        self._queue_metric('win_rate', win_rate)
    
    def record_error(self, error_type: str, component: str) -> None:
        """
        Registra um erro
        
        Args:
            error_type: Tipo de erro
            component: Componente onde ocorreu o erro
        """
        self._queue_metric('error', error_type, component)
    
    def record_api_call(self, endpoint: str, method: str) -> None:
        """
        Registra uma chamada de API
        
        Args:
            endpoint: Endpoint da API
            method: Método HTTP
        """
        self._queue_metric('api_call', endpoint, method)
    
    def update_rate_limit(self, limit_type: str, usage: float) -> None:
        """
        Atualiza uso do rate limit
        
        Args:
            limit_type: Tipo de limite ('weight', 'orders')
            usage: Uso em porcentagem
        """
        self._queue_metric('rate_limit', limit_type, usage)
    
    def update_system_state(self, state: str) -> None:
        """
        Atualiza estado do sistema
        
        Args:
            state: Estado ('running', 'paused', 'error', 'maintenance', 'emergency')
        """
        self._queue_metric('system_state', state)
    
    def record_alert(self, severity: str, alert_type: str) -> None:
        """
        Registra um alerta
        
        Args:
            severity: Severidade ('critical', 'warning', 'info')
            alert_type: Tipo de alerta
        """
        self._queue_metric('alert', severity, alert_type)
    
    def record_latency(self, operation: str, seconds: float) -> None:
        """
        Registra latência
        
        Args:
            operation: Nome da operação
            seconds: Tempo em segundos
        """
        self._queue_metric('latency', operation, seconds)
    
    def record_execution_time(self, operation: str, seconds: float) -> None:
        """
        Registra tempo de execução
        
        Args:
            operation: Nome da operação
            seconds: Tempo em segundos
        """
        self._queue_metric('execution_time', operation, seconds)
    
    def time_operation(self, operation: str) -> Callable:
        """
        Decorador para medir tempo de operação
        
        Args:
            operation: Nome da operação
            
        Returns:
            Callable: Decorador
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    self.record_execution_time(operation, time.time() - start_time)
                    return result
                except Exception as e:
                    self.record_error(type(e).__name__, operation)
                    raise
            return wrapper
        return decorator


class AlertManager:
    """
    Gerenciador de alertas para monitoramento
    
    Características:
    - Monitoramento de métricas críticas
    - Geração de alertas baseados em thresholds
    - Integração com o exportador de métricas
    """
    
    def __init__(
        self,
        metrics_exporter: MetricsExporter,
        drawdown_threshold: float = 15.0,
        daily_loss_threshold: float = 5.0,
        error_rate_threshold: float = 10,
        latency_threshold: float = 1.0
    ):
        """
        Inicializa o gerenciador de alertas
        
        Args:
            metrics_exporter: Exportador de métricas
            drawdown_threshold: Threshold de drawdown em porcentagem
            daily_loss_threshold: Threshold de perda diária em porcentagem
            error_rate_threshold: Threshold de taxa de erros por minuto
            latency_threshold: Threshold de latência em segundos
        """
        self.metrics = metrics_exporter
        self.drawdown_threshold = drawdown_threshold
        self.daily_loss_threshold = daily_loss_threshold
        self.error_rate_threshold = error_rate_threshold
        self.latency_threshold = latency_threshold
        
        # Contadores para cálculo de taxas
        self.error_count = 0
        self.last_error_check = time.time()
        
        # Estado de alertas
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
        
        # Lock para acesso concorrente
        self._lock = threading.RLock()
        
        logger.info(f"AlertManager inicializado (drawdown={drawdown_threshold}%, "
                   f"daily_loss={daily_loss_threshold}%, "
                   f"error_rate={error_rate_threshold}/min, "
                   f"latency={latency_threshold}s)")
    
    def check_drawdown(self, current_drawdown: float) -> None:
        """
        Verifica drawdown e gera alertas se necessário
        
        Args:
            current_drawdown: Drawdown atual em porcentagem
        """
        alert_id = 'drawdown'
        
        with self._lock:
            if current_drawdown >= self.drawdown_threshold:
                if alert_id not in self.active_alerts:
                    severity = 'critical' if current_drawdown >= self.drawdown_threshold * 1.5 else 'warning'
                    self._create_alert(
                        alert_id,
                        severity,
                        'drawdown',
                        f'Drawdown alto: {current_drawdown:.2f}% (threshold: {self.drawdown_threshold:.2f}%)'
                    )
            elif alert_id in self.active_alerts:
                self._resolve_alert(alert_id)
    
    def check_daily_loss(self, daily_pnl: float, capital: float) -> None:
        """
        Verifica perda diária e gera alertas se necessário
        
        Args:
            daily_pnl: PnL diário em USD
            capital: Capital total em USD
        """
        if capital <= 0:
            return
        
        daily_loss_pct = abs(daily_pnl) / capital * 100 if daily_pnl < 0 else 0
        alert_id = 'daily_loss'
        
        with self._lock:
            if daily_loss_pct >= self.daily_loss_threshold:
                if alert_id not in self.active_alerts:
                    severity = 'critical' if daily_loss_pct >= self.daily_loss_threshold * 1.5 else 'warning'
                    self._create_alert(
                        alert_id,
                        severity,
                        'pnl',
                        f'Perda diária alta: {daily_loss_pct:.2f}% (threshold: {self.daily_loss_threshold:.2f}%)'
                    )
            elif alert_id in self.active_alerts:
                self._resolve_alert(alert_id)
    
    def check_error_rate(self) -> None:
        """
        Verifica taxa de erros e gera alertas se necessário
        """
        now = time.time()
        
        with self._lock:
            elapsed = now - self.last_error_check
            
            if elapsed < 60:
                return
            
            error_rate = self.error_count / (elapsed / 60)
            self.error_count = 0
            self.last_error_check = now
            
            alert_id = 'error_rate'
            
            if error_rate >= self.error_rate_threshold:
                if alert_id not in self.active_alerts:
                    severity = 'critical' if error_rate >= self.error_rate_threshold * 2 else 'warning'
                    self._create_alert(
                        alert_id,
                        severity,
                        'errors',
                        f'Taxa de erros alta: {error_rate:.2f}/min (threshold: {self.error_rate_threshold}/min)'
                    )
            elif alert_id in self.active_alerts:
                self._resolve_alert(alert_id)
    
    def check_latency(self, operation: str, latency: float) -> None:
        """
        Verifica latência e gera alertas se necessário
        
        Args:
            operation: Nome da operação
            latency: Latência em segundos
        """
        alert_id = f'latency_{operation}'
        
        with self._lock:
            if latency >= self.latency_threshold:
                if alert_id not in self.active_alerts:
                    severity = 'critical' if latency >= self.latency_threshold * 2 else 'warning'
                    self._create_alert(
                        alert_id,
                        severity,
                        'latency',
                        f'Latência alta em {operation}: {latency:.2f}s (threshold: {self.latency_threshold:.2f}s)'
                    )
            elif alert_id in self.active_alerts:
                self._resolve_alert(alert_id)
    
    def record_error(self, error_type: str, component: str) -> None:
        """
        Registra um erro e atualiza contadores
        
        Args:
            error_type: Tipo de erro
            component: Componente onde ocorreu o erro
        """
        with self._lock:
            self.error_count += 1
            self.metrics.record_error(error_type, component)
            
            # Verificar taxa de erros
            self.check_error_rate()
    
    def _create_alert(self, alert_id: str, severity: str, alert_type: str, message: str) -> None:
        """
        Cria um alerta
        
        Args:
            alert_id: ID do alerta
            severity: Severidade ('critical', 'warning', 'info')
            alert_type: Tipo de alerta
            message: Mensagem do alerta
        """
        with self._lock:
            self.active_alerts[alert_id] = {
                'severity': severity,
                'type': alert_type,
                'message': message,
                'created_at': time.time()
            }
            
            # Registrar no exportador de métricas
            self.metrics.record_alert(severity, alert_type)
            
            # Log
            log_level = logging.CRITICAL if severity == 'critical' else logging.WARNING
            logger.log(log_level, f"ALERTA: {message}")
    
    def _resolve_alert(self, alert_id: str) -> None:
        """
        Resolve um alerta
        
        Args:
            alert_id: ID do alerta
        """
        with self._lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts.pop(alert_id)
                logger.info(f"Alerta resolvido: {alert['message']}")
    
    def get_active_alerts(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtém alertas ativos
        
        Returns:
            Dict: Alertas ativos
        """
        with self._lock:
            return self.active_alerts.copy()


# Singleton para acesso global
_metrics_exporter_instance = None

def get_metrics_exporter() -> Optional[MetricsExporter]:
    """
    Retorna a instância global do MetricsExporter.
    
    Returns:
        Optional[MetricsExporter]: Instância do MetricsExporter ou None se não inicializado
    """
    return _metrics_exporter_instance

def initialize_metrics_exporter(
    port: int = 8000,
    prefix: str = 'btc_elite',
    enable_pushgateway: bool = False,
    pushgateway_url: Optional[str] = None,
    pushgateway_job: str = 'btc_elite_trader',
    instance_name: Optional[str] = None,
    push_interval: int = 15,
    system_metrics_interval: int = 5
) -> MetricsExporter:
    """
    Inicializa a instância global do MetricsExporter.
    
    Args:
        port: Porta para o servidor HTTP
        prefix: Prefixo para as métricas
        enable_pushgateway: Se deve enviar métricas para um Pushgateway
        pushgateway_url: URL do Pushgateway (ex: 'localhost:9091')
        pushgateway_job: Nome do job no Pushgateway
        instance_name: Nome da instância (default: hostname)
        push_interval: Intervalo em segundos para envio de métricas ao Pushgateway
        system_metrics_interval: Intervalo em segundos para coleta de métricas do sistema
        
    Returns:
        MetricsExporter: Instância do MetricsExporter
    """
    global _metrics_exporter_instance
    _metrics_exporter_instance = MetricsExporter(
        port=port,
        prefix=prefix,
        enable_pushgateway=enable_pushgateway,
        pushgateway_url=pushgateway_url,
        pushgateway_job=pushgateway_job,
        instance_name=instance_name,
        push_interval=push_interval,
        system_metrics_interval=system_metrics_interval
    )
    
    # Iniciar automaticamente
    _metrics_exporter_instance.start()
    
    return _metrics_exporter_instance


# Exemplo de uso
if __name__ == "__main__":
    # Inicializar exportador de métricas
    metrics = initialize_metrics_exporter(port=8000)
    
    # Inicializar gerenciador de alertas
    alerts = AlertManager(metrics)
    
    # Exemplo de uso
    metrics.update_pnl(100.0, 10.0)
    metrics.update_drawdown(5.0, 10.0)
    metrics.update_sharpe(2.5)
    metrics.record_trade('win', 'funding_arbitrage', 1000.0)
    metrics.update_position('BTCUSDT', 'long', 500.0)
    metrics.update_funding_rate('BTCUSDT', 0.01)
    metrics.update_capital(10000.0)
    metrics.update_win_rate(65.0)
    
    # Verificar alertas
    alerts.check_drawdown(5.0)
    alerts.check_daily_loss(-100.0, 10000.0)
    
    # Manter o programa rodando para demonstração
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        metrics.stop()
        print("Métricas paradas")

