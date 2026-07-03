import math
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter


@dataclass
class ClassificationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    specificity: float
    auc_roc: Optional[float] = None
    confusion_matrix: Optional[List[List[int]]] = None
    per_class_metrics: Optional[Dict[str, Dict[str, float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "specificity": round(self.specificity, 4),
            "auc_roc": round(self.auc_roc, 4) if self.auc_roc else None,
        }


@dataclass
class GenerationMetrics:
    syntax_correctness: float
    semantic_validity: float
    completeness: float
    readability: float
    parameterization: float
    bleu_score: Optional[float] = None
    code_similarity: Optional[float] = None

    @property
    def overall_quality(self) -> float:
        weights = {
            "syntax_correctness": 0.2,
            "semantic_validity": 0.2,
            "completeness": 0.25,
            "readability": 0.15,
            "parameterization": 0.2,
        }
        return sum(getattr(self, k) * v for k, v in weights.items())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "syntax_correctness": round(self.syntax_correctness, 4),
            "semantic_validity": round(self.semantic_validity, 4),
            "completeness": round(self.completeness, 4),
            "readability": round(self.readability, 4),
            "parameterization": round(self.parameterization, 4),
            "overall_quality": round(self.overall_quality, 4),
            "bleu_score": round(self.bleu_score, 4) if self.bleu_score else None,
            "code_similarity": round(self.code_similarity, 4)
            if self.code_similarity
            else None,
        }


@dataclass
class DeployabilityMetrics:
    first_attempt_success: float
    pass_at_1: float
    pass_at_5: float
    pass_at_10: float
    pass_at_25: float
    average_iterations: float
    average_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "first_attempt_success": round(self.first_attempt_success, 4),
            "pass@1": round(self.pass_at_1, 4),
            "pass@5": round(self.pass_at_5, 4),
            "pass@10": round(self.pass_at_10, 4),
            "pass@25": round(self.pass_at_25, 4),
            "average_iterations": round(self.average_iterations, 2),
            "average_time_ms": round(self.average_time_ms, 2),
        }


