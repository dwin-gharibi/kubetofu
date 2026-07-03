import logging
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    SECURITY = "security"
    CONFIGURATION = "configuration"
    RESOURCE = "resource"
    PERFORMANCE = "performance"
    UNKNOWN = "unknown"


@dataclass
class AnomalyResult:
    is_anomaly: bool
    anomaly_score: float
    anomaly_type: AnomalyType = AnomalyType.UNKNOWN
    confidence: float = 0.0
    explanation: Optional[str] = None
    features_contribution: Dict[str, float] = field(default_factory=dict)


@dataclass
class DetectionMetrics:
    precision: float
    recall: float
    f1_score: float
    auc_roc: float
    false_positive_rate: float
    true_positive_rate: float


class AnomalyDetector(ABC):
    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.model = None
        self.is_fitted = False
        self.threshold: float = 0.0

    @abstractmethod
    def fit(self, X: np.ndarray) -> None:
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> List[AnomalyResult]:
        pass

    @abstractmethod
    def score_samples(self, X: np.ndarray) -> np.ndarray:
        pass

    def evaluate(self, X: np.ndarray, y_true: np.ndarray) -> DetectionMetrics:
        from sklearn.metrics import (
            precision_score,
            recall_score,
            f1_score,
            roc_auc_score,
            roc_curve,
        )

        predictions = [r.is_anomaly for r in self.predict(X)]
        y_pred = np.array([1 if p else 0 for p in predictions])
        scores = self.score_samples(X)

        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)

        try:
            auc = roc_auc_score(y_true, scores)
        except:
            auc = 0.0

        fpr, tpr, _ = roc_curve(y_true, scores)

        return DetectionMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            auc_roc=auc,
            false_positive_rate=float(np.mean(fpr)),
            true_positive_rate=float(np.mean(tpr)),
        )


class IsolationForestDetector(AnomalyDetector):
    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        max_samples: str = "auto",
    ):
        super().__init__(contamination)
        self.n_estimators = n_estimators
        self.max_samples = max_samples

    def fit(self, X: np.ndarray) -> None:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            random_state=42,
        )
        self.model.fit(X_scaled)

        scores = self.model.decision_function(X_scaled)
        self.threshold = np.percentile(scores, self.contamination * 100)

        self.is_fitted = True
        logger.info(f"IsolationForest fitted with threshold={self.threshold:.4f}")

    def predict(self, X: np.ndarray) -> List[AnomalyResult]:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)

        predictions = self.model.predict(X_scaled)
        scores = self.model.decision_function(X_scaled)

        results = []
        for i, (pred, score) in enumerate(zip(predictions, scores)):
            is_anomaly = pred == -1

            anomaly_score = 1 - (score - scores.min()) / (
                scores.max() - scores.min() + 1e-9
            )

            results.append(
                AnomalyResult(
                    is_anomaly=is_anomaly,
                    anomaly_score=float(anomaly_score),
                    confidence=float(
                        abs(score - self.threshold) / (abs(self.threshold) + 1e-9)
                    ),
                    explanation=f"Isolation depth score: {score:.4f}",
                )
            )

        return results

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")
        X_scaled = self.scaler.transform(X)
        return -self.model.decision_function(X_scaled)


class OneClassSVMDetector(AnomalyDetector):
    def __init__(
        self,
        contamination: float = 0.1,
        kernel: str = "rbf",
        nu: Optional[float] = None,
        gamma: str = "scale",
    ):
        super().__init__(contamination)
        self.kernel = kernel
        self.nu = nu or contamination
        self.gamma = gamma

    def fit(self, X: np.ndarray) -> None:
        from sklearn.svm import OneClassSVM
        from sklearn.preprocessing import StandardScaler

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = OneClassSVM(kernel=self.kernel, nu=self.nu, gamma=self.gamma)
        self.model.fit(X_scaled)

        scores = self.model.decision_function(X_scaled)
        self.threshold = np.percentile(scores, self.contamination * 100)

        self.is_fitted = True
        logger.info(f"OneClassSVM fitted with nu={self.nu}")

    def predict(self, X: np.ndarray) -> List[AnomalyResult]:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)

        predictions = self.model.predict(X_scaled)
        scores = self.model.decision_function(X_scaled)

        results = []
        for pred, score in zip(predictions, scores):
            is_anomaly = pred == -1

            anomaly_score = 1 - (score - scores.min()) / (
                scores.max() - scores.min() + 1e-9
            )

            results.append(
                AnomalyResult(
                    is_anomaly=is_anomaly,
                    anomaly_score=float(anomaly_score),
                    confidence=float(abs(score) / (abs(self.threshold) + 1e-9)),
                    explanation=f"Distance from boundary: {score:.4f}",
                )
            )

        return results

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")
        X_scaled = self.scaler.transform(X)
        return -self.model.decision_function(X_scaled)


