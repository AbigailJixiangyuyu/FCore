"""Build a DeepSeek conversation from verified lifecycle evidence."""

import json
import re

from app.schemas.reports import ReportFollowUpRequest

from .facts import ReportFacts

REPORT_PROMPT = """Write a concise English report for a graph analyst using the supplied evidence.
Present the report as plain text in short paragraphs.

Use initial_prompt, when provided, to focus the report on the analyst's request. Ground factual
claims in the verified evidence fields. Connect the historical pattern and its members to the
selected current community. Interpret the current SLADE scores and coverage, and relate the
forecast to these communities and their members.
Support the analysis with the supplied counts, scores and snapshot labels. Refer to individual
accounts by their supplied aliases.

Higher SLADE scores describe more unusual observed interactions. Treat unscored members as having
unknown risk. Explain the forecast at the selected edge threshold using its actual outcome.
Retained, added and exited counts use the forecast query's own observed q,k baseline.
Describe unavailable predictions using the supplied forecast outcome."""

FOLLOW_UP_PROMPT = """Discuss the lifecycle report with a graph analyst. Answer the latest question
in the language it uses. Use the earlier questions and replies to resolve references such as
"those members". Use the submitted evidence in the first user message for factual claims and
explain what information is missing when it cannot answer a question. Refer to individual accounts
by their supplied aliases. Describe high SLADE scores as unusual observed interactions and explain
forecast results as conditional on the selected edge threshold. Retained, added and exited counts
use the forecast query's own observed q,k baseline. Respond in plain text."""


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
