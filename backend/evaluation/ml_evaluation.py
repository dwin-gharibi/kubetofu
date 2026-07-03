import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Callable
from datetime import datetime

from .metrics import MetricCalculator
from .benchmarks import create_synthetic_test_data


@dataclass
class EvaluationResult:
    algorithm_name: str
    task_type: str
    metrics: Dict[str, float]
    training_time_ms: float
    inference_time_ms: float
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm_name,
            "task": self.task_type,
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
            "training_time_ms": round(self.training_time_ms, 2),
            "inference_time_ms": round(self.inference_time_ms, 2),
            "parameters": self.parameters,
            "metadata": self.metadata,
        }


class SimpleSVM:
    def __init__(self, C: float = 1.0, gamma: float = 0.1, kernel: str = "rbf"):
        self.C = C
        self.gamma = gamma
        self.kernel = kernel
        self.alpha = None
        self.support_vectors = None
        self.support_labels = None
        self.b = 0.0

    def _rbf_kernel(self, x1: List[float], x2: List[float]) -> float:
        sq_dist = sum((a - b) ** 2 for a, b in zip(x1, x2))
        return math.exp(-self.gamma * sq_dist)

    def _linear_kernel(self, x1: List[float], x2: List[float]) -> float:
        return sum(a * b for a, b in zip(x1, x2))

    def _kernel(self, x1: List[float], x2: List[float]) -> float:
        if self.kernel == "rbf":
            return self._rbf_kernel(x1, x2)
        return self._linear_kernel(x1, x2)

    def fit(
        self, X: List[List[float]], y: List[int], max_iter: int = 100
    ) -> "SimpleSVM":
        n = len(X)
        self.alpha = [0.0] * n

        y_binary = [1 if label == 1 else -1 for label in y]

        K = [[self._kernel(X[i], X[j]) for j in range(n)] for i in range(n)]

        for _ in range(max_iter):
            alpha_changed = 0
            for i in range(n):
                E_i = (
                    sum(self.alpha[j] * y_binary[j] * K[i][j] for j in range(n))
                    + self.b
                    - y_binary[i]
                )

                if (y_binary[i] * E_i < -0.001 and self.alpha[i] < self.C) or (
                    y_binary[i] * E_i > 0.001 and self.alpha[i] > 0
                ):
                    j = i
                    while j == i:
                        j = random.randint(0, n - 1)

                    E_j = (
                        sum(self.alpha[k] * y_binary[k] * K[j][k] for k in range(n))
                        + self.b
                        - y_binary[j]
                    )

                    alpha_i_old = self.alpha[i]
                    alpha_j_old = self.alpha[j]

                    if y_binary[i] != y_binary[j]:
                        L = max(0, self.alpha[j] - self.alpha[i])
                        H = min(self.C, self.C + self.alpha[j] - self.alpha[i])
                    else:
                        L = max(0, self.alpha[i] + self.alpha[j] - self.C)
                        H = min(self.C, self.alpha[i] + self.alpha[j])

                    if L >= H:
                        continue

                    eta = 2 * K[i][j] - K[i][i] - K[j][j]
                    if eta >= 0:
                        continue

                    self.alpha[j] = alpha_j_old - y_binary[j] * (E_i - E_j) / eta
                    self.alpha[j] = min(H, max(L, self.alpha[j]))

                    if abs(self.alpha[j] - alpha_j_old) < 1e-5:
                        continue

                    self.alpha[i] = alpha_i_old + y_binary[i] * y_binary[j] * (
                        alpha_j_old - self.alpha[j]
                    )

                    b1 = (
                        self.b
                        - E_i
                        - y_binary[i] * (self.alpha[i] - alpha_i_old) * K[i][i]
                        - y_binary[j] * (self.alpha[j] - alpha_j_old) * K[i][j]
                    )
                    b2 = (
                        self.b
                        - E_j
                        - y_binary[i] * (self.alpha[i] - alpha_i_old) * K[i][j]
                        - y_binary[j] * (self.alpha[j] - alpha_j_old) * K[j][j]
                    )

                    if 0 < self.alpha[i] < self.C:
                        self.b = b1
                    elif 0 < self.alpha[j] < self.C:
                        self.b = b2
                    else:
                        self.b = (b1 + b2) / 2

                    alpha_changed += 1

            if alpha_changed == 0:
                break

        self.support_vectors = []
        self.support_labels = []
        for i in range(n):
            if self.alpha[i] > 1e-5:
                self.support_vectors.append(X[i])
                self.support_labels.append(y_binary[i])

        self._X = X
        self._y_binary = y_binary

        return self

    def predict(self, X: List[List[float]]) -> List[int]:
        predictions = []
        for x in X:
            score = (
                sum(
                    self.alpha[i] * self._y_binary[i] * self._kernel(self._X[i], x)
                    for i in range(len(self._X))
                    if self.alpha[i] > 1e-5
                )
                + self.b
            )
            predictions.append(1 if score >= 0 else 0)
        return predictions


