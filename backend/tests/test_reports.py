import asyncio
import json
from copy import deepcopy
from itertools import combinations

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.schemas.analysis import Structure
from app.services import link_prediction
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
    # The forecast uses a different k from the submitted S12 maximum core.
    clique = ["0", "14", "16", "2", "49"]
    connections = [(u, v, 0.8) for u, v in combinations(clique, 2)]
    connections += [(node, "21", 0.55) for node in clique if node != "2"]
    connections += [(node, "29", 0.5) for node in clique if node != "2"]

    def predict(*args, horizon):
        assert horizon == 1
        return {
            "model_version": "test-zebra",
            "pairs": [
                {"u": u, "v": v, "probability": probability, "currently_connected": False}
                for u, v, probability in connections
            ],
        }

    def score(scope, request, models_dir):
        assert request.snapshot_id == "S12" and request.top_r is None
        return {
            "model_version": "test-slade", "snapshot_id": "S12",
            "accounts": [
                {"account_id": "12", "rank": 8, "score": 0.4321},
                {"account_id": "49", "rank": 13, "score": 0.1234},
                {"account_id": "2", "rank": 1, "score": 0.9},
            ],
        }

    monkeypatch.setattr(link_prediction, "full_network_prediction", predict)
    monkeypatch.setattr(evidence, "score_accounts", score)
    future_query = dict(account="49", k=4, model="zebra", threshold=0.5, horizon=1)
    forecast = query("link-prediction/community", **future_query)
    body = dict(ctx, history=ref(historical), current=dict(ref(current), risk_model_version="test-slade"),
                future=dict(ctx, **future_query, target_snapshot=forecast["target_snapshot"],
                            model_version=forecast["model_version"], result_fingerprint=forecast["result_fingerprint"]))
    return application, body, forecast, Structure(**historical), Structure(**current)


