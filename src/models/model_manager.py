"""
Model Manager - Gerenciador de modelos de machine learning
"""

import asyncio
import logging
import pickle
import joblib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from .xgboost_model import XGBoostModel
from .lstm_model import LSTMModel
from .random_forest_model import RandomForestModel
from .ensemble_model import EnsembleModel
from ..core.logger import get_trading_logger

logger = get_trading_logger(__name__)

class ModelManager:
    """
    Gerenciador de modelos de machine learning
    
    Responsabilidades:
    - Gerenciar ciclo de vida dos modelos
    - Treinar modelos offline
    - Fazer predições em tempo real
    - Avaliar performance dos modelos
    - Gerenciar ensemble de modelos
    - Auto-retreinamento
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o gerenciador de modelos
        
        Args:
            config: Configurações do sistema
        """
        self.config = config
        self.models_config = config.get('models', {})
        
        # Modelos disponíveis
        self.available_models = {
            'xgboost': XGBoostModel,
            'lstm': LSTMModel,
            'random_forest': RandomForestModel
        }
        
        # Modelos ativos
        self.active_models: Dict[str, Any] = {}
        self.ensemble_model: Optional[EnsembleModel] = None
        
        # Preprocessors
        self.scalers: Dict[str, Any] = {}
        self.feature_columns: List[str] = []
        
        # Dados de treinamento
        self.training_data: Optional[pd.DataFrame] = None
        self.validation_data: Optional[pd.DataFrame] = None
        
        # Métricas de performance
        self.model_metrics: Dict[str, Dict[str, float]] = {}
        
        # Configurações
        self.models_path = Path(config.get('environment', {}).get('models_path', 'data/models/'))
        self.models_path.mkdir(parents=True, exist_ok=True)
        
        # Estado
        self.is_initialized = False
        self.last_training_time = datetime.min
        self.training_in_progress = False
        
        logger.info("ModelManager inicializado")
    
    async def initialize(self) -> bool:
        """
        Inicializa o gerenciador de modelos
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            logger.info("🧠 Inicializando Model Manager...")
            
            # Carregar modelos salvos se existirem
            await self._load_saved_models()
            
            # Inicializar modelos habilitados
            enabled_models = self._get_enabled_models()
            
            for model_name in enabled_models:
                success = await self._initialize_model(model_name)
                if not success:
                    logger.warning(f"⚠️ Falha ao inicializar modelo: {model_name}")
            
            # Inicializar ensemble se configurado
            if self.models_config.get('ensemble', {}).get('enabled', True):
                await self._initialize_ensemble()
            
            # Carregar dados de treinamento se disponíveis
            await self._load_training_data()
            
            self.is_initialized = True
            logger.info(f"✅ Model Manager inicializado com {len(self.active_models)} modelos")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização do Model Manager: {e}")
            return False
    
    async def train_models_offline(self, data: Optional[pd.DataFrame] = None) -> bool:
        """
        Treina todos os modelos offline
        
        Args:
            data: Dados de treinamento (opcional)
            
        Returns:
            bool: True se treinamento bem-sucedido
        """
        if self.training_in_progress:
            logger.warning("⚠️ Treinamento já em progresso")
            return False
        
        try:
            self.training_in_progress = True
            logger.info("🎯 Iniciando treinamento offline dos modelos...")
            
            # Usar dados fornecidos ou carregar dados históricos
            if data is not None:
                training_data = data
            else:
                training_data = await self._prepare_training_data()
            
            if training_data is None or len(training_data) < 1000:
                logger.error("❌ Dados insuficientes para treinamento")
                return False
            
            # Preparar features e targets
            X, y = await self._prepare_features_and_targets(training_data)
            
            if X is None or y is None:
                logger.error("❌ Erro na preparação de features")
                return False
            
            # Split train/validation
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Treinar cada modelo
            training_results = {}
            
            for model_name, model in self.active_models.items():
                logger.info(f"🔄 Treinando modelo: {model_name}")
                
                try:
                    # Treinar modelo
                    training_result = await model.train(X_train, y_train, X_val, y_val)
                    training_results[model_name] = training_result
                    
                    # Avaliar modelo
                    metrics = await self._evaluate_model(model, X_val, y_val)
                    self.model_metrics[model_name] = metrics
                    
                    logger.info(f"✅ Modelo {model_name} treinado - Accuracy: {metrics.get('accuracy', 0):.3f}")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao treinar {model_name}: {e}")
                    training_results[model_name] = {'success': False, 'error': str(e)}
            
            # Treinar ensemble
            if self.ensemble_model and len([r for r in training_results.values() if r.get('success', False)]) > 1:
                logger.info("🔄 Treinando ensemble...")
                
                try:
                    ensemble_result = await self._train_ensemble(X_train, y_train, X_val, y_val)
                    training_results['ensemble'] = ensemble_result
                    
                    # Avaliar ensemble
                    ensemble_metrics = await self._evaluate_model(self.ensemble_model, X_val, y_val)
                    self.model_metrics['ensemble'] = ensemble_metrics
                    
                    logger.info(f"✅ Ensemble treinado - Accuracy: {ensemble_metrics.get('accuracy', 0):.3f}")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao treinar ensemble: {e}")
            
            # Salvar modelos treinados
            await self._save_models()
            
            # Atualizar timestamp
            self.last_training_time = datetime.now()
            
            # Log resumo do treinamento
            successful_models = len([r for r in training_results.values() if r.get('success', False)])
            logger.info(f"🎯 Treinamento concluído: {successful_models}/{len(training_results)} modelos")
            
            return successful_models > 0
            
        except Exception as e:
            logger.error(f"❌ Erro no treinamento offline: {e}")
            return False
        finally:
            self.training_in_progress = False
    
    async def predict(
        self, 
        features: pd.DataFrame, 
        model_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Faz predição usando modelo específico ou ensemble
        
        Args:
            features: Features para predição
            model_name: Nome do modelo (None para ensemble)
            
        Returns:
            Optional[Dict]: Resultado da predição
        """
        try:
            # Preprocessar features
            processed_features = await self._preprocess_features(features)
            
            if processed_features is None:
                return None
            
            # Usar modelo específico ou ensemble
            if model_name and model_name in self.active_models:
                model = self.active_models[model_name]
                prediction = await model.predict(processed_features)
                
                return {
                    'model': model_name,
                    'prediction': prediction,
                    'confidence': getattr(model, 'last_confidence', 0.5),
                    'timestamp': datetime.now()
                }
            
            elif self.ensemble_model:
                # Usar ensemble
                prediction = await self.ensemble_model.predict(processed_features)
                
                return {
                    'model': 'ensemble',
                    'prediction': prediction,
                    'confidence': getattr(self.ensemble_model, 'last_confidence', 0.5),
                    'timestamp': datetime.now()
                }
            
            else:
                logger.warning("⚠️ Nenhum modelo disponível para predição")
                return None
            
        except Exception as e:
            logger.error(f"❌ Erro na predição: {e}")
            return None
    
    async def get_model_metrics(self) -> Dict[str, Dict[str, float]]:
        """
        Retorna métricas de todos os modelos
        
        Returns:
            Dict: Métricas dos modelos
        """
        return self.model_metrics.copy()
    
    async def retrain_if_needed(self) -> bool:
        """
        Retreina modelos se necessário
        
        Returns:
            bool: True se retreinamento foi executado
        """
        try:
            # Verificar se é hora de retreinar
            time_since_training = datetime.now() - self.last_training_time
            retrain_interval = timedelta(days=self.models_config.get('retrain_interval_days', 7))
            
            if time_since_training < retrain_interval:
                return False
            
            # Verificar se performance degradou
            if await self._should_retrain_based_on_performance():
                logger.info("🔄 Iniciando retreinamento automático...")
                return await self.train_models_offline()
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro no retreinamento automático: {e}")
            return False
    
    async def shutdown(self):
        """
        Shutdown do gerenciador
        """
        try:
            logger.info("🛑 Finalizando Model Manager...")
            
            # Salvar modelos
            await self._save_models()
            
            # Limpar modelos da memória
            self.active_models.clear()
            self.ensemble_model = None
            
            logger.info("✅ Model Manager finalizado")
            
        except Exception as e:
            logger.error(f"❌ Erro no shutdown: {e}")
    
    def _get_enabled_models(self) -> List[str]:
        """
        Obtém lista de modelos habilitados
        
        Returns:
            List[str]: Nomes dos modelos habilitados
        """
        enabled = []
        
        for model_name, model_config in self.models_config.items():
            if (model_config.get('enabled', False) and 
                model_name in self.available_models):
                enabled.append(model_name)
        
        return enabled
    
    async def _initialize_model(self, model_name: str) -> bool:
        """
        Inicializa um modelo específico
        
        Args:
            model_name: Nome do modelo
            
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            if model_name not in self.available_models:
                logger.error(f"❌ Modelo desconhecido: {model_name}")
                return False
            
            # Obter configuração do modelo
            model_config = self.models_config.get(model_name, {})
            
            # Criar instância do modelo
            model_class = self.available_models[model_name]
            model = model_class(model_config)
            
            # Inicializar modelo
            if await model.initialize():
                self.active_models[model_name] = model
                logger.info(f"✅ Modelo {model_name} inicializado")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar modelo {model_name}: {e}")
            return False
    
    async def _initialize_ensemble(self) -> bool:
        """
        Inicializa modelo ensemble
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            if len(self.active_models) < 2:
                logger.warning("⚠️ Modelos insuficientes para ensemble")
                return False
            
            ensemble_config = self.models_config.get('ensemble', {})
            
            self.ensemble_model = EnsembleModel(
                list(self.active_models.values()),
                ensemble_config
            )
            
            if await self.ensemble_model.initialize():
                logger.info("✅ Ensemble inicializado")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar ensemble: {e}")
            return False
    
    async def _load_saved_models(self):
        """
        Carrega modelos salvos do disco
        """
        try:
            models_found = 0
            
            for model_file in self.models_path.glob("*.pkl"):
                try:
                    model_name = model_file.stem
                    
                    with open(model_file, 'rb') as f:
                        model_data = pickle.load(f)
                    
                    # Recriar modelo
                    if model_name in self.available_models:
                        model_class = self.available_models[model_name]
                        model = model_class(self.models_config.get(model_name, {}))
                        
                        # Carregar estado do modelo
                        if await model.load_state(model_data):
                            self.active_models[model_name] = model
                            models_found += 1
                            logger.info(f"📁 Modelo {model_name} carregado do disco")
                
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao carregar modelo {model_file}: {e}")
            
            if models_found > 0:
                logger.info(f"📁 {models_found} modelos carregados do disco")
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelos salvos: {e}")
    
    async def _save_models(self):
        """
        Salva modelos no disco
        """
        try:
            saved_count = 0
            
            for model_name, model in self.active_models.items():
                try:
                    model_file = self.models_path / f"{model_name}.pkl"
                    
                    # Obter estado do modelo
                    model_state = await model.get_state()
                    
                    # Salvar no disco
                    with open(model_file, 'wb') as f:
                        pickle.dump(model_state, f)
                    
                    saved_count += 1
                    logger.info(f"💾 Modelo {model_name} salvo")
                
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao salvar modelo {model_name}: {e}")
            
            # Salvar ensemble se existir
            if self.ensemble_model:
                try:
                    ensemble_file = self.models_path / "ensemble.pkl"
                    ensemble_state = await self.ensemble_model.get_state()
                    
                    with open(ensemble_file, 'wb') as f:
                        pickle.dump(ensemble_state, f)
                    
                    saved_count += 1
                    logger.info("💾 Ensemble salvo")
                
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao salvar ensemble: {e}")
            
            logger.info(f"💾 {saved_count} modelos salvos")
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar modelos: {e}")
    
    async def _load_training_data(self):
        """
        Carrega dados de treinamento
        """
        try:
            # Implementar carregamento de dados históricos
            # Por enquanto, dados vazios
            self.training_data = pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar dados de treinamento: {e}")
    
    async def _prepare_training_data(self) -> Optional[pd.DataFrame]:
        """
        Prepara dados de treinamento
        
        Returns:
            Optional[pd.DataFrame]: Dados preparados
        """
        try:
            # Implementar preparação de dados
            # Por enquanto, retornar dados vazios
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ Erro ao preparar dados: {e}")
            return None
    
    async def _prepare_features_and_targets(
        self, 
        data: pd.DataFrame
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
        """
        Prepara features e targets para treinamento
        
        Args:
            data: Dados brutos
            
        Returns:
            Tuple: (features, targets)
        """
        try:
            # Implementar preparação de features
            # Por enquanto, retornar None
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Erro ao preparar features: {e}")
            return None, None
    
    async def _preprocess_features(self, features: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Preprocessa features para predição
        
        Args:
            features: Features brutas
            
        Returns:
            Optional[pd.DataFrame]: Features processadas
        """
        try:
            # Implementar preprocessamento
            return features
            
        except Exception as e:
            logger.error(f"❌ Erro no preprocessamento: {e}")
            return None
    
    async def _evaluate_model(self, model, X_val: pd.DataFrame, y_val: pd.Series) -> Dict[str, float]:
        """
        Avalia performance de um modelo
        
        Args:
            model: Modelo a ser avaliado
            X_val: Features de validação
            y_val: Targets de validação
            
        Returns:
            Dict: Métricas de performance
        """
        try:
            # Fazer predições
            predictions = await model.predict(X_val)
            
            # Calcular métricas
            metrics = {
                'accuracy': accuracy_score(y_val, predictions),
                'precision': precision_score(y_val, predictions, average='weighted'),
                'recall': recall_score(y_val, predictions, average='weighted'),
                'f1_score': f1_score(y_val, predictions, average='weighted')
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Erro na avaliação: {e}")
            return {}
    
    async def _train_ensemble(
        self, 
        X_train: pd.DataFrame, 
        y_train: pd.Series,
        X_val: pd.DataFrame, 
        y_val: pd.Series
    ) -> Dict[str, Any]:
        """
        Treina modelo ensemble
        
        Args:
            X_train: Features de treinamento
            y_train: Targets de treinamento
            X_val: Features de validação
            y_val: Targets de validação
            
        Returns:
            Dict: Resultado do treinamento
        """
        try:
            if self.ensemble_model:
                return await self.ensemble_model.train(X_train, y_train, X_val, y_val)
            
            return {'success': False, 'error': 'Ensemble não inicializado'}
            
        except Exception as e:
            logger.error(f"❌ Erro no treinamento do ensemble: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _should_retrain_based_on_performance(self) -> bool:
        """
        Verifica se deve retreinar baseado na performance
        
        Returns:
            bool: True se deve retreinar
        """
        try:
            # Implementar lógica de verificação de performance
            # Por enquanto, sempre retornar False
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar performance: {e}")
            return False
    
    def get_model_status(self) -> Dict[str, Any]:
        """
        Retorna status dos modelos
        
        Returns:
            Dict: Status dos modelos
        """
        return {
            'initialized': self.is_initialized,
            'training_in_progress': self.training_in_progress,
            'last_training_time': self.last_training_time.isoformat(),
            'active_models': list(self.active_models.keys()),
            'ensemble_enabled': self.ensemble_model is not None,
            'model_metrics': self.model_metrics
        }

