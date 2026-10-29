"""Métricas do dashboard. Funções puras sobre o DataFrame de Answers (exceto as que consultam o banco)."""
import math
import sqlite3
from datetime import datetime

import numpy as np
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
               a.is_correct, a.confidence, a.time_seconds, a.answered_at, COALESCE(TRIM(a.reasoning), '') AS reasoning
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


def study_activity(df: pd.DataFrame, now: pd.Timestamp | None = None, days: int = 14) -> dict:
    """Quanto você está estudando: Questions e tempo por dia, sequência de dias e hoje vs. o mesmo dia da semana passada.
    Usa o histórico todo (qualquer kind); o tempo é a soma de time_seconds das Answers do dia (as sem tempo contam 0)."""
    now = now or pd.Timestamp.now(tz=df["answered_at"].dt.tz if len(df) else None)
    today = now.tz_localize(None).normalize()
    if df.empty:
        return {"today": {"questions": 0, "seconds": 0.0}, "last_week": None, "days": [], "avg_per_day": None,
                "avg_per_active_day": None, "active_days": 0, "streak": {"current": 0, "longest": 0, "today_done": False},
                "week": {"current": 0, "previous": None}}
    d = df.assign(day=df["answered_at"].dt.tz_localize(None).dt.normalize())
    per = d.groupby("day").agg(questions=("answer_id", "size"), seconds=("time_seconds", "sum"))
    first = per.index.min()
    span = pd.date_range(first, max(today, per.index.max()), freq="D")
    per = per.reindex(span, fill_value=0)
    per["seconds"] = per["seconds"].astype(float)
    q, sec = per["questions"], per["seconds"]
    week_ago = today - pd.Timedelta(days=7)

    def sum_days(start, end):  # [start, end] inclusivo
        return int(q[(q.index >= start) & (q.index <= end)].sum())

    active = q > 0
    longest = run = 0
    for a in active:
        run = run + 1 if a else 0
        longest = max(longest, run)
    # A sequência continua viva se hoje ainda não teve estudo mas ontem teve (o dia não acabou).
    end = today if active.get(today, False) else today - pd.Timedelta(days=1)
    current = 0
    while end >= first and active.get(end, False):
        current += 1
        end -= pd.Timedelta(days=1)
    elapsed = per.loc[:today]
    return {
        "today": {"questions": int(q.get(today, 0)), "seconds": float(sec.get(today, 0.0))},
        "last_week": {"day": week_ago.isoformat(), "questions": int(q.get(week_ago, 0)), "seconds": float(sec.get(week_ago, 0.0))}
        if week_ago >= first else None,  # sem histórico naquele dia, não há com o que comparar
        "days": [{"day": i.isoformat(), "questions": int(r.questions), "seconds": float(r.seconds)}
                 for i, r in per.loc[today - pd.Timedelta(days=days - 1):today].iterrows()],
        "avg_per_day": float(elapsed["questions"].mean()),
        "avg_per_active_day": float(elapsed.loc[elapsed["questions"] > 0, "questions"].mean()) if (elapsed["questions"] > 0).any() else None,
        "active_days": int((elapsed["questions"] > 0).sum()),
        "streak": {"current": current, "longest": longest, "today_done": bool(active.get(today, False))},
        "week": {"current": sum_days(today - pd.Timedelta(days=6), today),
                 "previous": sum_days(today - pd.Timedelta(days=13), today - pd.Timedelta(days=7)) if today - pd.Timedelta(days=13) >= first else None},
    }


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


# ---- Análises de apoio ao estudo (todas puras sobre o DataFrame de Answers) ----

def review_queue(df: pd.DataFrame, cons: pd.DataFrame, top: int = 20) -> pd.DataFrame:
    """Questions a revisar primeiro. A pontuação soma: nível de Consistency (errando 3, instável 2), taxa de erro,
    acertos com chute e erros com Confidence 'confiante' (o erro mais perigoso). Questions estáveis ficam de fora."""
    cols = ["question_id", "level", "score", "answers", "wrong", "lucky", "confident_wrong", "section", "course"]
    if df.empty or cons.empty:
        return pd.DataFrame(columns=cols)
    g = df.groupby("question_id").agg(answers=("is_correct", "size"), wrong=("is_correct", lambda x: int((~x).sum())))
    lucky = df[df["is_correct"] & (df["confidence"] == "guess")].groupby("question_id").size()
    cw = df[~df["is_correct"] & (df["confidence"] == "confident")].groupby("question_id").size()
    g["lucky"] = lucky.reindex(g.index).fillna(0).astype(int)
    g["confident_wrong"] = cw.reindex(g.index).fillna(0).astype(int)
    t = cons.set_index("question_id")[["level", "section", "course"]].join(g, how="inner")
    t = t[t["level"] != "stable"]
    level_w = t["level"].map({"failing": 3.0, "unstable": 2.0, "learned": 0.5, "few_data": 1.0}).fillna(0)
    t["score"] = (level_w + 2 * t["wrong"] / t["answers"] + 1.0 * t["lucky"].clip(upper=3) + 1.5 * t["confident_wrong"].clip(upper=3)).round(2)
    t = t[(t["wrong"] > 0) | (t["lucky"] > 0)]  # sem erro nem chute não há o que revisar
    return t.sort_values(["score", "wrong"], ascending=False).head(top).reset_index()[cols]


