"""Temas das Questions, derivados dos links da documentação nas explicações da Udemy.

As regras ficam em `topics.json` na pasta da Certification. Cada link da explicação vira uma chave
`<serviço>/<resto do caminho>` (sem o idioma, sem `latest`, sem `.html`) e a primeira regra cujo padrão
casa define o tema do link. O tema principal da Question é o mais citado; empate vai para a regra
que vem antes no arquivo. Os demais temas citados são os secundários (as arestas entre temas).
"""
import collections
import itertools
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

NO_TOPIC = "Sem tema"
DOCS_HOST = "docs.aws.amazon.com"
_LANG = re.compile(r"[a-z]{2}_[a-z]{2}")


def load_rules(path: Path) -> list[tuple[str, re.Pattern]]:
    data = json.loads(path.read_text())
    return [(r["topic"], re.compile(r["pattern"])) for r in data["rules"]]


def link_key(url: str) -> str | None:
    p = urlparse(url)
    if p.netloc != DOCS_HOST:
        return None
    parts = [x for x in p.path.split("/") if x and not _LANG.fullmatch(x)]
    if len(parts) > 1 and parts[1] == "latest":
        parts.pop(1)
    return "/".join(parts).removesuffix(".html") or None


def topic_of_link(url: str, rules) -> str | None:
    key = link_key(url)
    if key is None:
        return None
    return next((topic for topic, rx in rules if rx.search(key)), None)


def topics_for_html(html: str, rules) -> list[tuple[str, int]]:
    """[(tema, nº de links)] com o principal primeiro. Cada URL conta uma vez por Question."""
    urls = set(re.findall(r'href="(https?://[^"]+)"', html))
    counts = collections.Counter(t for t in (topic_of_link(u, rules) for u in urls) if t)
    order = {topic: i for i, (topic, _) in enumerate(rules)}
    return sorted(counts.items(), key=lambda kv: (-kv[1], order[kv[0]]))


def apply(conn: sqlite3.Connection, certification_id: int, rules) -> dict[str, int]:
    """Recalcula os temas de todas as revisões da Certification. Os temas não entram no hash da
    revisão: mudar as regras reclassifica tudo sem criar revisões novas."""
    rows = conn.execute(
        """
        SELECT r.id, r.explanation_html FROM question_revision r
        JOIN question q ON q.id = r.question_id JOIN course c ON c.id = q.course_id
        WHERE c.certification_id = ?
        """,
        (certification_id,),
    ).fetchall()
    conn.execute(
        "DELETE FROM revision_topic WHERE question_revision_id IN (SELECT r.id FROM question_revision r "
        "JOIN question q ON q.id = r.question_id JOIN course c ON c.id = q.course_id WHERE c.certification_id = ?)",
        (certification_id,),
    )
    untagged = 0
    for rev_id, html in rows:
        tagged = topics_for_html(html, rules)
        untagged += not tagged
        for i, (topic, n) in enumerate(tagged):
            conn.execute(
                "INSERT INTO revision_topic (question_revision_id, topic, links, is_primary) VALUES (?, ?, ?, ?)",
                (rev_id, topic, n, int(i == 0)),
            )
    conn.commit()
    return {"revisions": len(rows), "untagged": untagged}


def edges(topics_by_question: dict[int, list[str]]) -> collections.Counter:
    """Quantas Questions citam cada par de temas (pares sem ordem, em ordem alfabética)."""
    pairs = collections.Counter()
    for topics in topics_by_question.values():
        for a, b in itertools.combinations(sorted(set(topics)), 2):
            pairs[(a, b)] += 1
    return pairs
