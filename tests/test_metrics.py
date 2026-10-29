import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from studies import attempts, metrics
from studies.db import connect
from studies.normalize import load_certification

CERT = Path("data/certifications/aws-certified-gen-ai-developer")
TZ = "America/Sao_Paulo"


def make_df(rows):
    """rows: (question_id, dia, is_correct, confidence, section, first_time)"""
    df = pd.DataFrame(rows, columns=["question_id", "day", "is_correct", "confidence", "section"])
    df["answered_at"] = pd.to_datetime(df["day"]).dt.tz_localize(TZ) + pd.Timedelta(hours=12)
    df["answer_id"] = range(len(df))
    df["course"] = "c"
    df["time_seconds"] = 30.0
    df["is_first_time"] = ~df.duplicated("question_id")
    return df


def test_trend_compares_with_previous_window():
    df = make_df([(1, "2026-10-01", False, None, "S"), (2, "2026-10-02", False, None, "S"),
                  (3, "2026-10-10", True, None, "S"), (4, "2026-10-11", True, None, "S"),
                  (5, "2026-10-12", False, None, "S"), (6, "2026-10-13", True, None, "S")])
    start, end = pd.Timestamp("2026-10-08", tz=TZ), pd.Timestamp("2026-10-15", tz=TZ)
    t = metrics.trend(df, start, end)
    assert t["current"] == 0.75 and t["previous"] == 0.0 and t["delta"] == 0.75
    assert metrics.trend(df, pd.Timestamp("2026-09-01", tz=TZ), pd.Timestamp("2026-09-10", tz=TZ))["current"] is None


def test_first_time_flag_uses_whole_history_not_the_window():
    df = make_df([(1, "2026-10-01", False, None, "S"), (1, "2026-10-10", True, None, "S")])
    windowed = metrics.in_window(df, pd.Timestamp("2026-10-05", tz=TZ), pd.Timestamp("2026-10-20", tz=TZ))
    assert windowed["is_first_time"].tolist() == [False]
    prog = metrics.progression(windowed, "D")
    assert set(prog["segment"]) == {"Repetições"}


def test_progression_splits_segments_and_rolls():
    df = make_df([(1, "2026-10-01", True, None, "S"), (2, "2026-10-01", False, None, "S"),
                  (1, "2026-10-02", True, None, "S"), (3, "2026-10-03", True, None, "S")])
    p = metrics.progression(df, "D", rolling=2)
    new = p[p["segment"] == "Inéditas"].set_index("bucket")
    assert new.loc["2026-10-01", "accuracy"] == 0.5
    assert new.loc["2026-10-03", "rolling"] == pytest.approx(1.0)  # dia 2 sem inéditas + dia 3 certa
    assert new.loc["2026-10-02", "n"] == 0
    rep = p[p["segment"] == "Repetições"]
    assert rep["n"].sum() == 1


def test_by_granularity():
    df = make_df([(1, "2026-10-01", True, None, "A"), (2, "2026-10-01", False, None, "A"), (3, "2026-10-01", True, None, "B")])
    sec = metrics.by_granularity(df, "section").set_index("group")
    assert sec.loc["A", "accuracy"] == 0.5 and sec.loc["B", "n"] == 1
    assert metrics.by_granularity(df, "overall")["accuracy"].iloc[0] == pytest.approx(2 / 3)
    assert len(metrics.by_granularity(df, "question")) == 3


def test_best_window_ignores_tiny_buckets():
    rows = [(i, "2026-10-05", i % 2 == 0, None, "S") for i in range(10)]        # semana A: 50% (n=10)
    rows += [(100 + i, "2026-10-12", i < 8, None, "S") for i in range(10)]      # semana B: 80% (n=10)
    rows += [(200, "2026-10-19", True, None, "S")]                               # semana C: 100% mas n=1
    best = metrics.best_window(make_df(rows), "W", min_n=10)
    assert best["accuracy"] == 0.8 and best["n"] == 10
    assert metrics.best_window(make_df(rows[:3]), "W", min_n=10) is None


def test_calibration_puts_unmarked_aside():
    df = make_df([(1, "2026-10-01", True, "confident", "S"), (2, "2026-10-01", True, "confident", "S"),
                  (3, "2026-10-01", False, "guess", "S"), (4, "2026-10-01", True, None, "S")])
    c = metrics.calibration(df).set_index("level")
    assert c.loc["confident", "accuracy"] == 1.0 and c.loc["guess", "accuracy"] == 0.0
    assert not c.loc["unmarked", "in_calibration"] and c.loc["confident", "in_calibration"]
    assert "educated_guess" not in c.index