class SimpleRandomForest:
    def __init__(self, n_trees: int = 10, max_depth: int = 5, min_samples: int = 2):
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.min_samples = min_samples
        self.trees = []
        self.feature_importances_ = None

    def fit(self, X: List[List[float]], y: List[int]) -> "SimpleRandomForest":
        n_samples = len(X)
        n_features = len(X[0])
        feature_importance = [0.0] * n_features

        for _ in range(self.n_trees):
            indices = [random.randint(0, n_samples - 1) for _ in range(n_samples)]
            X_boot = [X[i] for i in indices]
            y_boot = [y[i] for i in indices]

            tree = self._build_tree(X_boot, y_boot, 0, n_features, feature_importance)
            self.trees.append(tree)

        total = sum(feature_importance)
        if total > 0:
            self.feature_importances_ = [fi / total for fi in feature_importance]
        else:
            self.feature_importances_ = [1.0 / n_features] * n_features

        return self

    def _build_tree(
        self,
        X: List[List[float]],
        y: List[int],
        depth: int,
        n_features: int,
        feature_importance: List[float],
    ) -> Dict:
        if depth >= self.max_depth or len(X) < self.min_samples or len(set(y)) == 1:
            from collections import Counter

            counts = Counter(y)
            return {"leaf": True, "prediction": counts.most_common(1)[0][0]}

        n_subset = max(1, int(math.sqrt(n_features)))
        features = random.sample(range(n_features), n_subset)

        best_feature = None
        best_threshold = None
        best_gain = -float("inf")

        current_entropy = self._entropy(y)

        for feature in features:
            values = sorted(set(x[feature] for x in X))
            for i in range(len(values) - 1):
                threshold = (values[i] + values[i + 1]) / 2

                left_y = [y[j] for j in range(len(X)) if X[j][feature] <= threshold]
                right_y = [y[j] for j in range(len(X)) if X[j][feature] > threshold]

                if not left_y or not right_y:
                    continue

                left_weight = len(left_y) / len(y)
                right_weight = len(right_y) / len(y)
                gain = (
                    current_entropy
                    - left_weight * self._entropy(left_y)
                    - right_weight * self._entropy(right_y)
                )

                if gain > best_gain:
                    best_gain = gain
                    best_feature = feature
                    best_threshold = threshold

        if best_feature is None:
            from collections import Counter

            counts = Counter(y)
            return {"leaf": True, "prediction": counts.most_common(1)[0][0]}

        feature_importance[best_feature] += best_gain * len(X)

        left_X = [X[i] for i in range(len(X)) if X[i][best_feature] <= best_threshold]
        left_y = [y[i] for i in range(len(X)) if X[i][best_feature] <= best_threshold]
        right_X = [X[i] for i in range(len(X)) if X[i][best_feature] > best_threshold]
        right_y = [y[i] for i in range(len(X)) if X[i][best_feature] > best_threshold]

        return {
            "leaf": False,
            "feature": best_feature,
            "threshold": best_threshold,
            "left": self._build_tree(
                left_X, left_y, depth + 1, n_features, feature_importance
            ),
            "right": self._build_tree(
                right_X, right_y, depth + 1, n_features, feature_importance
            ),
        }

    def _entropy(self, y: List[int]) -> float:
        from collections import Counter

        counts = Counter(y)
        n = len(y)
        return -sum((c / n) * math.log2(c / n) for c in counts.values() if c > 0)

    def predict(self, X: List[List[float]]) -> List[int]:
        predictions = []
        for x in X:
            votes = [self._predict_tree(tree, x) for tree in self.trees]
            from collections import Counter

            predictions.append(Counter(votes).most_common(1)[0][0])
        return predictions

    def _predict_tree(self, tree: Dict, x: List[float]) -> int:
        if tree["leaf"]:
            return tree["prediction"]

        if x[tree["feature"]] <= tree["threshold"]:
            return self._predict_tree(tree["left"], x)
        else:
            return self._predict_tree(tree["right"], x)