class AutoencoderDetector(AnomalyDetector):
    def __init__(
        self,
        contamination: float = 0.1,
        encoding_dim: int = 8,
        hidden_layers: Tuple[int, ...] = (32, 16),
        epochs: int = 100,
    ):
        super().__init__(contamination)
        self.encoding_dim = encoding_dim
        self.hidden_layers = hidden_layers
        self.epochs = epochs

    def fit(self, X: np.ndarray) -> None:
        from sklearn.preprocessing import StandardScaler
        from sklearn.neural_network import MLPRegressor

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        layers = (
            list(self.hidden_layers)
            + [self.encoding_dim]
            + list(reversed(self.hidden_layers))
        )

        self.model = MLPRegressor(
            hidden_layer_sizes=tuple(layers),
            activation="relu",
            solver="adam",
            max_iter=self.epochs,
            early_stopping=True,
            validation_fraction=0.1,
            random_state=42,
        )

        self.model.fit(X_scaled, X_scaled)

        reconstructed = self.model.predict(X_scaled)
        errors = np.mean((X_scaled - reconstructed) ** 2, axis=1)
        self.threshold = np.percentile(errors, (1 - self.contamination) * 100)

        self.is_fitted = True
        logger.info(f"Autoencoder fitted with threshold={self.threshold:.4f}")

    def predict(self, X: np.ndarray) -> List[AnomalyResult]:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)
        reconstructed = self.model.predict(X_scaled)

        errors = np.mean((X_scaled - reconstructed) ** 2, axis=1)

        results = []
        for i, error in enumerate(errors):
            is_anomaly = error > self.threshold

            feature_errors = (X_scaled[i] - reconstructed[i]) ** 2
            total_error = np.sum(feature_errors)
            contributions = {
                f"f{j}": float(fe / (total_error + 1e-9))
                for j, fe in enumerate(feature_errors)
            }

            results.append(
                AnomalyResult(
                    is_anomaly=is_anomaly,
                    anomaly_score=float(error / (self.threshold + 1e-9)),
                    confidence=float(
                        abs(error - self.threshold) / (self.threshold + 1e-9)
                    ),
                    features_contribution=contributions,
                    explanation=f"Reconstruction error: {error:.4f} (threshold: {self.threshold:.4f})",
                )
            )

        return results

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")
        X_scaled = self.scaler.transform(X)
        reconstructed = self.model.predict(X_scaled)
        return np.mean((X_scaled - reconstructed) ** 2, axis=1)


class EnsembleAnomalyDetector(AnomalyDetector):
    def __init__(
        self, contamination: float = 0.1, weights: Optional[Dict[str, float]] = None
    ):
        super().__init__(contamination)
        self.weights = weights or {
            "isolation_forest": 0.4,
            "one_class_svm": 0.3,
            "autoencoder": 0.3,
        }
        self.detectors = {}

    def fit(self, X: np.ndarray) -> None:
        self.detectors["isolation_forest"] = IsolationForestDetector(self.contamination)
        self.detectors["one_class_svm"] = OneClassSVMDetector(self.contamination)
        self.detectors["autoencoder"] = AutoencoderDetector(self.contamination)

        for name, detector in self.detectors.items():
            logger.info(f"Fitting {name}...")
            detector.fit(X)

        self.is_fitted = True
        logger.info("Ensemble anomaly detector fitted")

    def predict(self, X: np.ndarray) -> List[AnomalyResult]:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        all_results = {
            name: detector.predict(X) for name, detector in self.detectors.items()
        }

        combined_results = []
        for i in range(len(X)):
            weighted_score = sum(
                all_results[name][i].anomaly_score * self.weights[name]
                for name in self.detectors.keys()
            )

            votes = sum(
                1 if all_results[name][i].is_anomaly else 0
                for name in self.detectors.keys()
            )
            is_anomaly = votes >= len(self.detectors) / 2

            individual = {
                name: all_results[name][i].is_anomaly for name in self.detectors.keys()
            }

            combined_results.append(
                AnomalyResult(
                    is_anomaly=is_anomaly,
                    anomaly_score=weighted_score,
                    confidence=float(
                        abs(votes - len(self.detectors) / 2) / len(self.detectors)
                    ),
                    explanation=f"Individual: {individual}, weighted_score={weighted_score:.4f}",
                )
            )

        return combined_results

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        scores = []
        for name, detector in self.detectors.items():
            scores.append(detector.score_samples(X) * self.weights[name])

        return np.sum(scores, axis=0)
