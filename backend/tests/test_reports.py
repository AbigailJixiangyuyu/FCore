import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.reports import evidence
from app.services.reports.facts import ReportFacts, collect_facts
from app.services.reports.provider import ReportClient


def provider_delta(**delta):
    chunk = {"model": "deepseek-flash", "choices": [{"delta": delta}]}
    return f"data: {json.dumps(chunk)}\n\n"


@pytest.fixture
def submitted_report(app_with_test_core, monkeypatch):
    application = app_with_test_core(Settings())
    client = TestClient(application)
    dataset = next(d for d in client.get("/api/datasets").json()["datasets"] if d["dataset_id"] == "email-eu-core-dept3")
    ctx = {k: dataset[k] for k in ("dataset_id", "dataset_version", "observed_until")}
    def query(path, **parameters):
        response = client.post("/api/" + path, json={**ctx, **parameters})
        assert response.status_code == 200, response.text
        return response.json()
    def ref(structure):
        return {k: structure[k] for k in (*ctx, "origin", "parameters", "method", "structure_id", "membership_hash", "snapshot_id")}

    historical = query("patterns/mine", pattern="temporal_core", k=7, start_snapshot_id="S10", end_snapshot_id="S11")["structures"][0]
    current = query("queries/max-core", algorithm="pkmc")["structures"][0]
    shared = set(historical["members"]) & set(current["members"])
    assert (len(historical["members"]), len(current["members"]), len(shared)) == (18, 30, 13)
    chosen = sorted(shared)[0]
    forecast = {"account": chosen, "k": 1, "model_version": "test-zebra", "threshold": 0.5,
                "target_snapshot": "S13", "result_fingerprint": "forecast-1", "status": "ok", "members": [chosen],
                "comparison": {"retained": [chosen], "added": [], "exited": []}}
    monkeypatch.setattr(evidence, "forecast_community", lambda *args: forecast)
    monkeypatch.setattr(evidence, "score_accounts", lambda *args: {
        "model_version": "test-slade", "snapshot_id": "S12",
        "accounts": [{"account_id": chosen, "rank": 13, "score": 0.1234}],
    })
    body = dict(ctx, history=ref(historical), current=dict(ref(current), risk_model_version="test-slade"),
                future=dict(ctx, account=chosen, k=1, model="zebra", threshold=0.5, horizon=1, target_snapshot="S13",
                            model_version="test-zebra", result_fingerprint="forecast-1"))
    return application, body, historical, current, forecast


