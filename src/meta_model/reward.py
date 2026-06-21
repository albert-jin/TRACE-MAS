"""
Reward functions for EvoMAS / TRACE-MAS.

The original EvoMAS reward is:
    reward = accuracy - beta * cost

TRACE-MAS keeps that behavior when no integrity metrics are present, and adds
optional integrity signals for grounded, robust, low-hallucination MAS
self-revision.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


DEFAULT_INTEGRITY_WEIGHTS = {
    "evidence_support": 0.2,
    "consistency_score": 0.1,
    "robustness_score": 0.2,
    "hallucination_risk": -0.3,
    "unsupported_claims": -0.1,
    "contradiction_score": -0.2,
}


def _get_cost(metrics: Dict[str, Any], cost_weight: str = "both") -> float:
    """Extract the cost term from flat or nested metric dictionaries."""
    explicit_cost = metrics.get("cost", metrics.get("total_cost", None))
    total_tokens = metrics.get("total_tokens", metrics.get("token_cost", 0))
    total_time = metrics.get("total_time", 0.0)

    if explicit_cost is not None and cost_weight == "both":
        return float(explicit_cost or 0.0)
    if "token_costs" in metrics:
        total_tokens = metrics["token_costs"].get("total_tokens", total_tokens)
    if "time_costs" in metrics:
        total_time = metrics["time_costs"].get("total_time", total_time)

    if cost_weight == "tokens":
        return float(total_tokens or 0)
    if cost_weight == "time":
        return float(total_time or 0.0)
    if cost_weight == "both":
        return float(total_tokens or 0) + 1000.0 * float(total_time or 0.0)
    return 0.0


def _get_accuracy(metrics: Dict[str, Any]) -> float:
    """Extract task score and normalize common 0-100 values to 0-1."""
    accuracy = float(metrics.get("accuracy", metrics.get("score", 0.0)) or 0.0)
    if accuracy > 1.0:
        accuracy = accuracy / 100.0
    return accuracy


def compute_integrity_score(
    metrics: Dict[str, Any],
    integrity_weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute TRACE-MAS integrity bonus/penalty.

    Missing metrics contribute zero, so legacy EvoMAS experiments keep the
    original reward behavior exactly.
    """
    weights = dict(DEFAULT_INTEGRITY_WEIGHTS)
    if integrity_weights:
        weights.update(integrity_weights)

    score = 0.0
    for key, weight in weights.items():
        value = metrics.get(key, 0.0)
        try:
            score += float(weight) * float(value)
        except (TypeError, ValueError):
            logger.debug("Skipping non-numeric integrity metric %s=%r", key, value)
    return score


def compute_reward(
    metrics: Dict[str, Any],
    beta: float = 1e-6,
    cost_weight: str = "both",
    integrity_weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute reward for a configuration on a task.

    Args:
        metrics: Dictionary containing accuracy/cost metrics and optional
            TRACE-MAS integrity metrics such as evidence_support,
            hallucination_risk, unsupported_claims, contradiction_score,
            consistency_score, and robustness_score.
        beta: Cost trade-off parameter.
        cost_weight: Which cost metric to use ("tokens", "time", or "both").
        integrity_weights: Optional coefficient overrides.

    Returns:
        Reward value, where higher is better.
    """
    accuracy = _get_accuracy(metrics)
    cost = _get_cost(metrics, cost_weight)
    integrity_score = compute_integrity_score(metrics, integrity_weights)
    reward = accuracy + integrity_score - beta * cost

    logger.debug(
        "Reward: accuracy=%.4f, integrity=%+.4f, cost=%.2f, beta=%s, reward=%.4f",
        accuracy,
        integrity_score,
        cost,
        beta,
        reward,
    )
    return reward


def compare_configurations(
    metrics_1: Dict[str, Any],
    metrics_2: Dict[str, Any],
    beta: float = 1e-6,
    cost_weight: str = "both",
    integrity_weights: Optional[Dict[str, float]] = None,
) -> int:
    """Compare two configurations based on reward."""
    reward_1 = compute_reward(metrics_1, beta, cost_weight, integrity_weights)
    reward_2 = compute_reward(metrics_2, beta, cost_weight, integrity_weights)

    if reward_1 > reward_2:
        return 1
    if reward_1 < reward_2:
        return -1
    return 0


def should_add_to_pool(
    new_metrics: Dict[str, Any],
    parent_metrics: Dict[str, Any],
    beta: float = 1e-6,
    cost_weight: str = "both",
    improvement_threshold: float = 0.01,
    integrity_weights: Optional[Dict[str, float]] = None,
) -> bool:
    """Determine whether a new configuration should be added to the pool."""
    reward_new = compute_reward(new_metrics, beta, cost_weight, integrity_weights)
    reward_parent = compute_reward(parent_metrics, beta, cost_weight, integrity_weights)
    improvement = reward_new - reward_parent

    logger.info("Reward comparison:")
    logger.info("  New:    %.4f", reward_new)
    logger.info("  Parent: %.4f", reward_parent)
    logger.info("  Improvement: %+.4f", improvement)

    return improvement > improvement_threshold


def compute_reward_with_details(
    metrics: Dict[str, Any],
    beta: float = 1e-6,
    cost_weight: str = "both",
    integrity_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute reward with a detailed breakdown."""
    accuracy = _get_accuracy(metrics)
    cost = _get_cost(metrics, cost_weight)
    integrity_score = compute_integrity_score(metrics, integrity_weights)
    cost_penalty = beta * cost
    reward = accuracy + integrity_score - cost_penalty

    breakdown = (
        f"Reward = {reward:.4f}\n"
        f"  Accuracy: {accuracy:.4f}\n"
        f"  Integrity: {integrity_score:+.4f}\n"
        f"  Cost: {cost:.2f} (penalty: -{cost_penalty:.4f})"
    )

    return {
        "reward": reward,
        "accuracy": accuracy,
        "integrity_score": integrity_score,
        "cost": cost,
        "cost_penalty": cost_penalty,
        "breakdown": breakdown,
    }


def select_best_configuration(
    configs_with_metrics: list,
    beta: float = 1e-6,
    cost_weight: str = "both",
    integrity_weights: Optional[Dict[str, float]] = None,
) -> int:
    """Select the best configuration from a list based on reward."""
    if not configs_with_metrics:
        raise ValueError("Empty configuration list")

    best_idx = 0
    best_reward = float("-inf")

    for i, (_, metrics) in enumerate(configs_with_metrics):
        reward = compute_reward(metrics, beta, cost_weight, integrity_weights)
        if reward > best_reward:
            best_reward = reward
            best_idx = i

    logger.info("Selected configuration %s with reward %.4f", best_idx, best_reward)
    return best_idx


