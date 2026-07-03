import logging
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple
from enum import Enum
import random

logger = logging.getLogger(__name__)


class OptimizationObjective(str, Enum):
    MINIMIZE_COST = "minimize_cost"
    MAXIMIZE_PERFORMANCE = "maximize_performance"
    MINIMIZE_RESOURCES = "minimize_resources"
    MAXIMIZE_AVAILABILITY = "maximize_availability"
    MULTI_OBJECTIVE = "multi_objective"


@dataclass
class OptimizationResult:
    best_solution: np.ndarray
    best_fitness: float
    convergence_history: List[float] = field(default_factory=list)
    iterations: int = 0
    execution_time: float = 0.0
    pareto_front: Optional[List[Tuple[np.ndarray, float]]] = None


@dataclass
class ResourceConstraints:
    min_cpu: float = 0.1
    max_cpu: float = 32.0
    min_memory: float = 128
    max_memory: float = 131072
    min_replicas: int = 1
    max_replicas: int = 100
    max_cost: Optional[float] = None
    min_availability: float = 0.99


class IaCOptimizer(ABC):
    def __init__(
        self,
        objective: OptimizationObjective,
        constraints: Optional[ResourceConstraints] = None,
    ):
        self.objective = objective
        self.constraints = constraints or ResourceConstraints()
        self.fitness_function: Optional[Callable] = None

    @abstractmethod
    def optimize(
        self,
        fitness_fn: Callable[[np.ndarray], float],
        dimensions: int,
        bounds: List[Tuple[float, float]],
        max_iterations: int = 100,
    ) -> OptimizationResult:
        pass

    def _check_constraints(self, solution: np.ndarray) -> bool:
        return np.all(solution >= 0)


