import json
import os
import sys
import time
from pathlib import Path

import streamlit as st

# O Community Cloud roda este arquivo direto, sem instalar o pacote: põe src/ no caminho de imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studies import attempts, backup, dashboard, selection
from studies.db import backend, connect
from studies.text import option_to_markdown

KIND_LABELS = {"exam": "Exam", "review": "Review", "drill": "Drill"}
CONFIDENCE_LABELS = {"confident": "Confiante", "educated_guess": "Educated guess", "guess": "Chute"}

st.set_page_config(page_title="Studies", layout="wide")


@st.cache_resource
def get_conn(db_path: str | None):
    return connect(db_path, check_same_thread=False)


def _secrets_to_env() -> None:
    """No Community Cloud as credenciais do Turso vêm de st.secrets."""
    for key in ("TURSO_URL", "TURSO_TOKEN"):
        try:
            if key in st.secrets:
                os.environ.setdefault(key, st.secrets[key])
        except FileNotFoundError:
            return


_secrets_to_env()
conn = get_conn(os.environ.get("STUDIES_DB"))
ss = st.session_state


def go_home():
    ss.pop("attempt_id", None)
    ss.pop("pos", None)


def open_attempt(attempt_id: int):
    ss.attempt_id = attempt_id
    ss.pos = attempts.first_unanswered(conn, attempt_id) or 1


def home():
    st.title("Studies")
    if backend(conn) == "sqlite":
        stale, age, hint = backup.is_stale(), backup.last_backup_age(), "Rode `uv run python -m studies.backup`."
    else:
        stale, age = backup.is_remote_stale(conn), backup.remote_backup_age(conn)
        hint = "Confira o workflow de backup no GitHub (Actions)."
    if stale:
        st.warning(("Nenhum backup do banco ainda" if age is None else f"Último backup há {age.days} dias") + ". " + hint)

    st.subheader("Attempts em andamento")
    running = attempts.in_progress_attempts(conn)
    if not running:
        st.caption("Nenhum.")
    for a in running:
        cols = st.columns([6, 1, 1])
        label = f"{a['course_slug']} / {a['exam_title']}" if a["kind"] == "exam" else KIND_LABELS[a["kind"]]
        cols[0].write(f"**{label}** · {a['answered']}/{a['total']} respondidas · iniciado em {a['started_at'][:16]}")
        cols[1].button("Retomar", key=f"resume{a['id']}", on_click=open_attempt, args=(a["id"],))
        cols[2].button("Abandonar", key=f"abandon{a['id']}", on_click=attempts.abandon_attempt, args=(conn, a["id"]))

    st.subheader("Novo Attempt")
    cert = conn.execute("SELECT id, name FROM certification ORDER BY name").fetchall()
    if not cert:
        st.warning("Banco vazio. Rode `uv run python -m studies.load`.")
        return
    cert_id = st.selectbox("Certification", [c["id"] for c in cert], format_func={c["id"]: c["name"] for c in cert}.get)

    mode = st.radio(
        "Modo", ["practice", "exam"], horizontal=True,
        format_func={"practice": "Practice (gabarito após cada resposta)", "exam": "Exam (gabarito só ao finalizar)"}.get,
    )
    shuffle = st.checkbox("Embaralhar opções")
    tab_exam, tab_review, tab_drill = st.tabs(["Exam completo", "Review", "Drill por Section"])

    with tab_exam:
        exams = conn.execute(
            "SELECT e.id, COALESCE(e.label, e.title) AS title, c.slug AS course FROM exam e JOIN course c ON c.id = e.course_id "
            "WHERE c.certification_id = ? ORDER BY c.slug, e.position", (cert_id,)
        ).fetchall()
        labels = {e["id"]: f"{e['course']} / {e['title']}" for e in exams}
        exam_id = st.selectbox("Exam", list(labels), format_func=labels.get)
        if st.button("Iniciar Exam", type="primary"):
            open_attempt(attempts.start_attempt(conn, exam_id, mode, shuffle))
            st.rerun()

    with tab_review:
        flt = st.selectbox("Filtro", list(selection.REVIEW_FILTERS), format_func=selection.REVIEW_FILTERS.get)
        revs = selection.review_questions(conn, cert_id, flt)
        st.caption(f"{len(revs)} Questions com esse filtro.")
        if st.button("Iniciar Review", type="primary", disabled=not revs):
            open_attempt(attempts.create_attempt(conn, revs, "review", mode, shuffle))
            st.rerun()

    with tab_drill:
        by = st.radio("Escolher por", ["section", "topic"], horizontal=True,
                      format_func={"section": "Section (domínio do exame)", "topic": "Tema (derivado da documentação citada)"}.get)
        include_secondary = False
        if by == "section":
            sections = conn.execute("SELECT id, name FROM section WHERE certification_id = ? ORDER BY name", (cert_id,)).fetchall()
            section_id = st.selectbox("Section", [x["id"] for x in sections], format_func={x["id"]: x["name"] for x in sections}.get)
            available = len(selection.section_pool(conn, cert_id, section_id))
        else:
            names = selection.topic_names(conn, cert_id)
            topic = st.selectbox("Tema", names, format_func=lambda t: f"{t} ({len(selection.topic_pool(conn, cert_id, t))})") if names else None
            include_secondary = st.checkbox("Incluir Questions que só citam o tema (secundário)")
            available = len(selection.topic_pool(conn, cert_id, topic, include_secondary)) if topic else 0
        if available == 0:
            st.info("Nenhuma Question disponível. Rode `uv run python -m studies.load` para calcular os temas." if by == "topic" else "Nenhuma Question.")
        else:
            n = st.number_input("Quantas Questions", min_value=1, max_value=available, value=min(20, available), step=5)
            pure_random = st.checkbox("Sorteio puramente aleatório (sem priorizar inéditas e erradas)")
            st.caption(f"{available} Questions disponíveis.")
            if st.button("Iniciar Drill", type="primary"):
                if by == "section":
                    revs = selection.drill_questions(conn, cert_id, section_id, int(n), pure_random)
                else:
                    revs = selection.drill_questions_by_topic(conn, cert_id, topic, int(n), pure_random, include_secondary)
                open_attempt(attempts.create_attempt(conn, revs, "drill", mode, shuffle))
                st.rerun()


