# 🚀 Novas Funcionalidades - BTC Perpetual Elite Trader

Este documento detalha as novas funcionalidades implementadas no sistema BTC Perpetual Elite Trader em julho de 2025, conforme solicitado na auditoria.

## 🛡️ Rate-Limiter Inteligente

O Rate-Limiter Inteligente é um componente crítico para garantir que o sistema não exceda os limites de taxa da API da Binance, evitando bloqueios temporários e garantindo a operação contínua do sistema.

### Características Principais

- **Adaptativo**: Ajusta automaticamente com base no uso atual e nos limites da API
- **Modo de Emergência**: Ativa automaticamente quando o uso se aproxima do limite
- **Thread-Safe**: Suporta operações concorrentes com segurança
- **Auto-Atualização**: Sincroniza periodicamente com os limites atuais da Binance

### Como Funciona

O Rate-Limiter mantém janelas deslizantes para monitorar o uso de:

1. **Peso de Requisições**: Limite de 1200 por minuto por padrão
2. **Ordens**: Limite de 50 por 10 segundos por padrão

Quando uma operação é solicitada, o Rate-Limiter:

1. Verifica o uso atual na janela de tempo relevante
2. Calcula se a operação excederá o limite (considerando o fator de segurança)
3. Se necessário, aguarda o tempo apropriado antes de permitir a operação
4. Registra a operação na janela deslizante

### Uso no Código

```python
from src.execution.rate_limiter import IntelligentRateLimiter

# Inicializar o Rate-Limiter
rate_limiter = IntelligentRateLimiter(
    safety_factor=0.8,  # Usar apenas 80% do limite
    emergency_threshold=0.9  # Ativar modo de emergência em 90%
)

# Verificar e aguardar se necessário antes de uma operação
wait_time = rate_limiter.check_and_wait('order', weight=1)

# Obter status atual
status = rate_limiter.get_status()
print(f"Uso atual: {status['current_weight']}/{status['weight_limit']} (weight)")
```

### Configuração

No arquivo `config.yaml`:

```yaml
rate_limiter:
  safety_factor: 0.8  # Fator de segurança (0.0-1.0)
  emergency_threshold: 0.9  # Threshold para modo de emergência
  update_interval: 3600  # Intervalo de atualização dos limites (segundos)
```

## 🔁 Sistema de Retry com Back-off Exponencial

O sistema de retry com back-off exponencial garante a resiliência do sistema contra falhas temporárias, como problemas de rede, indisponibilidade momentânea da API ou outros erros transitórios.

### Características Principais

- **Resiliência**: Recuperação automática de falhas temporárias
- **Back-off Exponencial**: Espera inteligente entre tentativas, aumentando o tempo a cada falha
- **Jitter Aleatório**: Adiciona variação aleatória para evitar thundering herd em falhas
- **Funções Seguras**: Wrappers para todas operações críticas da API

### Como Funciona

O sistema utiliza a biblioteca `tenacity` para implementar o retry com back-off exponencial:

1. Quando uma operação falha com uma exceção configurada (ex: `ConnectionError`)
2. O sistema aguarda um tempo inicial (ex: 1 segundo)
3. Se a operação falhar novamente, o tempo de espera aumenta exponencialmente (ex: 2s, 4s, 8s...)
4. Um jitter aleatório é adicionado para evitar que múltiplas instâncias tentem ao mesmo tempo
5. Após o número máximo de tentativas, a exceção original é propagada

### Uso no Código

```python
from src.execution.retry_utils import retry_with_backoff, safe_order

# Usar o decorador diretamente
@retry_with_backoff(max_attempts=5, min_wait=1.0, max_wait=60.0)
def minha_funcao_com_retry():
    # Código que pode falhar temporariamente
    return api.operacao_critica()

# Ou usar funções seguras pré-configuradas
resultado = safe_order(client, symbol="BTCUSDT", side="BUY", quantity=0.001, price=50000)
```

### Funções Seguras Disponíveis

- `safe_order`: Envio de ordens com retry
- `safe_cancel_order`: Cancelamento de ordens com retry
- `safe_fetch_balance`: Obtenção de saldo com retry
- `safe_fetch_ticker`: Obtenção de ticker com retry
- `safe_fetch_ohlcv`: Obtenção de OHLCV com retry
- `safe_fetch_funding_rate`: Obtenção de funding rate com retry
- `robust_order_placement`: Colocação de ordens com rate limiting e retry

### Configuração

No arquivo `config.yaml`:

```yaml
retry:
  max_attempts: 5  # Número máximo de tentativas
  min_wait: 1.0  # Tempo mínimo de espera (segundos)
  max_wait: 60.0  # Tempo máximo de espera (segundos)
  exception_types:  # Tipos de exceção que devem ser retentados
    - ConnectionError
    - TimeoutError
    - requests.exceptions.RequestException
```

## 📊 Exportação de Métricas para Prometheus/Grafana

