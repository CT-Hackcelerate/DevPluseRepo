"""Desktop UI for the token optimizer.

A small Tkinter app (no extra dependencies) with three input sources:
  * **Document** — pick a .docx / .txt / .md file,
  * **JIRA** — connect with a base URL + email + API token and fetch issues by JQL,
  * **GitHub (Git)** — connect with a token and fetch a pull request (or all open PRs).

Whatever the source, the fetched text is optimized (compression + optional Haiku
summarization), shown original-vs-optimized with a token review, and written to
``optimized_output.txt`` in the project root.

Connection fields fall back to your environment / .env when left blank, so you can
either type credentials here or configure them once in .env (see .env.example).

Launch with ``tokenopt ui`` or ``python -m token_optimizer.ui``.
"""

from __future__ import annotations

import threading
from pathlib import Path

from .config import Config
from .integrations.document import SUPPORTED_EXTENSIONS, read_document
from .integrations.sources import build_config, fetch_github_text, fetch_jira_text
from .optimize.text_pipeline import TextOptimizer, write_output

# Write the output text file into the project root folder.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_FILE = _PROJECT_ROOT / "optimized_output.txt"


def launch() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    config = Config()
    state = {"text": ""}
    action_buttons: list = []

    root = tk.Tk()
    root.title("TokenOptimizer — Document / JIRA / Git Optimizer")
    root.geometry("1040x760")
    root.minsize(820, 600)

    # ── shared helpers ──────────────────────────────────────────────
    def _field(parent, label, row, *, show=None, default="", width=48):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=width, show=show).grid(
            row=row, column=1, sticky="we", padx=4, pady=3
        )
        parent.columnconfigure(1, weight=1)
        return var

    def _set_text(widget, content: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)

    def _set_busy(busy: bool) -> None:
        for btn in action_buttons:
            btn.config(state="disabled" if busy else "normal")
        if not busy:
            optimize_btn.config(state="normal" if state["text"] else "disabled")

    def load_source(text: str, label: str) -> None:
        state["text"] = text
        _set_text(original_box, text)
        _set_text(optimized_box, "")
        for var in (raw_var, opt_var, saved_var, method_var):
            var.set("—")
        optimize_btn.config(state="normal" if text else "disabled")
        if text:
            # Optimize immediately so the token-savings numbers appear without
            # requiring an extra click. Deferred so the "Original" pane paints
            # first. Re-run manually after toggling 'Summarize'.
            stats_var.set(f"{label} — {len(text):,} chars loaded. Optimizing…")
            root.after(50, run_optimize)
        else:
            stats_var.set(f"{label} — nothing to optimize.")

    def _run_bg(work, on_ok, *, busy: str) -> None:
        stats_var.set(busy)
        _set_busy(True)

        def worker() -> None:
            try:
                res = work()
                root.after(0, lambda: (_set_busy(False), on_ok(res)))
            except Exception as exc:
                root.after(0, lambda e=exc: (_set_busy(False), _failed(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _failed(exc: Exception) -> None:
        stats_var.set(f"Error: {exc}")
        messagebox.showerror("Operation failed", str(exc))

    # ── source notebook (Document / JIRA / GitHub) ──────────────────
    sources = ttk.Notebook(root)
    sources.pack(fill="x", padx=10, pady=(10, 4))

    # -- Document tab --
    doc_tab = ttk.Frame(sources, padding=10)
    sources.add(doc_tab, text="  Document  ")
    doc_path_var = tk.StringVar(value="No document selected.")

    def choose_file() -> None:
        filetypes = [
            ("Documents", " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)),
            ("Word documents", "*.docx"),
            ("Text files", "*.txt *.md *.log"),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(title="Select a document", filetypes=filetypes)
        if not path:
            return
        try:
            text = read_document(path)
        except Exception as exc:
            messagebox.showerror("Could not read document", str(exc))
            return
        doc_path_var.set(path)
        load_source(text, "Document")

    doc_btn = ttk.Button(doc_tab, text="Select Document…", command=choose_file)
    doc_btn.grid(row=0, column=0, sticky="w")
    ttk.Label(doc_tab, textvariable=doc_path_var, foreground="#555").grid(
        row=0, column=1, sticky="w", padx=10
    )
    doc_tab.columnconfigure(1, weight=1)
    action_buttons.append(doc_btn)

    # -- JIRA tab --
    jira_tab = ttk.Frame(sources, padding=10)
    sources.add(jira_tab, text="  JIRA  ")
    jira_url_var = _field(jira_tab, "Base URL", 0, default=config.jira_base_url)
    jira_email_var = _field(jira_tab, "Email", 1, default=config.jira_email)
    jira_token_var = _field(jira_tab, "API token", 2, show="•")
    jira_jql_var = _field(jira_tab, "JQL query", 3, default="project = ABC AND status = 'To Do'")
    jira_max_var = _field(jira_tab, "Max results", 4, default="25", width=8)

    def fetch_jira() -> None:
        jql = jira_jql_var.get().strip()
        if not jql:
            messagebox.showwarning("JQL required", "Enter a JQL query to fetch issues.")
            return
        cfg = build_config(
            jira_base_url=jira_url_var.get().strip(),
            jira_email=jira_email_var.get().strip(),
            jira_api_token=jira_token_var.get().strip(),
        )
        try:
            maxr = int(jira_max_var.get())
        except ValueError:
            maxr = 25
        _run_bg(
            lambda: fetch_jira_text(cfg, jql, maxr),
            lambda res: load_source(res[0], f"JIRA: {res[1]} issue(s)"),
            busy="Connecting to JIRA…",
        )

    jira_btn = ttk.Button(jira_tab, text="Connect & Fetch Issues", command=fetch_jira)
    jira_btn.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
    action_buttons.append(jira_btn)
    ttk.Label(
        jira_tab, text="Blank fields fall back to your .env values.", foreground="#888"
    ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # -- GitHub (Git) tab --
    gh_tab = ttk.Frame(sources, padding=10)
    sources.add(gh_tab, text="  GitHub (Git)  ")
    gh_url_var = _field(gh_tab, "API URL", 0, default=config.github_api_url)
    gh_token_var = _field(gh_tab, "Token", 1, show="•")
    gh_owner_var = _field(gh_tab, "Owner", 2)
    gh_repo_var = _field(gh_tab, "Repository", 3)
    gh_number_var = _field(gh_tab, "PR number (blank = all open PRs)", 4, width=12)
    gh_diff_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        gh_tab, text="Include diff (deeper read, more tokens)", variable=gh_diff_var
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 0))

    def fetch_github() -> None:
        owner = gh_owner_var.get().strip()
        repo = gh_repo_var.get().strip()
        if not owner or not repo:
            messagebox.showwarning("Repo required", "Enter both an owner and a repository.")
            return
        cfg = build_config(
            github_api_url=gh_url_var.get().strip(),
            github_token=gh_token_var.get().strip(),
        )
        num_raw = gh_number_var.get().strip()
        number = int(num_raw) if num_raw.isdigit() else None
        _run_bg(
            lambda: fetch_github_text(
                cfg, owner, repo, number, include_diff=gh_diff_var.get()
            ),
            lambda res: load_source(res[0], f"GitHub: {res[1]} PR(s)"),
            busy="Connecting to GitHub…",
        )

    gh_btn = ttk.Button(gh_tab, text="Connect & Fetch", command=fetch_github)
    gh_btn.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
    action_buttons.append(gh_btn)
    ttk.Label(
        gh_tab, text="Blank Token/URL fall back to your .env values.", foreground="#888"
    ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # ── control bar ─────────────────────────────────────────────────
    controls = ttk.Frame(root, padding=(10, 4))
    controls.pack(fill="x")

    summarize_var = tk.BooleanVar(value=False)
    if config.anthropic_api_key:
        summarize_label = "Summarize with Claude (Haiku)"
    else:
        summarize_label = "Summarize (no API key: offline extractive summary)"
    ttk.Checkbutton(
        controls,
        text=summarize_label,
        variable=summarize_var,
    ).pack(side="left")

    optimize_btn = ttk.Button(controls, text="Optimize", command=lambda: run_optimize())
    optimize_btn.pack(side="left", padx=12)
    optimize_btn.config(state="disabled")

    # ── token metrics panel (the review numbers) ────────────────────
    metrics = ttk.Labelframe(root, text="Token review", padding=(10, 6))
    metrics.pack(fill="x", padx=10, pady=(4, 0))

    raw_var = tk.StringVar(value="—")
    opt_var = tk.StringVar(value="—")
    saved_var = tk.StringVar(value="—")
    method_var = tk.StringVar(value="—")

    def _metric(col: int, title: str, var: tk.StringVar, color: str) -> None:
        cell = ttk.Frame(metrics)
        cell.grid(row=0, column=col, padx=18, sticky="w")
        ttk.Label(cell, text=title, foreground="#666").pack(anchor="w")
        tk.Label(cell, textvariable=var, font=("Segoe UI", 16, "bold"), fg=color).pack(
            anchor="w"
        )

    _metric(0, "Original tokens", raw_var, "#b00")
    _metric(1, "Optimized tokens", opt_var, "#0a5")
    _metric(2, "Tokens saved", saved_var, "#06c")
    _metric(3, "Counted via", method_var, "#555")

    # ── status bar ──────────────────────────────────────────────────
    stats_var = tk.StringVar(value="Choose a source (Document / JIRA / GitHub) to begin.")
    ttk.Label(root, textvariable=stats_var, padding=(12, 4), foreground="#0a5").pack(fill="x")

    # ── text panes ──────────────────────────────────────────────────
    panes = ttk.Panedwindow(root, orient="horizontal")
    panes.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _make_pane(title: str):
        frame = ttk.Labelframe(panes, text=title, padding=4)
        text = tk.Text(frame, wrap="word", font=("Consolas", 10), undo=False)
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        panes.add(frame, weight=1)
        return text

    original_box = _make_pane("Original")
    optimized_box = _make_pane("Optimized")

    # ── optimize action ─────────────────────────────────────────────
    def run_optimize() -> None:
        if not state["text"]:
            return
        summarize = summarize_var.get()
        text = state["text"]
        _run_bg(
            lambda: _optimize(text, summarize),
            _done,
            busy="Optimizing…",
        )

    def _optimize(text: str, summarize: bool):
        result = TextOptimizer(config).optimize(text, summarize=summarize)
        write_output(result, str(OUTPUT_FILE))
        return result

    def _done(result) -> None:
        _set_text(optimized_box, result.optimized_text)
        raw_var.set(f"{result.raw_tokens:,}")
        opt_var.set(f"{result.optimized_tokens:,}")
        saved_var.set(f"{result.tokens_saved:,}  ({result.reduction_pct:.1f}%)")
        method_labels = {
            "api": "API count_tokens",
            "tiktoken": "local tiktoken",
            "estimate": "local estimate",
        }
        method_var.set(method_labels.get(result.token_method, result.token_method))
        stats_var.set(
            f"Done. Stages: {', '.join(result.stages) or 'none'}   |   saved to: {OUTPUT_FILE.name}"
        )

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())
