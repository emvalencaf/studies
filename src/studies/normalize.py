import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from studies import topics

SUPPORTED_TYPES = {"multiple-choice", "multi-select"}


def content_hash(assessment: dict, section: str) -> str:
    prompt = assessment["prompt"]
    payload = {
        "type": assessment["assessment_type"],
        "section": section,
        "question": prompt["question"],
        "answers": prompt["answers"],
        "correct": sorted(assessment["correct_response"]),
        "explanation": prompt.get("explanation", ""),
        "links": prompt.get("links", []),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def canonical_section(raw_name: str, mapping: dict[str, list[str]]) -> str:
    for canonical, variants in mapping.items():
        if raw_name in variants:
            return canonical
    raise ValueError(f"Section sem mapeamento em certification.json: {raw_name!r}")


def _upsert(conn: sqlite3.Connection, table: str, keys: dict, values: dict) -> int:
    cols = {**keys, **values}
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
    if values:
        sql += (
            f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET "
            + ", ".join(f"{c}=excluded.{c}" for c in values)
        )
    else:
        sql += f"ON CONFLICT ({', '.join(keys)}) DO NOTHING"
    conn.execute(sql, list(cols.values()))
    where = " AND ".join(f"{k}=?" for k in keys)
    return conn.execute(f"SELECT id FROM {table} WHERE {where}", list(keys.values())).fetchone()[0]


def load_certification(conn: sqlite3.Connection, cert_dir: Path) -> dict[str, int]:
    """Carrega os JSONs brutos de uma Certification. Idempotente: Questions com
    conteúdo igual só renovam last_seen_at; conteúdo diferente cria nova revisão."""
    cfg = json.loads((cert_dir / "certification.json").read_text())
    now = datetime.now(timezone.utc).isoformat()
    stats = {"questions": 0, "new_revisions": 0, "skipped": 0}

    cert_id = _upsert(conn, "certification", {"slug": cert_dir.name}, {"name": cfg["name"]})
    for canonical in cfg["sections"]:
        _upsert(conn, "section", {"certification_id": cert_id, "name": canonical}, {})

    for course_slug, course in cfg["courses"].items():
        course_id = _upsert(
            conn, "course",
            {"certification_id": cert_id, "slug": course_slug},
            {"udemy_course_id": course["udemy_course_id"], "url": course["url"]},
        )
        for position, quiz in enumerate(course["quizzes"], start=1):
            quiz_id = quiz["id"]
            raw = json.loads((cert_dir / "raw" / course_slug / f"{quiz_id}.json").read_text())
            conn.execute(
                "INSERT INTO exam (id, course_id, position, title, label, udemy_version) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (id) DO UPDATE SET course_id=excluded.course_id, position=excluded.position, "
                "title=excluded.title, label=excluded.label, udemy_version=excluded.udemy_version",
                (quiz_id, course_id, position, quiz["title"], quiz.get("label"), quiz["version"]),
            )
            for item in raw["results"]:
                if item["assessment_type"] not in SUPPORTED_TYPES:
                    stats["skipped"] += 1
                    continue
                stats["questions"] += 1
                section = canonical_section(item["section"], cfg["sections"])
                section_id = conn.execute(
                    "SELECT id FROM section WHERE certification_id=? AND name=?", (cert_id, section)
                ).fetchone()[0]
                question_id = _upsert(
                    conn, "question",
                    {"course_id": course_id, "udemy_id": item["id"]}, {"exam_id": quiz_id},
                )
                h = content_hash(item, section)
                updated = conn.execute(
                    "UPDATE question_revision SET last_seen_at=? WHERE question_id=? AND content_hash=?",
                    (now, question_id, h),
                ).rowcount
                if updated:
                    continue
                prompt = item["prompt"]
                conn.execute(
                    "INSERT INTO question_revision (question_id, content_hash, assessment_type, section_id, "
                    "prompt_html, explanation_html, options_json, correct_json, links_json, "
                    "first_seen_at, last_seen_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        question_id, h, item["assessment_type"], section_id,
                        prompt["question"], prompt.get("explanation", ""),
                        json.dumps(prompt["answers"], ensure_ascii=False),
                        json.dumps(sorted(item["correct_response"])),
                        json.dumps(prompt.get("links", []), ensure_ascii=False),
                        now, now,
                    ),
                )
                stats["new_revisions"] += 1
    conn.commit()
    rules_path = cert_dir / "topics.json"
    if rules_path.exists():
        stats["untagged"] = topics.apply(conn, cert_id, topics.load_rules(rules_path))["untagged"]
    return stats
