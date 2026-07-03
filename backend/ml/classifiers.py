import logging
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ClassificationTarget(str, Enum):
    IAC_TYPE = "iac_type"
    ERROR_CATEGORY = "error_category"
    SECURITY_SEVERITY = "security_severity"
    COST_TIER = "cost_tier"
    QUALITY_LEVEL = "quality_level"
    DEPLOYMENT_RISK = "deployment_risk"


@dataclass
class ClassificationResult:
    predicted_class: str
    confidence: float
    probabilities: Dict[str, float] = field(default_factory=dict)
    features_importance: Dict[str, float] = field(default_factory=dict)
    explanation: Optional[str] = None


@dataclass
class TrainingMetrics:
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    confusion_matrix: List[List[int]] = field(default_factory=list)
    roc_auc: Optional[float] = None
    training_time: float = 0.0


class IaCClassifier(ABC):
    def __init__(self, target: ClassificationTarget):
        self.target = target
        self.is_trained = False
        self.classes: List[str] = []
        self.feature_names: List[str] = []

    @abstractmethod
    def train(
        self, X: np.ndarray, y: np.ndarray, feature_names: Optional[List[str]] = None
    ) -> TrainingMetrics:
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> List[ClassificationResult]:
        pass

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        pass

    def extract_features(self, iac_code: str) -> np.ndarray:
        features = []

        features.append(len(iac_code))
        features.append(iac_code.count("\n"))
        features.append(iac_code.count("{"))
        features.append(iac_code.count(":"))

        keywords = [
            "resource",
            "provider",
            "variable",
            "output",
            "apiVersion",
            "kind",
            "metadata",
            "spec",
            "FROM",
            "RUN",
            "COPY",
            "CMD",
            "services",
            "volumes",
            "networks",
            "hosts",
            "tasks",
            "handlers",
        ]
        for kw in keywords:
            features.append(iac_code.count(kw))

        features.append(len(set(iac_code.split())))
        features.append(iac_code.count("#") + iac_code.count("//"))

        return np.array(features).reshape(1, -1)


class SVMClassifier(IaCClassifier):
    def __init__(
        self,
        target: ClassificationTarget,
        kernel: str = "rbf",
        C: float = 1.0,
        gamma: str = "scale",
    ):
        super().__init__(target)
        self.kernel = kernel
        self.C = C
        self.gamma = gamma
        self.model = None
        self.scaler = None

    def train(
        self, X: np.ndarray, y: np.ndarray, feature_names: Optional[List[str]] = None
    ) -> TrainingMetrics:
        import time

        start_time = time.time()

        self.feature_names = feature_names or [f"f{i}" for i in range(X.shape[1])]
        self.classes = list(np.unique(y))

        from sklearn.preprocessing import StandardScaler

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        from sklearn.svm import SVC

        self.model = SVC(
            kernel=self.kernel,
            C=self.C,
            gamma=self.gamma,
            probability=True,
            class_weight="balanced",
        )
        self.model.fit(X_scaled, y)

        y_pred = self.model.predict(X_scaled)

        from sklearn.metrics import (
            accuracy_score,
            precision_score,
            recall_score,
            f1_score,
            confusion_matrix,
            roc_auc_score,
        )

        metrics = TrainingMetrics(
            accuracy=accuracy_score(y, y_pred),
            precision=precision_score(y, y_pred, average="weighted", zero_division=0),
            recall=recall_score(y, y_pred, average="weighted", zero_division=0),
            f1_score=f1_score(y, y_pred, average="weighted", zero_division=0),
            confusion_matrix=confusion_matrix(y, y_pred).tolist(),
            training_time=time.time() - start_time,
        )

        if len(self.classes) == 2:
            y_proba = self.model.predict_proba(X_scaled)[:, 1]
            metrics.roc_auc = roc_auc_score(y, y_proba)

        self.is_trained = True
        logger.info(
            f"SVM trained: accuracy={metrics.accuracy:.4f}, F1={metrics.f1_score:.4f}"
        )

        return metrics

    def predict(self, X: np.ndarray) -> List[ClassificationResult]:
        if not self.is_trained:
            raise RuntimeError("Model not trained")

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        results = []
        for i, pred in enumerate(predictions):
            proba_dict = {
                cls: float(probabilities[i, j]) for j, cls in enumerate(self.classes)
            }
            results.append(
                ClassificationResult(
                    predicted_class=str(pred),
                    confidence=float(max(probabilities[i])),
                    probabilities=proba_dict,
                )
            )

        return results

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise RuntimeError("Model not trained")
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)


