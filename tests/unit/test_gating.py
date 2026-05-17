"""Gating policy DSL — numeric thresholds, baseline comparisons, PR comment."""
from melp.services.run.gating import RuleResult, render_pr_comment, GateDecision


def test_render_pr_comment_pass():
    decision = GateDecision(
        run_id="run_x", passed=True, blocking_failures=0, warnings=0, policy_hash="abcd1234",
        rules=[
            RuleResult(
                rule_id=0, metric="bleu", slice="overall", operator=">=", threshold=0.7,
                severity="blocking", actual=0.75, baseline=None, passed=True, reason="ok",
            ),
        ],
    )
    md = render_pr_comment(decision)
    assert "✅" in md
    assert "bleu" in md
    assert "abcd1234" in md


def test_render_pr_comment_fail():
    decision = GateDecision(
        run_id="run_y", passed=False, blocking_failures=1, warnings=0, policy_hash="ef012345",
        rules=[
            RuleResult(
                rule_id=0, metric="bleu", slice="long", operator=">= baseline", threshold=None,
                severity="blocking", actual=0.41, baseline=0.69, passed=False,
                reason="diff -0.2800 fails >= baseline margin=0.0",
            ),
        ],
    )
    md = render_pr_comment(decision)
    assert "❌" in md
    assert "fails" in md