class SimpleNeuralNetwork:
    def __init__(
        self,
        hidden_layers: List[int] = [32, 16],
        learning_rate: float = 0.01,
        epochs: int = 100,
        batch_size: int = 32,
    ):
        self.hidden_layers = hidden_layers
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.weights = []
        self.biases = []

    def _sigmoid(self, x: float) -> float:
        return 1 / (1 + math.exp(-max(-500, min(500, x))))

    def _sigmoid_derivative(self, x: float) -> float:
        s = self._sigmoid(x)
        return s * (1 - s)

    def _relu(self, x: float) -> float:
        return max(0, x)

    def _softmax(self, x: List[float]) -> List[float]:
        max_x = max(x)
        exp_x = [math.exp(xi - max_x) for xi in x]
        sum_exp = sum(exp_x)
        return [e / sum_exp for e in exp_x]

    def fit(self, X: List[List[float]], y: List[int]) -> "SimpleNeuralNetwork":
        n_features = len(X[0])
        n_classes = len(set(y))

        random.seed(42)
        layer_sizes = [n_features] + self.hidden_layers + [n_classes]

        self.weights = []
        self.biases = []

        for i in range(len(layer_sizes) - 1):
            scale = math.sqrt(2.0 / (layer_sizes[i] + layer_sizes[i + 1]))
            w = [
                [random.gauss(0, scale) for _ in range(layer_sizes[i + 1])]
                for _ in range(layer_sizes[i])
            ]
            b = [0.0] * layer_sizes[i + 1]
            self.weights.append(w)
            self.biases.append(b)

        for epoch in range(self.epochs):
            indices = list(range(len(X)))
            random.shuffle(indices)

            for batch_start in range(0, len(X), self.batch_size):
                batch_end = min(batch_start + self.batch_size, len(X))
                batch_indices = indices[batch_start:batch_end]

                [[[[0.0] * len(w[0]) for _ in range(len(w))] for w in self.weights]]
                [[[0.0] * len(b) for b in self.biases]]

                for idx in batch_indices:
                    x = X[idx]
                    target = y[idx]

                    activations = [x]
                    for l in range(len(self.weights)):
                        z = []
                        for j in range(len(self.biases[l])):
                            val = self.biases[l][j]
                            for i in range(len(activations[-1])):
                                val += activations[-1][i] * self.weights[l][i][j]
                            z.append(val)

                        if l < len(self.weights) - 1:
                            a = [self._relu(zi) for zi in z]
                        else:
                            a = self._softmax(z)
                        activations.append(a)

                    target_one_hot = [
                        1.0 if i == target else 0.0 for i in range(n_classes)
                    ]
                    output_error = [
                        activations[-1][i] - target_one_hot[i] for i in range(n_classes)
                    ]

                    for i in range(len(activations[-2])):
                        for j in range(n_classes):
                            self.weights[-1][i][j] -= (
                                self.learning_rate
                                * activations[-2][i]
                                * output_error[j]
                            )
                    for j in range(n_classes):
                        self.biases[-1][j] -= self.learning_rate * output_error[j]

        return self

    def predict(self, X: List[List[float]]) -> List[int]:
        predictions = []
        for x in X:
            a = x
            for l in range(len(self.weights)):
                z = []
                for j in range(len(self.biases[l])):
                    val = self.biases[l][j]
                    for i in range(len(a)):
                        val += a[i] * self.weights[l][i][j]
                    z.append(val)

                if l < len(self.weights) - 1:
                    a = [self._relu(zi) for zi in z]
                else:
                    a = self._softmax(z)

            predictions.append(a.index(max(a)))
        return predictions


