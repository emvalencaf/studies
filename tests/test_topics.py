import re
import shutil
from pathlib import Path

import pytest

from studies import topics
from studies.db import connect
from studies.normalize import load_certification

CERT = Path("data/certifications/aws-certified-gen-ai-developer")
RULES = topics.load_rules(CERT / "topics.json")


def html(*urls):
    return "".join(f'<a href="{u}">x</a>' for u in urls)


def test_link_key_strips_language_latest_and_extension():
    assert topics.link_key("https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html") == "bedrock/userguide/guardrails"
    assert topics.link_key("https://docs.aws.amazon.com/en_us/lambda/latest/dg/x.html?utm=1") == "lambda/dg/x"
    assert topics.link_key("https://aws.amazon.com/blogs/x") is None
    assert topics.link_key("https://docs.aws.amazon.com/") is None


@pytest.mark.parametrize("url,topic", [
    ("https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html", "Bedrock: Guardrails"),
    ("https://docs.aws.amazon.com/bedrock/latest/APIReference/API_CreateGuardrail.html", "Bedrock: Guardrails"),
    ("https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking.html", "Bedrock: Knowledge Bases e RAG"),
    ("https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_Retrieve.html", "Bedrock: Knowledge Bases e RAG"),
    ("https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_CreateAgent.html", "Agentes (Bedrock Agents e AgentCore)"),
    ("https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html", "Agentes (Bedrock Agents e AgentCore)"),
    ("https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html", "Bedrock: Prompt Management e Flows"),
    ("https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html", "Bedrock: Inferência e throughput"),
    ("https://docs.aws.amazon.com/bedrock/latest/userguide/something-new.html", "Bedrock: outros"),
    ("https://docs.aws.amazon.com/step-functions/latest/dg/x.html", "Orquestração (Step Functions, EventBridge)"),
    ("https://docs.aws.amazon.com/nova/latest/userguide/x.html", "Amazon Nova"),
    ("https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/x.html", "Amazon Q e Quick"),
])
def test_rules_classify_links(url, topic):
    assert topics.topic_of_link(url, RULES) == topic


def test_unknown_service_has_no_topic():
    assert topics.topic_of_link("https://docs.aws.amazon.com/some-new-service/latest/x.html", RULES) is None


def test_primary_is_most_cited_and_ties_follow_rule_order():
    g = "https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails"
    k = "https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking"
    result = topics.topics_for_html(html(g + ".html", g + "-components.html", k + ".html"), RULES)
    assert result == [("Bedrock: Guardrails", 2), ("Bedrock: Knowledge Bases e RAG", 1)]
    tie = topics.topics_for_html(html(k + ".html", g + ".html"), RULES)
    assert tie[0][0] == "Bedrock: Guardrails"  # Guardrails vem antes no topics.json
    # a mesma URL repetida conta uma vez
    assert topics.topics_for_html(html(g + ".html", g + ".html"), RULES) == [("Bedrock: Guardrails", 1)]


def test_edges_count_unordered_pairs():
    e = topics.edges({1: ["B", "A", "C"], 2: ["A", "B"], 3: ["A"]})
    assert e[("A", "B")] == 2 and e[("A", "C")] == 1 and e[("B", "C")] == 1
    assert len(e) == 3


@pytest.fixture
def conn(tmp_path):
    dest = tmp_path / CERT.name
    shutil.copytree(CERT, dest)
    c = connect(":memory:")
    stats = load_certification(c, dest)
    return c, dest, stats


def test_load_assigns_one_primary_per_tagged_revision(conn):
    c, _, stats = conn
    assert stats["untagged"] < 975 * 0.1
    bad = c.execute("SELECT question_revision_id FROM revision_topic GROUP BY question_revision_id HAVING sum(is_primary) != 1").fetchall()
    assert bad == []
    tagged = c.execute("SELECT count(DISTINCT question_revision_id) FROM revision_topic").fetchone()[0]
    assert tagged + stats["untagged"] == 975


def test_changing_rules_reclassifies_without_new_revisions(conn):
    c, dest, _ = conn
    before = c.execute("SELECT count(*) FROM question_revision").fetchone()[0]
    (dest / "topics.json").write_text('{"rules": [{"topic": "Tudo", "pattern": "."}]}')
    stats = load_certification(c, dest)
    assert stats["new_revisions"] == 0
    assert c.execute("SELECT count(*) FROM question_revision").fetchone()[0] == before
    assert {r[0] for r in c.execute("SELECT DISTINCT topic FROM revision_topic")} == {"Tudo"}


def test_no_topics_file_is_fine(conn):
    c, dest, _ = conn
    (dest / "topics.json").unlink()
    assert "untagged" not in load_certification(c, dest)