def test_report_verifies_submitted_results_before_one_provider_call(submitted_report):
    application, body, historical, current, forecast = submitted_report
    client = TestClient(application)
    chosen = forecast["account"]
    calls = []
    first = "The two selections share 13 members."
    second = "\n\nNode N001 has a current SLADE score of 0.1234."

    def completion(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert payload["stream"] is True and "response_format" not in payload
        assert payload["thinking"] == {"type": "enabled"}
        facts = json.loads(payload["messages"][1]["content"])
        assert facts["history_current_overlap"] == 13 and facts["all_three_overlap"] == 1
        assert facts["risk_scored"] == 1 and facts["current_in_global_top"] == 0
        assert facts["forecast_query_node"] == facts["risk_member_1_node"] != chosen
        assert facts["without_last_min_internal_degree"] == 5 and facts["without_first_min_internal_degree"] == 2
        assert facts["forecast_baseline_size"] == 1 and facts["current_size"] == 30
        return httpx.Response(
            200, headers={"Content-Type": "text/event-stream"},
            text=(
                ": keep-alive\n\n" + provider_delta(role="assistant")
                + provider_delta(reasoning_content="Thinking about the evidence.", content=None)
                + provider_delta(content=first) + provider_delta(content=second)
                + 'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n'
                + "data: [DONE]\n\n"
            ),
        )

    application.state.report_client = ReportClient("https://provider.invalid", "test", "deepseek-flash", httpx.MockTransport(completion))
    for stage, field in (("future", "result_fingerprint"), ("history", "membership_hash"), ("current", "risk_model_version"), ("future", "dataset_version")):
        stale = deepcopy(body)
        stale[stage][field] = "changed"
        response = client.post("/api/reports/generate", json=stale)
        assert response.status_code == 409 and stage.title() in response.json()["detail"]
    assert not calls
    report = client.post("/api/reports/generate", json=body)
    assert len(calls) == 1 and calls[0].url.path == "/chat/completions"
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/jsonl"
    assert report.headers["x-accel-buffering"] == "no"
    assert [json.loads(line) for line in report.iter_lines()] == [
        {"type": "start", "model": "deepseek-flash", "node_labels": {"N001": chosen}},
        {"type": "delta", "content": first},
        {"type": "delta", "content": second},
        {"type": "done"},
    ]

    # A scored empty core can have exits. Missing pairs cannot establish exits.
    from app.schemas.analysis import Structure
    for status, comparison in (("no_predicted_community", {"retained": [], "added": [], "exited": [chosen]}),
                               ("no_scored_pairs", None)):
        facts = collect_facts(Structure(**historical), Structure(**current), None, {
            **forecast, "status": status, "members": [], "comparison": comparison,
        }).values
        assert "unavailable" in facts["risk_status"]
        assert ("forecast_exited" in facts) == (comparison is not None)


def test_follow_ups_send_the_original_report_and_prior_turns(submitted_report):
    application, body, _, _, forecast = submitted_report
    client = TestClient(application)
    calls = []
    answers = ["13 人属于同一组。", "其中 1 人预计仍在 S13。"]
    initial_prompt = f"Compare vertex {forecast['account']} across the three stages."

    def completion(request):
        payload = json.loads(request.content)
        assert payload["stream"] and payload["thinking"] == {"type": "enabled"}
        messages = payload["messages"]
        supplied = json.loads(messages[1]["content"])
        assert supplied["all_three_overlap"] == 1
        assert supplied["initial_prompt"] == "Compare vertex N001 across the three stages."
        answer = answers[len(calls)]
        calls.append(messages)
        return httpx.Response(
            200, headers={"Content-Type": "text/event-stream"},
            text=provider_delta(content=answer) + "data: [DONE]\n\n",
        )

    application.state.report_client = ReportClient(
        "https://provider.invalid", "test", "deepseek-flash", httpx.MockTransport(completion),
    )
    report_content = "\nThe two selections share 13 members, including N001.\n"
    question = f"节点{forecast['account']}所在的这一组有 13 人吗？"
    follow_up = dict(body, initial_prompt=initial_prompt, report_content=report_content, turns=[], question=question)
    path = "/api/reports/follow-up"

    stale = deepcopy(follow_up)
    stale["future"]["result_fingerprint"] = "changed"
    assert client.post(path, json=stale).status_code == 409
    assert client.post(path, json={**follow_up, "question": "  "}).status_code == 422
    assert not calls

    first = client.post(path, json=follow_up)
    assert first.status_code == 200 and first.headers["content-type"] == "application/jsonl"
    assert [json.loads(line) for line in first.iter_lines()][1:] == [
        {"type": "delta", "content": answers[0]}, {"type": "done"},
    ]
    next_question = "其中多少人预计仍在 S13？"
    second = client.post(path, json={
        **follow_up, "turns": [{"question": question, "answer": answers[0]}], "question": next_question,
    })
    assert second.status_code == 200
    assert len(calls) == 2
    assert calls[1][2:] == [
        {"role": "assistant", "content": report_content},
        {"role": "user", "content": "节点N001所在的这一组有 13 人吗？"},
        {"role": "assistant", "content": answers[0]},
        {"role": "user", "content": next_question},
    ]
    assert calls[0] == calls[1][:4]


def test_first_message_supplies_the_analysts_request_with_verified_evidence(submitted_report):
    application, body, _, _, forecast = submitted_report
    client = TestClient(application)
    supplied = []

    def completion(request):
        supplied.append(json.loads(json.loads(request.content)["messages"][1]["content"]))
        return httpx.Response(
            200, headers={"Content-Type": "text/event-stream"},
            text=provider_delta(content="Report for the submitted community.") + "data: [DONE]\n\n",
        )

    application.state.report_client = ReportClient("https://provider.invalid", "test", "test", httpx.MockTransport(completion))
    prompt = f"History · OTCD · S10–S11\nCompare vertex {forecast['account']} in S12 and S13."
    path = "/api/reports/generate"
    assert client.post(path, json={**body, "initial_prompt": "  "}).status_code == 422
    response = client.post(path, json={**body, "initial_prompt": prompt})
    assert response.status_code == 200 and len(supplied) == 1
    assert supplied[0]["initial_prompt"] == "History · OTCD · S10–S11\nCompare vertex N001 in S12 and S13."
    assert supplied[0]["history_current_overlap"] == 13
    assert [json.loads(line)["type"] for line in response.iter_lines()] == ["start", "delta", "done"]


def test_provider_errors_never_return_upstream_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", " ")
    assert ReportClient.from_env(tmp_path / ".env").model == "deepseek-flash"

    facts = ReportFacts()
    facts.node("node", "private@example.org")
    assert "private@" not in json.dumps(facts.values)
    with pytest.raises(HTTPException, match="LLM_API_KEY"):
        ReportClient("https://provider.invalid", "", "test").check_ready()

    def timeout(request):
        raise httpx.ReadTimeout("private upstream detail", request=request)

    async def read_events(transport):
        client = ReportClient("https://provider.invalid", "secret", "test", transport)
        async with client.stream(facts) as events:
            return [event async for event in events]

    for handler, code, hint in [
        (timeout, 504, "timed out"),
        (lambda _: httpx.Response(400, text="private upstream detail"), 502, "deepseek-flash"),
        (lambda _: httpx.Response(404), 502, "HTTP 404"),
        (lambda _: httpx.Response(401), 502, "API key"),
        (lambda _: httpx.Response(429), 429, "rate-limiting"),
        (lambda _: httpx.Response(200, text="private upstream detail"), 502, "readable stream"),
    ]:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(read_events(httpx.MockTransport(handler)))
        assert exc.value.status_code == code
        assert hint in exc.value.detail and "private upstream" not in exc.value.detail

    events = asyncio.run(read_events(httpx.MockTransport(lambda _: httpx.Response(
        200, headers={"Content-Type": "text/event-stream"},
        text=provider_delta(content="Already received.") + "data: private upstream detail\n\n",
    ))))
    assert events[1] == {"type": "delta", "content": "Already received."}
    assert events[-1]["type"] == "error" and "private upstream" not in events[-1]["detail"]