class GeneticAlgorithm(IaCOptimizer):
    def __init__(
        self,
        objective: OptimizationObjective,
        population_size: int = 50,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.1,
        elitism_rate: float = 0.1,
        tournament_size: int = 3,
    ):
        super().__init__(objective)
        self.population_size = population_size
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elitism_rate = elitism_rate
        self.tournament_size = tournament_size

    def optimize(
        self,
        fitness_fn: Callable[[np.ndarray], float],
        dimensions: int,
        bounds: List[Tuple[float, float]],
        max_iterations: int = 100,
    ) -> OptimizationResult:
        import time

        start_time = time.time()

        bounds_arr = np.array(bounds)

        population = self._initialize_population(dimensions, bounds_arr)
        fitness = np.array([fitness_fn(ind) for ind in population])

        convergence_history = []
        best_idx = (
            np.argmin(fitness)
            if self.objective == OptimizationObjective.MINIMIZE_COST
            else np.argmax(fitness)
        )
        best_solution = population[best_idx].copy()
        best_fitness = fitness[best_idx]
        convergence_history.append(best_fitness)

        for iteration in range(max_iterations):
            parents = self._tournament_selection(population, fitness)
            offspring = self._crossover(parents, bounds_arr)
            offspring = self._mutate(offspring, bounds_arr)
            offspring_fitness = np.array([fitness_fn(ind) for ind in offspring])

            elite_count = int(self.population_size * self.elitism_rate)
            if self.objective == OptimizationObjective.MINIMIZE_COST:
                elite_indices = np.argsort(fitness)[:elite_count]
            else:
                elite_indices = np.argsort(fitness)[-elite_count:]

            population = np.vstack(
                [
                    population[elite_indices],
                    offspring[: self.population_size - elite_count],
                ]
            )
            fitness = np.concatenate(
                [
                    fitness[elite_indices],
                    offspring_fitness[: self.population_size - elite_count],
                ]
            )

            if self.objective == OptimizationObjective.MINIMIZE_COST:
                current_best_idx = np.argmin(fitness)
                if fitness[current_best_idx] < best_fitness:
                    best_solution = population[current_best_idx].copy()
                    best_fitness = fitness[current_best_idx]
            else:
                current_best_idx = np.argmax(fitness)
                if fitness[current_best_idx] > best_fitness:
                    best_solution = population[current_best_idx].copy()
                    best_fitness = fitness[current_best_idx]

            convergence_history.append(best_fitness)

            if len(convergence_history) > 10:
                recent = convergence_history[-10:]
                if max(recent) - min(recent) < 1e-6:
                    logger.info(f"GA converged at iteration {iteration}")
                    break

        return OptimizationResult(
            best_solution=best_solution,
            best_fitness=best_fitness,
            convergence_history=convergence_history,
            iterations=iteration + 1,
            execution_time=time.time() - start_time,
        )

    def _initialize_population(self, dimensions: int, bounds: np.ndarray) -> np.ndarray:
        population = np.random.uniform(
            bounds[:, 0], bounds[:, 1], size=(self.population_size, dimensions)
        )
        return population

    def _tournament_selection(
        self, population: np.ndarray, fitness: np.ndarray
    ) -> np.ndarray:
        selected = []
        for _ in range(self.population_size):
            tournament_idx = np.random.choice(
                len(population), self.tournament_size, replace=False
            )
            tournament_fitness = fitness[tournament_idx]

            if self.objective == OptimizationObjective.MINIMIZE_COST:
                winner_idx = tournament_idx[np.argmin(tournament_fitness)]
            else:
                winner_idx = tournament_idx[np.argmax(tournament_fitness)]

            selected.append(population[winner_idx])

        return np.array(selected)

    def _crossover(self, parents: np.ndarray, bounds: np.ndarray) -> np.ndarray:
        offspring = []
        for i in range(0, len(parents) - 1, 2):
            p1, p2 = parents[i], parents[i + 1]

            if random.random() < self.crossover_rate:
                mask = np.random.random(len(p1)) < 0.5
                c1 = np.where(mask, p1, p2)
                c2 = np.where(mask, p2, p1)
            else:
                c1, c2 = p1.copy(), p2.copy()

            offspring.extend([c1, c2])

        return np.array(offspring)

    def _mutate(self, offspring: np.ndarray, bounds: np.ndarray) -> np.ndarray:
        for i in range(len(offspring)):
            if random.random() < self.mutation_rate:
                mutation = np.random.normal(0, 0.1, len(offspring[i]))
                offspring[i] += mutation * (bounds[:, 1] - bounds[:, 0])
                offspring[i] = np.clip(offspring[i], bounds[:, 0], bounds[:, 1])

        return offspring


