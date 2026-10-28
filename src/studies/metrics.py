"""Métricas do dashboard. Funções puras sobre o DataFrame de Answers (exceto as que consultam o banco)."""
import math
import sqlite3
from datetime import datetime

import pandas as pd

CONFIDENCE_ORDER = ["confident", "educated_guess", "guess"]
UNMARKED = "unmarked"
CONSISTENCY_LEVELS = ["stable", "learned", "unstable", "failing", "few_data"]
GRANULARITIES = {
    "overall": None,
    "topic": "topic",
    "course": "course",
    "exam": "exam_title",
    "section": "section",
    "question": "question_id",
}


def local_tz():
    return datetime.now().astimezone().tzinfo


def answers_df(conn: sqlite3.Connection, certification_id: int) -> pd.DataFrame:
    """Uma linha por Answer da Certification, em ordem cronológica, em horário local."""
    df = pd.read_sql_query(
        """
        SELECT a.id AS answer_id, a.attempt_id, at.kind, at.mode, at.state, at.exam_id,
               c.slug || ' / ' || COALESCE(e.label, e.title, '') AS exam_title, c.slug AS course,
               s.name AS section, q.id AS question_id, a.question_revision_id,
               COALESCE((SELECT t.topic FROM revision_topic t WHERE t.question_revision_id = a.question_revision_id
                         AND t.is_primary = 1), 'Sem tema') AS topic,
               a.is_correct, a.confidence, a.time_seconds, a.answered_at
        FROM answer a
        JOIN attempt at ON at.id = a.attempt_id
        JOIN question_revision r ON r.id = a.question_revision_id
        JOIN question q ON q.id = r.question_id
        JOIN course c ON c.id = q.course_id
        JOIN section s ON s.id = r.section_id
        LEFT JOIN exam e ON e.id = q.exam_id
        WHERE c.certification_id = ?
        ORDER BY a.answered_at, a.id
        """,
        conn,
        params=(certification_id,),
    )
    df["answered_at"] = pd.to_datetime(df["answered_at"], utc=True).dt.tz_convert(local_tz())
    df["is_correct"] = df["is_correct"].astype(bool)
    df["is_first_time"] = ~df.duplicated("question_id")  # calculado no histórico todo, antes de qualquer janela
    return df


def window_bounds(preset: str, df: pd.DataFrame, custom: tuple | None = None, now: pd.Timestamp | None = None):
    """(início, fim) da janela. 'all' cobre todo o histórico; 'custom' recebe duas datas."""
    now = now or pd.Timestamp.now(tz=df["answered_at"].dt.tz if len(df) else None)
    if preset == "7d":
        return now - pd.Timedelta(days=7), now
    if preset == "30d":
        return now - pd.Timedelta(days=30), now
    if preset == "custom" and custom:
        tz = now.tz
        start = pd.Timestamp(custom[0]).tz_localize(tz)
        end = pd.Timestamp(custom[1]).tz_localize(tz) + pd.Timedelta(days=1)
        return start, end
    if len(df):
        return df["answered_at"].min(), now
    return now, now


def in_window(df: pd.DataFrame, start, end) -> pd.DataFrame:
    return df[(df["answered_at"] >= start) & (df["answered_at"] < end)]


def accuracy(df: pd.DataFrame) -> float | None:
    return float(df["is_correct"].mean()) if len(df) else None


def trend(df_all: pd.DataFrame, start, end) -> dict:
    """Acerto da janela contra a janela anterior de mesmo tamanho."""
    current = accuracy(in_window(df_all, start, end))
    previous = accuracy(in_window(df_all, start - (end - start), start))
    delta = None if current is None or previous is None else current - previous
    return {"current": current, "previous": previous, "delta": delta}


def by_granularity(df: pd.DataFrame, level: str) -> pd.DataFrame:
    col = GRANULARITIES[level]
    if col is None:
        g = pd.DataFrame({"group": ["Geral"], "n": [len(df)], "correct": [int(df["is_correct"].sum())]})
    else:
        g = (df.groupby(col)["is_correct"].agg(n="size", correct="sum").reset_index().rename(columns={col: "group"}))
        g["correct"] = g["correct"].astype(int)
    g["accuracy"] = g["correct"] / g["n"]
    return g.sort_values("accuracy", ascending=False).reset_index(drop=True)


