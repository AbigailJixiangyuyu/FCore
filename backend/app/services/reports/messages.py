"""Build a DeepSeek conversation from verified lifecycle evidence."""

import json
import re

from app.schemas.reports import ReportFollowUpRequest

from .facts import ReportFacts

EVIDENCE_GUIDANCE = """Use only the three submitted community results. Cite evidence using its ID,
such as 〔H01〕, 〔C01〕, 〔C02〕 or 〔P01〕. Each stage has its own method, window and, where applicable,
query node and k. When these differ, describe the overlap between the selections and avoid
attributing every membership difference to the passage of time.

Use the historical method's actual finding. Periodic presence refers to the listed snapshots.
A burst witness describes an individual member's window. Compare history with current, then
current with the submitted prediction. Give the number retained, added and exited and use net
change alongside turnover. Retention is the share of the earlier selection that appears in the
later one. Use the membership groups and node aliases to identify members shared across stages.
Describe every future membership or change as predicted for the specified target snapshot.

Use SLADE scores only for scored members of the current selection. Describe coverage, mean,
median and any notable members in the context of both community and global rank. Higher scores
indicate more unusual current interactions. Connect a named member's score to its historical
and predicted membership when supported. If scoring evidence is unavailable, state which
conclusions the evidence can support. Missing forecast scores leave future membership unknown."""

REPORT_PROMPT = """Write a concise English analysis for a graph analyst in short plain-text paragraphs.
Use initial_prompt, when provided, to focus the report on the analyst's question. Connect the
historical pattern, observed membership changes, current anomaly scores and predicted retention
or turnover. Highlight specific members whose history, current score and forecast merit attention.

""" + EVIDENCE_GUIDANCE

FOLLOW_UP_PROMPT = """Answer the latest question about the lifecycle report in the language it uses.
Use earlier replies to resolve references. Use the supplied evidence in the first user message for
factual claims. Explain what information is missing when the question goes beyond that evidence.
Respond in plain text.

""" + EVIDENCE_GUIDANCE


def _node_mentions(aliases: dict[str, str]) -> re.Pattern[str]:
    accounts = "|".join(re.escape(account) for account in sorted(aliases, key=len, reverse=True))
    return re.compile(
        rf"((?:(?i:\b(?:vertex|node|account)\b)|顶点|节点|账户)\s*[:：]?\s*`?)"
        rf"({accounts})(?![A-Za-z0-9_-]|\.[A-Za-z0-9_])",
    )


def report_messages(
    facts: ReportFacts, follow_up: ReportFollowUpRequest | None = None,
    *, initial_prompt: str | None = None,
) -> list[dict[str, str]]:
    mentions = _node_mentions(facts.aliases) if facts.aliases else None

    def with_aliases(text: str) -> str:
        if mentions is None:
            return text
        return mentions.sub(lambda match: match[1] + facts.aliases[match[2]], text)

    supplied = {**facts.values}
    if initial_prompt is not None:
        supplied["initial_prompt"] = with_aliases(initial_prompt)
    messages = [
        {"role": "system", "content": FOLLOW_UP_PROMPT if follow_up else REPORT_PROMPT},
        {"role": "user", "content": json.dumps(supplied, ensure_ascii=False)},
    ]
    if follow_up is None:
        return messages

    messages.append({"role": "assistant", "content": follow_up.report_content})
    for turn in follow_up.turns:
        messages.extend((
            {"role": "user", "content": with_aliases(turn.question)},
            {"role": "assistant", "content": turn.answer},
        ))
    messages.append({"role": "user", "content": with_aliases(follow_up.question)})
    return messages