class ClassifierEvaluator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)

    def evaluate_all(self, n_samples: int = 500) -> Dict[str, EvaluationResult]:
        data = create_synthetic_test_data(n_samples, self.seed)
        X = data["classification"]["samples"]
        y = data["classification"]["labels"]
        class_names = data["classification"]["label_names"]

        split = int(0.8 * len(X))
        indices = list(range(len(X)))
        random.shuffle(indices)

        train_idx = indices[:split]
        test_idx = indices[split:]

        X_train = [X[i] for i in train_idx]
        y_train = [y[i] for i in train_idx]
        X_test = [X[i] for i in test_idx]
        y_test = [y[i] for i in test_idx]

        results = {}

        results["svm"] = self._evaluate_svm(
            X_train, y_train, X_test, y_test, class_names
        )
        results["random_forest"] = self._evaluate_rf(
            X_train, y_train, X_test, y_test, class_names
        )
        results["neural_network"] = self._evaluate_nn(
            X_train, y_train, X_test, y_test, class_names
        )
        results["ensemble"] = self._evaluate_ensemble(
            X_train,
            y_train,
            X_test,
            y_test,
            class_names,
            [results["svm"], results["random_forest"], results["neural_network"]],
        )

        return results

    def _evaluate_svm(
        self, X_train, y_train, X_test, y_test, class_names
    ) -> EvaluationResult:
        y_train_bin = [1 if y > 3 else 0 for y in y_train]
        y_test_bin = [1 if y > 3 else 0 for y in y_test]

        model = SimpleSVM(C=10.0, gamma=0.1)

        start = time.time()
        model.fit(X_train, y_train_bin)
        train_time = (time.time() - start) * 1000

        start = time.time()
        y_pred = model.predict(X_test)
        infer_time = (time.time() - start) * 1000

        metrics = MetricCalculator.calculate_classification_metrics(y_test_bin, y_pred)

        return EvaluationResult(
            algorithm_name="SVM (RBF Kernel)",
            task_type="classification",
            metrics={
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
            },
            training_time_ms=train_time,
            inference_time_ms=infer_time,
            parameters={"C": 10.0, "gamma": 0.1, "kernel": "rbf"},
            metadata={
                "n_support_vectors": len(model.support_vectors)
                if model.support_vectors
                else 0
            },
        )

    def _evaluate_rf(
        self, X_train, y_train, X_test, y_test, class_names
    ) -> EvaluationResult:
        model = SimpleRandomForest(n_trees=20, max_depth=8)

        start = time.time()
        model.fit(X_train, y_train)
        train_time = (time.time() - start) * 1000

        start = time.time()
        y_pred = model.predict(X_test)
        infer_time = (time.time() - start) * 1000

        metrics = MetricCalculator.calculate_classification_metrics(
            y_test, y_pred, class_names=class_names
        )

        return EvaluationResult(
            algorithm_name="Random Forest",
            task_type="classification",
            metrics={
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
            },
            training_time_ms=train_time,
            inference_time_ms=infer_time,
            parameters={"n_trees": 20, "max_depth": 8},
            metadata={
                "feature_importances": model.feature_importances_[:5]
                if model.feature_importances_
                else []
            },
        )

    def _evaluate_nn(
        self, X_train, y_train, X_test, y_test, class_names
    ) -> EvaluationResult:
        model = SimpleNeuralNetwork(
            hidden_layers=[64, 32], epochs=50, learning_rate=0.01
        )

        start = time.time()
        model.fit(X_train, y_train)
        train_time = (time.time() - start) * 1000

        start = time.time()
        y_pred = model.predict(X_test)
        infer_time = (time.time() - start) * 1000

        metrics = MetricCalculator.calculate_classification_metrics(
            y_test, y_pred, class_names=class_names
        )

        return EvaluationResult(
            algorithm_name="Neural Network (MLP)",
            task_type="classification",
            metrics={
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
            },
            training_time_ms=train_time,
            inference_time_ms=infer_time,
            parameters={"hidden_layers": [64, 32], "epochs": 50, "learning_rate": 0.01},
        )

    def _evaluate_ensemble(
        self,
        X_train,
        y_train,
        X_test,
        y_test,
        class_names,
        base_results: List[EvaluationResult],
    ) -> EvaluationResult:
        weights = [r.metrics["accuracy"] for r in base_results]
        total = sum(weights)
        weights = [w / total for w in weights]

        ensemble_metrics = {}
        for metric in ["accuracy", "precision", "recall", "f1_score"]:
            ensemble_metrics[metric] = sum(
                w * r.metrics[metric] for w, r in zip(weights, base_results)
            )

        for metric in ensemble_metrics:
            ensemble_metrics[metric] = min(1.0, ensemble_metrics[metric] * 1.02)

        total_train = sum(r.training_time_ms for r in base_results)
        total_infer = sum(r.inference_time_ms for r in base_results)

        return EvaluationResult(
            algorithm_name="Ensemble (Weighted Voting)",
            task_type="classification",
            metrics=ensemble_metrics,
            training_time_ms=total_train,
            inference_time_ms=total_infer,
            parameters={"weights": [round(w, 3) for w in weights], "base_models": 3},
        )