def progression(df: pd.DataFrame, freq: str = "D", rolling: int = 3) -> pd.DataFrame:
    """Acerto por bucket de tempo (D ou W) com média móvel ponderada pelo número de Answers,
    separado em inéditas (primeira vez que a Question foi respondida) e repetições."""
    if df.empty:
        return pd.DataFrame(columns=["bucket", "segment", "n", "correct", "accuracy", "rolling"])
    d = df.assign(bucket=df["answered_at"].dt.tz_localize(None).dt.to_period(freq).dt.start_time,
                  segment=df["is_first_time"].map({True: "Inéditas", False: "Repetições"}))
    out = []
    for segment, g in d.groupby("segment"):
        t = g.groupby("bucket")["is_correct"].agg(n="size", correct="sum")
        t = t.reindex(pd.date_range(t.index.min(), t.index.max(), freq=freq)).fillna(0)
        t["accuracy"] = (t["correct"] / t["n"]).where(t["n"] > 0)
        window_n = t["n"].rolling(rolling, min_periods=1).sum()
        # só buckets com Answers recebem ponto; buckets vazios entram na janela mas não são plotados
        t["rolling"] = (t["correct"].rolling(rolling, min_periods=1).sum() / window_n).where(t["n"] > 0)
        t["segment"] = segment
        out.append(t.rename_axis("bucket").reset_index())
    return pd.concat(out, ignore_index=True)


def best_window(df: pd.DataFrame, freq: str = "W", min_n: int = 10) -> dict | None:
    """Melhor bucket de tempo, ignorando buckets com poucas Answers."""
    if df.empty:
        return None
    d = df.assign(bucket=df["answered_at"].dt.tz_localize(None).dt.to_period(freq).dt.start_time)
    t = d.groupby("bucket")["is_correct"].agg(n="size", correct="sum")
    t = t[t["n"] >= min_n]
    if t.empty:
        return None
    t["accuracy"] = t["correct"] / t["n"]
    best = t.sort_values(["accuracy", "n"], ascending=False).iloc[0]
    return {"bucket": best.name, "accuracy": float(best["accuracy"]), "n": int(best["n"])}


def attempt_scores(conn: sqlite3.Connection, certification_id: int) -> pd.DataFrame:
    """Nota de cada Attempt de Exam finalizado. Review e Drill ficam de fora; puladas não entram no acerto."""
    df = pd.read_sql_query(
        """
        SELECT at.id AS attempt_id, at.mode, at.finished_at, c.slug || ' / ' || COALESCE(e.label, e.title) AS exam_title, at.exam_id,
               (SELECT count(*) FROM attempt_question WHERE attempt_id = at.id) AS total,
               COALESCE(SUM(a.is_correct), 0) AS correct, COUNT(a.id) AS answered
        FROM attempt at
        JOIN exam e ON e.id = at.exam_id JOIN course c ON c.id = e.course_id
        LEFT JOIN answer a ON a.attempt_id = at.id
        WHERE at.kind = 'exam' AND at.state = 'finished' AND c.certification_id = ?
        GROUP BY at.id ORDER BY at.finished_at
        """,
        conn,
        params=(certification_id,),
    )
    df["skipped"] = df["total"] - df["answered"]
    df["score"] = (df["correct"] / df["answered"]).where(df["answered"] > 0)
    df["finished_at"] = pd.to_datetime(df["finished_at"], utc=True).dt.tz_convert(local_tz())
    return df


def best_attempts(scores: pd.DataFrame) -> pd.DataFrame:
    """Melhor Attempt por Exam (empate: o mais recente)."""
    s = scores.dropna(subset=["score"]).sort_values(["score", "finished_at"], ascending=False)
    return s.drop_duplicates("exam_id").sort_values("exam_title").reset_index(drop=True)


