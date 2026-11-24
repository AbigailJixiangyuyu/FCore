"""Compare the members of the verified, submitted communities."""

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean, median

from app.schemas.analysis import Structure

from .history import submitted_history_evidence, window


@dataclass
class ReportFacts:
    values: dict = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict, repr=False)

    def alias(self, account: str) -> str:
        return self.aliases.setdefault(account, f"N{len(self.aliases) + 1:03}")


def _membership_change(earlier: set[str], later: set[str]) -> dict:
    shared = len(earlier & later)
    return {
        "retained": shared,
        "added": len(later - earlier),
        "exited": len(earlier - later),
        "net_change": len(later) - len(earlier),
        "retention_rate": round(shared / len(earlier), 4) if earlier else None,
    }


def _membership_groups(facts: ReportFacts, stages: dict[str, set[str]]) -> list[dict]:
    """List each account once so follow-ups can identify any member of the submitted results."""
    groups = defaultdict(list)
    for account in sorted(set().union(*stages.values())):
        present_in = tuple(stage for stage, members in stages.items() if account in members)
        groups[present_in].append(facts.alias(account))
    return [{"stages": list(stages_present), "nodes": nodes} for stages_present, nodes in groups.items()]


def _current_risk(
    facts: ReportFacts, snapshot: str, historical: set[str] | None, current: set[str],
    predicted: set[str] | None, scores: dict | None,
) -> dict:
    rows = [] if scores is None else [row for row in scores["accounts"] if row["account_id"] in current]
    rows.sort(key=lambda row: row["rank"])
    record = {
        "id": "C02",
        "topic": "SLADE scores within the submitted current community",
        "snapshot": snapshot,
        "scored_members": len(rows),
        "unscored_members": len(current) - len(rows),
    }
    if not rows:
        record["evidence_gap"] = (
            "Current SLADE scores were unavailable at submission." if scores is None
            else "No member of the submitted community has a current SLADE score."
        )
        return record

    values = [row["score"] for row in rows]
    review_members = []
    for rank, row in enumerate(rows, start=1):
        if rank > 3 and row["rank"] > 10:
            break
        account = row["account_id"]
        member = {
            "node": facts.alias(account),
            "score": round(row["score"], 4),
            "community_rank": rank,
            "global_rank": row["rank"],
        }
        if historical is not None:
            member["in_submitted_history"] = account in historical
        if predicted is not None:
            member["in_submitted_prediction"] = account in predicted
        review_members.append(member)
    record.update(
        mean=round(mean(values), 4), median=round(median(values), 4),
        scored_members_in_global_top_10=sum(row["rank"] <= 10 for row in rows),
        highest_scoring_members=review_members,
    )
    return record


_CURRENT_METHODS = {
    "sigmod25-parallel-kcore-v1": "Parallel k-Core Decomposition",
    "tccs-online-v1": "TCCS",
    "pkmc-v1": "PKMC (global maximum k-core)",
    "maximum-core-v1": "Maximum k-core component",
}


def _add_query_parameters(facts: ReportFacts, record: dict, parameters: dict) -> None:
    if parameters.get("account") is not None:
        record["query_node"] = facts.alias(parameters["account"])
    if "k" in parameters:
        record["k"] = parameters["k"]


def collect_facts(history: Structure | None, current: Structure | None,
                  scores: dict | None, forecast: dict | None) -> ReportFacts:
    facts = ReportFacts()
    records = []
    stages = {}
    if history is not None:
        stages["history"] = set(history.members)
        record = submitted_history_evidence(history, facts.alias)
        _add_query_parameters(facts, record, history.parameters)
        records.append(record)

    if current is not None:
        stages["current"] = set(current.members)
        record = {
            "id": "C01", "topic": "submitted current community",
            "method": _CURRENT_METHODS.get(current.method, current.method),
            "window": window(current.parameters.get("start_snapshot_id") or current.snapshot_id, current.snapshot_id),
            "member_count": len(stages["current"]),
            "internal_edges": current.metrics["internal_edges"],
        }
        if "history" in stages:
            record["change_from_history"] = _membership_change(stages["history"], stages["current"])
        if "max_core" in current.parameters:
            record["maximum_core_order"] = current.parameters["max_core"]
        _add_query_parameters(facts, record, current.parameters)
        records.append(record)

    if forecast is not None:
        prediction = {
            "id": "P01", "topic": "submitted predicted community",
            "method": forecast["model"].title(), "target_snapshot": forecast["target_snapshot"],
        }
        _add_query_parameters(facts, prediction, forecast)
        if forecast["scored_pair_count"]:
            members = set(forecast["members"])
            prediction["predicted_member_count"] = len(members)
            if stages:
                earlier = next(reversed(stages))
                prediction[f"change_from_{earlier}"] = _membership_change(stages[earlier], members)
            if history is not None and current is not None:
                prediction["members_in_all_three"] = len(stages["history"] & stages["current"] & members)
            stages["predicted"] = members
        else:
            prediction["evidence_gap"] = "No candidate pair could be scored for this prediction."

    if current is not None:
        records.append(_current_risk(facts, current.observed_until, stages.get("history"),
                                     stages["current"], stages.get("predicted"), scores))
    if forecast is not None:
        records.append(prediction)
    facts.values = {"evidence": records, "membership_groups": _membership_groups(facts, stages)}
    return facts
