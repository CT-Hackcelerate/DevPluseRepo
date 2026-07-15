"""Command-line entry point.

Examples:
    tokenopt optimize-doc --file report.docx        # optimize a Word/text document
    tokenopt optimize-doc --file notes.txt --summarize
    tokenopt ui                                      # open the document optimizer UI
    tokenopt triage-jira --jql "project = ABC AND status = 'To Do'"
    tokenopt demo            # runs the optimizer on canned data (no external creds)
"""

from __future__ import annotations

import argparse
import os
import sys

from .config import Config


def _cmd_optimize_doc(args: argparse.Namespace) -> int:
    """Optimize a document's text and write the result to a text file."""
    from .optimize.text_pipeline import optimize_document, write_output
    from .run_log import log_run

    config = Config()
    out_path = args.out or os.path.join(os.getcwd(), "optimized_output.txt")
    source = {"type": "document", "file": args.file}
    options = {"summarize": bool(args.summarize)}
    try:
        result = optimize_document(config, args.file, summarize=args.summarize)
    except Exception as exc:
        log_path = log_run(
            command="optimize-doc", source=source, options=options,
            config=config, error=f"{type(exc).__name__}: {exc}",
        )
        if log_path:
            print(f"Run log: {log_path}", file=sys.stderr)
        raise

    write_output(result, out_path)
    log_path = log_run(
        command="optimize-doc", source=source, options=options,
        result=result, config=config, output_path=out_path,
    )

    print(result.optimized_text)
    print("\n" + result.summary(), file=sys.stderr)
    print(f"Optimized text written to: {out_path}", file=sys.stderr)
    if log_path:
        print(f"Run log written to:        {log_path}", file=sys.stderr)
    return 0


def _cmd_ui(args: argparse.Namespace) -> int:
    """Launch the desktop document-optimizer UI."""
    from .ui import launch

    return launch()


def _run_and_log(command: str, source: dict, options: dict, work) -> int:
    """Run a triage/review ``work`` callable, print its result, and log the run."""
    from .run_log import log_run

    config = Config()
    try:
        result = work(config)
    except Exception as exc:
        log_path = log_run(
            command=command, source=source, options=options,
            config=config, error=f"{type(exc).__name__}: {exc}",
        )
        if log_path:
            print(f"Run log: {log_path}", file=sys.stderr)
        raise

    log_path = log_run(
        command=command, source=source, options=options,
        result=result, config=config,
    )
    print(result.answer)
    print("\n" + result.summary(), file=sys.stderr)
    if log_path:
        print(f"Run log written to: {log_path}", file=sys.stderr)
    return 0


def _cmd_triage_jira(args: argparse.Namespace) -> int:
    from .automations.triage import triage_jira

    return _run_and_log(
        "triage-jira",
        {"type": "jira", "jql": args.jql, "max_results": args.max},
        {"max_results": args.max},
        lambda cfg: triage_jira(cfg, args.jql, max_results=args.max),
    )


def _cmd_triage_jenkins(args: argparse.Namespace) -> int:
    from .automations.triage import triage_jenkins_failure

    return _run_and_log(
        "triage-jenkins",
        {"type": "jenkins", "job": args.job, "build": args.build},
        {},
        lambda cfg: triage_jenkins_failure(cfg, args.job, args.build),
    )


def _cmd_review_github_pr(args: argparse.Namespace) -> int:
    from .automations.github import review_pr

    return _run_and_log(
        "review-github-pr",
        {"type": "github-pr", "owner": args.owner, "repo": args.repo, "number": args.number},
        {"post_comment": bool(args.post_comment)},
        lambda cfg: review_pr(cfg, args.owner, args.repo, args.number, post_comment=args.post_comment),
    )


def _cmd_triage_github_prs(args: argparse.Namespace) -> int:
    from .automations.github import triage_open_prs

    return _run_and_log(
        "triage-github-prs",
        {"type": "github-prs", "owner": args.owner, "repo": args.repo},
        {"include_diffs": bool(args.diffs)},
        lambda cfg: triage_open_prs(cfg, args.owner, args.repo, include_diffs=args.diffs),
    )


