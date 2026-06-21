"""
Meta-model package for evolutionary MAS optimization.

Implements Evolutionary Synthesis of Multi-Agent Systems (EvoMAS)
as described in the paper methodology.
"""

from .experience import (
    ActionExperience,
    MemoryStore,
    EvolutionTrace,
    consolidate_evolution_trace
)
from .selection import selection_operator, select_with_diversity
from .reward import (
    compute_reward,
    compare_configurations,
    should_add_to_pool,
    compute_reward_with_details,
    select_best_configuration
)
from .pool import (
    ConfigurationPool,
    should_update_pool,
    add_to_pool_if_better
)


def MetaModel(*args, **kwargs):
    """Lazy constructor to avoid importing model providers for utility imports."""
    from .metamodel import MetaModel as _MetaModel
    return _MetaModel(*args, **kwargs)


def run_evolution(*args, **kwargs):
    """Lazy import to avoid importing model providers for utility imports."""
    from .metamodel import run_evolution as _run_evolution
    return _run_evolution(*args, **kwargs)

__all__ = [
    # Core
    'MetaModel',
    'run_evolution',
    # Experience & Memory
    'ActionExperience',
    'MemoryStore',
    'EvolutionTrace',
    'consolidate_evolution_trace',
    # Selection
    'selection_operator',
    'select_with_diversity',
    # Reward
    'compute_reward',
    'compare_configurations',
    'should_add_to_pool',
    'compute_reward_with_details',
    'select_best_configuration',
    # Pool
    'ConfigurationPool',
    'should_update_pool',
    'add_to_pool_if_better',
]
