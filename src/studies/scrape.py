"""Baixa os Exams dos Courses da Certification usando a sessão logada da Udemy.

    uv run python -m studies.scrape login            # uma vez: login manual, salva storage_state.json
    uv run python -m studies.scrape run [cert_dir]   # baixa só o que mudou (--force baixa tudo)

As chamadas à API saem de dentro da página (fetch com os cookies do browser), porque a Udemy
protege a API com Cloudflare e requisições fora do browser recebem 403.
"""
import argparse
import json
from pathlib import Path

STORAGE_STATE = Path("storage_state.json")
DEFAULT_CERT = Path("data/certifications/aws-certified-gen-ai-developer")
LOGIN_URL = "https://www.udemy.com/join/login-popup/"
HOME_URL = "https://www.udemy.com/"
ASSESSMENT_FIELDS = "id,assessment_type,prompt,correct_response,section,question_plain,related_lectures"

# Roda no browser: segue a paginação e devolve a primeira página (count) e todos os results.
FETCH_ALL_JS = """
async (url) => {
  const results = []; let first = null;
  while (url) {
    const r = await fetch(url, {credentials: 'include'});
    if (!r.ok) return {error: r.status};
    const j = await r.json();
    first = first ?? j; results.push(...j.results); url = j.next;
  }
  return {first, results};
}
"""


def curriculum_url(udemy_course_id: int) -> str:
    return (f"/api-2.0/courses/{udemy_course_id}/subscriber-curriculum-items/?page_size=200"
            "&fields[quiz]=id,title,type,version&fields[lecture]=id,title&fields[chapter]=id,title")


def assessments_url(quiz_id: int, version: int) -> str:
    return f"/api-2.0/quizzes/{quiz_id}/assessments/?version={version}&page_size=250&fields[assessment]={ASSESSMENT_FIELDS}"


def parse_curriculum(items: list[dict]) -> list[dict]:
    return [{"id": i["id"], "title": i["title"], "version": i["version"]} for i in items if i.get("_class") == "quiz"]


def plan_course(configured: list[dict], curriculum: list[dict], raw_dir: Path, force: bool = False) -> dict:
    """Decide o que baixar. Quiz novo no currículo entra no fim da lista; quiz que sumiu do
    currículo fica na config (os dados já baixados continuam valendo) e é reportado."""
    known = {q["id"]: q for q in configured}
    to_download, up_to_date = [], []
    for q in curriculum:
        have = known.get(q["id"])
        raw_exists = (raw_dir / f"{q['id']}.json").exists()
        if force or have is None or have["version"] != q["version"] or not raw_exists:
            to_download.append(q)
        else:
            up_to_date.append(q["id"])
    missing = [q["id"] for q in configured if q["id"] not in {c["id"] for c in curriculum}]
    return {"download": to_download, "up_to_date": up_to_date, "missing_from_curriculum": missing}


def apply_downloaded(configured: list[dict], downloaded: list[dict]) -> list[dict]:
    """Atualiza título e versão dos Exams baixados, preservando a ordem; novos vão para o fim."""
    by_id = {q["id"]: q for q in downloaded}
    out = [{**q, **by_id.pop(q["id"], {})} for q in configured]
    return out + list(by_id.values())


def write_raw(raw_dir: Path, quiz_id: int, payload: dict) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    tmp = raw_dir / f".{quiz_id}.json.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False))
    tmp.replace(raw_dir / f"{quiz_id}.json")


def fetch_quiz(page, quiz: dict) -> dict:
    res = page.evaluate(FETCH_ALL_JS, assessments_url(quiz["id"], quiz["version"]))
    if "error" in res:
        raise RuntimeError(f"quiz {quiz['id']}: HTTP {res['error']}")
    first, results = res["first"], res["results"]
    if first["count"] != len(results):
        raise RuntimeError(f"quiz {quiz['id']}: esperadas {first['count']} Questions, vieram {len(results)}")
    return {**first, "next": None, "results": results}


def scrape_certification(page, cert_dir: Path, force: bool = False, log=print) -> dict:
    cfg_path = cert_dir / "certification.json"
    cfg = json.loads(cfg_path.read_text())
    summary = {"downloaded": 0, "up_to_date": 0, "failed": 0}
    for slug, course in cfg["courses"].items():
        res = page.evaluate(FETCH_ALL_JS, curriculum_url(course["udemy_course_id"]))
        if "error" in res:
            log(f"[{slug}] currículo falhou (HTTP {res['error']}); sessão expirada? Rode `login` de novo.")
            summary["failed"] += 1
            continue
        raw_dir = cert_dir / "raw" / slug
        plan = plan_course(course["quizzes"], parse_curriculum(res["results"]), raw_dir, force)
        summary["up_to_date"] += len(plan["up_to_date"])
        for q in plan["missing_from_curriculum"]:
            log(f"[{slug}] quiz {q} não está mais no currículo; dados mantidos.")
        done = []
        for quiz in plan["download"]:
            try:
                write_raw(raw_dir, quiz["id"], fetch_quiz(page, quiz))
            except RuntimeError as e:
                log(f"[{slug}] {e}")
                summary["failed"] += 1
                continue
            log(f"[{slug}] {quiz['title']} v{quiz['version']} baixado")
            done.append(quiz)
            summary["downloaded"] += 1
        course["quizzes"] = apply_downloaded(course["quizzes"], done)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")  # grava a cada Course
    return summary


def login(storage_state: Path = STORAGE_STATE) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(LOGIN_URL)
        input("Faça login na Udemy na janela aberta (inclua captcha/2FA) e aperte Enter aqui... ")
        page.goto(HOME_URL)
        context.storage_state(path=str(storage_state))
        browser.close()
    storage_state.chmod(0o600)
    print(f"Sessão salva em {storage_state}")


def run(cert_dir: Path, force: bool = False, headless: bool = False, storage_state: Path = STORAGE_STATE) -> dict:
    from playwright.sync_api import sync_playwright

    if not storage_state.exists():
        raise SystemExit("Sem sessão. Rode primeiro: uv run python -m studies.scrape login")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=str(storage_state))
        page = context.new_page()
        page.goto(HOME_URL, wait_until="domcontentloaded")
        try:
            return scrape_certification(page, cert_dir, force)
        finally:
            browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(prog="studies.scrape")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    r = sub.add_parser("run")
    r.add_argument("cert_dir", nargs="?", type=Path, default=DEFAULT_CERT)
    r.add_argument("--force", action="store_true", help="baixa tudo, mesmo sem mudança de version")
    r.add_argument("--headless", action="store_true", help="sem janela (a Udemy pode bloquear)")
    args = ap.parse_args()
    if args.cmd == "login":
        login()
        return
    summary = run(args.cert_dir, args.force, args.headless)
    print(summary)
    if summary["downloaded"]:
        print("Para criar as novas revisões no banco: uv run python -m studies.load")


if __name__ == "__main__":
    main()