def render_question(attempt_id: int, rows, pos: int, mode: str, state: str):
    row = rows[pos - 1]
    rev_id = row["id"]
    options = json.loads(row["options_json"])
    correct = json.loads(row["correct_json"])
    perm = json.loads(row["permutation_json"]) if row["permutation_json"] else None
    order = perm or list(range(len(options)))  # order[i] = índice original exibido na posição i
    multi = row["assessment_type"] == "multi-select"
    answered = row["selected_json"] is not None
    in_progress = state == "in_progress"
    reveal = (mode == "practice" and answered) or not in_progress

    letters = [attempts.LETTERS[i] for i in range(len(options))]
    labels = {l: f"{l}) {option_to_markdown(options[order[i]])}" for i, l in enumerate(letters)}
    correct_display = attempts.to_display(correct, perm)
    selected_display = attempts.to_display(json.loads(row["selected_json"]), perm) if answered else []
    key = f"{attempt_id}-{pos}"

    st.caption(f"Section: {conn.execute('SELECT name FROM section WHERE id=?', (row['section_id'],)).fetchone()[0]}")
    st.markdown(row["prompt_html"], unsafe_allow_html=True)
    if multi:
        st.info(f"Escolha {len(correct)} opções.")

    if reveal:
        for l in letters:
            mark = "✅" if l in correct_display else ("❌" if l in selected_display else "▫️")
            chosen = " **(sua resposta)**" if l in selected_display else ""
            st.markdown(f"{mark} {labels[l]}{chosen}")
        if answered:
            (st.success if row["is_correct"] else st.error)("Correto" if row["is_correct"] else "Errado")
        else:
            st.warning("Sem resposta")
        if row["confidence"]:
            st.caption(f"Confiança: {CONFIDENCE_LABELS[row['confidence']]}")
        if row["reasoning"]:
            st.caption(f"Seu raciocínio: {row['reasoning']}")
        tags = conn.execute("SELECT topic, is_primary FROM revision_topic WHERE question_revision_id = ? ORDER BY is_primary DESC, links DESC", (rev_id,)).fetchall()
        if tags:
            others = [t["topic"] for t in tags if not t["is_primary"]]
            st.caption(f"Tema: **{tags[0]['topic']}**" + (f" · também cita: {', '.join(others)}" if others else ""))
        with st.expander("Explicação da Udemy", expanded=True):
            st.markdown(row["explanation_html"], unsafe_allow_html=True)
        ai = st.text_area("AI Reasoning (cole do Gemini)", value=row["ai_reasoning"] or "", key=f"ai{rev_id}-{key}", height=160)
        if ai.strip() != (row["ai_reasoning"] or ""):
            if st.button("Salvar AI Reasoning", key=f"saveai{key}"):
                attempts.set_ai_reasoning(conn, rev_id, ai)
                st.rerun()
        return

    if not in_progress:
        return
    if mode == "exam" and answered:
        st.caption("Resposta registrada. Você pode trocá-la até finalizar.")

    shown = ss.setdefault(f"shown{key}", time.time())
    if multi:
        picked = [l for l in letters if st.checkbox(labels[l], value=l in selected_display, key=f"opt{key}{l}")]
    else:
        pick = st.radio("Resposta", letters, index=letters.index(selected_display[0]) if selected_display else None,
                        format_func=labels.get, key=f"opt{key}", label_visibility="collapsed")
        picked = [pick] if pick else []
    conf = st.radio("Confiança (opcional)", list(CONFIDENCE_LABELS), index=list(CONFIDENCE_LABELS).index(row["confidence"]) if row["confidence"] else None,
                    format_func=CONFIDENCE_LABELS.get, horizontal=True, key=f"conf{key}")
    reasoning = st.text_area("Seu raciocínio (opcional)", value=row["reasoning"] or "", key=f"why{key}", height=100)
    if st.button("Confirmar", type="primary", disabled=not picked, key=f"ok{key}"):
        attempts.record_answer(conn, attempt_id, rev_id, attempts.to_original(picked, perm), conf, reasoning, time.time() - shown)
        st.rerun()