class ParticleSwarmOptimization(IaCOptimizer):
    def __init__(
        self,
        objective: OptimizationObjective,
        swarm_size: int = 30,
        w: float = 0.7,
        c1: float = 1.5,
        c2: float = 1.5,
    ):
        super().__init__(objective)
        self.swarm_size = swarm_size
        self.w = w
        self.c1 = c1
        self.c2 = c2

    def optimize(
        self,
        fitness_fn: Callable[[np.ndarray], float],
        dimensions: int,
        bounds: List[Tuple[float, float]],
        max_iterations: int = 100,
    ) -> OptimizationResult:
        import time

        start_time = time.time()

        bounds_arr = np.array(bounds)

        positions = np.random.uniform(
            bounds_arr[:, 0], bounds_arr[:, 1], size=(self.swarm_size, dimensions)
        )

        velocities = np.random.uniform(
            -np.abs(bounds_arr[:, 1] - bounds_arr[:, 0]) * 0.1,
            np.abs(bounds_arr[:, 1] - bounds_arr[:, 0]) * 0.1,
            size=(self.swarm_size, dimensions),
        )

        fitness = np.array([fitness_fn(p) for p in positions])

        pbest_positions = positions.copy()
        pbest_fitness = fitness.copy()

        if self.objective == OptimizationObjective.MINIMIZE_COST:
            gbest_idx = np.argmin(fitness)
        else:
            gbest_idx = np.argmax(fitness)

        gbest_position = positions[gbest_idx].copy()
        gbest_fitness = fitness[gbest_idx]

        convergence_history = [gbest_fitness]

        for iteration in range(max_iterations):
            w = self.w - (self.w - 0.4) * (iteration / max_iterations)

            for i in range(self.swarm_size):
                r1 = np.random.random(dimensions)
                cognitive = self.c1 * r1 * (pbest_positions[i] - positions[i])

                r2 = np.random.random(dimensions)
                social = self.c2 * r2 * (gbest_position - positions[i])

                velocities[i] = w * velocities[i] + cognitive + social
                v_max = (bounds_arr[:, 1] - bounds_arr[:, 0]) * 0.2
                velocities[i] = np.clip(velocities[i], -v_max, v_max)
                positions[i] += velocities[i]
                positions[i] = np.clip(positions[i], bounds_arr[:, 0], bounds_arr[:, 1])
                current_fitness = fitness_fn(positions[i])

                if self.objective == OptimizationObjective.MINIMIZE_COST:
                    if current_fitness < pbest_fitness[i]:
                        pbest_positions[i] = positions[i].copy()
                        pbest_fitness[i] = current_fitness
                else:
                    if current_fitness > pbest_fitness[i]:
                        pbest_positions[i] = positions[i].copy()
                        pbest_fitness[i] = current_fitness

            if self.objective == OptimizationObjective.MINIMIZE_COST:
                best_idx = np.argmin(pbest_fitness)
                if pbest_fitness[best_idx] < gbest_fitness:
                    gbest_position = pbest_positions[best_idx].copy()
                    gbest_fitness = pbest_fitness[best_idx]
            else:
                best_idx = np.argmax(pbest_fitness)
                if pbest_fitness[best_idx] > gbest_fitness:
                    gbest_position = pbest_positions[best_idx].copy()
                    gbest_fitness = pbest_fitness[best_idx]

            convergence_history.append(gbest_fitness)

        return OptimizationResult(
            best_solution=gbest_position,
            best_fitness=gbest_fitness,
            convergence_history=convergence_history,
            iterations=max_iterations,
            execution_time=time.time() - start_time,
        )


class SimulatedAnnealing(IaCOptimizer):
    def __init__(
        self,
        objective: OptimizationObjective,
        initial_temp: float = 100.0,
        final_temp: float = 0.01,
        cooling_rate: float = 0.95,
    ):
        super().__init__(objective)
        self.initial_temp = initial_temp
        self.final_temp = final_temp
        self.cooling_rate = cooling_rate

    def optimize(
        self,
        fitness_fn: Callable[[np.ndarray], float],
        dimensions: int,
        bounds: List[Tuple[float, float]],
        max_iterations: int = 1000,
    ) -> OptimizationResult:
        import time

        start_time = time.time()

        bounds_arr = np.array(bounds)

        current = np.random.uniform(bounds_arr[:, 0], bounds_arr[:, 1])
        current_fitness = fitness_fn(current)

        best = current.copy()
        best_fitness = current_fitness

        temperature = self.initial_temp
        convergence_history = [best_fitness]
        iteration = 0

        while temperature > self.final_temp and iteration < max_iterations:
            neighbor = self._generate_neighbor(current, bounds_arr, temperature)
            neighbor_fitness = fitness_fn(neighbor)

            if self.objective == OptimizationObjective.MINIMIZE_COST:
                delta = neighbor_fitness - current_fitness
            else:
                delta = current_fitness - neighbor_fitness

            if delta < 0 or random.random() < np.exp(-delta / temperature):
                current = neighbor
                current_fitness = neighbor_fitness

                if self.objective == OptimizationObjective.MINIMIZE_COST:
                    if current_fitness < best_fitness:
                        best = current.copy()
                        best_fitness = current_fitness
                else:
                    if current_fitness > best_fitness:
                        best = current.copy()
                        best_fitness = current_fitness

            temperature *= self.cooling_rate
            convergence_history.append(best_fitness)
            iteration += 1

        return OptimizationResult(
            best_solution=best,
            best_fitness=best_fitness,
            convergence_history=convergence_history,
            iterations=iteration,
            execution_time=time.time() - start_time,
        )

    def _generate_neighbor(
        self, current: np.ndarray, bounds: np.ndarray, temperature: float
    ) -> np.ndarray:
        step_size = (
            (bounds[:, 1] - bounds[:, 0]) * (temperature / self.initial_temp) * 0.1
        )
        perturbation = np.random.normal(0, step_size)

        neighbor = current + perturbation
        neighbor = np.clip(neighbor, bounds[:, 0], bounds[:, 1])

        return neighbor


