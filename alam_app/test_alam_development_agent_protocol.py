from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROTOCOL = ROOT / "DEVELOPMENT_AGENT_PROTOCOL.md"
DIRECTION = ROOT / "ALAM_PRODUCT_DIRECTION_2026-09-03.md"


def test_development_protocol_matches_three_agent_ownership():
    protocol = PROTOCOL.read_text(encoding="utf-8")
    direction = DIRECTION.read_text(encoding="utf-8")

    # These documents are mandatory inputs to every development run. If they
    # disagree about the number or ownership of agents, automated developers can
    # legitimately choose overlapping files and race each other on main.
    assert "three scheduled development agents" in protocol
    assert "## Innovation Agent responsibility" in protocol
    assert "## Maintenance Agent responsibility" in protocol
    assert "## Stability & Integration Agent responsibility" in protocol
    assert "Content agents are data-only" in protocol
    assert "must never modify application code" in protocol
    assert "ALAM_PRODUCT_DIRECTION_2026-09-03.md" in protocol

    assert "## 7. Three development agents" in direction
    for agent_name in (
        "Innovation Agent",
        "Maintenance Agent",
        "Stability & Integration Agent",
    ):
        assert agent_name in protocol
        assert agent_name in direction

    stale_phrases = (
        "two scheduled development agents",
        "only two development agents are active",
        "Agent A — Backend Architect",
        "Agent B — Product Builder",
    )
    for phrase in stale_phrases:
        assert phrase not in protocol
