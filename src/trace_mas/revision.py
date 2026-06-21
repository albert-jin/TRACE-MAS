"""TRACE-guided MAS configuration revision operators.

These operators provide a method-specific search layer for TRACE-MAS. They do
not replace the EvoMAS configuration format; instead, they revise that format
through bounded, integrity-oriented operations.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional


VALID_ROUTING_POLICIES = {"all", "direct_parents", "topk_similarity"}


ConfigDict = Dict[str, Any]


@dataclass(frozen=True)
class TRACERevision:
    """A bounded configuration revision proposed from TRACE diagnostics."""

    revision_type: str
    rationale: str
    params: Dict[str, Any] = field(default_factory=dict)


def _copy_config(config: Mapping[str, Any]) -> ConfigDict:
    return deepcopy(dict(config))


def _ensure_execution(config: ConfigDict) -> Dict[str, Any]:
    execution = config.setdefault("execution", {})
    if not isinstance(execution, dict):
        raise TypeError("config['execution'] must be a dictionary")
    return execution


def _ensure_reports_to(config: ConfigDict) -> Dict[str, List[str]]:
    topology = config.setdefault("topology", {})
    if not isinstance(topology, dict):
        raise TypeError("config['topology'] must be a dictionary")
    reports_to = topology.setdefault("reports_to", {})
    if not isinstance(reports_to, dict):
        raise TypeError("config['topology']['reports_to'] must be a dictionary")
    return reports_to


def _agent_ids(config: Mapping[str, Any]) -> List[str]:
    agents = config.get("agents", {})
    if not isinstance(agents, dict):
        return []
    return list(agents.keys())


def set_context_routing(
    config: Mapping[str, Any],
    policy: str,
    top_k: Optional[int] = None,
) -> ConfigDict:
    """Return a config with an explicit TRACE-MAS context routing policy."""

    if policy not in VALID_ROUTING_POLICIES:
        raise ValueError(
            f"Unknown TRACE-MAS routing policy: {policy}. "
            f"Expected one of {sorted(VALID_ROUTING_POLICIES)}"
        )
    if top_k is not None and int(top_k) < 0:
        raise ValueError("top_k must be a non-negative integer or None")

    revised = _copy_config(config)
    execution = _ensure_execution(revised)
    execution["context_routing"] = policy
    if top_k is None:
        execution.pop("context_top_k", None)
    else:
        execution["context_top_k"] = int(top_k)
    _append_revision_note(
        revised,
        TRACERevision(
            revision_type="routing_revision",
            rationale="Set internal report exposure policy.",
            params={"policy": policy, "top_k": top_k},
        ),
    )
    return revised


def set_exposure_budget(config: Mapping[str, Any], top_k: int) -> ConfigDict:
    """Return a config with a bounded number of visible upstream reports."""

    if int(top_k) < 0:
        raise ValueError("top_k must be a non-negative integer")

    revised = _copy_config(config)
    execution = _ensure_execution(revised)
    execution["context_top_k"] = int(top_k)
    if execution.get("context_routing", "all") == "all":
        execution["context_routing"] = "topk_similarity"
    _append_revision_note(
        revised,
        TRACERevision(
            revision_type="exposure_budget_revision",
            rationale="Limit downstream context flooding.",
            params={"top_k": int(top_k)},
        ),
    )
    return revised


def find_sink_agents(config: Mapping[str, Any]) -> List[str]:
    """Find agents with no outgoing reports_to edges.

    Aggregators are usually sinks, but this helper uses topology first so it
    also works for custom role names.
    """

    role_sinks = []
    for agent_id, spec in config.get("agents", {}).items():
        if isinstance(spec, dict) and spec.get("role") in {"aggregator", "coordinator"}:
            role_sinks.append(agent_id)
    if role_sinks:
        return sorted(role_sinks)

    agents = set(_agent_ids(config))
    reports_to = config.get("topology", {}).get("reports_to", {})
    outgoing = {
        source
        for source, targets in reports_to.items()
        if isinstance(targets, Iterable) and list(targets)
    }
    sinks = sorted(agents - outgoing)
    if sinks:
        return sinks

    return []


def insert_verifier_before_sinks(
    config: Mapping[str, Any],
    verifier_id: str = "trace_verifier",
    model_id: Optional[str] = None,
    prompt: str = "trace_integrity_verifier",
    sink_agent_ids: Optional[List[str]] = None,
) -> ConfigDict:
    """Insert one verifier node before final sink agents.

    Existing upstream edges to each sink are redirected to the verifier, and
    the verifier reports to the sinks. This implements a TRACE-MAS revision
    operator rather than an unconstrained mutation.
    """

    revised = _copy_config(config)
    agents = revised.setdefault("agents", {})
    if not isinstance(agents, dict):
        raise TypeError("config['agents'] must be a dictionary")

    sinks = sink_agent_ids or find_sink_agents(revised)
    if not sinks:
        return revised

    reports_to = _ensure_reports_to(revised)
    if _sinks_already_have_verifier(revised, sinks, reports_to):
        _append_revision_note(
            revised,
            TRACERevision(
                revision_type="verifier_insertion_skipped",
                rationale="Sink agents already have a verifier as a direct parent.",
                params={"sinks": sinks},
            ),
        )
        return revised

    if verifier_id in agents:
        verifier_id = _unique_agent_id(agents.keys(), verifier_id)

    chosen_model = model_id or _infer_verifier_model(revised, sinks)
    agents[verifier_id] = {
        "id": verifier_id,
        "role": "verifier",
        "agent_type": "CodeAgent",
        "model_id": chosen_model,
        "prompt": prompt,
        "tools": [],
        "max_tokens": 4096,
        "temperature": 0.2,
        "device": None,
    }

    sink_set = set(sinks)
    upstream_sources: List[str] = []
    for source, targets in list(reports_to.items()):
        if not isinstance(targets, list):
            continue
        new_targets = []
        redirected = False
        for target in targets:
            if target in sink_set:
                redirected = True
            else:
                new_targets.append(target)
        if redirected:
            if verifier_id not in new_targets:
                new_targets.append(verifier_id)
            upstream_sources.append(source)
        reports_to[source] = new_targets

    original_agent_ids = sorted(set(_agent_ids(revised)) - {verifier_id})
    if not upstream_sources:
        if len(original_agent_ids) == 1 and original_agent_ids[0] in sink_set:
            # Single-agent MAS: keep the original agent first and make the
            # verifier the final sink.
            source = original_agent_ids[0]
            reports_to.setdefault(source, [])
            if verifier_id not in reports_to[source]:
                reports_to[source].append(verifier_id)
            upstream_sources.append(source)
            sink_set = set()
        else:
            for source in sorted(set(original_agent_ids) - sink_set):
                reports_to.setdefault(source, [])
                if verifier_id not in reports_to[source]:
                    reports_to[source].append(verifier_id)
                upstream_sources.append(source)

    reports_to[verifier_id] = list(dict.fromkeys(sink_set))
    revised["topology"]["reports_to"] = {
        source: targets for source, targets in reports_to.items() if targets
    }

    execution = _ensure_execution(revised)
    if execution.get("context_routing", "all") == "all":
        execution["context_routing"] = "direct_parents"
    _append_revision_note(
        revised,
        TRACERevision(
            revision_type="verifier_insertion",
            rationale="Add an integrity checkpoint before final aggregation.",
            params={"verifier_id": verifier_id, "sinks": sinks},
        ),
    )
    return revised


def plan_trace_revisions(metrics: Mapping[str, Any]) -> List[TRACERevision]:
    """Plan TRACE-MAS revisions from integrity and exposure diagnostics."""

    revisions: List[TRACERevision] = []
    hallucination_risk = float(metrics.get("hallucination_risk", 0.0) or 0.0)
    unsupported_claims = float(metrics.get("unsupported_claims", 0.0) or 0.0)
    contradiction_score = float(metrics.get("contradiction_score", 0.0) or 0.0)
    noisy_exposure_rate = float(metrics.get("noisy_report_exposure_rate", 0.0) or 0.0)
    context_reports = int(metrics.get("avg_visible_reports", 0) or 0)

    needs_exposure_bound = noisy_exposure_rate > 0.25 or context_reports > 4
    needs_verifier = hallucination_risk > 0.2 or unsupported_claims > 0 or contradiction_score > 0.2

    if needs_exposure_bound:
        revisions.append(
            TRACERevision(
                revision_type="routing_revision",
                rationale="High report exposure suggests context flooding.",
                params={"policy": "topk_similarity", "top_k": 2},
            )
        )

    if needs_verifier:
        revisions.append(
            TRACERevision(
                revision_type="verifier_insertion",
                rationale="Unsupported, contradictory, or risky claims require a verifier before aggregation.",
                params={},
            )
        )

    if contradiction_score > 0.2 and not needs_exposure_bound:
        revisions.append(
            TRACERevision(
                revision_type="routing_revision",
                rationale="Contradictory reports should be isolated to direct dependencies.",
                params={"policy": "direct_parents", "top_k": None},
            )
        )

    if not revisions:
        revisions.append(
            TRACERevision(
                revision_type="assessment_profile_revision",
                rationale="No severe exposure issue detected; keep routing and emphasize integrity scoring.",
                params={"integrity_profile": "balanced"},
            )
        )

    return revisions


def apply_trace_revision(config: Mapping[str, Any], revision: TRACERevision) -> ConfigDict:
    """Apply a single TRACE revision to a MAS configuration dictionary."""

    revision_type = revision.revision_type
    params = revision.params

    if revision_type == "routing_revision":
        return set_context_routing(
            config,
            policy=str(params.get("policy", "topk_similarity")),
            top_k=params.get("top_k"),
        )
    if revision_type == "exposure_budget_revision":
        return set_exposure_budget(config, top_k=int(params.get("top_k", 2)))
    if revision_type == "verifier_insertion":
        return insert_verifier_before_sinks(
            config,
            verifier_id=str(params.get("verifier_id", "trace_verifier")),
            model_id=params.get("model_id"),
            prompt=str(params.get("prompt", "trace_integrity_verifier")),
            sink_agent_ids=params.get("sinks"),
        )
    if revision_type == "assessment_profile_revision":
        revised = _copy_config(config)
        meta = revised.setdefault("meta", {})
        meta["trace_assessment_profile"] = params.get("integrity_profile", "balanced")
        _append_revision_note(revised, revision)
        return revised

    raise ValueError(f"Unsupported TRACE revision type: {revision_type}")


def apply_trace_revisions(
    config: Mapping[str, Any],
    revisions: Iterable[TRACERevision],
) -> ConfigDict:
    """Apply a sequence of TRACE revisions in order."""

    revised = _copy_config(config)
    for revision in revisions:
        revised = apply_trace_revision(revised, revision)
    return revised


def run_trace_self_revision_loop(
    initial_config: Mapping[str, Any],
    initial_metrics: Mapping[str, Any],
    *,
    evaluate_fn: Optional[Callable[[Mapping[str, Any]], Mapping[str, Any]]] = None,
    max_rounds: int = 1,
) -> Dict[str, Any]:
    """Run a lightweight TRACE self-revision loop.

    This helper separates the method loop from any specific LLM runner. If
    ``evaluate_fn`` is provided, each revised config is evaluated and the next
    round uses the returned metrics. Without an evaluator, the helper performs
    one diagnostic planning/application pass.
    """

    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")

    current_config = _copy_config(initial_config)
    current_metrics = dict(initial_metrics)
    history: List[Dict[str, Any]] = []

    for round_idx in range(max_rounds):
        revisions = plan_trace_revisions(current_metrics)
        next_config = apply_trace_revisions(current_config, revisions)
        entry: Dict[str, Any] = {
            "round": round_idx,
            "input_metrics": dict(current_metrics),
            "revisions": [
                {
                    "type": revision.revision_type,
                    "rationale": revision.rationale,
                    "params": revision.params,
                }
                for revision in revisions
            ],
        }

        if evaluate_fn is None:
            history.append(entry)
            current_config = next_config
            break

        next_metrics = dict(evaluate_fn(next_config))
        entry["output_metrics"] = next_metrics
        history.append(entry)

        current_config = next_config
        if _trace_score(next_metrics) <= _trace_score(current_metrics):
            current_metrics = next_metrics
            break
        current_metrics = next_metrics

    return {
        "config": current_config,
        "metrics": current_metrics,
        "history": history,
    }


def _trace_score(metrics: Mapping[str, Any]) -> float:
    accuracy = float(metrics.get("accuracy", metrics.get("score", 0.0)) or 0.0)
    if accuracy > 1.0:
        accuracy = accuracy / 100.0
    integrity_bonus = float(metrics.get("evidence_support", 0.0) or 0.0)
    integrity_bonus += float(metrics.get("consistency_score", 0.0) or 0.0)
    integrity_penalty = float(metrics.get("hallucination_risk", 0.0) or 0.0)
    integrity_penalty += float(metrics.get("unsupported_claims", 0.0) or 0.0)
    integrity_penalty += float(metrics.get("contradiction_score", 0.0) or 0.0)
    return accuracy + 0.1 * integrity_bonus - 0.1 * integrity_penalty


def _infer_verifier_model(config: Mapping[str, Any], sinks: List[str]) -> str:
    agents = config.get("agents", {})
    for sink in sinks:
        spec = agents.get(sink)
        if isinstance(spec, dict) and spec.get("model_id"):
            return str(spec["model_id"])
    for spec in agents.values():
        if isinstance(spec, dict) and spec.get("model_id"):
            return str(spec["model_id"])
    raise ValueError("Cannot infer verifier model_id from config")


def _sinks_already_have_verifier(
    config: Mapping[str, Any],
    sinks: List[str],
    reports_to: Mapping[str, List[str]],
) -> bool:
    if not sinks:
        return False

    agents = config.get("agents", {})
    for sink in sinks:
        has_verifier_parent = False
        for source, targets in reports_to.items():
            if sink not in (targets or []):
                continue
            source_spec = agents.get(source, {})
            if isinstance(source_spec, dict) and source_spec.get("role") == "verifier":
                has_verifier_parent = True
                break
        if not has_verifier_parent:
            return False
    return True


def _unique_agent_id(existing_ids: Iterable[str], base_id: str) -> str:
    existing = set(existing_ids)
    if base_id not in existing:
        return base_id
    idx = 2
    while f"{base_id}_{idx}" in existing:
        idx += 1
    return f"{base_id}_{idx}"


def _append_revision_note(config: ConfigDict, revision: TRACERevision) -> None:
    meta = config.setdefault("meta", {})
    history = meta.setdefault("trace_revisions", [])
    history.append(
        {
            "type": revision.revision_type,
            "rationale": revision.rationale,
            "params": revision.params,
        }
    )