class RandomForestClassifier(IaCClassifier):
    def __init__(
        self,
        target: ClassificationTarget,
        n_estimators: int = 100,
        max_depth: Optional[int] = None,
        min_samples_split: int = 2,
    ):
        super().__init__(target)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.model = None

    def train(
        self, X: np.ndarray, y: np.ndarray, feature_names: Optional[List[str]] = None
    ) -> TrainingMetrics:
        import time

        start_time = time.time()

        self.feature_names = feature_names or [f"f{i}" for i in range(X.shape[1])]
        self.classes = list(np.unique(y))

        from sklearn.ensemble import RandomForestClassifier as RF

        self.model = RF(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=self.min_samples_split,
            oob_score=True,
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        )
        self.model.fit(X, y)

        y_pred = self.model.predict(X)

        from sklearn.metrics import (
            accuracy_score,
            precision_score,
            recall_score,
            f1_score,
            confusion_matrix,
        )

        metrics = TrainingMetrics(
            accuracy=accuracy_score(y, y_pred),
            precision=precision_score(y, y_pred, average="weighted", zero_division=0),
            recall=recall_score(y, y_pred, average="weighted", zero_division=0),
            f1_score=f1_score(y, y_pred, average="weighted", zero_division=0),
            confusion_matrix=confusion_matrix(y, y_pred).tolist(),
            training_time=time.time() - start_time,
        )

        self.is_trained = True
        logger.info(
            f"RF trained: accuracy={metrics.accuracy:.4f}, OOB={self.model.oob_score_:.4f}"
        )

        return metrics

    def predict(self, X: np.ndarray) -> List[ClassificationResult]:
        if not self.is_trained:
            raise RuntimeError("Model not trained")

        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)

        importances = dict(zip(self.feature_names, self.model.feature_importances_))
        top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]

        results = []
        for i, pred in enumerate(predictions):
            proba_dict = {
                cls: float(probabilities[i, j]) for j, cls in enumerate(self.classes)
            }

            explanation = (
                f"Top features: {', '.join([f'{k}={v:.3f}' for k, v in top_features])}"
            )

            results.append(
                ClassificationResult(
                    predicted_class=str(pred),
                    confidence=float(max(probabilities[i])),
                    probabilities=proba_dict,
                    features_importance=importances,
                    explanation=explanation,
                )
            )

        return results

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise RuntimeError("Model not trained")
        return self.model.predict_proba(X)

    def get_feature_importance(self) -> Dict[str, float]:
        if not self.is_trained:
            raise RuntimeError("Model not trained")
        return dict(zip(self.feature_names, self.model.feature_importances_))


class NeuralNetworkClassifier(IaCClassifier):
    def __init__(
        self,
        target: ClassificationTarget,
        hidden_layers: Tuple[int, ...] = (128, 64, 32),
        activation: str = "relu",
        learning_rate: float = 0.001,
        max_iter: int = 500,
    ):
        super().__init__(target)
        self.hidden_layers = hidden_layers
        self.activation = activation
        self.learning_rate = learning_rate
        self.max_iter = max_iter
        self.model = None
        self.scaler = None

    def train(
        self, X: np.ndarray, y: np.ndarray, feature_names: Optional[List[str]] = None
    ) -> TrainingMetrics:
        import time

        start_time = time.time()

        self.feature_names = feature_names or [f"f{i}" for i in range(X.shape[1])]
        self.classes = list(np.unique(y))

        from sklearn.preprocessing import StandardScaler

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        from sklearn.neural_network import MLPClassifier

        self.model = MLPClassifier(
            hidden_layer_sizes=self.hidden_layers,
            activation=self.activation,
            solver="adam",
            learning_rate_init=self.learning_rate,
            max_iter=self.max_iter,
            early_stopping=True,
            validation_fraction=0.1,
            random_state=42,
        )
        self.model.fit(X_scaled, y)

        y_pred = self.model.predict(X_scaled)

        from sklearn.metrics import (
            accuracy_score,
            precision_score,
            recall_score,
            f1_score,
            confusion_matrix,
        )

        metrics = TrainingMetrics(
            accuracy=accuracy_score(y, y_pred),
            precision=precision_score(y, y_pred, average="weighted", zero_division=0),
            recall=recall_score(y, y_pred, average="weighted", zero_division=0),
            f1_score=f1_score(y, y_pred, average="weighted", zero_division=0),
            confusion_matrix=confusion_matrix(y, y_pred).tolist(),
            training_time=time.time() - start_time,
        )

        self.is_trained = True
        logger.info(
            f"NN trained: accuracy={metrics.accuracy:.4f}, iterations={self.model.n_iter_}"
        )

        return metrics

    def predict(self, X: np.ndarray) -> List[ClassificationResult]:
        if not self.is_trained:
            raise RuntimeError("Model not trained")

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        results = []
        for i, pred in enumerate(predictions):
            proba_dict = {
                cls: float(probabilities[i, j]) for j, cls in enumerate(self.classes)
            }
            results.append(
                ClassificationResult(
                    predicted_class=str(pred),
                    confidence=float(max(probabilities[i])),
                    probabilities=proba_dict,
                )
            )

        return results

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise RuntimeError("Model not trained")
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)