def attempt_view():
    attempt_id, pos = ss.attempt_id, ss.pos
    rows = attempts.attempt_questions(conn, attempt_id)
    total = len(rows)
    state, mode = conn.execute("SELECT state, mode FROM attempt WHERE id=?", (attempt_id,)).fetchone()
    s = attempts.summary(conn, attempt_id)

    top = st.columns([6, 1])
    top[0].progress((total - s["skipped"]) / total, text=f"Questão {pos}/{total} · {s['correct']} certas · {s['wrong']} erradas · {s['skipped']} sem resposta")
    top[1].button("Início", on_click=go_home)

    if state != "in_progress":
        st.success(f"Attempt {'finalizado' if state == 'finished' else 'abandonado'}: {s['correct']}/{s['correct'] + s['wrong']} certas, {s['skipped']} puladas.")
    render_question(attempt_id, rows, pos, mode, state)

    nav = st.columns(4)
    if nav[0].button("← Anterior", disabled=pos <= 1):
        ss.pos -= 1
        st.rerun()
    if nav[1].button("Próxima →", disabled=pos >= total):
        ss.pos += 1
        st.rerun()
    if state == "in_progress" and nav[3].button("Finalizar Attempt"):
        attempts.finish_attempt(conn, attempt_id)
        st.rerun()


page = st.sidebar.radio("Página", ["Estudar", "Dashboard"])
if page == "Dashboard":
    dashboard.render(conn)
elif "attempt_id" in ss:
    attempt_view()
else:
    home()
