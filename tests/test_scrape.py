import json
import shutil
from pathlib import Path

import pytest

from studies import scrape

CERT = Path("data/certifications/aws-certified-gen-ai-developer")


def item(i, version, title="T"):
    return {"_class": "quiz", "id": i, "title": f"{title}{i}", "version": version, "type": "practice-test"}


def test_parse_curriculum_keeps_only_quizzes():
    items = [{"_class": "chapter", "id": 1, "title": "c"}, item(2, 5), {"_class": "lecture", "id": 3, "title": "l"}]
    assert scrape.parse_curriculum(items) == [{"id": 2, "title": "T2", "version": 5}]


def test_plan_downloads_only_what_changed(tmp_path):
    (tmp_path / "1.json").write_text("{}")
    (tmp_path / "2.json").write_text("{}")
    configured = [{"id": 1, "title": "a", "version": 3}, {"id": 2, "title": "b", "version": 4},
                  {"id": 3, "title": "c", "version": 1}, {"id": 9, "title": "gone", "version": 1}]
    curriculum = [{"id": 1, "title": "a", "version": 3},      # igual
                  {"id": 2, "title": "b", "version": 5},      # versão nova
                  {"id": 3, "title": "c", "version": 1},      # igual, mas arquivo não existe
                  {"id": 4, "title": "new", "version": 1}]    # quiz novo
    plan = scrape.plan_course(configured, curriculum, tmp_path)
    assert [q["id"] for q in plan["download"]] == [2, 3, 4]
    assert plan["up_to_date"] == [1]
    assert plan["missing_from_curriculum"] == [9]
    assert len(scrape.plan_course(configured, curriculum, tmp_path, force=True)["download"]) == 4


def test_apply_downloaded_keeps_order_and_appends_new():
    configured = [{"id": 1, "title": "a", "version": 1}, {"id": 2, "title": "b", "version": 1}]
    out = scrape.apply_downloaded(configured, [{"id": 2, "title": "b2", "version": 2}, {"id": 7, "title": "n", "version": 1}])
    assert out == [{"id": 1, "title": "a", "version": 1}, {"id": 2, "title": "b2", "version": 2}, {"id": 7, "title": "n", "version": 1}]


class FakePage:
    """Responde ao fetch da página a partir de um dicionário url -> resposta."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def evaluate(self, js, url):
        self.calls.append(url)
        return self.routes[url]


def _quiz_payload(n, qid_start=100):
    results = [{"id": qid_start + i, "assessment_type": "multiple-choice", "prompt": {}, "correct_response": ["a"], "section": "S"} for i in range(n)]
    return {"first": {"count": n, "next": None, "previous": None, "results": results[:1]}, "results": results}


@pytest.fixture
def cert(tmp_path):
    dest = tmp_path / "cert"
    dest.mkdir()
    (dest / "certification.json").write_text(json.dumps({
        "name": "X", "sections": {},
        "courses": {"c1": {"udemy_course_id": 11, "url": "u", "quizzes": [{"id": 1, "title": "old", "version": 1}]}},
    }))
    return dest


def test_scrape_downloads_changed_quiz_and_updates_config(cert):
    page = FakePage({
        scrape.curriculum_url(11): {"first": {}, "results": [item(1, 2, "New"), item(2, 1, "Other")]},
        scrape.assessments_url(1, 2): _quiz_payload(3),
        scrape.assessments_url(2, 1): _quiz_payload(2, 500),
    })
    logs = []
    summary = scrape.scrape_certification(page, cert, log=logs.append)
    assert summary == {"downloaded": 2, "up_to_date": 0, "failed": 0}
    raw = json.loads((cert / "raw/c1/1.json").read_text())
    assert raw["count"] == 3 and len(raw["results"]) == 3 and raw["next"] is None
    quizzes = json.loads((cert / "certification.json").read_text())["courses"]["c1"]["quizzes"]
    assert quizzes == [{"id": 1, "title": "New1", "version": 2}, {"id": 2, "title": "Other2", "version": 1}]

    # segunda rodada sem mudança na Udemy: nada é baixado nem reescrito
    mtime = (cert / "raw/c1/1.json").stat().st_mtime_ns
    page2 = FakePage({scrape.curriculum_url(11): {"first": {}, "results": [item(1, 2, "New"), item(2, 1, "Other")]}})
    assert scrape.scrape_certification(page2, cert) == {"downloaded": 0, "up_to_date": 2, "failed": 0}
    assert page2.calls == [scrape.curriculum_url(11)]
    assert (cert / "raw/c1/1.json").stat().st_mtime_ns == mtime


def test_incomplete_download_is_not_saved_and_config_not_bumped(cert):
    bad = _quiz_payload(3)
    bad["first"]["count"] = 75  # Udemy diz 75, vieram 3
    page = FakePage({scrape.curriculum_url(11): {"first": {}, "results": [item(1, 2)]}, scrape.assessments_url(1, 2): bad})
    logs = []
    summary = scrape.scrape_certification(page, cert, log=logs.append)
    assert summary["failed"] == 1 and summary["downloaded"] == 0
    assert not (cert / "raw/c1/1.json").exists()
    assert json.loads((cert / "certification.json").read_text())["courses"]["c1"]["quizzes"][0]["version"] == 1


def test_expired_session_reports_and_continues(cert):
    page = FakePage({scrape.curriculum_url(11): {"error": 403}})
    logs = []
    assert scrape.scrape_certification(page, cert, log=logs.append)["failed"] == 1
    assert "login" in logs[0]


def test_real_config_matches_downloaded_files():
    cfg = json.loads((CERT / "certification.json").read_text())
    for slug, course in cfg["courses"].items():
        for q in course["quizzes"]:
            assert (CERT / "raw" / slug / f"{q['id']}.json").exists()


def test_scrape_preserves_hand_edited_label(cert):
    cfg_path = cert / "certification.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["courses"]["c1"]["quizzes"][0]["label"] = "Exam 1"
    cfg_path.write_text(json.dumps(cfg))
    page = FakePage({
        scrape.curriculum_url(11): {"first": {}, "results": [item(1, 2, "New"), item(2, 1, "Other")]},
        scrape.assessments_url(1, 2): _quiz_payload(3),
        scrape.assessments_url(2, 1): _quiz_payload(2, 500),
    })
    scrape.scrape_certification(page, cert, force=True)
    quizzes = json.loads(cfg_path.read_text())["courses"]["c1"]["quizzes"]
    assert quizzes[0] == {"id": 1, "title": "New1", "version": 2, "label": "Exam 1"}
    assert "label" not in quizzes[1]  # quiz novo ainda sem nome curto
