import logging
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ClusteringResult:
    labels: np.ndarray
    n_clusters: int
    centroids: Optional[np.ndarray] = None
    silhouette_score: float = 0.0
    calinski_harabasz_score: float = 0.0
    davies_bouldin_score: float = 0.0
    cluster_sizes: Dict[int, int] = field(default_factory=dict)


class IaCClusterer(ABC):
    def __init__(self):
        self.model = None
        self.is_fitted = False

    @abstractmethod
    def fit(self, X: np.ndarray) -> ClusteringResult:
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        pass

    def _calculate_metrics(
        self, X: np.ndarray, labels: np.ndarray
    ) -> Tuple[float, float, float]:
        from sklearn.metrics import (
            silhouette_score,
            calinski_harabasz_score,
            davies_bouldin_score,
        )

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        if n_clusters < 2:
            return 0.0, 0.0, float("inf")

        mask = labels != -1
        if np.sum(mask) < 2:
            return 0.0, 0.0, float("inf")

        silhouette = silhouette_score(X[mask], labels[mask])
        calinski = calinski_harabasz_score(X[mask], labels[mask])
        davies = davies_bouldin_score(X[mask], labels[mask])

        return silhouette, calinski, davies


class KMeansClusterer(IaCClusterer):
    def __init__(
        self,
        n_clusters: int = 5,
        max_iter: int = 300,
        n_init: int = 10,
        auto_k: bool = False,
    ):
        super().__init__()
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.n_init = n_init
        self.auto_k = auto_k

    def fit(self, X: np.ndarray) -> ClusteringResult:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        if self.auto_k:
            self.n_clusters = self._find_optimal_k(X_scaled)
            logger.info(f"Auto-selected k={self.n_clusters}")

        self.model = KMeans(
            n_clusters=self.n_clusters,
            init="k-means++",
            max_iter=self.max_iter,
            n_init=self.n_init,
            random_state=42,
        )
        labels = self.model.fit_predict(X_scaled)
        silhouette, calinski, davies = self._calculate_metrics(X_scaled, labels)

        unique, counts = np.unique(labels, return_counts=True)
        cluster_sizes = dict(zip(unique.tolist(), counts.tolist()))

        self.is_fitted = True
        self.scaler = scaler

        return ClusteringResult(
            labels=labels,
            n_clusters=self.n_clusters,
            centroids=self.model.cluster_centers_,
            silhouette_score=silhouette,
            calinski_harabasz_score=calinski,
            davies_bouldin_score=davies,
            cluster_sizes=cluster_sizes,
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def _find_optimal_k(self, X: np.ndarray, max_k: int = 15) -> int:
        from sklearn.cluster import KMeans

        inertias = []
        k_range = range(2, min(max_k + 1, len(X)))

        for k in k_range:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(X)
            inertias.append(kmeans.inertia_)

        if len(inertias) < 3:
            return 2

        d1 = np.diff(inertias)
        d2 = np.diff(d1)

        elbow_idx = np.argmax(d2) + 2

        return list(k_range)[elbow_idx] if elbow_idx < len(k_range) else 5


class DBSCANClusterer(IaCClusterer):
    def __init__(
        self, eps: Optional[float] = None, min_samples: int = 5, auto_eps: bool = True
    ):
        super().__init__()
        self.eps = eps
        self.min_samples = min_samples
        self.auto_eps = auto_eps

    def fit(self, X: np.ndarray) -> ClusteringResult:
        from sklearn.cluster import DBSCAN
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        if self.auto_eps:
            self.eps = self._estimate_eps(X_scaled)
            logger.info(f"Auto-estimated eps={self.eps:.4f}")

        self.model = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        labels = self.model.fit_predict(X_scaled)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        silhouette, calinski, davies = self._calculate_metrics(X_scaled, labels)

        unique, counts = np.unique(labels, return_counts=True)
        cluster_sizes = dict(zip(unique.tolist(), counts.tolist()))

        self.is_fitted = True
        self.scaler = scaler

        return ClusteringResult(
            labels=labels,
            n_clusters=n_clusters,
            silhouette_score=silhouette,
            calinski_harabasz_score=calinski,
            davies_bouldin_score=davies,
            cluster_sizes=cluster_sizes,
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        X_scaled = self.scaler.transform(X)

        from sklearn.neighbors import NearestNeighbors

        core_samples = self.model.components_
        if len(core_samples) == 0:
            return np.array([-1] * len(X))

        nn = NearestNeighbors(n_neighbors=1)
        nn.fit(core_samples)

        distances, indices = nn.kneighbors(X_scaled)
        labels = self.model.labels_[self.model.core_sample_indices_][indices.flatten()]

        labels[distances.flatten() > self.eps] = -1

        return labels

    def _estimate_eps(self, X: np.ndarray) -> float:
        from sklearn.neighbors import NearestNeighbors

        k = self.min_samples
        nn = NearestNeighbors(n_neighbors=k)
        nn.fit(X)

        distances, _ = nn.kneighbors(X)
        k_distances = np.sort(distances[:, -1])

        n = len(k_distances)
        idx = int(0.9 * n)

        return k_distances[idx]


class HierarchicalClusterer(IaCClusterer):
    def __init__(
        self,
        n_clusters: Optional[int] = None,
        linkage: str = "ward",
        distance_threshold: Optional[float] = None,
    ):
        super().__init__()
        self.n_clusters = n_clusters
        self.linkage = linkage
        self.distance_threshold = distance_threshold

    def fit(self, X: np.ndarray) -> ClusteringResult:
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        if self.n_clusters is None and self.distance_threshold is None:
            self.n_clusters = self._find_optimal_clusters(X_scaled)
            logger.info(f"Auto-selected n_clusters={self.n_clusters}")

        self.model = AgglomerativeClustering(
            n_clusters=self.n_clusters,
            linkage=self.linkage,
            distance_threshold=self.distance_threshold,
        )
        labels = self.model.fit_predict(X_scaled)

        n_clusters = len(set(labels))
        silhouette, calinski, davies = self._calculate_metrics(X_scaled, labels)

        unique, counts = np.unique(labels, return_counts=True)
        cluster_sizes = dict(zip(unique.tolist(), counts.tolist()))

        self.is_fitted = True
        self.scaler = scaler

        return ClusteringResult(
            labels=labels,
            n_clusters=n_clusters,
            silhouette_score=silhouette,
            calinski_harabasz_score=calinski,
            davies_bouldin_score=davies,
            cluster_sizes=cluster_sizes,
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted")

        from sklearn.neighbors import NearestNeighbors

        X_scaled = self.scaler.transform(X)

        train_labels = self.model.labels_

        nn = NearestNeighbors(n_neighbors=1)
        nn.fit(self.X_train)

        _, indices = nn.kneighbors(X_scaled)
        return train_labels[indices.flatten()]

    def _find_optimal_clusters(self, X: np.ndarray, max_clusters: int = 15) -> int:
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.metrics import silhouette_score

        best_score = -1
        best_k = 2

        for k in range(2, min(max_clusters + 1, len(X))):
            clustering = AgglomerativeClustering(n_clusters=k, linkage=self.linkage)
            labels = clustering.fit_predict(X)

            score = silhouette_score(X, labels)
            if score > best_score:
                best_score = score
                best_k = k

        return best_k