class MetricCalculator:
    @staticmethod
    def accuracy(y_true: List[int], y_pred: List[int]) -> float:
        if len(y_true) != len(y_pred) or len(y_true) == 0:
            return 0.0
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        return correct / len(y_true)

    @staticmethod
    def confusion_matrix(
        y_true: List[int], y_pred: List[int], n_classes: int
    ) -> List[List[int]]:
        matrix = [[0] * n_classes for _ in range(n_classes)]
        for t, p in zip(y_true, y_pred):
            if 0 <= t < n_classes and 0 <= p < n_classes:
                matrix[t][p] += 1
        return matrix

    @staticmethod
    def precision_recall_f1(
        y_true: List[int], y_pred: List[int], average: str = "macro"
    ) -> Tuple[float, float, float]:
        classes = sorted(set(y_true) | set(y_pred))

        precisions = []
        recalls = []
        f1s = []
        supports = []

        for c in classes:
            tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
            fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
            fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

            precisions.append(precision)
            recalls.append(recall)
            f1s.append(f1)
            supports.append(sum(1 for t in y_true if t == c))

        if average == "macro":
            return (
                sum(precisions) / len(precisions),
                sum(recalls) / len(recalls),
                sum(f1s) / len(f1s),
            )
        elif average == "weighted":
            total_support = sum(supports)
            if total_support == 0:
                return 0.0, 0.0, 0.0
            return (
                sum(p * s for p, s in zip(precisions, supports)) / total_support,
                sum(r * s for r, s in zip(recalls, supports)) / total_support,
                sum(f * s for f, s in zip(f1s, supports)) / total_support,
            )
        elif average == "micro":
            total_tp = sum(1 for t, p in zip(y_true, y_pred) if t == p)
            total_fp = len(y_pred) - total_tp
            total_fn = len(y_true) - total_tp

            precision = (
                total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
            )
            recall = (
                total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
            )
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

            return precision, recall, f1

        return 0.0, 0.0, 0.0

    @staticmethod
    def specificity(y_true: List[int], y_pred: List[int]) -> float:
        classes = sorted(set(y_true) | set(y_pred))
        specificities = []

        for c in classes:
            tn = sum(1 for t, p in zip(y_true, y_pred) if t != c and p != c)
            fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)

            spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            specificities.append(spec)

        return sum(specificities) / len(specificities) if specificities else 0.0

    @staticmethod
    def auc_roc_binary(y_true: List[int], y_scores: List[float]) -> float:
        if len(y_true) != len(y_scores) or len(y_true) == 0:
            return 0.5

        pairs = sorted(zip(y_scores, y_true), reverse=True)

        n_pos = sum(y_true)
        n_neg = len(y_true) - n_pos

        if n_pos == 0 or n_neg == 0:
            return 0.5

        tprs = [0.0]
        fprs = [0.0]

        tp = 0
        fp = 0

        for score, label in pairs:
            if label == 1:
                tp += 1
            else:
                fp += 1

            tprs.append(tp / n_pos)
            fprs.append(fp / n_neg)

        auc = 0.0
        for i in range(1, len(fprs)):
            auc += (fprs[i] - fprs[i - 1]) * (tprs[i] + tprs[i - 1]) / 2

        return auc

    @staticmethod
    def auc_roc_multiclass(
        y_true: List[int], y_scores: List[List[float]], average: str = "macro"
    ) -> float:
        classes = sorted(set(y_true))
        aucs = []

        for c in classes:
            y_binary = [1 if y == c else 0 for y in y_true]
            scores = [s[c] if c < len(s) else 0.0 for s in y_scores]

            auc = MetricCalculator.auc_roc_binary(y_binary, scores)
            aucs.append(auc)

        if average == "macro":
            return sum(aucs) / len(aucs) if aucs else 0.5

        return sum(aucs) / len(aucs) if aucs else 0.5

    @staticmethod
    def bleu_score(reference: str, hypothesis: str, max_n: int = 4) -> float:
        ref_tokens = reference.split()
        hyp_tokens = hypothesis.split()

        if len(hyp_tokens) == 0:
            return 0.0

        precisions = []

        for n in range(1, min(max_n + 1, len(hyp_tokens) + 1)):
            ref_ngrams = Counter(
                tuple(ref_tokens[i : i + n]) for i in range(len(ref_tokens) - n + 1)
            )
            hyp_ngrams = Counter(
                tuple(hyp_tokens[i : i + n]) for i in range(len(hyp_tokens) - n + 1)
            )

            matches = sum(min(hyp_ngrams[ng], ref_ngrams[ng]) for ng in hyp_ngrams)
            total = sum(hyp_ngrams.values())

            if total > 0:
                precisions.append(matches / total)
            else:
                precisions.append(0.0)

        if not precisions or all(p == 0 for p in precisions):
            return 0.0

        log_precision = sum(
            math.log(p) if p > 0 else -float("inf") for p in precisions
        ) / len(precisions)

        if log_precision == -float("inf"):
            return 0.0

        if len(hyp_tokens) >= len(ref_tokens):
            bp = 1.0
        else:
            bp = math.exp(1 - len(ref_tokens) / len(hyp_tokens))

        return bp * math.exp(log_precision)

    @staticmethod
    def code_similarity(code1: str, code2: str) -> float:
        tokens1 = set(code1.split())
        tokens2 = set(code2.split())

        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        return len(intersection) / len(union)

    @staticmethod
    def pass_at_k(n: int, c: int, k: int) -> float:
        if n - c < k:
            return 1.0

        log_prob = 0.0
        for i in range(k):
            log_prob += math.log(n - c - i) - math.log(n - i)

        return 1.0 - math.exp(log_prob)

    @classmethod
    def calculate_classification_metrics(
        cls,
        y_true: List[int],
        y_pred: List[int],
        y_scores: Optional[List[List[float]]] = None,
        class_names: Optional[List[str]] = None,
    ) -> ClassificationMetrics:
        n_classes = len(set(y_true) | set(y_pred))

        accuracy = cls.accuracy(y_true, y_pred)
        precision, recall, f1 = cls.precision_recall_f1(y_true, y_pred)
        specificity = cls.specificity(y_true, y_pred)

        auc = None
        if y_scores is not None:
            auc = cls.auc_roc_multiclass(y_true, y_scores)

        cm = cls.confusion_matrix(y_true, y_pred, n_classes)

        per_class = {}
        classes = sorted(set(y_true) | set(y_pred))
        for i, c in enumerate(classes):
            y_binary_true = [1 if y == c else 0 for y in y_true]
            y_binary_pred = [1 if y == c else 0 for y in y_pred]

            p, r, f = cls.precision_recall_f1(y_binary_true, y_binary_pred)

            name = class_names[i] if class_names and i < len(class_names) else str(c)
            per_class[name] = {
                "precision": p,
                "recall": r,
                "f1": f,
                "support": sum(y_binary_true),
            }

        return ClassificationMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            specificity=specificity,
            auc_roc=auc,
            confusion_matrix=cm,
            per_class_metrics=per_class,
        )

    @staticmethod
    def mean_squared_error(y_true: List[float], y_pred: List[float]) -> float:
        if len(y_true) != len(y_pred) or len(y_true) == 0:
            return float("inf")
        return sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true)

    @staticmethod
    def mean_absolute_error(y_true: List[float], y_pred: List[float]) -> float:
        if len(y_true) != len(y_pred) or len(y_true) == 0:
            return float("inf")
        return sum(abs(t - p) for t, p in zip(y_true, y_pred)) / len(y_true)

    @staticmethod
    def r_squared(y_true: List[float], y_pred: List[float]) -> float:
        if len(y_true) != len(y_pred) or len(y_true) == 0:
            return 0.0

        mean_true = sum(y_true) / len(y_true)
        ss_tot = sum((t - mean_true) ** 2 for t in y_true)
        ss_res = sum((t - p) ** 2 for t, p in zip(y_true, y_pred))

        if ss_tot == 0:
            return 1.0 if ss_res == 0 else 0.0

        return 1 - (ss_res / ss_tot)

    @staticmethod
    def silhouette_score(X: List[List[float]], labels: List[int]) -> float:
        def euclidean(a: List[float], b: List[float]) -> float:
            return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

        n = len(X)
        if n < 2:
            return 0.0

        clusters = sorted(set(labels))
        if len(clusters) < 2:
            return 0.0

        silhouettes = []

        for i in range(n):
            same_cluster = [j for j in range(n) if labels[j] == labels[i] and j != i]
            if same_cluster:
                a_i = sum(euclidean(X[i], X[j]) for j in same_cluster) / len(
                    same_cluster
                )
            else:
                a_i = 0.0

            b_i = float("inf")
            for c in clusters:
                if c == labels[i]:
                    continue
                other_cluster = [j for j in range(n) if labels[j] == c]
                if other_cluster:
                    avg_dist = sum(euclidean(X[i], X[j]) for j in other_cluster) / len(
                        other_cluster
                    )
                    b_i = min(b_i, avg_dist)

            if b_i == float("inf"):
                b_i = a_i

            if max(a_i, b_i) > 0:
                s_i = (b_i - a_i) / max(a_i, b_i)
            else:
                s_i = 0.0

            silhouettes.append(s_i)

        return sum(silhouettes) / len(silhouettes)