def _cmd_compress_prd(args: argparse.Namespace) -> int:
    """Skill 1 — compress a verbose PRD into dense requirement atoms."""
    from .integrations.document import read_document
    from .prd.compressor import compress_prd

    text = read_document(args.file)
    result = compress_prd(text)

    out_path = args.out or os.path.join(os.getcwd(), "compressed_prd.txt")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(result.compressed_text)

    print(result.compressed_text)
    print("\n" + result.summary(), file=sys.stderr)
    print(f"Compressed PRD written to: {out_path}", file=sys.stderr)
    return 0


def _cmd_anchor_plan(args: argparse.Namespace) -> int:
    """Skill 2a — anchor plan steps to real file:line references in a repo."""
    from .anchor.anchor import anchor_plan, anchoring_accuracy
    from .anchor.indexer import build_index

    with open(args.plan, "r", encoding="utf-8") as fh:
        steps = [ln.strip() for ln in fh if ln.strip()]

    index = build_index(args.repo)
    anchors = anchor_plan(steps, index)

    for anc in anchors:
        print(anc.render())

    accuracy = anchoring_accuracy(anchors)
    unresolved = sum(1 for a in anchors if a.unresolved_terms)
    print(
        f"\nIndexed {len(index)} symbols in {args.repo} | "
        f"{len(steps)} steps | anchoring accuracy {accuracy * 100:.0f}% | "
        f"{unresolved} step(s) with unresolved (possible hallucination) references",
        file=sys.stderr,
    )
    return 0


def _cmd_route(args: argparse.Namespace) -> int:
    """Skill 2b — classify a task's complexity and route it to a model."""
    from .router.router import RouterConfig, route_task

    route = route_task(args.task, RouterConfig())
    print(route.render())
    cls = route.classification
    if cls is not None:
        print(
            f"\nsignals: {cls.signals} | confidence {route.confidence:.2f}"
            + ("  (upgraded to premium: low confidence)" if route.upgraded else ""),
            file=sys.stderr,
        )
    return 0