class BayesianOptimization(IaCOptimizer):
    def __init__(
        self,
        objective: OptimizationObjective,
        n_initial: int = 5,
        acquisition: str = "ei",
    ):
        super().__init__(objective)
        self.n_initial = n_initial
        self.acquisition = acquisition

    def optimize(
        self,
        fitness_fn: Callable[[np.ndarray], float],
        dimensions: int,
        bounds: List[Tuple[float, float]],
        max_iterations: int = 50,
    ) -> OptimizationResult:
        import time

        start_time = time.time()

        bounds_arr = np.array(bounds)

        X_observed = self._latin_hypercube_sample(self.n_initial, bounds_arr)
        y_observed = np.array([fitness_fn(x) for x in X_observed])

        if self.objective == OptimizationObjective.MINIMIZE_COST:
            best_idx = np.argmin(y_observed)
        else:
            best_idx = np.argmax(y_observed)

        best_solution = X_observed[best_idx].copy()
        best_fitness = y_observed[best_idx]

        convergence_history = [best_fitness]

        for iteration in range(max_iterations - self.n_initial):
            gp = self._fit_gp(X_observed, y_observed)

            next_point = self._maximize_acquisition(
                gp, bounds_arr, X_observed, y_observed
            )
            next_fitness = fitness_fn(next_point)

            X_observed = np.vstack([X_observed, next_point])
            y_observed = np.append(y_observed, next_fitness)

            if self.objective == OptimizationObjective.MINIMIZE_COST:
                if next_fitness < best_fitness:
                    best_solution = next_point.copy()
                    best_fitness = next_fitness
            else:
                if next_fitness > best_fitness:
                    best_solution = next_point.copy()
                    best_fitness = next_fitness

            convergence_history.append(best_fitness)

        return OptimizationResult(
            best_solution=best_solution,
            best_fitness=best_fitness,
            convergence_history=convergence_history,
            iterations=max_iterations,
            execution_time=time.time() - start_time,
        )

    def _latin_hypercube_sample(self, n_samples: int, bounds: np.ndarray) -> np.ndarray:
        dimensions = len(bounds)
        samples = np.zeros((n_samples, dimensions))

        for d in range(dimensions):
            intervals = np.linspace(0, 1, n_samples + 1)

            for i in range(n_samples):
                samples[i, d] = np.random.uniform(intervals[i], intervals[i + 1])

        for d in range(dimensions):
            np.random.shuffle(samples[:, d])

        samples = samples * (bounds[:, 1] - bounds[:, 0]) + bounds[:, 0]

        return samples

    def _fit_gp(self, X: np.ndarray, y: np.ndarray):
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, ConstantKernel

        kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
        gp = GaussianProcessRegressor(
            kernel=kernel, n_restarts_optimizer=5, normalize_y=True
        )
        gp.fit(X, y)

        return gp

    def _maximize_acquisition(
        self, gp, bounds: np.ndarray, X_observed: np.ndarray, y_observed: np.ndarray
    ) -> np.ndarray:
        n_candidates = 1000
        candidates = np.random.uniform(
            bounds[:, 0], bounds[:, 1], size=(n_candidates, len(bounds))
        )

        mu, sigma = gp.predict(candidates, return_std=True)

        if self.objective == OptimizationObjective.MINIMIZE_COST:
            best_y = np.min(y_observed)
            improvement = best_y - mu
        else:
            best_y = np.max(y_observed)
            improvement = mu - best_y

        from scipy.stats import norm

        Z = improvement / (sigma + 1e-9)
        ei = improvement * norm.cdf(Z) + sigma * norm.pdf(Z)

        best_idx = np.argmax(ei)
        return candidates[best_idx]
