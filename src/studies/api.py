"""API HTTP sobre attempts, selection e metrics, para o front React.
Cada rota é uma casca fina: a lógica continua nesses módulos. Toda rota (menos /health) exige
`Authorization: Bearer <API_TOKEN>`, porque a API é pública e o conteúdo da Udemy é privado."""
import hmac
import json
import os
import threading
import time
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from studies import attempts, metrics, selection
from studies.db import connect


class NewAttempt(BaseModel):
    kind: str = "exam"  # exam | review | drill
    mode: str = "practice"
    shuffle: bool = False
    exam_id: int | None = None  # kind=exam
    certification_id: int | None = None  # review e drill
    filter: str | None = None  # review: um de REVIEW_FILTERS ou "priority" (usa n)
    section_id: int | None = None  # drill por Section
    topic: str | None = None  # drill por tema
    include_secondary: bool = False
    n: int = 20
    pure_random: bool = False


class NewAnswer(BaseModel):
    position: int
    selected: list[str]  # letras como exibidas na tela
    confidence: str | None = None
    reasoning: str | None = None
    time_seconds: float | None = None


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))  # NaN vira null


def create_app(conn=None, token: str | None = None, cors_origins: list[str] | None = None) -> FastAPI:
    token = token or os.environ.get("API_TOKEN")
    if not token:
        raise RuntimeError("API_TOKEN não definido: a API não sobe sem token.")
    lock = threading.Lock()  # a conexão (sqlite3 ou Turso) não é segura entre threads

    @asynccontextmanager
    async def lifespan(app):
        app.state.conn = conn or connect(check_same_thread=False)
        yield

    app = FastAPI(title="Studies API", lifespan=lifespan)
    origins = cors_origins if cors_origins is not None else [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    def auth(authorization: str | None = Header(default=None)):
        sent = (authorization or "").removeprefix("Bearer ")
        if not hmac.compare_digest(sent.encode(), token.encode()):
            raise HTTPException(401, "Token inválido")

    def db():
        with lock:
            yield app.state.conn

    secured = [Depends(auth)]

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/certifications", dependencies=secured)
    def certifications(c=Depends(db)):
        return [dict(r) for r in c.execute("SELECT id, name FROM certification ORDER BY name").fetchall()]

    @app.get("/certifications/{cert_id}/exams", dependencies=secured)
    def exams(cert_id: int, c=Depends(db)):
        rows = c.execute(
            "SELECT e.id, c.slug AS course, COALESCE(e.label, e.title) AS title FROM exam e JOIN course c ON c.id = e.course_id "
            "WHERE c.certification_id = ? ORDER BY c.slug, e.position", (cert_id,)).fetchall()
        return [dict(r) for r in rows]

    @app.get("/attempts", dependencies=secured)
    def running(c=Depends(db)):
        return [{k: r[k] for k in ("id", "kind", "mode", "started_at", "answered", "total", "course_slug", "exam_title")}
                for r in attempts.in_progress_attempts(c)]

    @app.post("/attempts", dependencies=secured, status_code=201)
    def new_attempt(body: NewAttempt, c=Depends(db)):
        if body.kind == "exam":
            if body.exam_id is None:
                raise HTTPException(422, "exam_id é obrigatório")
            return {"attempt_id": attempts.start_attempt(c, body.exam_id, body.mode, body.shuffle)}
        if body.certification_id is None:
            raise HTTPException(422, "certification_id é obrigatório")
        if body.kind == "review" and body.filter == "priority":  # fila de risco do dashboard, na ordem do risco
            revs = selection.priority_questions(c, body.certification_id, body.n)
        elif body.kind == "review":
            if body.filter not in selection.REVIEW_FILTERS:
                raise HTTPException(422, f"filter deve ser um de {list(selection.REVIEW_FILTERS)}")
            revs = selection.review_questions(c, body.certification_id, body.filter)
        elif body.kind == "drill" and body.section_id is not None:
            revs = selection.drill_questions(c, body.certification_id, body.section_id, body.n, body.pure_random)
        elif body.kind == "drill" and body.topic:
            revs = selection.drill_questions_by_topic(c, body.certification_id, body.topic, body.n, body.pure_random,
                                                      body.include_secondary)
        else:
            raise HTTPException(422, "kind inválido, ou drill sem section_id nem topic")
        if not revs:
            raise HTTPException(409, "Nenhuma Question com esse filtro")
        return {"attempt_id": attempts.create_attempt(c, revs, body.kind, body.mode, body.shuffle)}

    def _attempt(c, attempt_id: int):
        row = c.execute("SELECT id, kind, mode, state FROM attempt WHERE id = ?", (attempt_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Attempt não encontrado")
        return row

    def _score(c, attempt_id: int, kind: str, state: str) -> dict:
        s = attempts.summary(c, attempt_id)
        out = {**s, "answered": s["correct"] + s["wrong"], "pass": None}
        if kind == "exam":  # encerrado: puladas viram erros, como na prova real
            wrong = s["wrong"] + (0 if state == "in_progress" else s["skipped"])
            out["pass"] = metrics.pass_progress(s["correct"], wrong, s["total"])
        return out

    @app.get("/attempts/{attempt_id}", dependencies=secured)
    def attempt(attempt_id: int, c=Depends(db)):
        a = _attempt(c, attempt_id)
        rows = attempts.attempt_questions(c, attempt_id)
        return {"id": a["id"], "kind": a["kind"], "mode": a["mode"], "state": a["state"],
                "score": _score(c, attempt_id, a["kind"], a["state"]),
                "map": [{"position": r["position"], "answered": r["selected_json"] is not None,
                         # no Exam mode em andamento o mapa não pode entregar quais acertou
                         "is_correct": bool(r["is_correct"]) if r["selected_json"] is not None and (a["mode"] == "practice" or a["state"] != "in_progress") else None}
                        for r in rows]}

    @app.get("/attempts/{attempt_id}/questions/{position}", dependencies=secured)
    def question(attempt_id: int, position: int, c=Depends(db)):
        a = _attempt(c, attempt_id)
        rows = attempts.attempt_questions(c, attempt_id)
        if not 1 <= position <= len(rows):
            raise HTTPException(404, "Posição inexistente")
        r = rows[position - 1]
        options = json.loads(r["options_json"])
        perm = json.loads(r["permutation_json"]) if r["permutation_json"] else None
        order = perm or list(range(len(options)))
        answered = r["selected_json"] is not None
        reveal = (a["mode"] == "practice" and answered) or a["state"] != "in_progress"
        out = {
            "position": position, "total": len(rows), "state": a["state"], "mode": a["mode"],
            "section": c.execute("SELECT name FROM section WHERE id = ?", (r["section_id"],)).fetchone()[0],
            "prompt_html": r["prompt_html"], "multi": r["assessment_type"] == "multi-select",
            "options": [{"letter": attempts.LETTERS[i], "html": options[order[i]]} for i in range(len(options))],
            "answered": answered,
            "selected": attempts.to_display(json.loads(r["selected_json"]), perm) if answered else [],
            "confidence": r["confidence"], "reveal": reveal,
        }
        if out["multi"]:
            out["choose"] = len(json.loads(r["correct_json"]))
        if reveal:  # gabarito e explicação só saem do servidor quando o modo permite
            out.update(
                correct=attempts.to_display(json.loads(r["correct_json"]), perm), is_correct=bool(r["is_correct"]) if answered else None,
                reasoning=r["reasoning"], explanation_html=r["explanation_html"], ai_reasoning=r["ai_reasoning"],
                topics=[dict(t) for t in c.execute(
                    "SELECT topic, is_primary FROM revision_topic WHERE question_revision_id = ? ORDER BY is_primary DESC, links DESC",
                    (r["id"],)).fetchall()])
        return out

    @app.post("/attempts/{attempt_id}/answers", dependencies=secured)
    def answer(attempt_id: int, body: NewAnswer, c=Depends(db)):
        a = _attempt(c, attempt_id)
        rows = attempts.attempt_questions(c, attempt_id)
        if not 1 <= body.position <= len(rows):
            raise HTTPException(404, "Posição inexistente")
        r = rows[body.position - 1]
        perm = json.loads(r["permutation_json"]) if r["permutation_json"] else None
        try:
            ok = attempts.record_answer(c, attempt_id, r["id"], attempts.to_original(body.selected, perm),
                                        body.confidence, body.reasoning, body.time_seconds)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception as e:  # Practice trava na primeira resposta (UNIQUE)
            raise HTTPException(409, "Question já respondida neste Attempt") from e
        reveal = a["mode"] == "practice"
        return {"is_correct": ok if reveal else None, "score": _score(c, attempt_id, a["kind"], a["state"])}

    @app.post("/attempts/{attempt_id}/finish", dependencies=secured)
    def finish(attempt_id: int, c=Depends(db)):
        _attempt(c, attempt_id)
        attempts.finish_attempt(c, attempt_id)
        a = _attempt(c, attempt_id)
        return {"state": a["state"], "score": _score(c, attempt_id, a["kind"], a["state"])}

    @app.post("/attempts/{attempt_id}/abandon", dependencies=secured)
    def abandon(attempt_id: int, c=Depends(db)):
        _attempt(c, attempt_id)
        attempts.abandon_attempt(c, attempt_id)
        return {"state": "abandoned"}

    @app.get("/dashboard/{cert_id}", dependencies=secured)
    def dashboard(cert_id: int, kinds: list[str] = Query(default=["exam", "review", "drill"]),
                  stable_after: int = Query(3, ge=2, le=6), window: str = Query("all", pattern="^(7d|30d|all)$"),
                  freq: str = Query("D", pattern="^[DW]$"), roll: int = Query(3, ge=1, le=14), c=Depends(db)):
        t0 = time.perf_counter()
        df_all = metrics.answers_df(c, cert_id)
        scores = metrics.attempt_scores(c, cert_id)
        df_kind = df_all[df_all["kind"].isin(kinds)]
        if df_all.empty:  # sem Answers não há fuso para ancorar a janela
            start = end = None
            df = df_kind
        else:
            start, end = metrics.window_bounds(window, df_all)
            df = metrics.in_window(df_kind, start, end)
        cons = metrics.consistency(df_all, stable_after)
        best = metrics.best_attempts(scores)
        has = len(df) > 0
        tr = metrics.trend(df_kind, start, end) if len(df_kind) else {"current": None, "previous": None, "delta": None}
        grans = {g: metrics.by_granularity(df, g) for g in ("course", "exam", "section", "topic")} if has else {}
        if has:
            q = metrics.by_granularity(df, "question")
            grans["question"] = q[q["n"] >= 2].head(30)
        bw = metrics.best_window(df, freq, min_n=10)
        pace = metrics.pace(df)
        tm = df["time_seconds"].dropna() if has else df_all["time_seconds"].iloc[0:0]
        graph = metrics.topic_graph(c, cert_id, df)
        topic_acc = metrics.by_granularity(df, "topic").set_index("group") if has else None
        nodes = graph["nodes"].assign(
            answers=graph["nodes"]["topic"].map(topic_acc["n"]).fillna(0).astype(int) if has else 0,
            accuracy=graph["nodes"]["topic"].map(topic_acc["accuracy"]) if has else None)
        nodes = metrics.topic_impact(nodes)
        has_cons = not cons.empty
        insights = {
            "review_queue": _records(metrics.review_queue(df_all, cons)),
            "weak_neighbors": metrics.weak_neighbors(nodes, graph["edges"]) if len(graph["edges"]) else {},
            "calibration_by_section": _records(metrics.calibration_by_section(df)) if has else [],
            "calibration_trend": _records(metrics.calibration_trend(df, freq)),
            "time": metrics.time_vs_accuracy(df),
            "projection": metrics.projection(scores),
            "mode_effect": _records(metrics.mode_effect(df)) if has else [],
            "retention": _records(metrics.retention(df_all)) if has_cons else [],
            "heatmap": _records(metrics.section_heatmap(df_kind)),
            "reasoning": metrics.reasoning_effect(df) if has else None,
        }
        return {
            "insights": insights,
            "window": None if start is None else {"start": start.isoformat(), "end": end.isoformat()},
            "trend": tr,
            "accuracy_new": metrics.accuracy(df[df["is_first_time"]]) if has else None,
            "accuracy_repeat": metrics.accuracy(df[~df["is_first_time"]]) if has else None,
            "progression": _records(metrics.progression(df, freq, roll)),
            "by": {g: _records(t) for g, t in grans.items()},
            "best_window": None if bw is None else {**bw, "bucket": bw["bucket"].isoformat()},
            "pace": {"days": _records(pace), "median_seconds": None if tm.empty else float(tm.median()),
                     "mean_seconds": None if tm.empty else float(tm.mean())},
            "consistency_by_section": _records(metrics.consistency_summary(cons, "section")),
            "topics": {"nodes": _records(nodes), "edges": _records(graph["edges"])},
            "most_wrong": _records(metrics.most_wrong(df)) if has else [],
            "lucky_guesses": _records(metrics.lucky_guesses(df)) if has else [],
            "answers": len(df), "accuracy": metrics.accuracy(df),
            "readiness": metrics.readiness(scores), "streaks": metrics.streaks(df["is_correct"].tolist()),
            "scores": _records(scores[["attempt_id", "exam_title", "mode", "score", "answered", "skipped", "finished_at"]]),
            "best_per_exam": _records(best[["exam_title", "score", "mode", "finished_at"]]),
            "calibration": _records(metrics.calibration(df)) if len(df) else [],
            "consistency": _records(metrics.consistency_summary(cons, None)),
            "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        }

    return app


def app_from_env() -> FastAPI:
    """`uvicorn studies.api:app_from_env --factory`"""
    return create_app()