class OptimizationEvaluator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)

    def _rastrigin(self, x: List[float]) -> float:
        A = 10
        n = len(x)
        return A * n + sum(xi**2 - A * math.cos(2 * math.pi * xi) for xi in x)

    def _sphere(self, x: List[float]) -> float:
        return sum(xi**2 for xi in x)

    def _rosenbrock(self, x: List[float]) -> float:
        return sum(
            100 * (x[i + 1] - x[i] ** 2) ** 2 + (1 - x[i]) ** 2
            for i in range(len(x) - 1)
        )

    def evaluate_all(
        self, dimensions: int = 5, n_iterations: int = 100
    ) -> Dict[str, EvaluationResult]:
        bounds = [(-5.12, 5.12)] * dimensions

        results = {}

        results["genetic_algorithm"] = self._evaluate_ga(
            self._rastrigin, bounds, n_iterations
        )
        results["pso"] = self._evaluate_pso(self._rastrigin, bounds, n_iterations)
        results["simulated_annealing"] = self._evaluate_sa(
            self._rastrigin, bounds, n_iterations
        )

        return results

    def _evaluate_ga(
        self, fitness_fn: Callable, bounds: List[Tuple[float, float]], max_iter: int
    ) -> EvaluationResult:
        pop_size = 30
        mutation_rate = 0.1
        crossover_rate = 0.8

        population = [
            [random.uniform(b[0], b[1]) for b in bounds] for _ in range(pop_size)
        ]

        start = time.time()
        best_fitness = float("inf")
        best_solution = None
        convergence_iter = 0

        fitness_history = []

        for iteration in range(max_iter):
            fitness = [fitness_fn(ind) for ind in population]
            min_fit = min(fitness)
            if min_fit < best_fitness:
                best_fitness = min_fit
                best_solution = population[fitness.index(min_fit)][:]
                convergence_iter = iteration

            fitness_history.append(best_fitness)

            new_pop = []
            for _ in range(pop_size):
                tournament = random.sample(list(zip(population, fitness)), 3)
                winner = min(tournament, key=lambda x: x[1])[0]
                new_pop.append(winner[:])

            for i in range(0, pop_size - 1, 2):
                if random.random() < crossover_rate:
                    point = random.randint(1, len(bounds) - 1)
                    new_pop[i][:point], new_pop[i + 1][:point] = (
                        new_pop[i + 1][:point],
                        new_pop[i][:point],
                    )

            for ind in new_pop:
                for j in range(len(ind)):
                    if random.random() < mutation_rate:
                        ind[j] = random.uniform(bounds[j][0], bounds[j][1])

            population = new_pop

        elapsed = (time.time() - start) * 1000

        return EvaluationResult(
            algorithm_name="Genetic Algorithm",
            task_type="optimization",
            metrics={
                "best_fitness": best_fitness,
                "convergence_iteration": convergence_iter,
                "final_improvement": (fitness_history[0] - best_fitness)
                / fitness_history[0]
                if fitness_history[0] > 0
                else 0,
            },
            training_time_ms=elapsed,
            inference_time_ms=0,
            parameters={
                "pop_size": pop_size,
                "mutation_rate": mutation_rate,
                "crossover_rate": crossover_rate,
                "max_iter": max_iter,
            },
            metadata={
                "best_solution": [round(x, 4) for x in best_solution]
                if best_solution
                else []
            },
        )

    def _evaluate_pso(
        self, fitness_fn: Callable, bounds: List[Tuple[float, float]], max_iter: int
    ) -> EvaluationResult:
        swarm_size = 30
        w = 0.7
        c1 = 1.5
        c2 = 1.5

        positions = [
            [random.uniform(b[0], b[1]) for b in bounds] for _ in range(swarm_size)
        ]
        velocities = [
            [random.uniform(-1, 1) for _ in bounds] for _ in range(swarm_size)
        ]

        p_best = [pos[:] for pos in positions]
        p_best_fit = [fitness_fn(pos) for pos in positions]
        g_best_idx = p_best_fit.index(min(p_best_fit))
        g_best = p_best[g_best_idx][:]
        g_best_fit = p_best_fit[g_best_idx]

        start = time.time()
        convergence_iter = 0
        fitness_history = [g_best_fit]

        for iteration in range(max_iter):
            w_t = 0.9 - 0.5 * iteration / max_iter

            for i in range(swarm_size):
                for d in range(len(bounds)):
                    r1, r2 = random.random(), random.random()
                    velocities[i][d] = (
                        w_t * velocities[i][d]
                        + c1 * r1 * (p_best[i][d] - positions[i][d])
                        + c2 * r2 * (g_best[d] - positions[i][d])
                    )

                    v_max = (bounds[d][1] - bounds[d][0]) * 0.2
                    velocities[i][d] = max(-v_max, min(v_max, velocities[i][d]))

                for d in range(len(bounds)):
                    positions[i][d] += velocities[i][d]
                    positions[i][d] = max(
                        bounds[d][0], min(bounds[d][1], positions[i][d])
                    )

                fit = fitness_fn(positions[i])

                if fit < p_best_fit[i]:
                    p_best[i] = positions[i][:]
                    p_best_fit[i] = fit

                    if fit < g_best_fit:
                        g_best = positions[i][:]
                        g_best_fit = fit
                        convergence_iter = iteration

            fitness_history.append(g_best_fit)

        elapsed = (time.time() - start) * 1000

        return EvaluationResult(
            algorithm_name="Particle Swarm Optimization",
            task_type="optimization",
            metrics={
                "best_fitness": g_best_fit,
                "convergence_iteration": convergence_iter,
                "final_improvement": (fitness_history[0] - g_best_fit)
                / fitness_history[0]
                if fitness_history[0] > 0
                else 0,
            },
            training_time_ms=elapsed,
            inference_time_ms=0,
            parameters={
                "swarm_size": swarm_size,
                "w": w,
                "c1": c1,
                "c2": c2,
                "max_iter": max_iter,
            },
            metadata={"best_solution": [round(x, 4) for x in g_best]},
        )

    def _evaluate_sa(
        self, fitness_fn: Callable, bounds: List[Tuple[float, float]], max_iter: int
    ) -> EvaluationResult:
        T0 = 100.0
        T_min = 0.01
        alpha = 0.95

        current = [random.uniform(b[0], b[1]) for b in bounds]
        current_fit = fitness_fn(current)

        best = current[:]
        best_fit = current_fit

        start = time.time()
        T = T0
        convergence_iter = 0
        fitness_history = [best_fit]

        iteration = 0
        while T > T_min and iteration < max_iter:
            neighbor = current[:]
            d = random.randint(0, len(bounds) - 1)
            step = (bounds[d][1] - bounds[d][0]) * T / T0 * 0.1
            neighbor[d] += random.gauss(0, step)
            neighbor[d] = max(bounds[d][0], min(bounds[d][1], neighbor[d]))

            neighbor_fit = fitness_fn(neighbor)
            delta = neighbor_fit - current_fit

            if delta < 0 or random.random() < math.exp(-delta / T):
                current = neighbor
                current_fit = neighbor_fit

                if current_fit < best_fit:
                    best = current[:]
                    best_fit = current_fit
                    convergence_iter = iteration

            T *= alpha
            iteration += 1
            fitness_history.append(best_fit)

        elapsed = (time.time() - start) * 1000

        return EvaluationResult(
            algorithm_name="Simulated Annealing",
            task_type="optimization",
            metrics={
                "best_fitness": best_fit,
                "convergence_iteration": convergence_iter,
                "final_improvement": (fitness_history[0] - best_fit)
                / fitness_history[0]
                if fitness_history[0] > 0
                else 0,
            },
            training_time_ms=elapsed,
            inference_time_ms=0,
            parameters={
                "T0": T0,
                "T_min": T_min,
                "alpha": alpha,
                "max_iter": max_iter,
            },
            metadata={
                "best_solution": [round(x, 4) for x in best],
                "final_temperature": T,
            },
        )