class CrossValidator:
    def __init__(self, n_folds: int = 5, shuffle: bool = True, seed: int = 42):
        self.n_folds = n_folds
        self.shuffle = shuffle
        self.seed = seed

    def split(
        self, X: List[Any], y: Optional[List[Any]] = None
    ) -> List[Tuple[List[int], List[int]]]:
        import random

        n = len(X)
        indices = list(range(n))

        if self.shuffle:
            random.seed(self.seed)
            random.shuffle(indices)

        fold_size = n // self.n_folds
        folds = []

        for i in range(self.n_folds):
            start = i * fold_size
            end = start + fold_size if i < self.n_folds - 1 else n

            test_indices = indices[start:end]
            train_indices = indices[:start] + indices[end:]

            folds.append((train_indices, test_indices))

        return folds

    def cross_validate(
        self,
        X: List[List[float]],
        y: List[int],
        train_fn,
        predict_fn,
    ) -> Dict[str, Any]:
        folds = self.split(X, y)

        fold_metrics = []

        for fold_idx, (train_idx, test_idx) in enumerate(folds):
            X_train = [X[i] for i in train_idx]
            y_train = [y[i] for i in train_idx]
            X_test = [X[i] for i in test_idx]
            y_test = [y[i] for i in test_idx]

            model = train_fn(X_train, y_train)

            y_pred = predict_fn(model, X_test)

            metrics = MetricCalculator.calculate_classification_metrics(y_test, y_pred)
            fold_metrics.append(metrics)

        def mean_std(values):
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / len(values)
            return mean, math.sqrt(var)

        return {
            "accuracy": mean_std([m.accuracy for m in fold_metrics]),
            "precision": mean_std([m.precision for m in fold_metrics]),
            "recall": mean_std([m.recall for m in fold_metrics]),
            "f1_score": mean_std([m.f1_score for m in fold_metrics]),
            "fold_results": [m.to_dict() for m in fold_metrics],
        }
