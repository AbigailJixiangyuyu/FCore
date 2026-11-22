"""Local set comparisons, risk statistics and report-scoped node aliases."""

from dataclasses import dataclass, field
from statistics import mean, median

from app.schemas.analysis import Structure
from .history import history_facts, window


@dataclass
class ReportFacts:
    # Only values is serialized for the provider.
    values: dict = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict, repr=False)

    def node(self, name: str, account: str) -> None:
        self.values[name] = self.aliases.setdefault(account, f"N{len(self.aliases) + 1:03}")


def _risk_facts(facts, scores, current, history, predicted, comparison):
    values = facts.values
    if scores is None:
        values["risk_status"] = "SLADE scores unavailable"
        return
    ranked = sorted((r for r in scores["accounts"] if r["account_id"] in current), key=lambda r: r["rank"])
    values.update(risk_scored=len(ranked), risk_unscored=len(current) - len(ranked), risk_snapshot=scores["snapshot_id"])
    if not ranked:
        values["risk_status"] = "no current community members could be scored"
        return
    top = {r["account_id"] for r in ranked if r["rank"] <= 10}
    dist = [r["score"] for r in ranked]
    values.update(risk_status="scored", risk_mean=f"{mean(dist):.4f}", risk_median=f"{median(dist):.4f}",
                  global_top_limit=10, current_in_global_top=len(top), historical_current_in_global_top=len(top & history))
    if comparison is not None:
        values.update(top_members_predicted=len(top & predicted), top_members_predicted_to_exit=len(top.intersection(comparison["exited"])))
    for index, entry in enumerate(ranked[:2], 1):
        account = entry["account_id"]
        prefix = f"risk_member_{index}_"
        facts.node(prefix + "node", account)
        values[prefix + "global_rank"] = entry["rank"]
        values[prefix + "score"] = f'{entry["score"]:.4f}'
        values[prefix + "in_history"] = account in history
        if comparison is not None:
            values[prefix + "in_prediction"] = account in predicted
            values[prefix + "forecast_change"] = next(
                (label for label in ("retained", "added", "exited") if account in comparison[label]),
                "outside both forecast and its observed baseline",
            )


def collect_facts(history: Structure, current: Structure, scores: dict | None, forecast: dict) -> ReportFacts:
    facts = ReportFacts()
    history_facts(history, facts)
    past, present, predicted = set(history.members), set(current.members), set(forecast["members"])
    shared = past & present
    parameters = current.parameters
    method = "global maximum core" if current.origin == "max_core" else "local core"
    if parameters.get("algorithm") == "tccs":
        method = "temporal core component"
    facts.values.update(
        current_method=method,
        current_k=parameters.get("k", parameters.get("max_core")),
        current_size=len(present),
        current_internal_edges=current.metrics["internal_edges"],
        current_density=f'{current.metrics["density"]:.2%}',
        current_window=window(parameters.get("start_snapshot_id", current.snapshot_id), current.snapshot_id),
        history_current_overlap=len(shared),
        share_of_history_also_current=f"{len(shared) / len(past):.1%}",
        observed_snapshot=current.observed_until,
        prediction_target=forecast["target_snapshot"],
        prediction_k=forecast["k"],
        edge_probability_threshold=forecast["threshold"],
        prediction_status=forecast["status"],
        forecast_outcome={
            "ok": "a predicted community was found",
            "no_historical_community": "the query node had no qualifying historical community",
            "no_scored_pairs": "no candidate pairs could be scored",
            "no_threshold_edges": "no scored edge exceeded the probability threshold",
            "no_predicted_community": "the predicted edges did not form the requested community",
        }[forecast["status"]],
    )
    if "account" in parameters:
        facts.node("current_query_node", parameters["account"])
    facts.node("forecast_query_node", forecast["account"])
    comparison = forecast["comparison"]
    if comparison is not None:
        facts.values.update(
            forecast_size=len(predicted),
            current_forecast_overlap=len(present & predicted),
            all_three_overlap=len(shared & predicted),
            share_of_current_also_predicted=f"{len(present & predicted) / len(present):.1%}",
            forecast_retained=len(comparison["retained"]),
            forecast_added=len(comparison["added"]),
            forecast_exited=len(comparison["exited"]),
            forecast_baseline_size=len(comparison["retained"]) + len(comparison["exited"]),
        )
    _risk_facts(facts, scores, present, past, predicted, comparison)
    return facts