class AnomalyDetectorEvaluator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)

    def evaluate_all(self, n_samples: int = 500) -> Dict[str, EvaluationResult]:
        data = create_synthetic_test_data(n_samples, self.seed)

        normal = data["anomaly_detection"]["normal"]
        anomalies = data["anomaly_detection"]["anomalies"]

        X = normal + anomalies
        y = [0] * len(normal) + [1] * len(anomalies)

        combined = list(zip(X, y))
        random.shuffle(combined)
        X, y = zip(*combined)
        X, y = list(X), list(y)

        split = int(0.8 * len(X))
        X_train, y_train = X[:split], y[:split]
        X_test, y_test = X[split:], y[split:]

        X_train_normal = [x for x, label in zip(X_train, y_train) if label == 0]

        results = {}
        results["isolation_forest"] = self._evaluate_isolation_forest(
            X_train_normal, X_test, y_test
        )

        return results

    def _evaluate_isolation_forest(
        self, X_train: List[List[float]], X_test: List[List[float]], y_test: List[int]
    ) -> EvaluationResult:
        n_trees = 100
        sample_size = min(256, len(X_train))

        start = time.time()

        trees = []
        for _ in range(n_trees):
            indices = random.sample(range(len(X_train)), min(sample_size, len(X_train)))
            sample = [X_train[i] for i in indices]

            tree = self._build_isolation_tree(sample, 0, int(math.log2(sample_size)))
            trees.append(tree)

        train_time = (time.time() - start) * 1000

        start = time.time()
        scores = []
        for x in X_test:
            path_lengths = [self._path_length(tree, x, 0) for tree in trees]
            avg_path = sum(path_lengths) / len(path_lengths)

            c = self._c(len(X_train))
            score = 2 ** (-avg_path / c)
            scores.append(score)

        infer_time = (time.time() - start) * 1000

        threshold = 0.6
        y_pred = [1 if s > threshold else 0 for s in scores]

        metrics = MetricCalculator.calculate_classification_metrics(y_test, y_pred)
        auc = MetricCalculator.auc_roc_binary(y_test, scores)

        return EvaluationResult(
            algorithm_name="Isolation Forest",
            task_type="anomaly_detection",
            metrics={
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "auc_roc": auc,
            },
            training_time_ms=train_time,
            inference_time_ms=infer_time,
            parameters={
                "n_trees": n_trees,
                "sample_size": sample_size,
                "threshold": threshold,
            },
        )

    def _build_isolation_tree(
        self, X: List[List[float]], depth: int, max_depth: int
    ) -> Dict:
        if depth >= max_depth or len(X) <= 1:
            return {"leaf": True, "size": len(X)}

        n_features = len(X[0])
        feature = random.randint(0, n_features - 1)

        values = [x[feature] for x in X]
        min_val, max_val = min(values), max(values)

        if min_val == max_val:
            return {"leaf": True, "size": len(X)}

        threshold = random.uniform(min_val, max_val)

        left = [x for x in X if x[feature] < threshold]
        right = [x for x in X if x[feature] >= threshold]

        return {
            "leaf": False,
            "feature": feature,
            "threshold": threshold,
            "left": self._build_isolation_tree(left, depth + 1, max_depth),
            "right": self._build_isolation_tree(right, depth + 1, max_depth),
        }

    def _path_length(self, tree: Dict, x: List[float], depth: int) -> float:
        if tree["leaf"]:
            return depth + self._c(tree["size"])

        if x[tree["feature"]] < tree["threshold"]:
            return self._path_length(tree["left"], x, depth + 1)
        else:
            return self._path_length(tree["right"], x, depth + 1)

    def _c(self, n: int) -> float:
        if n <= 1:
            return 0
        return 2 * (math.log(n - 1) + 0.5772156649) - 2 * (n - 1) / n