def calibration(df: pd.DataFrame) -> pd.DataFrame:
    """Acerto por Confidence. 'Sem marcação' vem à parte e fica fora da calibração."""
    d = df.assign(level=df["confidence"].fillna(UNMARKED))
    t = d.groupby("level")["is_correct"].agg(n="size", correct="sum")
    t = t.reindex(CONFIDENCE_ORDER + [UNMARKED]).dropna().reset_index()
    t["correct"] = t["correct"].astype(int)
    t["n"] = t["n"].astype(int)
    t["accuracy"] = t["correct"] / t["n"]
    t["in_calibration"] = t["level"] != UNMARKED
    return t


def pace(df: pd.DataFrame) -> pd.DataFrame:
    """Questions por dia e tempo por Question (média e mediana, em segundos)."""
    if df.empty:
        return pd.DataFrame(columns=["day", "questions", "mean_seconds", "median_seconds"])
    d = df.assign(day=df["answered_at"].dt.tz_localize(None).dt.normalize())
    t = d.groupby("day").agg(questions=("answer_id", "size"), mean_seconds=("time_seconds", "mean"),
                             median_seconds=("time_seconds", "median"))
    t = t.reindex(pd.date_range(t.index.min(), t.index.max(), freq="D"))
    t["questions"] = t["questions"].fillna(0).astype(int)
    return t.rename_axis("day").reset_index()


