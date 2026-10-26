import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from studies import metrics

# Slots categóricos em ordem fixa (validados com validate_palette.js nos dois temas).
LIGHT = {"s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a", "s4": "#eda100", "muted": "#8d8c87",
         "text": "#0b0b0b", "grid": "rgba(0,0,0,0.08)"}
DARK = {"s1": "#3987e5", "s2": "#d95926", "s3": "#199e70", "s4": "#c98500", "muted": "#8d8c87",
        "text": "#f0efec", "grid": "rgba(255,255,255,0.10)"}

CONF_LABELS = {"confident": "Confiante", "educated_guess": "Educated guess", "guess": "Chute", "unmarked": "Sem marcação"}
LEVEL_LABELS = {"stable": "Estável", "learned": "Aprendida", "unstable": "Instável", "failing": "Errando", "few_data": "Poucos dados"}
GRAN_LABELS = {"overall": "Geral", "course": "Course", "exam": "Exam", "section": "Section", "topic": "Tema", "question": "Question"}
HEAT_LIGHT = ["#cde2fb", "#3987e5", "#0d366b"]
HEAT_DARK = ["#14263d", "#1c5cab", "#6da7ec"]


def short(topic: str) -> str:
    return topic.split(" (")[0]
KIND_LABELS = {"exam": "Exam", "review": "Review", "drill": "Drill"}
WINDOW_LABELS = {"7d": "Últimos 7 dias", "30d": "Últimos 30 dias", "all": "Todo o período", "custom": "Intervalo livre"}


def palette() -> dict:
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except Exception:
        return LIGHT


def style(fig: go.Figure, pal: dict, pct: bool = True, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=24, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=pal["text"]), hovermode="x unified", legend=dict(orientation="h", y=1.12, x=0),
    )
    fig.update_xaxes(showgrid=False, linecolor=pal["grid"], zeroline=False)
    fig.update_yaxes(gridcolor=pal["grid"], zeroline=False, tickformat=".0%" if pct else None,
                     range=[0, 1.02] if pct else None)
    return fig


def fmt_pct(x) -> str:
    return "–" if x is None or pd.isna(x) else f"{x:.0%}"


