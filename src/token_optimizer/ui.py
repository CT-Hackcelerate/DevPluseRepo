"""Desktop UI for the token optimizer — enterprise edition.

A dependency-free Tkinter application with a branded header, menu bar, themed
controls, KPI metric cards and a status bar. Three input sources:
  * **Document** — pick a .docx / .txt / .md file,
  * **JIRA** — connect with a base URL + email + API token and fetch issues by JQL,
  * **GitHub (Git)** — connect with a token and fetch a pull request (or all open PRs).

Whatever the source, the fetched text is optimized (deterministic reductions +
optional summarization), shown original-vs-optimized with a token review, written
to ``optimized_output.txt``, and logged to ``logs/``.

Connection fields fall back to your environment / .env when left blank.

Launch with ``tokenopt ui`` or ``python -m token_optimizer.ui``.
"""

from __future__ import annotations

import os
import threading
import webbrowser
from pathlib import Path

from .config import Config
from .integrations.document import SUPPORTED_EXTENSIONS, read_document
from .integrations.sources import build_config, fetch_github_text, fetch_jira_text
from .optimize.text_pipeline import TextOptimizer, write_output

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_FILE = _PROJECT_ROOT / "optimized_output.txt"
_DOCS_PDF = _PROJECT_ROOT / "documents" / "TokenOptimizer_Documentation.pdf"

APP_TITLE = "TokenOptimizer"
APP_TAGLINE = "Enterprise Token Optimization Console"

# ── enterprise palette ──────────────────────────────────────────────────────
BG = "#eef1f6"        # app background
SURFACE = "#ffffff"   # cards / panels
BORDER = "#d3dbe8"    # hairline borders
INK = "#16233a"       # primary text
MUTED = "#5f6b7d"     # secondary text
PRIMARY = "#1a5eb8"   # brand blue (buttons, accents)
PRIMARY_DARK = "#134a94"
HEADER_BG = "#12365c"  # deep navy header band
HEADER_FG = "#ffffff"
HEADER_SUB = "#b7c6da"
CHIP_BG = "#1d4a78"
DANGER = "#c0392b"
SUCCESS = "#1e8e4e"
INFO = "#1a5eb8"

FONT = ("Segoe UI", 10)
FONT_SM = ("Segoe UI", 9)
FONT_SEMI = ("Segoe UI Semibold", 10)
FONT_BRAND = ("Segoe UI Semibold", 18)
FONT_TAG = ("Segoe UI", 10)
FONT_METRIC = ("Segoe UI", 21, "bold")
FONT_METRIC_LBL = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 10)