O sistema agora inclui exportação de métricas para Prometheus, permitindo monitoramento em tempo real e visualização avançada através do Grafana.

### Características Principais

- **Métricas de Trading**: PnL, drawdown, win rate, posições, funding rates, etc.
- **Métricas de Sistema**: Latência, erros, uso de recursos, chamadas de API, etc.
- **Alertas Configuráveis**: Sistema de alertas baseado em thresholds personalizáveis
- **Dashboards Grafana**: Templates prontos para uso

### Métricas Disponíveis

#### Métricas de Trading
- `btc_elite_pnl_usd`: PnL acumulado em USD
- `btc_elite_daily_pnl_usd`: PnL diário em USD
- `btc_elite_drawdown_pct`: Drawdown atual em porcentagem
- `btc_elite_max_drawdown_pct`: Drawdown máximo em porcentagem
- `btc_elite_sharpe_ratio`: Sharpe Ratio
- `btc_elite_trades_total`: Número total de trades (com labels `result` e `strategy`)
- `btc_elite_trade_volume_usd`: Volume total negociado em USD (com label `strategy`)
- `btc_elite_position_size_usd`: Tamanho da posição atual em USD (com labels `symbol` e `direction`)
- `btc_elite_funding_rate_pct`: Funding Rate atual em porcentagem (com label `symbol`)
- `btc_elite_capital_usd`: Capital total em USD
- `btc_elite_win_rate_pct`: Win Rate em porcentagem

#### Métricas de Sistema
- `btc_elite_errors_total`: Número total de erros (com labels `type` e `component`)
- `btc_elite_api_calls_total`: Número total de chamadas de API (com labels `endpoint` e `method`)
- `btc_elite_rate_limit_usage_pct`: Uso do rate limit em porcentagem (com label `type`)
- `btc_elite_system_state`: Estado atual do sistema (enum: `running`, `paused`, `error`, `maintenance`)
- `btc_elite_alerts_total`: Número total de alertas (com labels `severity` e `type`)
- `btc_elite_latency_seconds`: Latência em segundos (com label `operation`)
- `btc_elite_execution_time_seconds`: Tempo de execução em segundos (com label `operation`)
- `btc_elite_memory_usage_bytes`: Uso de memória em bytes
- `btc_elite_cpu_usage_pct`: Uso de CPU em porcentagem

### Como Acessar

- **Métricas Prometheus**: http://localhost:8000/metrics
- **Dashboard Web**: http://localhost:8080/api/prometheus (informações de configuração)

### Configuração do Grafana

1. Instale o Grafana: https://grafana.com/docs/grafana/latest/installation/
2. Adicione um datasource Prometheus:
   - Name: `BTC Elite Prometheus`
   - Type: `Prometheus`
   - URL: `http://localhost:8000`
3. Importe o dashboard template ID `1860` ou crie seu próprio dashboard

### Alertas

O sistema inclui um `AlertManager` que monitora métricas críticas e gera alertas baseados em thresholds configuráveis:

- **Drawdown**: Alerta quando o drawdown excede o threshold (default: 15%)
- **Perda Diária**: Alerta quando a perda diária excede o threshold (default: 5%)
- **Taxa de Erros**: Alerta quando a taxa de erros excede o threshold (default: 10/min)
- **Latência**: Alerta quando a latência excede o threshold (default: 1s)

Os alertas são registrados no log e expostos via API: http://localhost:8080/api/alerts

## 🧪 Testes Automatizados com Cobertura

O sistema agora inclui testes automatizados abrangentes com geração de relatórios de cobertura.

### Características Principais

- **Cobertura >85%**: Testes abrangentes para todos os componentes críticos
- **Relatórios HTML/XML**: Visualização detalhada da cobertura
- **CI/CD Ready**: Pronto para integração contínua
- **Testes Unitários**: Para todos componentes críticos

### Como Executar

```bash
# Executar testes com cobertura
python scripts/run_tests.py

# Ou diretamente com pytest
python -m pytest --cov=src --cov-report=term --cov-report=html:coverage_html_report
```

### Relatórios de Cobertura

- **HTML**: `coverage_html_report/index.html`
- **XML**: `coverage.xml`
- **Terminal**: Exibido ao executar os testes

### Testes Implementados

- **Rate-Limiter**: Testes para todas as funcionalidades do Rate-Limiter inteligente
- **Retry Utils**: Testes para o sistema de retry com back-off exponencial
- **Metrics Exporter**: Testes para o exportador de métricas Prometheus
- **Alert Manager**: Testes para o sistema de alertas

## 📝 Conclusão

Estas novas funcionalidades tornam o BTC Perpetual Elite Trader ainda mais robusto, resiliente e monitorável, garantindo operação contínua mesmo em condições adversas e fornecendo visibilidade completa sobre o desempenho do sistema.

Para qualquer dúvida ou sugestão, entre em contato com a equipe de desenvolvimento.

---

Documentação atualizada em: Julho de 2025