def topic_impact(nodes: pd.DataFrame) -> pd.DataFrame:
    """Peso de cada tema (parte das Questions) e impacto = Questions principais × taxa de erro.
    Tema com muita Question e acerto médio pesa mais que tema pequeno com acerto baixo."""
    n = nodes.copy()
    if n.empty:
        return n.assign(share=[], impact=[])
    n["share"] = n["primary"] / max(int(n["primary"].sum()), 1)
    n["impact"] = ((1 - n["accuracy"]) * n["primary"]).where(n["answers"] > 0)
    return n


def weak_neighbors(nodes: pd.DataFrame, edges: pd.DataFrame, below: float = 0.7) -> dict[str, list[str]]:
    """Para cada tema fraco (acerto < below), os vizinhos que também são fracos."""
    acc = nodes.set_index("topic")["accuracy"]
    weak = set(acc[(acc < below) & (nodes.set_index("topic")["answers"] > 0)].index)
    out: dict[str, list[str]] = {t: [] for t in weak}
    for a, b in edges[["a", "b"]].itertuples(index=False):
        if a in weak and b in weak:
            out[a].append(b)
            out[b].append(a)
    return {t: v for t, v in out.items() if v}


def calibration_by_section(df: pd.DataFrame) -> pd.DataFrame:
    d = df.assign(level=df["confidence"].fillna(UNMARKED))
    t = d.groupby(["section", "level"])["is_correct"].agg(n="size", correct="sum").reset_index()
    t["accuracy"] = t["correct"] / t["n"]
    return t[["section", "level", "n", "accuracy"]]


