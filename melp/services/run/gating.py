"""Release gating: policy DSL + evaluation. Phase 3.

A gating policy is a YAML/JSON document attached to a project. It declares a
list of *rules*; each rule asserts a metric meets some bar. A run "passes the
gate" iff every blocking rule passes; warning-severity rules don't block but
appear in the response and the PR comment.

Example policy::

    rules:
      - metric: bleu
        slice: overall
        operator: ">="
        threshold: 0.7
        severity: blocking
      - metric: bleu
        slice: long
        operator: ">= baseline"
        margin: 0.0
        severity: blocking
      - metric: rouge_l
        slice: overall
        operator: ">= baseline"
        severity: warning

Operators:
  ``>=`` / ``<=`` / ``>`` / ``<`` — numeric threshold check against ``point_estimate``.
  ``>= baseline`` / ``<= baseline`` — paired comparison to ``baseline_run_id``;
  requires ``baseline_run_id`` on the run and ``margin`` (default 0.0).

Significance gate:
  ``require_significant: true`` on a rule means a baseline-comparison rule
  only counts as failing if the paired test was significant at α=0.05.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from melp.common import models


Severity = Literal["blocking", "warning"]


@dataclass
class RuleResult:
    rule_id: int
    metric: str
    slice: str
    operator: str
    threshold: float | None
    severity: Severity
    actual: float | None
    baseline: float | None
    passed: bool
    reason: str


@dataclass
class GateDecision:
    run_id: str
    passed: bool
    blocking_failures: int
    warnings: int
    rules: list[RuleResult]
    policy_hash: str

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def _result_for(
    db: Session, run_id: str, metric_name: str, slice_name: str
) -> models.RunResult | None:
    q = (
        db.query(models.RunResult)
        .join(models.MetricVersion, models.MetricVersion.id == models.RunResult.metric_version_id)
        .join(models.Metric, models.Metric.id == models.MetricVersion.metric_id)
        .filter(models.RunResult.run_id == run_id, models.Metric.name == metric_name)
    )
    if slice_name == "overall":
        q = q.filter(models.RunResult.slice_def_id.is_(None))
    else:
        q = (
            q.join(models.SliceDef, models.SliceDef.id == models.RunResult.slice_def_id)
            .filter(models.SliceDef.name == slice_name)
        )
    return q.one_or_none()


def _eval_rule(
    db: Session,
    run: models.Run,
    rule: dict[str, Any],
    rule_id: int,
) -> RuleResult:
    metric = rule["metric"]
    slice_name = rule.get("slice", "overall")
    op = rule.get("operator", ">=")
    threshold = rule.get("threshold")
    margin = float(rule.get("margin", 0.0))
    severity: Severity = rule.get("severity", "blocking")
    require_sig = bool(rule.get("require_significant", False))

    rr = _result_for(db, run.id, metric, slice_name)
    if rr is None:
        return RuleResult(
            rule_id, metric, slice_name, op, threshold, severity,
            actual=None, baseline=None, passed=False,
            reason=f"no result for metric={metric!r} slice={slice_name!r}",
        )

    if op in (">=", "<=", ">", "<"):
        if threshold is None:
            return RuleResult(
                rule_id, metric, slice_name, op, None, severity,
                actual=rr.point_estimate, baseline=None, passed=False,
                reason="numeric operator requires `threshold`",
            )
        ok = (
            (op == ">=" and rr.point_estimate >= threshold) or
            (op == "<=" and rr.point_estimate <= threshold) or
            (op == ">"  and rr.point_estimate >  threshold) or
            (op == "<"  and rr.point_estimate <  threshold)
        )
        return RuleResult(
            rule_id, metric, slice_name, op, threshold, severity,
            actual=rr.point_estimate, baseline=None, passed=ok,
            reason=("ok" if ok else f"{rr.point_estimate:.4f} {op} {threshold} is false"),
        )

    if op in (">= baseline", "<= baseline"):
        if not run.baseline_run_id:
            return RuleResult(
                rule_id, metric, slice_name, op, None, severity,
                actual=rr.point_estimate, baseline=None, passed=False,
                reason="rule references baseline but run has no baseline_run_id",
            )
        b_rr = _result_for(db, run.baseline_run_id, metric, slice_name)
        if b_rr is None:
            return RuleResult(
                rule_id, metric, slice_name, op, None, severity,
                actual=rr.point_estimate, baseline=None, passed=False,
                reason="baseline run has no matching result for this metric/slice",
            )
        diff = rr.point_estimate - b_rr.point_estimate
        ok = (op == ">= baseline" and diff >= -margin) or (op == "<= baseline" and diff <=  margin)
        if require_sig and rr.p_value is not None and rr.p_value >= 0.05:
            ok = True  # not significant → treat as "no regression"
        return RuleResult(
            rule_id, metric, slice_name, op, None, severity,
            actual=rr.point_estimate, baseline=b_rr.point_estimate, passed=ok,
            reason=("ok" if ok else f"diff {diff:+.4f} fails {op} margin={margin}"),
        )

    return RuleResult(
        rule_id, metric, slice_name, op, threshold, severity,
        actual=rr.point_estimate, baseline=None, passed=False,
        reason=f"unknown operator: {op!r}",
    )


def evaluate_policy(
    db: Session,
    run: models.Run,
    policy: dict[str, Any],
) -> GateDecision:
    import hashlib
    import json

    rules = policy.get("rules") or []
    results = [_eval_rule(db, run, rule, i) for i, rule in enumerate(rules)]
    blocking = [r for r in results if r.severity == "blocking" and not r.passed]
    warnings = [r for r in results if r.severity == "warning" and not r.passed]
    policy_hash = hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()[:16]
    return GateDecision(
        run_id=run.id,
        passed=len(blocking) == 0,
        blocking_failures=len(blocking),
        warnings=len(warnings),
        rules=results,
        policy_hash=policy_hash,
    )


def render_pr_comment(decision: GateDecision) -> str:
    """Markdown payload suitable for posting back to a PR."""
    lines: list[str] = []
    badge = "✅ MELP gate passed" if decision.passed else "❌ MELP gate failed"
    lines.append(f"### {badge}")
    lines.append("")
    lines.append(f"Run: `{decision.run_id}` · policy `{decision.policy_hash}`")
    lines.append("")
    lines.append("| Metric | Slice | Rule | Result | Detail |")
    lines.append("|---|---|---|---|---|")
    for r in decision.rules:
        icon = "✅" if r.passed else ("⚠️" if r.severity == "warning" else "❌")
        rule_desc = f"{r.operator} {r.threshold}" if r.threshold is not None else r.operator
        detail = r.reason
        lines.append(
            f"| `{r.metric}` | `{r.slice}` | {rule_desc} | {icon} {r.severity} | {detail} |"
        )
    return "\n".join(lines)
