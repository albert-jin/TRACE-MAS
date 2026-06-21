"""TRACE-MAS method-specific utilities.

The package contains the TRACE-guided configuration revision layer. It keeps
the original EvoMAS YAML schema compatible while exposing method-specific
operators that can be described as routing, exposure, verifier, and assessment
revisions rather than generic mutation/crossover.
"""

from .revision import (
    TRACERevision,
    apply_trace_revision,
    apply_trace_revisions,
    find_sink_agents,
    insert_verifier_before_sinks,
    plan_trace_revisions,
    run_trace_self_revision_loop,
    set_context_routing,
    set_exposure_budget,
)

__all__ = [
    "TRACERevision",
    "apply_trace_revision",
    "apply_trace_revisions",
    "find_sink_agents",
    "insert_verifier_before_sinks",
    "plan_trace_revisions",
    "run_trace_self_revision_loop",
    "set_context_routing",
    "set_exposure_budget",
]