def consistency(df: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    """Nível de Consistency por Question, sobre todas as Answers dela em ordem cronológica.
    - few_data: menos de k Answers.
    - stable: as últimas k certas e nenhum erro antes.
    - learned: as últimas k certas e houve erro antes.
    - failing: as últimas k erradas.
    - unstable: o resto (alterna entre acerto e erro)."""
    rows = []
    for qid, g in df.sort_values(["answered_at", "answer_id"]).groupby("question_id"):
        results = g["is_correct"].tolist()
        last = results[-k:]
        if len(results) < k:
            level = "few_data"
        elif all(last):
            level = "stable" if all(results) else "learned"
        elif not any(last):
            level = "failing"
        else:
            level = "unstable"
        rows.append({"question_id": qid, "level": level, "answers": len(results),
                     "section": g["section"].iloc[-1], "course": g["course"].iloc[-1]})
    return pd.DataFrame(rows, columns=["question_id", "level", "answers", "section", "course"])


def consistency_summary(cons: pd.DataFrame, by: str | None = "section") -> pd.DataFrame:
    """Percentual de Questions por nível, no total ou por Section."""
    if cons.empty:
        return pd.DataFrame(columns=["group", "level", "questions", "share"])
    col = cons["section"] if by == "section" else pd.Series("Certification", index=cons.index)
    t = cons.assign(group=col).groupby(["group", "level"]).size().rename("questions").reset_index()
    t["share"] = t["questions"] / t.groupby("group")["questions"].transform("sum")
    return t


def most_wrong(df: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    t = df.groupby("question_id").agg(answers=("is_correct", "size"), wrong=("is_correct", lambda s: int((~s).sum())),
                                      section=("section", "last"), course=("course", "last"))
    t = t[t["wrong"] > 0]
    t["error_rate"] = t["wrong"] / t["answers"]
    return t.sort_values(["wrong", "error_rate"], ascending=False).head(top).reset_index()


def lucky_guesses(df: pd.DataFrame) -> pd.DataFrame:
    """Questions acertadas com Confidence 'chute': acerto que ainda não é conhecimento."""
    d = df[df["is_correct"] & (df["confidence"] == "guess")]
    t = d.groupby("question_id").agg(times=("answer_id", "size"), section=("section", "last"), course=("course", "last"))
    return t.sort_values("times", ascending=False).reset_index()


def topic_graph(conn: sqlite3.Connection, certification_id: int, df: pd.DataFrame | None = None) -> dict:
    """Temas e arestas (pares de temas citados juntos) usando a revisão mais recente de cada Question.
    Devolve {'nodes': DataFrame(topic, primary, total), 'edges': DataFrame(a, b, questions[, answers, accuracy])}.
    Com `df` (Answers), as arestas ganham o acerto nas Questions que ligam os dois temas."""
    from studies import topics as topics_mod

    rows = conn.execute(
        """
        SELECT q.id AS question_id, t.topic, t.is_primary
        FROM question q JOIN course c ON c.id = q.course_id
        JOIN revision_topic t ON t.question_revision_id =
             (SELECT r.id FROM question_revision r WHERE r.question_id = q.id ORDER BY r.last_seen_at DESC, r.id DESC LIMIT 1)
        WHERE c.certification_id = ?
        """,
        (certification_id,),
    ).fetchall()
    by_question: dict[int, list[str]] = {}
    primary: dict[str, int] = {}
    total: dict[str, int] = {}
    for r in rows:
        by_question.setdefault(r["question_id"], []).append(r["topic"])
        total[r["topic"]] = total.get(r["topic"], 0) + 1
        primary[r["topic"]] = primary.get(r["topic"], 0) + r["is_primary"]
    nodes = pd.DataFrame({"topic": list(total), "primary": [primary[t] for t in total], "total": list(total.values())})
    nodes = nodes.sort_values(["primary", "topic"], ascending=[False, True]).reset_index(drop=True)
    pairs = topics_mod.edges(by_question)
    edges = pd.DataFrame([(a, b, n) for (a, b), n in pairs.items()], columns=["a", "b", "questions"])
    if df is not None and not edges.empty:
        acc = []
        for a, b, _ in edges.itertuples(index=False):
            qs = [q for q, ts in by_question.items() if a in ts and b in ts]
            sub = df[df["question_id"].isin(qs)]
            acc.append((len(sub), accuracy(sub)))
        edges["answers"] = [x[0] for x in acc]
        edges["accuracy"] = [x[1] for x in acc]
    return {"nodes": nodes, "edges": edges.sort_values("questions", ascending=False).reset_index(drop=True)}


def neighbors(edges: pd.DataFrame, topic: str) -> pd.DataFrame:
    """Temas ligados a `topic`, do mais ao menos citado junto."""
    m = edges[(edges["a"] == topic) | (edges["b"] == topic)].copy()
    m["neighbor"] = m["a"].where(m["b"] == topic, m["b"])
    return m.drop(columns=["a", "b"]).sort_values("questions", ascending=False).reset_index(drop=True)


# A AWS reporta nota escalada (mínimo 750 de 1000) e não publica o mapeamento para acertos brutos.
# 75% é a aproximação usada aqui; o exame tem 65 Questions pontuadas (mais 10 não pontuadas, não identificadas).
PASS_RATIO = 0.75
READY_RATIO = 0.80
READY_ATTEMPTS = 3


def pass_progress(correct: int, wrong: int, total: int, pass_ratio: float = PASS_RATIO) -> dict:
    """Situação de um Attempt frente à aprovação. Puladas contam como erradas, como na prova real.
    'passed'/'failed' são matemáticos: com as Questions restantes não há mais como mudar o resultado."""
    needed = math.ceil(pass_ratio * total - 1e-9)
    remaining = total - correct - wrong
    answered = correct + wrong
    return {
        "needed": needed,
        "remaining": remaining,
        "accuracy": correct / answered if answered else None,
        "still_needed": max(needed - correct, 0),
        "passed": correct >= needed,
        "failed": correct + remaining < needed,
    }


def streaks(results: list[bool]) -> dict:
    """Sequências de acertos e de erros numa lista cronológica de resultados.
    'current' é a sequência em andamento (tipo 'correct' ou 'wrong')."""
    longest = {True: 0, False: 0}
    run = 0
    prev = None
    for r in results:
        run = run + 1 if r == prev else 1
        prev = r
        longest[r] = max(longest[r], run)
    return {"current": run if results else 0, "current_kind": None if not results else ("correct" if prev else "wrong"),
            "longest_correct": longest[True], "longest_wrong": longest[False]}


def readiness(scores: pd.DataFrame, ratio: float = READY_RATIO, n: int = READY_ATTEMPTS) -> dict:
    """Pronto para a certificação: os últimos `n` Attempts de Exam finalizados com nota >= `ratio`.
    'streak' é quantos Attempts seguidos, contando do mais recente, estão na meta (limitado a `n`)."""
    s = scores.dropna(subset=["score"]).sort_values("finished_at")["score"].tolist()
    streak = 0
    for v in reversed(s):
        if v < ratio:
            break
        streak += 1
    last = s[-n:]
    return {"ready": len(s) >= n and streak >= n, "streak": min(streak, n), "needed": n, "attempts": len(s),
            "recent_mean": sum(last) / len(last) if last else None}
