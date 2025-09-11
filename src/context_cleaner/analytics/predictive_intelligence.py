"""
Advanced Predictive Intelligence Engine for Context Cleaner

This module provides sophisticated predictive analytics capabilities building upon
the existing analytics foundation, adding enterprise-grade forecasting, early warning
systems, and intelligent optimization recommendations.

Phase 4 - PR23: Advanced Predictive Analytics Suite
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
import json

from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class ForecastHorizon(Enum):
    """Forecast time horizons for predictive models."""
    HOUR = "1hour"
    DAY = "1day"
    WEEK = "1week"
    MONTH = "1month"
    QUARTER = "3months"


class PredictionType(Enum):
    """Types of predictions supported by the engine."""
    PRODUCTIVITY = "productivity"
    CONTEXT_HEALTH = "context_health"
    USAGE_PATTERN = "usage_pattern"
    RESOURCE_OPTIMIZATION = "resource_optimization"
    COST_FORECAST = "cost_forecast"


@dataclass
class PredictionResult:
    """Container for prediction results with confidence intervals."""
    prediction_id: str
    model_type: PredictionType
    horizon: ForecastHorizon
    predicted_value: float
    confidence_interval: Tuple[float, float]
    confidence_level: float = 0.95
    model_accuracy: float = 0.0
    feature_importance: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert prediction result to dictionary format."""
        return {
            "prediction_id": self.prediction_id,
            "model_type": self.model_type.value,
            "horizon": self.horizon.value,
            "predicted_value": self.predicted_value,
            "confidence_interval": list(self.confidence_interval),
            "confidence_level": self.confidence_level,
            "model_accuracy": self.model_accuracy,
            "feature_importance": self.feature_importance,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class EarlyWarning:
    """Early warning alert for predicted issues."""
    warning_id: str
    warning_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    predicted_event: str
    probability: float
    time_to_event: timedelta
    recommended_actions: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert warning to dictionary format."""
        return {
            "warning_id": self.warning_id,
            "warning_type": self.warning_type,
            "severity": self.severity,
            "predicted_event": self.predicted_event,
            "probability": self.probability,
            "time_to_event_hours": self.time_to_event.total_seconds() / 3600,
            "recommended_actions": self.recommended_actions,
            "created_at": self.created_at.isoformat()
        }


class ProductivityForecastEngine:
    """Advanced productivity forecasting with multi-variate time series analysis."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the productivity forecast engine."""
        self.config = config or {}
        self.models = {}
        self.scalers = {}
        self.feature_history = []
        self.accuracy_history = {}
        
        # Model hyperparameters
        self.rf_params = {
            'n_estimators': 100,
            'max_depth': 10,
            'random_state': 42
        }
        
    async def train_models(self, historical_data: pd.DataFrame) -> Dict[str, float]:
        """Train predictive models on historical productivity data."""
        logger.info("Training productivity forecast models...")
        
        try:
            # Feature engineering
            features = self._engineer_features(historical_data)
            
            # Train models for different horizons
            accuracies = {}
            for horizon in [ForecastHorizon.HOUR, ForecastHorizon.DAY, ForecastHorizon.WEEK]:
                X, y = self._prepare_training_data(features, horizon)
                
                if len(X) < 10:  # Need minimum data points
                    logger.warning(f"Insufficient data for {horizon.value} forecasting")
                    continue
                
                # Scale features
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                self.scalers[horizon] = scaler
                
                # Train Random Forest model
                model = RandomForestRegressor(**self.rf_params)
                model.fit(X_scaled, y)
                self.models[horizon] = model
                
                # Calculate accuracy
                y_pred = model.predict(X_scaled)
                accuracy = r2_score(y, y_pred)
                accuracies[horizon.value] = accuracy
                
                logger.info(f"Model trained for {horizon.value}: R² = {accuracy:.3f}")
            
            return accuracies
            
        except Exception as e:
            logger.error(f"Error training productivity models: {e}")
            return {}
    
    async def forecast_productivity(
        self, 
        horizon: ForecastHorizon,
        current_features: Dict[str, float] = None
    ) -> Optional[PredictionResult]:
        """Generate productivity forecast for specified horizon."""
        
        if horizon not in self.models:
            logger.warning(f"No trained model available for {horizon.value}")
            return None
            
        try:
            # Get current features or use defaults
            if current_features is None:
                current_features = await self._get_current_features()
            
            # Prepare feature vector
            feature_vector = self._prepare_feature_vector(current_features)
            
            # Scale features
            scaler = self.scalers[horizon]
            feature_vector_scaled = scaler.transform([feature_vector])
            
            # Make prediction
            model = self.models[horizon]
            prediction = model.predict(feature_vector_scaled)[0]
            
            # Calculate confidence interval using model uncertainty
            predictions = np.array([
                tree.predict(feature_vector_scaled)[0] 
                for tree in model.estimators_
            ])
            confidence_interval = (
                float(np.percentile(predictions, 2.5)),
                float(np.percentile(predictions, 97.5))
            )
            
            # Feature importance
            feature_names = list(current_features.keys())
            importance_dict = dict(zip(
                feature_names,
                model.feature_importances_.tolist()
            ))
            
            return PredictionResult(
                prediction_id=f"prod_{horizon.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                model_type=PredictionType.PRODUCTIVITY,
                horizon=horizon,
                predicted_value=float(prediction),
                confidence_interval=confidence_interval,
                model_accuracy=self.accuracy_history.get(horizon, 0.0),
                feature_importance=importance_dict,
                metadata={
                    'current_features': current_features,
                    'model_trees': len(model.estimators_)
                }
            )
            
        except Exception as e:
            logger.error(f"Error forecasting productivity: {e}")
            return None
    
    def _engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engineer features for productivity forecasting."""
        # Time-based features
        data['hour'] = pd.to_datetime(data.get('timestamp', pd.Timestamp.now())).dt.hour
        data['day_of_week'] = pd.to_datetime(data.get('timestamp', pd.Timestamp.now())).dt.dayofweek
        data['is_weekend'] = data['day_of_week'].isin([5, 6])
        
        # Rolling averages
        for window in [3, 7, 14]:
            data[f'productivity_ma_{window}'] = data.get('productivity_score', 0).rolling(window).mean()
            
        # Volatility measures
        data['productivity_volatility'] = data.get('productivity_score', 0).rolling(7).std()
        
        # Context health features
        data['context_health_trend'] = data.get('context_health_score', 0).diff()
        
        return data.fillna(0)
    
    def _prepare_training_data(
        self, 
        features: pd.DataFrame, 
        horizon: ForecastHorizon
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data for specified forecast horizon."""
        
        # Define lag based on horizon
        horizon_lags = {
            ForecastHorizon.HOUR: 1,
            ForecastHorizon.DAY: 24,
            ForecastHorizon.WEEK: 168
        }
        
        lag = horizon_lags.get(horizon, 24)
        
        # Feature columns
        feature_cols = [
            'hour', 'day_of_week', 'is_weekend',
            'productivity_ma_3', 'productivity_ma_7', 'productivity_ma_14',
            'productivity_volatility', 'context_health_trend'
        ]
        
        # Create lagged target
        target_col = 'productivity_score'
        X = features[feature_cols].iloc[:-lag].values
        y = features[target_col].shift(-lag).dropna().values
        
        return X, y
    
    def _prepare_feature_vector(self, current_features: Dict[str, float]) -> List[float]:
        """Convert current features dictionary to feature vector."""
        feature_order = [
            'hour', 'day_of_week', 'is_weekend',
            'productivity_ma_3', 'productivity_ma_7', 'productivity_ma_14',
            'productivity_volatility', 'context_health_trend'
        ]
        
        return [current_features.get(feature, 0.0) for feature in feature_order]
    
    async def _get_current_features(self) -> Dict[str, float]:
        """Get current feature values for forecasting."""
        now = datetime.now()
        
        # TODO: Integrate with existing analytics to get real values
        return {
            'hour': float(now.hour),
            'day_of_week': float(now.weekday()),
            'is_weekend': float(now.weekday() >= 5),
            'productivity_ma_3': 0.75,  # Placeholder
            'productivity_ma_7': 0.72,  # Placeholder
            'productivity_ma_14': 0.70, # Placeholder
            'productivity_volatility': 0.15, # Placeholder
            'context_health_trend': 0.02 # Placeholder
        }


class ContextHealthPredictor:
    """Predict context health degradation and maintenance needs."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the context health predictor."""
        self.config = config or {}
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.health_model = None
        self.health_history = []
        
        # Health degradation thresholds
        self.degradation_thresholds = {
            'CRITICAL': 0.3,
            'HIGH': 0.5,
            'MEDIUM': 0.7,
            'LOW': 0.8
        }
    
    async def predict_health_degradation(
        self, 
        current_health_score: float,
        context_metrics: Dict[str, float]
    ) -> List[EarlyWarning]:
        """Predict potential context health issues."""
        
        warnings = []
        
        try:
            # Calculate degradation probability
            degradation_prob = await self._calculate_degradation_probability(
                current_health_score, context_metrics
            )
            
            # Check for immediate warnings
            for severity, threshold in self.degradation_thresholds.items():
                if current_health_score < threshold:
                    warning = EarlyWarning(
                        warning_id=f"health_{severity.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        warning_type="CONTEXT_HEALTH_DEGRADATION",
                        severity=severity,
                        predicted_event=f"Context health may degrade to {threshold} level",
                        probability=degradation_prob,
                        time_to_event=self._estimate_degradation_time(
                            current_health_score, threshold
                        ),
                        recommended_actions=self._get_health_recommendations(severity)
                    )
                    warnings.append(warning)
                    break
            
            # Anomaly detection for unusual patterns
            if len(self.health_history) > 10:
                recent_metrics = np.array([[
                    current_health_score,
                    context_metrics.get('token_count', 0),
                    context_metrics.get('conversation_length', 0),
                    context_metrics.get('complexity_score', 0)
                ]])
                
                anomaly_score = self.anomaly_detector.decision_function(recent_metrics)[0]
                
                if anomaly_score < -0.5:  # Anomaly threshold
                    anomaly_warning = EarlyWarning(
                        warning_id=f"anomaly_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        warning_type="CONTEXT_ANOMALY",
                        severity="MEDIUM",
                        predicted_event="Unusual context pattern detected",
                        probability=0.8,
                        time_to_event=timedelta(hours=2),
                        recommended_actions=[
                            "Review recent context changes",
                            "Consider context cleanup",
                            "Monitor context health closely"
                        ]
                    )
                    warnings.append(anomaly_warning)
            
            return warnings
            
        except Exception as e:
            logger.error(f"Error predicting health degradation: {e}")
            return []
    
    async def _calculate_degradation_probability(
        self, 
        current_health: float,
        metrics: Dict[str, float]
    ) -> float:
        """Calculate probability of health degradation."""
        
        # Simple heuristic model (could be ML-based)
        base_risk = 1.0 - current_health
        
        # Risk factors
        token_risk = min(metrics.get('token_count', 0) / 100000, 1.0)
        complexity_risk = metrics.get('complexity_score', 0) / 10.0
        
        total_risk = base_risk * 0.5 + token_risk * 0.3 + complexity_risk * 0.2
        
        return min(total_risk, 1.0)
    
    def _estimate_degradation_time(
        self, 
        current_health: float, 
        threshold: float
    ) -> timedelta:
        """Estimate time until health reaches threshold."""
        
        if current_health <= threshold:
            return timedelta(hours=0)
        
        # Simple linear degradation model
        degradation_rate = 0.05  # 5% per hour (placeholder)
        hours_to_threshold = (current_health - threshold) / degradation_rate
        
        return timedelta(hours=min(hours_to_threshold, 24))
    
    def _get_health_recommendations(self, severity: str) -> List[str]:
        """Get recommended actions based on health severity."""
        
        recommendations = {
            'CRITICAL': [
                "Immediate context cleanup required",
                "Consider starting fresh conversation",
                "Archive important information",
                "Review context cleanup frequency"
            ],
            'HIGH': [
                "Schedule context cleanup within 2 hours",
                "Review and summarize key points",
                "Consider conversation archival",
                "Monitor health closely"
            ],
            'MEDIUM': [
                "Plan context cleanup within 24 hours",
                "Review conversation efficiency",
                "Consider topic organization",
                "Monitor token usage"
            ],
            'LOW': [
                "Context cleanup recommended within week",
                "Continue monitoring",
                "Optimize conversation flow",
                "Review productivity patterns"
            ]
        }
        
        return recommendations.get(severity, [])


class PredictiveIntelligenceEngine:
    """Main orchestrator for all predictive intelligence capabilities."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the predictive intelligence engine."""
        self.config = config or {}
        self.productivity_engine = ProductivityForecastEngine(config)
        self.health_predictor = ContextHealthPredictor(config)
        self.prediction_cache = {}
        self.warning_cache = {}
        
    async def initialize(self, historical_data: pd.DataFrame = None):
        """Initialize all predictive models."""
        logger.info("Initializing Predictive Intelligence Engine...")
        
        try:
            if historical_data is not None and len(historical_data) > 0:
                # Train productivity models
                accuracies = await self.productivity_engine.train_models(historical_data)
                logger.info(f"Productivity models trained with accuracies: {accuracies}")
                
                # Train anomaly detection for health prediction
                if len(historical_data) > 20:
                    health_features = historical_data[[
                        'context_health_score', 'token_count', 
                        'conversation_length', 'complexity_score'
                    ]].fillna(0)
                    
                    self.health_predictor.anomaly_detector.fit(health_features)
                    logger.info("Context health anomaly detector trained")
            
            logger.info("Predictive Intelligence Engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing predictive engine: {e}")
            return False
    
    async def generate_predictions(
        self, 
        horizons: List[ForecastHorizon] = None
    ) -> List[PredictionResult]:
        """Generate predictions for specified horizons."""
        
        if horizons is None:
            horizons = [ForecastHorizon.HOUR, ForecastHorizon.DAY, ForecastHorizon.WEEK]
        
        predictions = []
        
        for horizon in horizons:
            try:
                # Productivity forecast
                prod_prediction = await self.productivity_engine.forecast_productivity(horizon)
                if prod_prediction:
                    predictions.append(prod_prediction)
                    
            except Exception as e:
                logger.error(f"Error generating prediction for {horizon.value}: {e}")
        
        return predictions
    
    async def check_early_warnings(
        self,
        current_health_score: float,
        context_metrics: Dict[str, float]
    ) -> List[EarlyWarning]:
        """Check for early warning conditions."""
        
        warnings = await self.health_predictor.predict_health_degradation(
            current_health_score, context_metrics
        )
        
        # Cache warnings
        for warning in warnings:
            self.warning_cache[warning.warning_id] = warning
        
        return warnings
    
    async def get_prediction_summary(self) -> Dict[str, Any]:
        """Get summary of all current predictions and warnings."""
        
        # Generate fresh predictions
        predictions = await self.generate_predictions()
        
        # Get current warnings (placeholder values for now)
        current_metrics = {
            'token_count': 50000,
            'conversation_length': 150,
            'complexity_score': 6.5
        }
        warnings = await self.check_early_warnings(0.75, current_metrics)
        
        return {
            'predictions': [pred.to_dict() for pred in predictions],
            'warnings': [warning.to_dict() for warning in warnings],
            'summary': {
                'total_predictions': len(predictions),
                'total_warnings': len(warnings),
                'critical_warnings': len([w for w in warnings if w.severity == 'CRITICAL']),
                'model_count': len(self.productivity_engine.models),
                'last_updated': datetime.now().isoformat()
            }
        }


# Global instance for easy access
_predictive_engine = None

def get_predictive_engine(config: Dict[str, Any] = None) -> PredictiveIntelligenceEngine:
    """Get or create global predictive intelligence engine instance."""
    global _predictive_engine
    if _predictive_engine is None:
        _predictive_engine = PredictiveIntelligenceEngine(config)
    return _predictive_engine