def _cmd_ab_suite(args: argparse.Namespace) -> int:
    """Eval — run the 8-case, 2-BU A/B suite (baseline vs optimised)."""
    from .anchor.indexer import build_index
    from .eval.ab_runner import run_ab_suite
    from .eval.datasets import sample_cases

    index = build_index(args.repo)
    summary = run_ab_suite(sample_cases(), index)

    print(summary.summary())
    print("\nper-case:")
    for r in summary.results:
        print("  " + r.summary())
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    """Eval — render the A/B results to a self-contained HTML dashboard."""
    from .eval.dashboard import write_dashboard

    out_path = args.out or os.path.join(os.getcwd(), "ab_dashboard.html")
    write_dashboard(out_path, repo=args.repo)
    print(f"Dashboard written to: {out_path}", file=sys.stderr)
    print(out_path)
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    """Run the full optimization pipeline on synthetic JIRA-shaped data."""
    from .optimize.pipeline import OptimizedRunner

    items = [
        {
            "key": "ABC-101",
            "summary": "NullPointerException on checkout",
            "description": "User reports a crash. " * 200,  # deliberately verbose
            "status": {"name": "To Do"},
            "priority": {"name": "High"},
            "issuetype": {"name": "Bug"},
            "labels": ["payments", "regression"],
            "assignee": {"displayName": "Jane Dev"},
            "extra_noise": {"customfield_1": "x" * 500, "watchers": list(range(50))},
        },
        {
            "key": "ABC-102",
            "summary": "Add dark mode toggle",
            "description": "Feature request. " * 150,
            "status": {"name": "To Do"},
            "priority": {"name": "Low"},
            "issuetype": {"name": "Story"},
            "labels": ["ui"],
            "assignee": None,
            "extra_noise": {"customfield_1": "y" * 500},
        },
    ]

    runner = OptimizedRunner(Config())
    result = runner.run(
        system=(
            "You are a triage assistant. For each JIRA issue output: <key> — "
            "priority, area, one-line next action."
        ),
        task="Triage these issues.",
        items=items,
        profile="jira_issue",
        summarize=False,  # items are small after filtering; skip the extra call
    )
    print(result.answer)
    print("\n" + result.summary(), file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tokenopt", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("optimize-doc", help="Optimize a Word/text document's tokens")
    p.add_argument("--file", required=True, help="Path to a .docx/.txt/.md document")
    p.add_argument(
        "--summarize",
        action="store_true",
        help="Also summarize with Claude Haiku (needs ANTHROPIC_API_KEY)",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Output text file (default: optimized_output.txt in the current folder)",
    )
    p.set_defaults(func=_cmd_optimize_doc)

    p = sub.add_parser("ui", help="Open the desktop document-optimizer UI")
    p.set_defaults(func=_cmd_ui)

    p = sub.add_parser("triage-jira", help="Triage JIRA issues matching a JQL query")
    p.add_argument("--jql", required=True)
    p.add_argument("--max", type=int, default=25)
    p.set_defaults(func=_cmd_triage_jira)

    p = sub.add_parser("triage-jenkins", help="Root-cause a Jenkins build failure")
    p.add_argument("--job", required=True)
    p.add_argument("--build", default="lastBuild")
    p.set_defaults(func=_cmd_triage_jenkins)

    p = sub.add_parser("review-github-pr", help="Review a single GitHub pull request")
    p.add_argument("--owner", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--number", type=int, required=True)
    p.add_argument(
        "--post-comment",
        action="store_true",
        help="Post the review back as a PR comment",
    )
    p.set_defaults(func=_cmd_review_github_pr)

    p = sub.add_parser("triage-github-prs", help="Triage all open PRs in a repo")
    p.add_argument("--owner", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument(
        "--diffs",
        action="store_true",
        help="Pull and compress each diff for a deeper read (more tokens)",
    )
    p.set_defaults(func=_cmd_triage_github_prs)

    p = sub.add_parser(
        "compress-prd",
        help="Skill 1: compress a verbose PRD into dense requirement atoms",
    )
    p.add_argument("--file", required=True, help="Path to a .docx/.txt/.md PRD")
    p.add_argument(
        "--out",
        default=None,
        help="Output file (default: compressed_prd.txt in the current folder)",
    )
    p.set_defaults(func=_cmd_compress_prd)

    p = sub.add_parser(
        "anchor-plan",
        help="Skill 2a: anchor plan steps to real file:line references",
    )
    p.add_argument(
        "--plan",
        required=True,
        help="Text file with one plan step per line",
    )
    p.add_argument(
        "--repo",
        default=os.getcwd(),
        help="Repository root to index (default: current directory)",
    )
    p.set_defaults(func=_cmd_anchor_plan)

    p = sub.add_parser(
        "route",
        help="Skill 2b: classify a task's complexity and route it to a model",
    )
    p.add_argument("--task", required=True, help="Task description to route")
    p.set_defaults(func=_cmd_route)

    p = sub.add_parser(
        "ab-suite",
        help="Eval: run the 8-case, 2-BU A/B suite (baseline vs optimised)",
    )
    p.add_argument(
        "--repo",
        default="src",
        help="Repository root to index for anchoring (default: src)",
    )
    p.set_defaults(func=_cmd_ab_suite)

    p = sub.add_parser(
        "dashboard",
        help="Eval: render the A/B results to a self-contained HTML dashboard",
    )
    p.add_argument(
        "--repo",
        default="src",
        help="Repository root to index for anchoring (default: src)",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Output HTML file (default: ab_dashboard.html in the current folder)",
    )
    p.set_defaults(func=_cmd_dashboard)

    p = sub.add_parser("demo", help="Run the optimizer on canned data")
    p.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # surface clean errors to the terminal
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