def test_report_verifies_submitted_results_before_one_provider_call(submitted_report):
    application, body, forecast, history, current = submitted_report
    client = TestClient(application)
    calls = []
    first = "The submitted selections share 13 of the 18 historical members.〔C01〕"
    second = "\n\nNode N001 has a current SLADE score of 0.1234."

    def completion(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert payload["stream"] is True and "response_format" not in payload
        assert payload["thinking"] == {"type": "enabled"}
        facts = json.loads(payload["messages"][1]["content"])
        records = {row["id"]: row for row in facts["evidence"]}
        assert set(records) == {"H01", "C01", "C02", "P01"}
        h, c, risk, p = (records[key] for key in ("H01", "C01", "C02", "P01"))
        assert (h["method"], h["analysis_window"], h["member_count"], h["k"]) == ("OTCD", "S10–S11", 18, 7)
        assert [row["min_internal_degree"] for row in h["min_internal_degree_by_window"]] == [5, 2, 7]
        assert (c["maximum_core_order"], c["member_count"]) == (7, 30)
        assert "query_node" not in c and "query_node" not in h
        assert c["change_from_history"] == {"retained": 13, "added": 17, "exited": 5, "net_change": 12, "retention_rate": 0.7222}
        assert (p["target_snapshot"], p["k"], p["predicted_member_count"], p["members_in_all_three"]) == ("S13", 4, 6, 3)
        assert p["change_from_current"] == {"retained": 3, "added": 3, "exited": 27, "net_change": -24, "retention_rate": 0.1}
        assert (risk["snapshot"], risk["scored_members"], risk["unscored_members"]) == ("S12", 2, 28)
        assert risk["mean"] == risk["median"] == round((0.4321 + 0.1234) / 2, 4)
        assert risk["scored_members_in_global_top_10"] == 1
        top, other = risk["highest_scoring_members"]
        assert (top["global_rank"], top["in_submitted_history"], top["in_submitted_prediction"]) == (8, False, False)
        assert other["node"] == p["query_node"] and other["in_submitted_prediction"]
        for field in ("threshold", "epsilon", "prediction_status", "forecast_outcome", "history_length"):
            assert field not in payload["messages"][1]["content"]
        return httpx.Response(
            200, headers={"Content-Type": "text/event-stream"},
            text=(
                ": keep-alive\n\n" + provider_delta(role="assistant")
                + provider_delta(reasoning_content="Thinking about the evidence.", content=None)
                + provider_delta(reasoning_content="Checking the overlap.", content=first) + provider_delta(content=second)
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
    events = [json.loads(line) for line in report.iter_lines()]
    labels = events[0]["node_labels"]
    assert events[0]["type"] == "start" and labels["N001"] == forecast["account"]
    supplied = json.loads(json.loads(calls[0].content)["messages"][1]["content"])
    groups = supplied["membership_groups"]
    for stage, expected in (("history", history.members), ("current", current.members), ("predicted", forecast["members"])):
        assert {labels[node] for g in groups if stage in g["stages"] for node in g["nodes"]} == set(expected)
    assert events[1:] == [
        {"type": "thinking", "content": "Thinking about the evidence."},
        {"type": "thinking", "content": "Checking the overlap."},
        {"type": "delta", "content": first},
        {"type": "delta", "content": second},
        {"type": "done"},
    ]


def test_report_and_follow_up_use_only_submitted_stages(submitted_report):
    application, body, forecast, history, _ = submitted_report
    client = TestClient(application)
    captured = []

    def completion(request):
        messages = json.loads(request.content)["messages"]
        captured.append((messages[0]["content"], json.loads(messages[1]["content"])))
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                              text=provider_delta(content="Analysis.") + "data: [DONE]\n\n")

    application.state.report_client = ReportClient("https://provider.invalid", "test", "test", httpx.MockTransport(completion))
    stage_ids = {"history": {"H01"}, "current": {"C01", "C02"}, "future": {"P01"}}
    context = {key: value for key, value in body.items() if key not in stage_ids}
    follow_up = {"report_content": "Analysis.", "question": "Which members?"}
    for size in range(4):
        for selected in combinations(stage_ids, size):
            request = {**context, **{key: body[key] for key in selected}}
            first = client.post("/api/reports/generate", json=request)
            follow = client.post("/api/reports/follow-up", json={**request, **follow_up})
            if not selected:
                assert first.status_code == follow.status_code == 422 and not captured
                continue
            assert first.status_code == follow.status_code == 200
            (prompt, facts), (_, follow_facts) = captured[-2:]
            assert facts == follow_facts
            assert prompt.count("- **") == size
            records = {record["id"]: record for record in facts["evidence"]}
            assert records.keys() == set.union(*(stage_ids[stage] for stage in selected))
            if "C02" in records:
                member = records["C02"]["highest_scoring_members"][0]
                assert ("in_submitted_history" in member) == ("history" in selected)
                assert ("in_submitted_prediction" in member) == ("future" in selected)
            if selected == ("history", "future"):
                retained = len(set(history.members) & set(forecast["members"]))
                assert records["P01"]["change_from_history"]["retained"] == retained
                assert "change_from_current" not in records["P01"]
                assert "historical selection" in prompt
            if selected == ("future",):
                assert "Predicted community" in prompt
                assert not any(key.startswith("change_from_") for key in records["P01"])


def test_disjoint_selections_empty_prediction_and_missing_scores(submitted_report):
    _, _, forecast, history, current = submitted_report
    history = history.model_copy(update={"members": ["h"]})
    current = current.model_copy(update={"members": ["c"]})
    for members, scored_pairs in ((["f"], 1), ([], 1), ([], 0)):
        result = {**forecast, "members": members, "scored_pair_count": scored_pairs}
        facts = collect_facts(history, current, None, result)
        records = {row["id"]: row for row in facts.values["evidence"]}
        assert records["C01"]["change_from_history"] == {
            "retained": 0, "added": 1, "exited": 1, "net_change": 0, "retention_rate": 0.0,
        }
        risk, prediction = records["C02"], records["P01"]
        assert risk["scored_members"] == 0 and risk["unscored_members"] == 1
        assert "evidence_gap" in risk and "mean" not in risk
        if scored_pairs:
            assert prediction["members_in_all_three"] == 0
            assert prediction["predicted_member_count"] == len(members)
            assert prediction["change_from_current"] == {
                "retained": 0, "added": len(members), "exited": 1,
                "net_change": len(members) - 1, "retention_rate": 0.0,
            }
        else:
            assert "evidence_gap" in prediction and "change_from_current" not in prediction
            assert "members_in_all_three" not in prediction and "predicted_member_count" not in prediction


def test_follow_ups_send_the_original_report_and_prior_turns(submitted_report):
    application, body, forecast, _, _ = submitted_report
    client = TestClient(application)
    calls = []
    report_content = "The two selections share 13 members, including N001."
    answers = ["13 人属于同一组。", "其中 3 人预计仍在 S13。"]
    initial_prompt = f"Compare vertex {forecast['account']} across the three stages."

    def completion(request):
        payload = json.loads(request.content)
        assert payload["stream"] and payload["thinking"] == {"type": "enabled"}
        messages = payload["messages"]
        supplied = json.loads(messages[1]["content"])
        assert supplied["initial_prompt"] == "Compare vertex N001 across the three stages."
        answer = (report_content, *answers)[len(calls)]
        calls.append(messages)
        return httpx.Response(
            200, headers={"Content-Type": "text/event-stream"},
            text=provider_delta(content=answer) + "data: [DONE]\n\n",
        )

    application.state.report_client = ReportClient(
        "https://provider.invalid", "test", "deepseek-flash", httpx.MockTransport(completion),
    )
    question = f"节点{forecast['account']}所在的这一组有 13 人吗？"
    follow_up = dict(body, initial_prompt=initial_prompt, report_content=report_content, turns=[], question=question)
    path = "/api/reports/follow-up"

    stale = deepcopy(follow_up)
    stale["future"]["result_fingerprint"] = "changed"
    assert client.post(path, json=stale).status_code == 409
    assert client.post(path, json={**follow_up, "question": "  "}).status_code == 422
    assert not calls

    initial = client.post("/api/reports/generate", json={**body, "initial_prompt": initial_prompt})
    assert initial.status_code == 200
    assert [json.loads(line) for line in initial.iter_lines()][1]["content"] == report_content

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
    assert len(calls) == 3
    assert calls[0][1] == calls[1][1] == calls[2][1]
    assert calls[2][2:] == [
        {"role": "assistant", "content": report_content},
        {"role": "user", "content": "节点N001所在的这一组有 13 人吗？"},
        {"role": "assistant", "content": answers[0]},
        {"role": "user", "content": next_question},
    ]
    assert calls[1] == calls[2][:4]


def test_first_message_supplies_the_analysts_request_with_verified_evidence(submitted_report):
    application, body, forecast, _, _ = submitted_report
    client = TestClient(application)
    supplied = []
    context = {key: body[key] for key in ("dataset_id", "dataset_version", "observed_until")}
    selected = client.post("/api/queries/local-core", json={
        **context, "algorithm": "tccs", "account": "14", "k": 7, "start_snapshot_id": "S10",
    }).json()["structures"][0]
    historical = client.post("/api/patterns/mine", json={
        **context, "pattern": "periodic", "account": "49", "k": 4, "epsilon": 1.0,
    }).json()["structures"][0]
    body = {
        **body, "history": {key: historical[key] for key in body["history"]},
        "current": {**{key: selected[key] for key in body["current"] if key in selected}, "risk_model_version": "test-slade"},
    }

    def completion(request):
        supplied.append(json.loads(json.loads(request.content)["messages"][1]["content"]))
        return httpx.Response(
            200, headers={"Content-Type": "text/event-stream"},
            text=provider_delta(content="Report for the submitted community.") + "data: [DONE]\n\n",
        )

    application.state.report_client = ReportClient("https://provider.invalid", "test", "test", httpx.MockTransport(completion))
    prompt = f"Compare vertex {forecast['account']} in S12 and S13."
    path = "/api/reports/generate"
    assert client.post(path, json={**body, "initial_prompt": "  "}).status_code == 422
    response = client.post(path, json={**body, "initial_prompt": prompt})
    assert response.status_code == 200 and len(supplied) == 1
    records = {row["id"]: row for row in supplied[0]["evidence"]}
    h, c, p = (records[key] for key in ("H01", "C01", "P01"))
    assert supplied[0]["initial_prompt"] == f"Compare vertex {p['query_node']} in S12 and S13."
    assert "epsilon" not in json.dumps(supplied[0])
    assert h["analysis_window"] == "S01–S11" and h["community_present_snapshots"] == ["S02", "S04", "S06"]
    assert c["window"] == "S10–S12" and c["member_count"] == len(selected["members"])
    assert (h["k"], c["k"], p["k"]) == (4, 7, 4)
    assert c["query_node"] != h["query_node"] == p["query_node"]
    assert [json.loads(line)["type"] for line in response.iter_lines()] == ["start", "delta", "done"]


def test_provider_errors_never_return_upstream_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", " ")
    assert ReportClient.from_env(tmp_path / ".env").model == "deepseek-flash"

    facts = ReportFacts()
    facts.values["node"] = facts.alias("private@example.org")
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