def launch() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    config = Config()
    state: dict = {"text": ""}
    action_buttons: list = []

    root = tk.Tk()
    root.title(f"{APP_TITLE} — {APP_TAGLINE}")
    root.geometry("1200x920")
    root.minsize(980, 720)
    root.configure(bg=BG)

    # ── theme ───────────────────────────────────────────────────────────────
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=BG, foreground=INK, font=FONT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=INK, font=FONT)
    style.configure("Card.TLabel", background=SURFACE, foreground=INK)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_SM)
    style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED, font=FONT_SM)
    style.configure("CardHeading.TLabel", background=SURFACE, foreground=INK, font=FONT_SEMI)
    style.configure("TButton", font=FONT, padding=(12, 6))
    style.configure("Primary.TButton", background=PRIMARY, foreground="#ffffff",
                    font=FONT_SEMI, padding=(18, 8), borderwidth=0)
    style.map("Primary.TButton",
              background=[("active", PRIMARY_DARK), ("disabled", "#9fb2c9")],
              foreground=[("disabled", "#eef1f6")])
    style.configure("Secondary.TButton", background="#e4eaf3", foreground=INK,
                    padding=(14, 7), borderwidth=0)
    style.map("Secondary.TButton", background=[("active", "#d3ddec")])
    style.configure("TCheckbutton", background=SURFACE, foreground=INK, font=FONT)
    style.map("TCheckbutton", background=[("active", SURFACE)])
    style.configure("TNotebook", background=SURFACE, borderwidth=0, tabmargins=(6, 4, 6, 0))
    style.configure("TNotebook.Tab", padding=(20, 9), font=FONT, background="#dde4ef",
                    foreground=MUTED)
    style.map("TNotebook.Tab",
              background=[("selected", SURFACE)],
              foreground=[("selected", PRIMARY)],
              expand=[("selected", (1, 1, 1, 0))])
    style.configure("TEntry", fieldbackground=SURFACE, padding=5, relief="flat")
    style.configure("Card.TCheckbutton", background=SURFACE)
    style.map("Card.TCheckbutton", background=[("active", SURFACE)])
    style.configure("Brand.Horizontal.TProgressbar", troughcolor="#dce3ee",
                    background=PRIMARY, borderwidth=0)

    # ── shared helpers ────────────────────────────────────────────────────────
    def _card(parent, **pack_kw):
        """A white surface panel with a hairline border."""
        outer = tk.Frame(parent, bg=BORDER)  # 1px border via padding trick
        inner = ttk.Frame(outer, style="Card.TFrame", padding=12)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        outer.pack(**pack_kw)
        return inner

    def _field(parent, label, row, *, show=None, default="", width=46):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=2)
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=width, show=show).grid(
            row=row, column=1, sticky="we", pady=2)
        parent.columnconfigure(1, weight=1)
        return var

    def _set_text(widget, content: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)

    def _set_busy(busy: bool) -> None:
        for btn in action_buttons:
            btn.config(state="disabled" if busy else "normal")
        if busy:
            progress.pack(side="right", padx=(0, 4))
            progress.start(12)
        else:
            progress.stop()
            progress.pack_forget()
            optimize_btn.config(state="normal" if state["text"] else "disabled")

    def load_source(text: str, label: str) -> None:
        state["text"] = text
        state["label"] = label
        _set_text(original_box, text)
        _set_text(optimized_box, "")
        for var in (raw_var, opt_var, saved_var, method_var):
            var.set("—")
        optimize_btn.config(state="normal" if text else "disabled")
        if text:
            stats_var.set(f"{label} — {len(text):,} characters loaded. Optimizing…")
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

    # ── header band ────────────────────────────────────────────────────────────
    header = tk.Frame(root, bg=HEADER_BG)
    header.pack(fill="x")
    hleft = tk.Frame(header, bg=HEADER_BG)
    hleft.pack(side="left", padx=20, pady=14)
    # Logo mark: a rounded square with the initials.
    mark = tk.Label(hleft, text="T:O", bg=PRIMARY, fg="#ffffff",
                    font=("Segoe UI Semibold", 15), padx=10, pady=4)
    mark.pack(side="left", padx=(0, 12))
    htext = tk.Frame(hleft, bg=HEADER_BG)
    htext.pack(side="left")
    tk.Label(htext, text=APP_TITLE, bg=HEADER_BG, fg=HEADER_FG, font=FONT_BRAND).pack(anchor="w")
    tk.Label(htext, text=APP_TAGLINE, bg=HEADER_BG, fg=HEADER_SUB, font=FONT_TAG).pack(anchor="w")

    # Right side: operating-mode chip.
    if config.anthropic_api_key:
        mode_text, mode_color = "Mode: Claude API", "#2ecc71"
    elif config.local_model:
        mode_text, mode_color = "Mode: Local model", "#f1c40f"
    else:
        mode_text, mode_color = "Mode: Offline", "#8fb4e0"
    chip = tk.Frame(header, bg=CHIP_BG)
    chip.pack(side="right", padx=20, pady=18)
    tk.Label(chip, text="●", bg=CHIP_BG, fg=mode_color, font=("Segoe UI", 10)).pack(
        side="left", padx=(10, 4), pady=4)
    tk.Label(chip, text=mode_text, bg=CHIP_BG, fg="#ffffff", font=FONT_SM).pack(
        side="left", padx=(0, 12), pady=4)

    # ── menu bar ────────────────────────────────────────────────────────────────
    def _open_docs():
        if _DOCS_PDF.exists():
            webbrowser.open(_DOCS_PDF.as_uri())
        else:
            messagebox.showinfo(
                "Documentation",
                "Generate the PDF first:\n\npython scripts/generate_docs_pdf.py",
            )

    def _save_as():
        if not optimized_box.get("1.0", "end").strip():
            messagebox.showinfo("Nothing to save", "Optimize a source first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(optimized_box.get("1.0", "end").strip() + "\n")
            stats_var.set(f"Optimized text saved to: {path}")

    def _about():
        messagebox.showinfo(
            f"About {APP_TITLE}",
            f"{APP_TITLE}\n{APP_TAGLINE}\n\n"
            "Reduces the tokens sent to an LLM — fully offline when needed.\n"
            "Deterministic reductions + tiered summarization + per-run logging.",
        )

    menubar = tk.Menu(root)
    filemenu = tk.Menu(menubar, tearoff=0)
    filemenu.add_command(label="Open Document…", command=lambda: choose_file())
    filemenu.add_command(label="Save Optimized As…", command=_save_as)
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=root.destroy)
    menubar.add_cascade(label="File", menu=filemenu)
    helpmenu = tk.Menu(menubar, tearoff=0)
    helpmenu.add_command(label="Documentation (PDF)", command=_open_docs)
    helpmenu.add_command(label=f"About {APP_TITLE}", command=_about)
    menubar.add_cascade(label="Help", menu=helpmenu)
    root.config(menu=menubar)

    # ── body container: config on the left, review on the right ────────────────
    # Two columns so the (tall) config forms never steal vertical space from the
    # review panes — the panes fill the full window height independently.
    body = ttk.Frame(root, padding=(16, 14))
    body.pack(fill="both", expand=True)

    left = ttk.Frame(body, width=390)
    left.pack(side="left", fill="y", padx=(0, 14))
    left.pack_propagate(False)  # keep the config column at a fixed width

    right = ttk.Frame(body)
    right.pack(side="left", fill="both", expand=True)

    # -- Source card (notebook) --
    src_card = _card(left, fill="x")
    ttk.Label(src_card, text="1.  Select a data source", style="CardHeading.TLabel").pack(
        anchor="w", pady=(0, 8))
    sources = ttk.Notebook(src_card)
    sources.pack(fill="x")

    # Document tab
    doc_tab = ttk.Frame(sources, style="Card.TFrame", padding=14)
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

    doc_btn = ttk.Button(doc_tab, text="Select Document…", style="Secondary.TButton",
                         command=choose_file)
    doc_btn.grid(row=0, column=0, sticky="w")
    ttk.Label(doc_tab, textvariable=doc_path_var, style="CardMuted.TLabel").grid(
        row=0, column=1, sticky="w", padx=12)
    doc_tab.columnconfigure(1, weight=1)
    action_buttons.append(doc_btn)

    # JIRA tab
    jira_tab = ttk.Frame(sources, style="Card.TFrame", padding=14)
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

    jira_btn = ttk.Button(jira_tab, text="Connect & Fetch Issues", style="Secondary.TButton",
                          command=fetch_jira)
    jira_btn.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
    action_buttons.append(jira_btn)
    ttk.Label(jira_tab, text="Blank fields fall back to your .env values.",
              style="CardMuted.TLabel").grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # GitHub tab
    gh_tab = ttk.Frame(sources, style="Card.TFrame", padding=14)
    sources.add(gh_tab, text="  GitHub (Git)  ")
    gh_url_var = _field(gh_tab, "API URL", 0, default=config.github_api_url)
    gh_token_var = _field(gh_tab, "Token", 1, show="•")
    gh_owner_var = _field(gh_tab, "Owner", 2)
    gh_repo_var = _field(gh_tab, "Repository", 3)
    gh_number_var = _field(gh_tab, "PR number (blank = all open PRs)", 4, width=12)
    gh_diff_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(gh_tab, text="Include diff (deeper read, more tokens)",
                    variable=gh_diff_var, style="Card.TCheckbutton").grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

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
            lambda: fetch_github_text(cfg, owner, repo, number, include_diff=gh_diff_var.get()),
            lambda res: load_source(res[0], f"GitHub: {res[1]} PR(s)"),
            busy="Connecting to GitHub…",
        )

    gh_btn = ttk.Button(gh_tab, text="Connect & Fetch", style="Secondary.TButton",
                        command=fetch_github)
    gh_btn.grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 0))
    action_buttons.append(gh_btn)
    ttk.Label(gh_tab, text="Blank Token/URL fall back to your .env values.",
              style="CardMuted.TLabel").grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # -- Action card (options + optimize + progress) --
    act_card = _card(left, fill="x")
    act_card.pack_configure(pady=(12, 0))
    ttk.Label(act_card, text="2.  Optimize", style="CardHeading.TLabel").pack(
        anchor="w", pady=(0, 8))
    act_row = ttk.Frame(act_card, style="Card.TFrame")
    act_row.pack(fill="x")

    # Default ON when offline (extractive summary is free and gives the biggest
    # reduction). Default OFF when an API key is set so auto-optimize on load
    # doesn't spend cloud tokens without the user asking.
    summarize_var = tk.BooleanVar(value=not config.anthropic_api_key)
    if config.anthropic_api_key:
        summarize_label = "Summarize with Claude (Haiku)"
    elif config.local_model:
        summarize_label = "Summarize with local model"
    else:
        summarize_label = "Summarize (offline extractive — no API key)"
    # Stacked layout — the config column is narrow, so options sit above the button.
    ttk.Checkbutton(act_row, text=summarize_label, variable=summarize_var,
                    style="Card.TCheckbutton").pack(anchor="w")

    btn_row = ttk.Frame(act_card, style="Card.TFrame")
    btn_row.pack(fill="x", pady=(10, 0))
    optimize_btn = ttk.Button(btn_row, text="Optimize  ▸", style="Primary.TButton",
                              command=lambda: run_optimize())
    optimize_btn.pack(side="left")
    optimize_btn.config(state="disabled")

    progress = ttk.Progressbar(btn_row, mode="indeterminate", length=150,
                               style="Brand.Horizontal.TProgressbar")

    # -- KPI metric cards (top of the right column) --
    kpi_wrap = ttk.Frame(right)
    kpi_wrap.pack(fill="x")
    raw_var = tk.StringVar(value="—")
    opt_var = tk.StringVar(value="—")
    saved_var = tk.StringVar(value="—")
    method_var = tk.StringVar(value="—")

    def _metric_card(col: int, title: str, var: tk.StringVar, color: str) -> None:
        outer = tk.Frame(kpi_wrap, bg=BORDER)
        outer.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
        inner = tk.Frame(outer, bg=SURFACE)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        bar = tk.Frame(inner, bg=color, height=3)
        bar.pack(fill="x")
        pad = tk.Frame(inner, bg=SURFACE)
        pad.pack(fill="both", expand=True, padx=16, pady=(10, 12))
        tk.Label(pad, text=title.upper(), bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(pad, textvariable=var, bg=SURFACE, fg=color, font=FONT_METRIC).pack(anchor="w")
        kpi_wrap.columnconfigure(col, weight=1)

    _metric_card(0, "Original tokens", raw_var, DANGER)
    _metric_card(1, "Optimized tokens", opt_var, INFO)
    _metric_card(2, "Tokens saved", saved_var, SUCCESS)
    _metric_card(3, "Counted via", method_var, MUTED)

    # -- Text comparison panes (fill the rest of the right column) --
    panes_wrap = _card(right, fill="both", expand=True)
    panes_wrap.pack_configure(pady=(12, 0))
    ttk.Label(panes_wrap, text="3.  Review", style="CardHeading.TLabel").pack(
        anchor="w", pady=(0, 8))
    panes = ttk.Panedwindow(panes_wrap, orient="horizontal")
    panes.pack(fill="both", expand=True)

    def _make_pane(title: str, accent: str):
        outer = tk.Frame(panes, bg=BORDER)
        inner = tk.Frame(outer, bg=SURFACE)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        cap = tk.Frame(inner, bg=SURFACE)
        cap.pack(fill="x")
        tk.Frame(cap, bg=accent, width=4, height=20).pack(side="left", padx=(0, 8))
        tk.Label(cap, text=title, bg=SURFACE, fg=INK, font=FONT_SEMI).pack(
            side="left", pady=6)
        txt = tk.Text(inner, wrap="word", font=FONT_MONO, undo=False, relief="flat",
                      bg=SURFACE, fg=INK, padx=10, pady=8, borderwidth=0, height=12, width=40,
                      insertbackground=INK, highlightthickness=0)
        scroll = ttk.Scrollbar(inner, command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        panes.add(outer, weight=1)
        return txt

    original_box = _make_pane("Original", DANGER)
    optimized_box = _make_pane("Optimized", SUCCESS)

    # ── status bar ────────────────────────────────────────────────────────────
    statusbar = tk.Frame(root, bg="#dbe3ef")
    statusbar.pack(fill="x", side="bottom")
    stats_var = tk.StringVar(value="Ready. Choose a data source (Document / JIRA / GitHub) to begin.")
    tk.Label(statusbar, textvariable=stats_var, bg="#dbe3ef", fg=INK, font=FONT_SM,
             anchor="w", padx=14, pady=6).pack(side="left", fill="x", expand=True)
    tk.Label(statusbar, text=f"v{_app_version()}", bg="#dbe3ef", fg=MUTED, font=FONT_SM,
             padx=14).pack(side="right")

    # ── optimize action ────────────────────────────────────────────────────────
    def run_optimize() -> None:
        if not state["text"]:
            return
        summarize = summarize_var.get()
        text = state["text"]
        _run_bg(lambda: _optimize(text, summarize), _done, busy="Optimizing…")

    def _optimize(text: str, summarize: bool):
        from .run_log import log_run

        result = TextOptimizer(config).optimize(text, summarize=summarize)
        write_output(result, str(OUTPUT_FILE))
        state["log_path"] = log_run(
            command="ui",
            source={"type": "ui", "label": state.get("label", ""), "chars": len(text)},
            options={"summarize": bool(summarize)},
            result=result,
            config=config,
            output_path=str(OUTPUT_FILE),
        )
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
        log_note = ""
        if state.get("log_path"):
            log_note = f"   |   log: {os.path.basename(state['log_path'])}"
        tier = getattr(result, "summary_tier", "none")
        stats_var.set(
            f"Done in {getattr(result, 'duration_ms', 0):.0f} ms   |   "
            f"stages: {', '.join(result.stages) or 'none'}   |   tier: {tier}   |   "
            f"saved to: {OUTPUT_FILE.name}{log_note}"
        )

    root.mainloop()
    return 0


def _app_version() -> str:
    try:
        from importlib.metadata import version

        return version("token-optimizer")
    except Exception:
        return "0.1.0"


if __name__ == "__main__":
    raise SystemExit(launch())
