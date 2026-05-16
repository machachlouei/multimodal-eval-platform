"""melp CLI. Wraps the SDK. See FR-10.

Examples::

    melp project create --name vision-quality
    melp metric list
    melp run submit examples/captioner_classic.yaml
    melp run get run_01...
    melp run watch run_01...
"""
from __future__ import annotations

import json

import click
import yaml
from rich.console import Console
from rich.table import Table

from melp.sdk import MELPClient

console = Console()


def _client(ctx: click.Context) -> MELPClient:
    return ctx.obj["client"]


@click.group()
@click.option("--base-url", default=None, help="MELP API base URL")
@click.option("--token", default=None, help="bearer token")
@click.pass_context
def cli(ctx: click.Context, base_url: str | None, token: str | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["client"] = MELPClient(base_url=base_url, token=token)


# ---------- project ----------
@cli.group()
def project() -> None:
    """Project commands."""


@project.command("list")
@click.pass_context
def project_list(ctx: click.Context) -> None:
    rows = _client(ctx).list_projects()
    t = Table("id", "name", "description")
    for p in rows:
        t.add_row(p["id"], p["name"], p.get("description", ""))
    console.print(t)


@project.command("create")
@click.option("--name", required=True)
@click.option("--description", default="")
@click.pass_context
def project_create(ctx: click.Context, name: str, description: str) -> None:
    console.print_json(json.dumps(_client(ctx).create_project(name, description)))


# ---------- metric ----------
@cli.group()
def metric() -> None:
    """Metric commands."""


@metric.command("list")
@click.pass_context
def metric_list(ctx: click.Context) -> None:
    rows = _client(ctx).list_metrics()
    t = Table("id", "name", "description")
    for m in rows:
        t.add_row(m["id"], m["name"], m.get("description", "")[:60])
    console.print(t)


# ---------- run ----------
@cli.group()
def run() -> None:
    """Run commands."""


@run.command("submit")
@click.argument("spec_path", type=click.Path(exists=True))
@click.pass_context
def run_submit(ctx: click.Context, spec_path: str) -> None:
    with open(spec_path) as f:
        spec = yaml.safe_load(f)
    c = _client(ctx)
    project = spec["project"]
    payload = {
        "model_version_id": spec["model_version_id"],
        "dataset_version_id": spec["dataset_version_id"],
        "metric_version_ids": spec["metric_version_ids"],
        "judge_config_version_id": spec.get("judge_config_version_id"),
        "slice_set": spec.get("slice_set", []),
        "baseline_run_id": spec.get("baseline_run_id"),
        "seed": spec.get("seed", 42),
        "priority": spec.get("priority", "normal"),
        "name": spec.get("name", ""),
    }
    r = c.submit_run(project, **payload)
    console.print_json(json.dumps(r))


@run.command("get")
@click.argument("run_id")
@click.option("--project", required=True)
@click.pass_context
def run_get(ctx: click.Context, run_id: str, project: str) -> None:
    console.print_json(json.dumps(_client(ctx).get_run(project, run_id)))


@run.command("watch")
@click.argument("run_id")
@click.option("--project", required=True)
@click.pass_context
def run_watch(ctx: click.Context, run_id: str, project: str) -> None:
    r = _client(ctx).wait_for_run(project, run_id)
    console.print_json(json.dumps(r))


@run.command("list")
@click.option("--project", required=True)
@click.option("--status", default=None)
@click.pass_context
def run_list(ctx: click.Context, project: str, status: str | None) -> None:
    rows = _client(ctx).list_runs(project, status=status)
    t = Table("id", "status", "model", "dataset", "submitted_at")
    for r in rows:
        t.add_row(r["id"], r["status"], r["model_version_id"], r["dataset_version_id"], r["submitted_at"])
    console.print(t)


@run.command("leaderboard")
@click.option("--project", required=True)
@click.argument("metric_version_id")
@click.pass_context
def run_leaderboard(ctx: click.Context, project: str, metric_version_id: str) -> None:
    rows = _client(ctx).leaderboard(project, metric_version_id)
    t = Table("run_id", "point", "ci_low", "ci_high", "model")
    for r in rows:
        t.add_row(
            r["run_id"],
            f"{r['point_estimate']:.4f}",
            f"{r.get('ci_low') or '':.4}" if r.get("ci_low") is not None else "",
            f"{r.get('ci_high') or '':.4}" if r.get("ci_high") is not None else "",
            r["model_version_id"],
        )
    console.print(t)


if __name__ == "__main__":
    cli(prog_name="melp", obj={})