@pytest.mark.parametrize("results,level", [
    ([True, True, True], "stable"),
    ([False, True, True, True], "learned"),
    ([False, False, False], "failing"),
    ([True, False, True], "unstable"),
    ([True, True, False], "unstable"),
    ([True, True], "few_data"),
    ([False, False, True, True, True], "learned"),
])
def test_consistency_levels(results, level):
    rows = [(1, f"2026-10-{i + 1:02d}", r, None, "S") for i, r in enumerate(results)]
    assert metrics.consistency(make_df(rows), k=3)["level"].tolist() == [level]


def test_consistency_threshold_is_configurable_and_summary_shares():
    rows = [(1, f"2026-10-0{i + 1}", True, None, "A") for i in range(2)] + [(2, "2026-10-01", False, None, "A")]
    df = make_df(rows)
    assert metrics.consistency(df, k=3)["level"].tolist() == ["few_data", "few_data"]
    cons = metrics.consistency(df, k=2)
    assert dict(zip(cons["question_id"], cons["level"])) == {1: "stable", 2: "few_data"}
    s = metrics.consistency_summary(cons, "section")
    assert s["share"].sum() == pytest.approx(1.0)
    assert metrics.consistency_summary(pd.DataFrame(columns=cons.columns)).empty


def test_pace_fills_empty_days_and_most_wrong_and_lucky():
    df = make_df([(1, "2026-10-01", False, "guess", "S"), (1, "2026-10-03", False, None, "S"),
                  (2, "2026-10-03", True, "guess", "S")])
    p = metrics.pace(df)
    assert p["questions"].tolist() == [1, 0, 2]
    mw = metrics.most_wrong(df)
    assert mw["question_id"].tolist() == [1] and mw["wrong"].iloc[0] == 2
    assert metrics.lucky_guesses(df)["question_id"].tolist() == [2]