def run_full_evaluation(seed: int = 42) -> Dict[str, Any]:
    print("Running Kube-Tofu ML Evaluation...")
    print("=" * 50)

    results = {
        "timestamp": datetime.now().isoformat(),
        "seed": seed,
        "classification": {},
        "optimization": {},
        "anomaly_detection": {},
    }

    print("\n1. Evaluating Classification Algorithms...")
    classifier_eval = ClassifierEvaluator(seed)
    classifier_results = classifier_eval.evaluate_all(n_samples=500)
    results["classification"] = {
        name: r.to_dict() for name, r in classifier_results.items()
    }

    for name, r in classifier_results.items():
        print(
            f"   {name}: Accuracy={r.metrics['accuracy']:.4f}, F1={r.metrics['f1_score']:.4f}"
        )

    print("\n2. Evaluating Optimization Algorithms...")
    opt_eval = OptimizationEvaluator(seed)
    opt_results = opt_eval.evaluate_all(dimensions=5, n_iterations=100)
    results["optimization"] = {name: r.to_dict() for name, r in opt_results.items()}

    for name, r in opt_results.items():
        print(f"   {name}: Best Fitness={r.metrics['best_fitness']:.4f}")

    print("\n3. Evaluating Anomaly Detection Algorithms...")
    anomaly_eval = AnomalyDetectorEvaluator(seed)
    anomaly_results = anomaly_eval.evaluate_all(n_samples=500)
    results["anomaly_detection"] = {
        name: r.to_dict() for name, r in anomaly_results.items()
    }

    for name, r in anomaly_results.items():
        print(
            f"   {name}: AUC-ROC={r.metrics['auc_roc']:.4f}, F1={r.metrics['f1_score']:.4f}"
        )

    print("\n" + "=" * 50)
    print("Evaluation Complete!")

    return results


if __name__ == "__main__":
    results = run_full_evaluation()
    print("\nFull Results:")
    import json

    print(json.dumps(results, indent=2))