def render(conn):
    st.title("Dashboard")
    certs = conn.execute("SELECT id, name FROM certification ORDER BY name").fetchall()
    if not certs:
        st.warning("Banco vazio.")
        return
    cert_id = st.selectbox("Certification", [c["id"] for c in certs], format_func={c["id"]: c["name"] for c in certs}.get)
    df_all = metrics.answers_df(conn, cert_id)
    if df_all.empty:
        st.info("Nenhuma Answer ainda. Faça um Attempt na página Estudar.")
        return
    pal = palette()

    f1, f2, f3, f4 = st.columns([2, 3, 2, 2])
    window = f1.radio("Janela", list(WINDOW_LABELS), format_func=WINDOW_LABELS.get, index=2)
    custom = None
    if window == "custom":
        today = pd.Timestamp.now().date()
        custom = f1.date_input("Intervalo", value=(df_all["answered_at"].min().date(), today))
        if len(custom) != 2:
            st.stop()
    kinds = f2.multiselect("Tipos de Attempt", list(KIND_LABELS), default=list(KIND_LABELS), format_func=KIND_LABELS.get)
    gran = f3.selectbox("Granularidade", list(GRAN_LABELS), format_func=GRAN_LABELS.get, index=3)
    freq = f4.radio("Bucket", ["D", "W"], format_func={"D": "Dia", "W": "Semana"}.get, horizontal=True)
    roll = f4.slider("Média móvel (buckets)", 1, 14, 3)

    df_kind = df_all[df_all["kind"].isin(kinds)]
    start, end = metrics.window_bounds(window, df_all, custom)
    win = metrics.in_window(df_kind, start, end)
    st.caption(f"{start:%d/%m/%Y} a {end:%d/%m/%Y} · {len(win)} Answers")

    tr = metrics.trend(df_kind, start, end)
    new, rep = win[win["is_first_time"]], win[~win["is_first_time"]]
    k = st.columns(4)
    k[0].metric("Acerto na janela", fmt_pct(tr["current"]),
                None if tr["delta"] is None else f"{tr['delta'] * 100:+.0f} pp vs janela anterior")
    k[1].metric("Answers", len(win))
    k[2].metric("Acerto em inéditas", fmt_pct(metrics.accuracy(new)), help="Primeira vez que a Question foi respondida. Mede conhecimento.")
    k[3].metric("Acerto em repetições", fmt_pct(metrics.accuracy(rep)), help="Pode estar inflado por memória.")

    t_prog, t_best, t_cal, t_pace, t_cons, t_topic, t_q = st.tabs(
        ["Progressão", "Melhor desempenho", "Calibração", "Ritmo", "Consistência", "Temas", "Questions"])

    with t_prog:
        prog = metrics.progression(win, freq, roll)
        if prog.empty:
            st.info("Sem Answers na janela.")
        else:
            fig = go.Figure()
            for segment, color in (("Inéditas", pal["s1"]), ("Repetições", pal["s2"])):
                g = prog[prog["segment"] == segment]
                if g.empty:
                    continue
                fig.add_trace(go.Scatter(x=g["bucket"], y=g["rolling"], name=segment, mode="lines+markers",
                                         line=dict(color=color, width=2), marker=dict(size=8, line=dict(width=2, color="rgba(0,0,0,0)")),
                                         customdata=g[["n", "accuracy"]], connectgaps=True,
                                         hovertemplate="%{y:.0%} (móvel) · bucket %{customdata[1]:.0%} em %{customdata[0]:.0f} Answers"))
            st.plotly_chart(style(fig, pal), width="stretch")
            st.caption("Linhas: média móvel ponderada pelo número de Answers. Inéditas medem conhecimento; repetições podem refletir memória.")
        gtab = metrics.by_granularity(win, gran)
        st.subheader(f"Acerto por {GRAN_LABELS[gran]}")
        if gran == "question":
            gtab = gtab[gtab["n"] >= 2]
        shown = gtab.rename(columns={"group": GRAN_LABELS[gran], "n": "Answers", "correct": "Certas", "accuracy": "Acerto"})
        st.dataframe(shown, hide_index=True, width="stretch",
                     column_config={"Acerto": st.column_config.ProgressColumn("Acerto", format="percent", min_value=0, max_value=1)})

    with t_best:
        scores = metrics.attempt_scores(conn, cert_id)
        st.caption("Só Attempts de Exam finalizados. Review e Drill ficam de fora; puladas não entram no acerto.")
        if scores.empty:
            st.info("Nenhum Exam finalizado ainda.")
        else:
            best = metrics.best_attempts(scores)
            top = best.sort_values("score", ascending=False).iloc[0]
            st.metric("Melhor nota", fmt_pct(top["score"]))
            st.caption(f"{top['exam_title']} ({top['mode']})")
            fig = go.Figure(go.Scatter(x=scores["finished_at"], y=scores["score"], mode="lines+markers", name="Nota por Attempt",
                                       line=dict(color=pal["s1"], width=2), marker=dict(size=8),
                                       customdata=scores[["exam_title", "mode", "answered", "skipped"]],
                                       hovertemplate="%{y:.0%} · %{customdata[0]} (%{customdata[1]}) · %{customdata[2]} respondidas, %{customdata[3]} puladas"))
            st.plotly_chart(style(fig, pal), width="stretch")
            st.subheader("Melhor Attempt por Exam")
            st.dataframe(best[["exam_title", "score", "mode", "answered", "skipped", "finished_at"]].rename(columns={
                "exam_title": "Exam", "score": "Nota", "mode": "Modo", "answered": "Respondidas", "skipped": "Puladas", "finished_at": "Quando"}),
                hide_index=True, width="stretch",
                column_config={"Nota": st.column_config.ProgressColumn("Nota", format="percent", min_value=0, max_value=1)})
        bw = metrics.best_window(win, freq, min_n=10)
        st.subheader("Melhor janela")
        if bw is None:
            st.caption(f"Nenhum {'dia' if freq == 'D' else 'semana'} com 10 ou mais Answers ainda.")
        else:
            st.metric(f"Melhor {'dia' if freq == 'D' else 'semana'}", fmt_pct(bw["accuracy"]))
            st.caption(f"{bw['bucket']:%d/%m/%Y} · {bw['n']} Answers")

    with t_cal:
        cal = metrics.calibration(win)
        if cal.empty:
            st.info("Sem Answers na janela.")
        else:
            colors = [pal["muted"] if not r else pal["s1"] for r in cal["in_calibration"]]
            fig = go.Figure(go.Bar(x=[CONF_LABELS[l] for l in cal["level"]], y=cal["accuracy"], marker_color=colors,
                                   text=[f"{a:.0%}<br>n={n}" for a, n in zip(cal["accuracy"], cal["n"])], textposition="outside",
                                   customdata=cal["n"], hovertemplate="%{y:.0%} de acerto em %{customdata} Answers<extra></extra>"))
            fig.update_traces(marker_line_width=0, width=0.5)
            st.plotly_chart(style(fig, pal).update_layout(hovermode="closest", showlegend=False), width="stretch")
            st.caption("Quem está bem calibrado acerta mais quando está confiante do que quando chuta. "
                       "'Sem marcação' (cinza) fica fora da calibração.")

    with t_pace:
        pace = metrics.pace(win)
        if pace.empty:
            st.info("Sem Answers na janela.")
        else:
            fig = go.Figure(go.Bar(x=pace["day"], y=pace["questions"], name="Questions", marker_color=pal["s1"],
                                   hovertemplate="%{y} Questions<extra></extra>"))
            st.plotly_chart(style(fig, pal, pct=False, height=260).update_layout(showlegend=False, hovermode="closest"), width="stretch")
            tm = win["time_seconds"].dropna()
            c = st.columns(3)
            c[0].metric("Questions por dia (dias ativos)", f"{pace.loc[pace['questions'] > 0, 'questions'].mean():.0f}")
            c[1].metric("Tempo mediano por Question", "–" if tm.empty else f"{tm.median():.0f} s")
            c[2].metric("Tempo médio por Question", "–" if tm.empty else f"{tm.mean():.0f} s",
                        help="Sensível a pausas longas; compare com a mediana.")

    with t_cons:
        kth = st.slider("Acertos seguidos para considerar estável", 2, 6, 3)
        st.caption("Calculado sobre todo o histórico de cada Question, independente da janela e dos tipos de Attempt selecionados.")
        cons = metrics.consistency(df_all, kth)
        summ = metrics.consistency_summary(cons, "section")
        total = metrics.consistency_summary(cons, None)
        if cons.empty:
            st.info("Sem dados.")
        else:
            level_colors = {"stable": pal["s1"], "learned": pal["s2"], "unstable": pal["s3"], "failing": pal["s4"], "few_data": pal["muted"]}
            groups = pd.concat([total.assign(group="Certification (total)"), summ])
            order = ["Certification (total)"] + sorted(summ["group"].unique())
            fig = go.Figure()
            for level in metrics.CONSISTENCY_LEVELS:
                g = groups[groups["level"] == level].set_index("group").reindex(order)
                fig.add_trace(go.Bar(y=order, x=g["share"].fillna(0), name=LEVEL_LABELS[level], orientation="h",
                                     marker=dict(color=level_colors[level], line=dict(width=2, color="rgba(0,0,0,0)")),
                                     customdata=g["questions"].fillna(0),
                                     hovertemplate="%{x:.0%} · %{customdata:.0f} Questions<extra>" + LEVEL_LABELS[level] + "</extra>"))
            fig.update_layout(barmode="stack", legend=dict(traceorder="normal"))
            style(fig, pal, height=120 + 46 * len(order)).update_layout(hovermode="closest")
            fig.update_xaxes(tickformat=".0%", range=[0, 1], showgrid=True, gridcolor=pal["grid"])
            fig.update_yaxes(tickformat=None, range=None, autorange="reversed", showgrid=False)
            st.plotly_chart(fig, width="stretch")
            st.caption(f"Estável: {kth} acertos seguidos sem nenhum erro antes · Aprendida: errou antes e agora acerta {kth} seguidas · "
                       f"Instável: alterna · Errando: {kth} erros seguidos · Poucos dados: menos de {kth} Answers.")
            st.dataframe(pd.DataFrame({"Nível": [LEVEL_LABELS[l] for l in metrics.CONSISTENCY_LEVELS],
                                       "Questions": [int((cons["level"] == l).sum()) for l in metrics.CONSISTENCY_LEVELS]}),
                         hide_index=True)

    with t_topic:
        st.caption("Tema = assunto da documentação AWS citada na explicação. Principal = o mais citado; as arestas ligam temas citados "
                   "na mesma Question.")
        graph = metrics.topic_graph(conn, cert_id, win)
        nodes, edges = graph["nodes"], graph["edges"]
        if nodes.empty:
            st.info("Sem temas. Rode `uv run python -m studies.load` para calculá-los.")
        else:
            acc = metrics.by_granularity(win, "topic").set_index("group")
            tbl = nodes.assign(answers=nodes["topic"].map(acc["n"]).fillna(0).astype(int),
                               accuracy=nodes["topic"].map(acc["accuracy"]))
            st.subheader("Temas (principal)")
            st.dataframe(tbl.rename(columns={"topic": "Tema", "primary": "Questions (principal)", "total": "Questions (citam)",
                                             "answers": "Answers na janela", "accuracy": "Acerto"}),
                         hide_index=True, width="stretch",
                         column_config={"Acerto": st.column_config.ProgressColumn("Acerto", format="percent", min_value=0, max_value=1)})

            st.subheader("Arestas: temas citados juntos")
            names = nodes["topic"].tolist()
            idx = {t: i for i, t in enumerate(names)}
            z = [[None] * len(names) for _ in names]
            text = [[""] * len(names) for _ in names]
            for a_, b_, n_ in edges[["a", "b", "questions"]].itertuples(index=False):
                for r, c in ((idx[a_], idx[b_]), (idx[b_], idx[a_])):
                    z[r][c] = n_
                    text[r][c] = f"{a_} + {b_}: {n_} Questions"
            fig = go.Figure(go.Heatmap(z=z, x=[short(t) for t in names], y=[short(t) for t in names], text=text,
                                       colorscale=HEAT_DARK if pal is DARK else HEAT_LIGHT, hoverongaps=False,
                                       hovertemplate="%{text}<extra></extra>", xgap=2, ygap=2,
                                       colorbar=dict(title="Questions", thickness=12)))
            fig.update_layout(height=120 + 30 * len(names), margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", font=dict(color=pal["text"]))
            fig.update_yaxes(autorange="reversed")
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, width="stretch")

            st.subheader("Vizinhos de um tema")
            focus = st.selectbox("Tema", names, format_func=lambda t: f"{t} ({int(nodes.set_index('topic').loc[t, 'primary'])} principal)")
            nb = metrics.neighbors(edges, focus)
            if nb.empty:
                st.caption("Esse tema nunca aparece junto de outro na mesma Question.")
            else:
                fig = go.Figure(go.Bar(y=[short(t) for t in nb["neighbor"]], x=nb["questions"], orientation="h", marker_color=pal["s1"],
                                       hovertemplate="%{x} Questions citam os dois<extra></extra>"))
                style(fig, pal, pct=False, height=60 + 30 * len(nb)).update_layout(showlegend=False, hovermode="closest")
                fig.update_yaxes(autorange="reversed", tickformat=None)
                fig.update_xaxes(showgrid=True, gridcolor=pal["grid"])
                st.plotly_chart(fig, width="stretch")
                st.dataframe(nb[["neighbor", "questions", "answers", "accuracy"]].rename(columns={
                    "neighbor": "Tema vizinho", "questions": "Questions em comum", "answers": "Answers na janela", "accuracy": "Acerto"}),
                    hide_index=True, width="stretch",
                    column_config={"Acerto": st.column_config.ProgressColumn("Acerto", format="percent", min_value=0, max_value=1)})

    with t_q:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Mais erradas")
            mw = metrics.most_wrong(win)
            st.dataframe(mw.rename(columns={"question_id": "Question", "answers": "Answers", "wrong": "Erros", "section": "Section",
                                            "course": "Course", "error_rate": "Taxa de erro"}),
                         hide_index=True, width="stretch",
                         column_config={"Taxa de erro": st.column_config.ProgressColumn("Taxa de erro", format="percent", min_value=0, max_value=1)})
        with c2:
            st.subheader("Acertadas com chute")
            st.caption("Acerto que ainda não é conhecimento.")
            lg = metrics.lucky_guesses(win)
            st.dataframe(lg.rename(columns={"question_id": "Question", "times": "Vezes", "section": "Section", "course": "Course"}),
                         hide_index=True, width="stretch")