class EnsembleClassifier(IaCClassifier):
    def __init__(
        self, target: ClassificationTarget, weights: Optional[Dict[str, float]] = None
    ):
        super().__init__(target)
        self.weights = weights or {"svm": 0.3, "rf": 0.4, "nn": 0.3}
        self.classifiers = {
            "svm": SVMClassifier(target),
            "rf": RandomForestClassifier(target),
            "nn": NeuralNetworkClassifier(target),
        }

    def train(
        self, X: np.ndarray, y: np.ndarray, feature_names: Optional[List[str]] = None
    ) -> TrainingMetrics:
        import time

        start_time = time.time()

        self.feature_names = feature_names or [f"f{i}" for i in range(X.shape[1])]
        self.classes = list(np.unique(y))

        individual_metrics = {}
        for name, clf in self.classifiers.items():
            logger.info(f"Training {name}...")
            individual_metrics[name] = clf.train(X, y, feature_names)

        y_pred = self._ensemble_predict(X)

        from sklearn.metrics import (
            accuracy_score,
            precision_score,
            recall_score,
            f1_score,
            confusion_matrix,
        )

        metrics = TrainingMetrics(
            accuracy=accuracy_score(y, y_pred),
            precision=precision_score(y, y_pred, average="weighted", zero_division=0),
            recall=recall_score(y, y_pred, average="weighted", zero_division=0),
            f1_score=f1_score(y, y_pred, average="weighted", zero_division=0),
            confusion_matrix=confusion_matrix(y, y_pred).tolist(),
            training_time=time.time() - start_time,
        )

        self.is_trained = True
        logger.info(f"Ensemble trained: accuracy={metrics.accuracy:.4f}")

        return metrics

    def _ensemble_predict(self, X: np.ndarray) -> np.ndarray:
        all_proba = []
        weights = []

        for name, clf in self.classifiers.items():
            if clf.is_trained:
                proba = clf.predict_proba(X)
                all_proba.append(proba * self.weights[name])
                weights.append(self.weights[name])

        combined_proba = np.sum(all_proba, axis=0) / sum(weights)

        predictions = [self.classes[i] for i in np.argmax(combined_proba, axis=1)]
        return np.array(predictions)

    def predict(self, X: np.ndarray) -> List[ClassificationResult]:
        if not self.is_trained:
            raise RuntimeError("Model not trained")

        predictions = self._ensemble_predict(X)
        probabilities = self.predict_proba(X)

        results = []
        for i, pred in enumerate(predictions):
            proba_dict = {
                cls: float(probabilities[i, j]) for j, cls in enumerate(self.classes)
            }

            individual_preds = {}
            for name, clf in self.classifiers.items():
                if clf.is_trained:
                    ind_result = clf.predict(X[i : i + 1])[0]
                    individual_preds[name] = ind_result.predicted_class

            explanation = f"Individual: {individual_preds}"

            results.append(
                ClassificationResult(
                    predicted_class=str(pred),
                    confidence=float(max(probabilities[i])),
                    probabilities=proba_dict,
                    explanation=explanation,
                )
            )

        return results

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise RuntimeError("Model not trained")

        all_proba = []
        weights = []

        for name, clf in self.classifiers.items():
            if clf.is_trained:
                proba = clf.predict_proba(X)
                all_proba.append(proba * self.weights[name])
                weights.append(self.weights[name])

        return np.sum(all_proba, axis=0) / sum(weights)