def calibration_trend(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """Por bucket: acerto quando confiante e quando chuta, e quantos erros foram com Confidence 'confiante'."""
    cols = ["bucket", "confident_n", "confident_accuracy", "guess_n", "guess_accuracy", "overconfident"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    d = df.assign(bucket=df["answered_at"].dt.tz_localize(None).dt.to_period(freq).dt.start_time)
    rows = []
    for b, g in d.groupby("bucket"):
        c, k = g[g["confidence"] == "confident"], g[g["confidence"] == "guess"]
        rows.append({"bucket": b, "confident_n": len(c), "confident_accuracy": accuracy(c),
                     "guess_n": len(k), "guess_accuracy": accuracy(k),
                     "overconfident": None if c.empty else float((~c["is_correct"]).mean())})
    return pd.DataFrame(rows, columns=cols)


TIME_BINS = [(0, 30, "< 30 s"), (30, 60, "30–60 s"), (60, 120, "1–2 min"), (120, 180, "2–3 min"), (180, math.inf, "> 3 min")]


def time_vs_accuracy(df: pd.DataFrame, slow_factor: float = 1.5, top: int = 10) -> dict:
    """Acerto por faixa de tempo, mediana de tempo de certas × erradas e Questions lentas (mediana > fator × mediana geral)."""
    d = df.dropna(subset=["time_seconds"])
    if d.empty:
        return {"bins": [], "median_correct": None, "median_wrong": None, "slow": []}
    bins = []
    for lo, hi, label in TIME_BINS:
        g = d[(d["time_seconds"] >= lo) & (d["time_seconds"] < hi)]
        bins.append({"label": label, "n": len(g), "accuracy": accuracy(g)})
    overall = d["time_seconds"].median()
    q = d.groupby("question_id").agg(answers=("is_correct", "size"), median_seconds=("time_seconds", "median"),
                                      accuracy=("is_correct", "mean"), section=("section", "last"))
    slow = q[q["median_seconds"] > slow_factor * overall].sort_values("median_seconds", ascending=False).head(top)
    return {"bins": bins, "median_all": float(overall),
            "median_correct": float(d[d["is_correct"]]["time_seconds"].median()) if d["is_correct"].any() else None,
            "median_wrong": float(d[~d["is_correct"]]["time_seconds"].median()) if (~d["is_correct"]).any() else None,
            "slow": json_records(slow.reset_index())}


def json_records(df: pd.DataFrame) -> list[dict]:
    import json
    return json.loads(df.to_json(orient="records", date_format="iso"))


def projection(scores: pd.DataFrame, target: float | None = None, last: int = 8) -> dict | None:
    """Tendência da nota nos últimos Exams (regressão linear no tempo). Faixa = ±1,64 desvio dos resíduos.
    Precisa de 3+ Exams finalizados."""
    target = READY_RATIO if target is None else target
    s = scores.dropna(subset=["score"]).tail(last)
    if len(s) < 3:
        return None
    x = (s["finished_at"] - s["finished_at"].iloc[0]).dt.total_seconds().to_numpy() / 86400
    y = s["score"].to_numpy()
    if x.max() == 0:
        slope, intercept = 0.0, float(y.mean())
    else:
        slope, intercept = (float(v) for v in np.polyfit(x, y, 1))
    fit = intercept + slope * x
    sd = float(((y - fit) ** 2).sum() / max(len(y) - 2, 1)) ** 0.5
    predicted = float(min(max(intercept + slope * x[-1], 0), 1))
    eta = None
    if predicted < target and slope > 0:
        eta = math.ceil((target - predicted) / slope)
    return {"n": len(s), "mean_recent": float(y[-3:].mean()), "predicted": predicted,
            "low": max(predicted - 1.64 * sd, 0.0), "high": min(predicted + 1.64 * sd, 1.0),
            "slope_per_week": slope * 7, "eta_days": eta, "target": target}


def mode_effect(df: pd.DataFrame) -> pd.DataFrame:
    """Practice × Exam: acerto geral, acerto nas inéditas e tempo mediano."""
    rows = []
    for mode, g in df.groupby("mode"):
        new = g[g["is_first_time"]]
        rows.append({"mode": mode, "n": len(g), "accuracy": accuracy(g), "new_n": len(new), "new_accuracy": accuracy(new),
                     "median_seconds": None if g["time_seconds"].dropna().empty else float(g["time_seconds"].median())})
    return pd.DataFrame(rows, columns=["mode", "n", "accuracy", "new_n", "new_accuracy", "median_seconds"])


RETENTION_BINS = [(0, 1, "mesmo dia"), (1, 3, "1–3 dias"), (3, 7, "3–7 dias"), (7, math.inf, "7+ dias")]


def retention(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada par de Answers consecutivas da mesma Question, o acerto na segunda segundo o intervalo.
    `kept` = acerto na segunda dado que a primeira foi certa (retenção); `recovered` = idem dado que foi errada."""
    d = df.sort_values(["answered_at", "answer_id"])
    prev_ok = d.groupby("question_id")["is_correct"].shift()
    gap = d.groupby("question_id")["answered_at"].diff().dt.total_seconds() / 86400
    p = pd.DataFrame({"gap": gap, "prev": prev_ok, "ok": d["is_correct"]}).dropna(subset=["gap", "prev"])
    rows = []
    for lo, hi, label in RETENTION_BINS:
        g = p[(p["gap"] >= lo) & (p["gap"] < hi)]
        kept, rec = g[g["prev"] == True], g[g["prev"] == False]  # noqa: E712
        rows.append({"label": label, "n": len(g),
                     "kept": None if kept.empty else float(kept["ok"].mean()), "kept_n": len(kept),
                     "recovered": None if rec.empty else float(rec["ok"].mean()), "recovered_n": len(rec)})
    return pd.DataFrame(rows)


def section_heatmap(df: pd.DataFrame, weeks: int = 12) -> pd.DataFrame:
    """Acerto e volume por Section × semana (últimas `weeks` semanas com atividade)."""
    if df.empty:
        return pd.DataFrame(columns=["section", "bucket", "n", "accuracy"])
    d = df.assign(bucket=df["answered_at"].dt.tz_localize(None).dt.to_period("W").dt.start_time)
    t = d.groupby(["section", "bucket"])["is_correct"].agg(n="size", correct="sum").reset_index()
    keep = sorted(t["bucket"].unique())[-weeks:]
    t = t[t["bucket"].isin(keep)]
    t["accuracy"] = t["correct"] / t["n"]
    return t[["section", "bucket", "n", "accuracy"]]


def reasoning_effect(df: pd.DataFrame, top: int = 8) -> dict:
    """Acerto com × sem raciocínio escrito e os erros recentes em que o raciocínio foi escrito
    (se parecia certo, a Question provavelmente tem uma armadilha)."""
    has = df["reasoning"].str.len() > 0
    wrong = df[has & ~df["is_correct"]].sort_values("answered_at", ascending=False).head(top)
    return {"with_n": int(has.sum()), "with_accuracy": accuracy(df[has]),
            "without_n": int((~has).sum()), "without_accuracy": accuracy(df[~has]),
            "wrong_with_reasoning": [{"question_id": int(r.question_id), "section": r.section, "confidence": None if pd.isna(r.confidence) else r.confidence,
                                      "reasoning": r.reasoning[:240]} for r in wrong.itertuples()]}