def test_window_bounds_presets():
    df = make_df([(1, "2026-10-01", True, None, "S")])
    now = pd.Timestamp("2026-10-20", tz=TZ)
    assert metrics.window_bounds("7d", df, now=now)[0] == now - pd.Timedelta(days=7)
    assert metrics.window_bounds("all", df, now=now)[0] == df["answered_at"].min()
    s, e = metrics.window_bounds("custom", df, (pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-03")), now=now)
    assert e - s == pd.Timedelta(days=3)


@pytest.fixture
def conn(tmp_path):
    dest = tmp_path / CERT.name
    shutil.copytree(CERT, dest)
    c = connect(":memory:")
    load_certification(c, dest)
    return c


def test_db_queries_exclude_review_drill_from_attempt_scores(conn):
    cert = conn.execute("SELECT id FROM certification").fetchone()[0]
    exam = 7310851
    a1 = attempts.start_attempt(conn, exam)
    rows = attempts.attempt_questions(conn, a1)
    for r in rows[:4]:
        c = json.loads(r["correct_json"])
        attempts.record_answer(conn, a1, r["id"], c if r["position"] <= 3 else ["a" if c != ["a"] else "b"], "confident")
    attempts.finish_attempt(conn, a1)
    drill = attempts.create_attempt(conn, [rows[0]["id"]], "drill")
    attempts.record_answer(conn, drill, rows[0]["id"], json.loads(rows[0]["correct_json"]))
    attempts.finish_attempt(conn, drill)
    abandoned = attempts.start_attempt(conn, exam)
    attempts.abandon_attempt(conn, abandoned)

    scores = metrics.attempt_scores(conn, cert)
    assert len(scores) == 1
    s = scores.iloc[0]
    assert (s["correct"], s["answered"], s["skipped"], s["score"]) == (3, 4, 71, 0.75)
    assert len(metrics.best_attempts(scores)) == 1

    df = metrics.answers_df(conn, cert)
    assert len(df) == 5 and df["kind"].tolist().count("drill") == 1
    assert df["is_first_time"].sum() == 4  # a Answer do Drill repete uma Question já respondida


def test_topic_graph_edges_and_neighbors(conn):
    cert = conn.execute("SELECT id FROM certification").fetchone()[0]
    g = metrics.topic_graph(conn, cert)
    nodes, edges = g["nodes"], g["edges"]
    assert nodes["primary"].sum() + 30 >= 940  # quase toda Question tem exatamente um principal
    assert (edges["a"] < edges["b"]).all() and edges["questions"].is_monotonic_decreasing
    top = edges.iloc[0]
    nb = metrics.neighbors(edges, top["a"])
    assert top["b"] in set(nb["neighbor"]) and top["a"] not in set(nb["neighbor"])
    assert nb["questions"].is_monotonic_decreasing


def test_topic_graph_accuracy_on_edges(conn):
    cert = conn.execute("SELECT id FROM certification").fetchone()[0]
    edges = metrics.topic_graph(conn, cert)["edges"]
    a, b = edges.iloc[0]["a"], edges.iloc[0]["b"]
    rows = conn.execute(
        "SELECT r.id FROM question_revision r JOIN revision_topic x ON x.question_revision_id=r.id AND x.topic=? "
        "JOIN revision_topic y ON y.question_revision_id=r.id AND y.topic=?", (a, b)).fetchall()
    a1 = attempts.create_attempt(conn, [r[0] for r in rows[:4]], "drill")
    for i, r in enumerate(attempts.attempt_questions(conn, a1)):
        c = json.loads(r["correct_json"])
        attempts.record_answer(conn, a1, r["id"], c if i < 3 else ["a" if c != ["a"] else "b"])
    attempts.finish_attempt(conn, a1)
    df = metrics.answers_df(conn, cert)
    edges2 = metrics.topic_graph(conn, cert, df)["edges"]
    row = edges2[(edges2["a"] == a) & (edges2["b"] == b)].iloc[0]
    assert row["answers"] == 4 and row["accuracy"] == 0.75
    assert metrics.by_granularity(df, "topic")["n"].sum() == 4


def test_pass_progress_math():
    p = metrics.pass_progress(correct=30, wrong=5, total=65)
    assert p["needed"] == 49 and p["remaining"] == 30 and p["still_needed"] == 19
    assert p["accuracy"] == pytest.approx(30 / 35) and not p["passed"] and not p["failed"]
    assert metrics.pass_progress(49, 0, 65)["passed"]
    assert metrics.pass_progress(30, 17, 65)["failed"]  # 30 + 18 restantes = 48 < 49
    assert not metrics.pass_progress(30, 16, 65)["failed"]
    assert metrics.pass_progress(0, 0, 65)["accuracy"] is None


def test_streaks():
    s = metrics.streaks([True, True, False, False, False, True, True, True, True])
    assert s == {"current": 4, "current_kind": "correct", "longest_correct": 4, "longest_wrong": 3}
    assert metrics.streaks([False])["current_kind"] == "wrong"
    assert metrics.streaks([])["current"] == 0


def test_readiness_needs_consecutive_recent_attempts():
    def scores(vals):
        return pd.DataFrame({"score": vals, "finished_at": pd.date_range("2026-10-01", periods=len(vals))})
    assert metrics.readiness(scores([0.9, 0.85, 0.8]))["ready"]
    assert not metrics.readiness(scores([0.9, 0.7, 0.85, 0.9]))["ready"]
    r = metrics.readiness(scores([0.5, 0.9, 0.85]))
    assert r["streak"] == 2 and not r["ready"]
    assert not metrics.readiness(scores([0.9, 0.9]))["ready"]


def _df(rows):
    import pandas as pd
    d = pd.DataFrame(rows, columns=["answer_id", "question_id", "is_correct", "confidence", "time_seconds", "answered_at", "mode", "section", "reasoning"])
    d["answered_at"] = pd.to_datetime(d["answered_at"], utc=True)
    d["is_first_time"] = ~d.duplicated("question_id")
    d["course"] = "c"
    return d


def test_insights_basics():
    import pandas as pd
    d = _df([
        (1, 1, False, "confident", 40, "2026-01-01 10:00", "practice", "A", "achei que era X"),
        (2, 1, True, "guess", 90, "2026-01-01 12:00", "exam", "A", ""),
        (3, 1, True, "confident", 20, "2026-01-10 12:00", "exam", "A", ""),
        (4, 2, True, "confident", 200, "2026-01-02 12:00", "exam", "B", ""),
    ])
    cons = metrics.consistency(d, 2)
    q = metrics.review_queue(d, cons)
    assert q["question_id"].tolist() == [1] and q.loc[0, "confident_wrong"] == 1 and q.loc[0, "lucky"] == 1
    r = metrics.retention(d)
    assert r.set_index("label").loc["mesmo dia", "recovered"] == 1.0 and r.set_index("label").loc["7+ dias", "kept"] == 1.0
    t = metrics.time_vs_accuracy(d)
    assert t["median_wrong"] == 40 and sum(b["n"] for b in t["bins"]) == 4
    d.loc[0, "confidence"] = None  # sem Confidence vira null no JSON, nunca NaN
    w = metrics.reasoning_effect(d)["wrong_with_reasoning"]
    assert w[0]["question_id"] == 1 and w[0]["confidence"] is None
    json.dumps(w, allow_nan=False)
    assert set(metrics.mode_effect(d)["mode"]) == {"practice", "exam"}
    assert not metrics.section_heatmap(d).empty and not metrics.calibration_trend(d).empty


def test_projection_needs_three_and_trends_up():
    import pandas as pd
    s = pd.DataFrame({"score": [0.5, 0.6, 0.7], "finished_at": pd.to_datetime(["2026-01-01", "2026-01-08", "2026-01-15"], utc=True)})
    assert metrics.projection(s.head(2)) is None
    p = metrics.projection(s)
    assert round(p["predicted"], 2) == 0.7 and p["eta_days"] == 7 and p["slope_per_week"] > 0.09
