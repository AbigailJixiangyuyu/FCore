"""Build a DeepSeek conversation from verified lifecycle evidence."""

import json

from app.schemas.reports import ReportFollowUpRequest

EVIDENCE_GUIDANCE = """Use only the submitted stages and cite only evidence IDs present in the supplied facts. Cite evidence using its ID,
such as 〔H01〕, 〔C01〕, 〔C02〕 or 〔P01〕. Each stage has its own method, window and, where applicable,
query node and k. When these differ, describe the overlap between the selections and avoid
attributing every membership difference to the passage of time.

Use the historical method's actual finding. Periodic presence refers to the listed snapshots.
A burst witness describes an individual member's window. Compare the submitted selections in
chronological order when a comparison is supplied. Give the number retained, added and exited and use net
change alongside turnover. Retention is the share of the earlier selection that appears in the
later one. Use the membership groups to identify members shared across stages. Quote node IDs
exactly as supplied, including leading zeros. Use inline code for IDs that contain Markdown punctuation.
Describe every future membership or change as predicted for the specified target snapshot.

Use SLADE scores only for scored members of the current selection. Describe coverage, mean,
median and any notable members in the context of both community and global rank. Higher scores
indicate more unusual current interactions. Connect a named member's score to its historical
and predicted membership when supported. If scoring evidence is unavailable, state which
conclusions the evidence can support. Missing forecast scores leave future membership unknown. Omitted stages provide no evidence."""

REPORT_PROMPT = """Write a concise English Markdown report for a graph analyst. Open with one sentence stating the
main finding. After a blank line, give the following Markdown bullet points in order:
{outline}
Lead each point with its conclusion, then support it with specific counts, vertices or snapshots.
Place each evidence ID immediately after the claim it supports. Use initial_prompt, when supplied,
to focus the analysis. Keep each point short.

""" + EVIDENCE_GUIDANCE


def _report_outline(facts: dict) -> str:
    ids = {row["id"] for row in facts.get("evidence", [])}
    points = []
    if "H01" in ids:
        points.append("- **Historical pattern**: describe the submitted community and the method's finding.")
    if "C01" in ids:
        if "H01" in ids:
            points.append("- **Current changes and unusual members**: compare with the historical selection and explain current SLADE evidence.")
        else:
            points.append("- **Current community and unusual members**: describe size, internal edges and current SLADE evidence.")
    if "P01" in ids:
        if "C01" in ids or "H01" in ids:
            earlier = "current" if "C01" in ids else "historical"
            points.append(f"- **Predicted changes**: compare predicted membership directly with the {earlier} selection when scores are available.")
        else:
            points.append("- **Predicted community**: describe the target snapshot, predicted size and members when scores are available.")
    if {"H01", "C01", "P01"} <= ids:
        points[-1] += " Identify members shared across all three stages when supported."
    return "\n".join(points)


FOLLOW_UP_PROMPT = """Answer the latest question about the lifecycle report in the language it uses.
Use earlier replies to resolve references. Use the supplied evidence in the first user message for
factual claims. Explain what information is missing when the question goes beyond that evidence.
Answer a question about a single value or vertex directly. For multiple findings or comparisons,
use a Markdown list with one finding per point. Bold only key conclusions. Place evidence IDs
immediately after the claims they support.

""" + EVIDENCE_GUIDANCE


def report_messages(
    facts: dict, follow_up: ReportFollowUpRequest | None = None,
    *, initial_prompt: str | None = None,
) -> list[dict[str, str]]:
    supplied = facts.copy()
    if initial_prompt is not None:
        supplied["initial_prompt"] = initial_prompt
    messages = [
        {"role": "system", "content": FOLLOW_UP_PROMPT if follow_up else REPORT_PROMPT.format(outline=_report_outline(facts))},
        {"role": "user", "content": json.dumps(supplied, ensure_ascii=False)},
    ]
    if follow_up is None:
        return messages

    messages.append({"role": "assistant", "content": follow_up.report_content})
    for turn in follow_up.turns:
        messages.extend((
            {"role": "user", "content": turn.question},
            {"role": "assistant", "content": turn.answer},
        ))
    messages.append({"role": "user", "content": follow_up.question})
    return messages
