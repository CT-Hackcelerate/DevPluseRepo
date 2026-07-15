"""Desktop UI for the token optimizer — enterprise edition.

A dependency-free Tkinter application with a branded header, menu bar, themed
controls, KPI metric cards and a status bar. Three input sources:
  * **Document** — pick a .docx / .txt / .md file,
  * **JIRA** — connect with a base URL + email + API token and fetch issues by JQL,
  * **GitHub (Git)** — connect with a token and fetch a pull request (or all open PRs).

Whatever the source, the fetched text is optimized (deterministic reductions +
optional summarization), shown original-vs-optimized with a token review, written
to ``optimized_output.txt``, and logged to ``logs/``.

A second top-level tab, **Feature-Dev Skills**, exposes the token-optimisation
skills in-app (2-column card grid on the left, result console on the right): PRD
compression (Skill 1), codebase ``file:line`` anchoring (Skill 2a),
complexity-based model routing (Skill 2b), and the 8-case / 2-BU A/B validation
suite. A third **Dashboard** tab renders the A/B results as native bar charts
(cost & quality per case) with KPI tiles and a one-click interactive HTML export.

Connection fields fall back to your environment / .env when left blank.

Launch with ``tokenopt ui`` or ``python -m token_optimizer.ui``.
"""

from __future__ import annotations

import os
import threading
import webbrowser
from pathlib import Path

from ..core.config import Config
from ..integrations.document import SUPPORTED_EXTENSIONS, read_document
from ..integrations.sources import build_config, fetch_github_text, fetch_jira_text
from ..optimize.text_pipeline import TextOptimizer, write_output

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_FILE = _PROJECT_ROOT / "optimized_output.txt"
_DOCS_PDF = _PROJECT_ROOT / "docs" / "TokenOptimizer_Documentation.pdf"

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
    # The API key present at launch (env / .env), captured before any UI override so
    # clearing the in-app field reverts to it rather than to nothing.
    env_api_key = config.anthropic_api_key

    root = tk.Tk()
    root.title(f"{APP_TITLE} — {APP_TAGLINE}")
    # Size to fit the usable display so content never runs behind the taskbar or
    # off the screen edge. winfo_screenheight over-reports (it ignores the taskbar),
    # so subtract a generous margin; the 1x4 skill row is fixed-height and the
    # result console absorbs the slack, so the layout stays fully visible without
    # scrolling even on short / scaled monitors.
    win_w = min(1280, root.winfo_screenwidth() - 60)
    win_h = min(900, root.winfo_screenheight() - 120)
    root.geometry(f"{win_w}x{win_h}+16+8")
    root.minsize(min(960, win_w), min(640, win_h))
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
    hleft.pack(side="left", padx=20, pady=9)
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
    chip.pack(side="right", padx=20, pady=12)
    mode_dot = tk.Label(chip, text="●", bg=CHIP_BG, fg=mode_color, font=("Segoe UI", 10))
    mode_dot.pack(side="left", padx=(10, 4), pady=4)
    mode_lbl = tk.Label(chip, text=mode_text, bg=CHIP_BG, fg="#ffffff", font=FONT_SM)
    mode_lbl.pack(side="left", padx=(0, 12), pady=4)

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
    helpmenu.add_command(label="▶  Guided Demo (auto tour)", command=lambda: _play_demo())
    helpmenu.add_separator()
    helpmenu.add_command(label="Documentation (PDF)", command=_open_docs)
    helpmenu.add_command(label=f"About {APP_TITLE}", command=_about)
    menubar.add_cascade(label="Help", menu=helpmenu)
    root.config(menu=menubar)

    # ── body container: config on the left, review on the right ────────────────
    # Two columns so the (tall) config forms never steal vertical space from the
    # review panes — the panes fill the full window height independently.
    body = ttk.Frame(root, padding=(16, 14))
    body.pack(fill="both", expand=True)

    # Top-level tabs: the classic optimizer, and the feature-dev skills console
    # (PRD compression, codebase anchoring, model routing, A/B validation).
    main_nb = ttk.Notebook(body)
    main_nb.pack(fill="both", expand=True)

    optimize_tab = ttk.Frame(main_nb, style="TFrame", padding=(4, 10))
    main_nb.add(optimize_tab, text="  Token Optimizer  ")
    skills_tab = ttk.Frame(main_nb, style="TFrame", padding=(4, 10))
    main_nb.add(skills_tab, text="  Feature-Dev Skills  ")
    dash_tab = ttk.Frame(main_nb, style="TFrame", padding=(4, 10))
    main_nb.add(dash_tab, text="  Dashboard  ")
    main_nb.enable_traversal()  # Ctrl+Tab / Ctrl+Shift+Tab switch tabs

    left = ttk.Frame(optimize_tab, width=390)
    left.pack(side="left", fill="y", padx=(0, 14))
    left.pack_propagate(False)  # keep the config column at a fixed width

    right = ttk.Frame(optimize_tab)
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

    # Optional Claude API key — lets the user opt into AI-model optimization
    # (Haiku summarization + exact token counts) for a more effective result.
    ttk.Label(doc_tab, text="Anthropic API key", style="Card.TLabel").grid(
        row=1, column=0, sticky="w", pady=(12, 2))
    doc_api_key_var = tk.StringVar(value="")
    ttk.Entry(doc_tab, textvariable=doc_api_key_var, show="•").grid(
        row=1, column=1, sticky="we", padx=12, pady=(12, 2))
    ttk.Label(
        doc_tab,
        text="Optional — enables Claude (Haiku) summarization and exact token counts "
             "for a more effective result. Leave blank to stay fully offline; a key set "
             "in your .env is used automatically.",
        style="CardMuted.TLabel", wraplength=430, justify="left",
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

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
    # Stacked layout — the config column is narrow, so options sit above the button.
    summarize_chk = ttk.Checkbutton(act_row, variable=summarize_var,
                                    style="Card.TCheckbutton")
    summarize_chk.pack(anchor="w")

    def _effective_api_key() -> str:
        """The key actually used: the UI field if filled, else the env / .env key."""
        return doc_api_key_var.get().strip() or env_api_key

    def _refresh_mode(*_args) -> None:
        """Reflect the effective key in the summarize label and the header mode chip."""
        if _effective_api_key():
            summarize_chk.config(text="Summarize with Claude (Haiku)")
            mode_dot.config(fg="#2ecc71")
            mode_lbl.config(text="Mode: Claude API")
        elif config.local_model:
            summarize_chk.config(text="Summarize with local model")
            mode_dot.config(fg="#f1c40f")
            mode_lbl.config(text="Mode: Local model")
        else:
            summarize_chk.config(text="Summarize (offline extractive — no API key)")
            mode_dot.config(fg="#8fb4e0")
            mode_lbl.config(text="Mode: Offline")

    # Update the label/chip live as the user types or clears the key.
    doc_api_key_var.trace_add("write", _refresh_mode)
    _refresh_mode()

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

    # ══ Feature-Dev Skills tab ══════════════════════════════════════════════════
    # The token-optimisation skills that match the customer ask, viewable in-app:
    # PRD compression (Skill 1), codebase anchoring (2a), model routing (2b), and
    # the A/B validation suite + dashboard. Each runs off the main thread.
    skills_state: dict = {"prd": ""}

    # Layout: all four skill cards in a 2-column grid on the LEFT half of the
    # window; the shared result console fills the RIGHT half. Charts/KPIs live on
    # the separate Dashboard tab.
    sk_content = ttk.Frame(skills_tab)
    sk_content.pack(fill="both", expand=True)
    sk_content.columnconfigure(0, weight=1, uniform="sk_half")
    sk_content.columnconfigure(1, weight=1, uniform="sk_half")
    sk_content.rowconfigure(0, weight=1)

    sk_left = ttk.Frame(sk_content)
    sk_left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
    for _i in (0, 1):
        sk_left.columnconfigure(_i, weight=1, uniform="sk_col")
        sk_left.rowconfigure(_i, weight=1, uniform="sk_row")
    cell_s1 = ttk.Frame(sk_left)
    cell_s1.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
    cell_s2 = ttk.Frame(sk_left)
    cell_s2.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
    cell_s3 = ttk.Frame(sk_left)
    cell_s3.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
    cell_s4 = ttk.Frame(sk_left)
    cell_s4.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))

    sk_right = ttk.Frame(sk_content)
    sk_right.grid(row=0, column=1, sticky="nsew")
    res_card = _card(sk_right, fill="both", expand=True)
    ttk.Label(res_card, text="Result", style="CardHeading.TLabel").pack(anchor="w", pady=(0, 8))
    skills_out = tk.Text(res_card, wrap="word", font=FONT_MONO, relief="flat",
                         bg=SURFACE, fg=INK, padx=10, pady=8, borderwidth=0,
                         height=12, highlightthickness=0)
    _skills_scroll = ttk.Scrollbar(res_card, command=skills_out.yview)
    skills_out.configure(yscrollcommand=_skills_scroll.set, state="disabled")
    _skills_scroll.pack(side="right", fill="y")
    skills_out.pack(side="left", fill="both", expand=True)

    def _skills_print(content: str) -> None:
        skills_out.config(state="normal")
        skills_out.delete("1.0", "end")
        skills_out.insert("1.0", content)
        skills_out.config(state="disabled")

    # -- Skill 1: PRD compression --
    c1 = _card(cell_s1, fill="both", expand=True)
    ttk.Label(c1, text="Skill 1 · PRD Compression", style="CardHeading.TLabel").pack(
        anchor="w", pady=(0, 4))
    ttk.Label(c1, text="Compresses PRD input ~67% into structured requirement atoms.",
              style="CardMuted.TLabel", wraplength=260, justify="left").pack(
        anchor="w", pady=(0, 8))
    prd_path_var = tk.StringVar(value="No PRD selected.")
    b1row = ttk.Frame(c1, style="Card.TFrame")
    b1row.pack(fill="x")
    prd_btn = ttk.Button(b1row, text="Select PRD…", style="Secondary.TButton",
                         command=lambda: choose_prd())
    prd_btn.pack(side="left")
    compress_btn = ttk.Button(b1row, text="Compress PRD  ▸", style="Primary.TButton",
                              command=lambda: do_compress())
    compress_btn.pack(side="left", padx=(8, 0))
    compress_btn.config(state="disabled")
    ttk.Label(c1, textvariable=prd_path_var, style="CardMuted.TLabel",
              wraplength=260).pack(anchor="w", pady=(8, 0))

    def choose_prd() -> None:
        filetypes = [
            ("Documents", " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(title="Select a PRD", filetypes=filetypes)
        if not path:
            return
        try:
            text = read_document(path)
        except Exception as exc:
            messagebox.showerror("Could not read PRD", str(exc))
            return
        skills_state["prd"] = text
        prd_path_var.set(path)
        compress_btn.config(state="normal")

    def do_compress() -> None:
        text = skills_state.get("prd", "")
        if not text:
            return

        def work():
            from ..skills.prd.compressor import compress_prd
            return compress_prd(text)

        def ok(r) -> None:
            _skills_print(
                "PRD COMPRESSION (Skill 1)\n" + "=" * 52 + "\n"
                f"raw: {r.raw_tokens} tokens   ->   compressed: {r.compressed_tokens} tokens\n"
                f"saved {r.tokens_saved} tokens  ({r.reduction_pct:.1f}% smaller)\n"
                f"{len(r.atoms)} requirement atoms kept, {r.dropped_units} units dropped\n\n"
                + r.compressed_text
            )
            stats_var.set(
                f"PRD compressed: {r.reduction_pct:.1f}% smaller "
                f"({r.raw_tokens}->{r.compressed_tokens} tok)"
            )

        _run_bg(work, ok, busy="Compressing PRD…")

    # -- Skill 2b: model router --
    c2 = _card(cell_s2, fill="both", expand=True)
    ttk.Label(c2, text="Skill 2b · Model Router", style="CardHeading.TLabel").pack(
        anchor="w", pady=(0, 4))
    ttk.Label(c2, text="Routes each task to the cheapest capable model by complexity.",
              style="CardMuted.TLabel", wraplength=260, justify="left").pack(
        anchor="w", pady=(0, 8))
    task_var = tk.StringVar()
    ttk.Entry(c2, textvariable=task_var).pack(fill="x")
    route_btn = ttk.Button(c2, text="Route Task  ▸", style="Primary.TButton",
                           command=lambda: do_route())
    route_btn.pack(anchor="w", pady=(8, 0))

    def do_route() -> None:
        task = task_var.get().strip()
        if not task:
            messagebox.showwarning("Task required", "Enter a task description to route.")
            return

        def work():
            from ..skills.router.router import RouterConfig, route_task
            return route_task(task, RouterConfig())

        def ok(rt) -> None:
            cls = rt.classification
            up = "  (upgraded to premium: low confidence)" if rt.upgraded else ""
            _skills_print(
                "MODEL ROUTING (Skill 2b)\n" + "=" * 52 + "\n"
                f"task:        {rt.task}\n\n"
                f"complexity:  {rt.complexity.value}\n"
                f"confidence:  {rt.confidence:.2f}{up}\n"
                f"model:       {rt.model}\n\n"
                f"signals:     {cls.signals if cls else {}}"
            )
            stats_var.set(f"Routed: {rt.complexity.value} -> {rt.model}")

        _run_bg(work, ok, busy="Routing task…")

    action_buttons.append(route_btn)

    # -- Skill 2a: codebase anchoring --
    c3 = _card(cell_s3, fill="both", expand=True)
    ttk.Label(c3, text="Skill 2a · Codebase Anchoring", style="CardHeading.TLabel").pack(
        anchor="w", pady=(0, 4))
    ttk.Label(c3, text="Anchors plan steps to real file:line refs; flags hallucinations.",
              style="CardMuted.TLabel", wraplength=260, justify="left").pack(
        anchor="w", pady=(0, 8))
    repo_var = tk.StringVar(value=str(_PROJECT_ROOT / "src"))
    rrow = ttk.Frame(c3, style="Card.TFrame")
    rrow.pack(fill="x")
    ttk.Label(rrow, text="Repo:", style="Card.TLabel").pack(side="left", padx=(0, 6))
    ttk.Entry(rrow, textvariable=repo_var).pack(side="left", fill="x", expand=True)
    plan_txt = tk.Text(c3, height=2, wrap="word", font=FONT_MONO, relief="flat",
                       bg="#f4f7fb", fg=INK, padx=8, pady=6, highlightthickness=1,
                       highlightbackground=BORDER, insertbackground=INK)
    plan_txt.pack(fill="both", expand=True, pady=(8, 0))
    plan_txt.insert("1.0", "Call compress_prd on the PRD text\n"
                    "Use build_index to index the repository\n")
    anchor_btn = ttk.Button(c3, text="Anchor Plan  ▸", style="Primary.TButton",
                            command=lambda: do_anchor())
    anchor_btn.pack(anchor="w", pady=(8, 0))

    def do_anchor() -> None:
        steps = [ln.strip() for ln in plan_txt.get("1.0", "end").splitlines() if ln.strip()]
        repo = repo_var.get().strip() or "."
        if not steps:
            messagebox.showwarning("Plan required", "Enter at least one plan step.")
            return

        def work():
            from ..skills.anchor.anchor import anchor_plan, anchoring_accuracy
            from ..skills.anchor.indexer import build_index
            index = build_index(repo)
            anchors = anchor_plan(steps, index)
            return len(index), anchors, anchoring_accuracy(anchors)

        def ok(res) -> None:
            nsym, anchors, acc = res
            unresolved = sum(1 for a in anchors if a.unresolved_terms)
            lines = [
                "CODEBASE ANCHORING (Skill 2a)\n" + "=" * 52,
                f"indexed {nsym} symbols in {repo}",
                f"anchoring accuracy {acc * 100:.0f}%   |   "
                f"{unresolved} step(s) with unresolved refs\n",
            ]
            lines.extend(a.render() for a in anchors)
            _skills_print("\n".join(lines))
            stats_var.set(
                f"Anchored {len(anchors)} step(s): {acc * 100:.0f}% accuracy, "
                f"{unresolved} unresolved"
            )

        _run_bg(work, ok, busy="Indexing & anchoring…")

    action_buttons.append(anchor_btn)

    # -- Validation: A/B suite (text summary here; charts on the Dashboard tab) --
    c4 = _card(cell_s4, fill="both", expand=True)
    ttk.Label(c4, text="Validation · A/B Suite", style="CardHeading.TLabel").pack(
        anchor="w", pady=(0, 4))
    ttk.Label(c4, text="Baseline vs optimised across 8 cases / 2 BUs.",
              style="CardMuted.TLabel", wraplength=260, justify="left").pack(
        anchor="w", pady=(0, 8))
    ab_row = ttk.Frame(c4, style="Card.TFrame")
    ab_row.pack(fill="x")
    ab_btn = ttk.Button(ab_row, text="Run A/B Suite  ▸", style="Primary.TButton",
                        command=lambda: do_ab())
    ab_btn.pack(side="left")
    charts_btn = ttk.Button(ab_row, text="Charts  ▸", style="Secondary.TButton",
                            command=lambda: main_nb.select(dash_tab))
    charts_btn.pack(side="left", padx=(8, 0))

    def do_ab() -> None:
        def work():
            from ..skills.anchor.indexer import build_index
            from ..evaluation.ab_runner import run_ab_suite
            from ..evaluation.datasets import sample_cases
            index = build_index(str(_PROJECT_ROOT / "src"))
            return run_ab_suite(sample_cases(), index)

        def ok(summ) -> None:
            lines = [summ.summary(), "", "per-case:"]
            lines.extend("  " + r.summary() for r in summ.results)
            _skills_print("\n".join(lines))
            stats_var.set(
                f"A/B: {summ.avg_cost_savings_pct:.0f}% saved, "
                f"quality {summ.avg_optimised_quality:.1f}/25"
            )

        _run_bg(work, ok, busy="Running A/B suite…")

    action_buttons.append(ab_btn)

    # ══ Dashboard tab ═══════════════════════════════════════════════════════════
    # Visual A/B results: KPI tiles + native bar charts (cost & quality per case),
    # plus a button to open the full interactive HTML dashboard in a browser.
    dsh_state: dict = {"summary": None, "loaded": False}

    dsh_top = ttk.Frame(dash_tab)
    dsh_top.pack(fill="x", pady=(0, 10))
    ttk.Label(dsh_top, text="A/B Validation — baseline vs optimised (8 cases / 2 BUs)",
              style="TLabel", font=FONT_SEMI).pack(side="left")
    dsh_run_btn = ttk.Button(dsh_top, text="Run A/B & Refresh  ▸", style="Primary.TButton",
                             command=lambda: do_dash_run())
    dsh_run_btn.pack(side="right")
    dsh_html_btn = ttk.Button(dsh_top, text="Open HTML Dashboard", style="Secondary.TButton",
                              command=lambda: do_dash_html())
    dsh_html_btn.pack(side="right", padx=(0, 8))

    dsh_kpi = ttk.Frame(dash_tab)
    dsh_kpi.pack(fill="x", pady=(0, 12))
    dsh_save = tk.StringVar(value="—")
    dsh_comp = tk.StringVar(value="—")
    dsh_qual = tk.StringVar(value="—")
    dsh_tok = tk.StringVar(value="—")

    def _dsh_card(col: int, title: str, var: tk.StringVar, color: str) -> None:
        outer = tk.Frame(dsh_kpi, bg=BORDER)
        outer.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
        inner = tk.Frame(outer, bg=SURFACE)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(inner, bg=color, height=3).pack(fill="x")
        pad = tk.Frame(inner, bg=SURFACE)
        pad.pack(fill="both", expand=True, padx=16, pady=(8, 10))
        tk.Label(pad, text=title.upper(), bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(pad, textvariable=var, bg=SURFACE, fg=color,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        dsh_kpi.columnconfigure(col, weight=1)

    _dsh_card(0, "Avg cost saved", dsh_save, SUCCESS)
    _dsh_card(1, "Avg PRD compression", dsh_comp, INFO)
    _dsh_card(2, "Avg quality (optimised)", dsh_qual, PRIMARY)
    _dsh_card(3, "Total tokens saved", dsh_tok, MUTED)

    charts_wrap = ttk.Frame(dash_tab)
    charts_wrap.pack(fill="both", expand=True)
    charts_wrap.columnconfigure(0, weight=1, uniform="ch")
    charts_wrap.columnconfigure(1, weight=1, uniform="ch")
    charts_wrap.rowconfigure(0, weight=1)

    def _chart_card(col: int, title: str):
        cell = ttk.Frame(charts_wrap)
        cell.grid(row=0, column=col, sticky="nsew", padx=(0, 6) if col == 0 else (6, 0))
        card = _card(cell, fill="both", expand=True)
        ttk.Label(card, text=title, style="CardHeading.TLabel").pack(anchor="w", pady=(0, 6))
        canvas = tk.Canvas(card, bg=SURFACE, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        return canvas

    cost_canvas = _chart_card(0, "Cost per feature request ($) — lower is better")
    qual_canvas = _chart_card(1, "Plan quality (/25) — higher is better")

    def _draw_chart(canvas, series, y_max, value_fmt, cats) -> None:
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 60 or h < 60:
            return
        ml, mr, mt, mb = 42, 12, 22, 56
        pw, ph = w - ml - mr, h - mt - mb
        base = mt + ph
        for i in range(5):
            yy = base - ph * i / 4
            canvas.create_line(ml, yy, w - mr, yy, fill="#e6e9f0")
            canvas.create_text(ml - 6, yy, text=value_fmt(y_max * i / 4), anchor="e",
                               fill=MUTED, font=("Segoe UI", 7))
        # legend (top-left)
        lx = ml
        for label, color, _vals in series:
            canvas.create_rectangle(lx, 4, lx + 9, 13, fill=color, outline="")
            canvas.create_text(lx + 13, 9, text=label, anchor="w", fill=MUTED,
                               font=("Segoe UI", 7))
            lx += 22 + len(label) * 6
        n = len(series)
        bandw = pw / max(1, len(cats))
        colw = min(16.0, (bandw * 0.72 - (n - 1) * 2) / n)
        groupw = n * colw + (n - 1) * 2
        for ci, cat in enumerate(cats):
            bx = ml + ci * bandw
            gx = bx + (bandw - groupw) / 2
            for si, (_label, color, vals) in enumerate(series):
                v = vals[ci]
                bh = (v / y_max) * ph if y_max else 0
                x = gx + si * (colw + 2)
                canvas.create_rectangle(x, base - bh, x + colw, base, fill=color, outline="")
            canvas.create_text(bx + bandw / 2, base + 6, text=cat, anchor="e", angle=32,
                               fill=MUTED, font=("Segoe UI", 7))

    def _redraw_charts(_evt=None) -> None:
        summ = dsh_state["summary"]
        if summ is None:
            for cv, msg in ((cost_canvas, "Click “Run A/B & Refresh” to draw the cost chart."),
                            (qual_canvas, "Click “Run A/B & Refresh” to draw the quality chart.")):
                cv.delete("all")
                w, h = cv.winfo_width(), cv.winfo_height()
                if w > 60:
                    cv.create_text(w / 2, h / 2, text=msg, fill=MUTED, font=FONT_SM)
            return
        cats = [r.name for r in summ.results]
        _draw_chart(
            cost_canvas,
            [("Baseline", INFO, [r.baseline.cost_usd for r in summ.results]),
             ("Optimised", SUCCESS, [r.optimised.cost_usd for r in summ.results])],
            max([r.baseline.cost_usd for r in summ.results] + [1e-9]) * 1.15,
            lambda v: f"${v:.3f}", cats,
        )
        _draw_chart(
            qual_canvas,
            [("Baseline", INFO, [float(r.baseline.quality.total) for r in summ.results]),
             ("Optimised", SUCCESS, [float(r.optimised.quality.total) for r in summ.results])],
            25.0, lambda v: f"{v:.0f}", cats,
        )

    cost_canvas.bind("<Configure>", _redraw_charts)
    qual_canvas.bind("<Configure>", _redraw_charts)

    def do_dash_run() -> None:
        def work():
            from ..skills.anchor.indexer import build_index
            from ..evaluation.ab_runner import run_ab_suite
            from ..evaluation.datasets import sample_cases
            from ..skills.prd.compressor import compress_prd
            index = build_index(str(_PROJECT_ROOT / "src"))
            summ = run_ab_suite(sample_cases(), index)
            by_name = {c.name: c for c in sample_cases()}
            raw = comp = 0
            for r in summ.results:
                cr = compress_prd(by_name[r.name].prd)
                raw += cr.raw_tokens
                comp += cr.compressed_tokens
            overall = 100.0 * (raw - comp) / raw if raw else 0.0
            return summ, overall

        def ok(res) -> None:
            summ, overall = res
            dsh_state["summary"] = summ
            dsh_save.set(f"{summ.avg_cost_savings_pct:.0f}%")
            dsh_comp.set(f"{overall:.0f}%")
            dsh_qual.set(f"{summ.avg_optimised_quality:.1f} / 25")
            dsh_tok.set(f"{summ.total_tokens_saved:,}")
            _redraw_charts()
            stats_var.set(
                f"Dashboard updated: {summ.avg_cost_savings_pct:.0f}% saved, "
                f"quality {summ.avg_optimised_quality:.1f}/25"
            )

        _run_bg(work, ok, busy="Running A/B suite…")

    def do_dash_html() -> None:
        def work():
            from ..evaluation.dashboard import write_dashboard
            return write_dashboard(str(_PROJECT_ROOT / "ab_dashboard.html"),
                                   repo=str(_PROJECT_ROOT / "src"))

        def ok(path) -> None:
            webbrowser.open(Path(path).as_uri())
            stats_var.set(f"HTML dashboard opened: {os.path.basename(path)}")

        _run_bg(work, ok, busy="Building HTML dashboard…")

    action_buttons.append(dsh_run_btn)

    # Auto-run the suite the first time the Dashboard tab is opened.
    def _on_tab_changed(_evt=None) -> None:
        if main_nb.select() == str(dash_tab) and not dsh_state["loaded"]:
            dsh_state["loaded"] = True
            do_dash_run()

    main_nb.bind("<<NotebookTabChanged>>", _on_tab_changed)

    # ── optimize action ────────────────────────────────────────────────────────
    def run_optimize() -> None:
        if not state["text"]:
            return
        # Apply the effective API key (UI field, else .env) on the main thread so a
        # user-supplied key turns on Claude summarization + exact token counts.
        config.anthropic_api_key = _effective_api_key()
        summarize = summarize_var.get()
        text = state["text"]
        _run_bg(lambda: _optimize(text, summarize), _done, busy="Optimizing…")

    def _optimize(text: str, summarize: bool):
        from ..core.run_log import log_run

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

    # ══ Guided Demo (Help → Guided Demo) ════════════════════════════════════════
    # An automated, video-style walkthrough: it advances on a timer, switches tabs,
    # runs each feature live, and narrates in an on-top caption box with playback
    # controls. Everything it drives is already defined above.
    def _play_demo() -> None:
        existing = state.get("demo_win")
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return

        sample_prd = (
            "Executive Summary\n\nThis document restates a lot of background at length. "
            "As mentioned, it is important and verbose on purpose.\n\n"
            "Requirements\n"
            "- The system must automatically retry a failed charge up to 3 times.\n"
            "- Each retry must be idempotent so a customer is never double-charged.\n"
            "- Acceptance criteria: Given a transient error, when a charge fails, then "
            "the system should retry with the same idempotency key.\n\n"
            "Out of scope\n- We will not change the refund flow.\n"
        )

        def act_doc():
            try:
                sources.select(doc_tab)
            except Exception:
                pass

        def act_sources():
            try:
                sources.select(jira_tab)
            except Exception:
                pass

        def act_compress():
            skills_state["prd"] = sample_prd
            prd_path_var.set("(demo sample PRD)")
            compress_btn.config(state="normal")
            do_compress()

        def act_route():
            task_var.set("redesign the auth architecture for concurrency and race conditions")
            do_route()

        # (tab, title, narration, action-or-None)
        scenes = [
            (optimize_tab, "Welcome to TokenOptimizer",
             "This quick auto-tour walks through every tab and feature. It advances on "
             "its own — use Prev/Next to step, Pause to hold, or Close to exit. There "
             "are three tabs: Token Optimizer, Feature-Dev Skills, and Dashboard.", None),
            (optimize_tab, "Menus — File & Help",
             "File offers Open Document and Save Optimized As. Help offers this Guided "
             "Demo, the Documentation (PDF), and About. Everything is also available on "
             "the command line via the 'tokenopt' command.", None),
            (optimize_tab, "Tab 1 · Token Optimizer",
             "Pick a data source and the text is optimized on load — deterministic "
             "reductions plus an optional summary — shrinking tokens before they ever "
             "reach the model.", act_doc),
            (optimize_tab, "Data sources",
             "Three sources: a Document (.docx / .txt / .md), JIRA (fetch issues by a "
             "JQL query), or GitHub (a single PR or all open PRs). Blank connection "
             "fields fall back to your .env values.", act_sources),
            (optimize_tab, "Optimize & Review",
             "The Summarize checkbox adds a summary pass. KPI cards show Original / "
             "Optimized / Saved % / Counted-via, and the panes show Original vs "
             "Optimized text side by side.", act_doc),
            (skills_tab, "Tab 2 · Feature-Dev Skills",
             "Four skill cards in two columns on the left, with a shared result console "
             "on the right — the token-optimisation skills for feature development.", None),
            (skills_tab, "Skill 1 · PRD Compression",
             "Compresses a verbose PRD into dense requirement atoms (~67% fewer tokens), "
             "keeping acceptance criteria verbatim. Watch the result console on the "
             "right fill in.", act_compress),
            (skills_tab, "Skill 2b · Model Router",
             "Classifies a task by complexity and routes it to the cheapest capable "
             "model — here a complex task routes to Opus, with the signals shown.", act_route),
            (skills_tab, "Skill 2a · Codebase Anchoring",
             "Anchors each plan step to a real file:line reference and flags unresolved "
             "symbols as possible hallucinations. Press 'Anchor Plan' to try it.", None),
            (skills_tab, "Validation · A/B Suite",
             "Runs 8 feature requests across 2 business units, baseline vs optimised. "
             "The 'Charts' button jumps to the Dashboard tab.", None),
            (dash_tab, "Tab 3 · Dashboard",
             "KPI tiles and native charts (cost & quality per case). It auto-runs the "
             "A/B suite the first time you open it, so the savings and quality appear "
             "at a glance. 'Open HTML Dashboard' exports an interactive report.", None),
            (optimize_tab, "That's the tour!",
             "Reopen anytime from Help → Guided Demo. Full docs are in Help → "
             "Documentation (PDF), and the CLI mirrors every feature. Happy optimizing!", None),
        ]

        SCENE_MS, TICK = 7000, 100
        st = {"i": 0, "paused": False, "after": None, "prog": 0.0}

        dw = tk.Toplevel(root)
        state["demo_win"] = dw
        dw.title("Guided Demo — TokenOptimizer")
        dw.transient(root)
        dw.attributes("-topmost", True)
        dw.resizable(False, False)
        root.update_idletasks()
        w = min(760, max(560, root.winfo_width() - 80))
        h = 224
        x = root.winfo_rootx() + (root.winfo_width() - w) // 2
        y = root.winfo_rooty() + root.winfo_height() - h - 28
        # Keep the whole caption (incl. its control row) on-screen on short displays.
        y = min(y, root.winfo_screenheight() - h - 70)
        dw.geometry(f"{w}x{h}+{max(x, 20)}+{max(y, 40)}")

        bar = tk.Frame(dw, bg=HEADER_BG)
        bar.pack(fill="x")
        counter_var = tk.StringVar(value="")
        tk.Label(bar, text="●  Guided Demo", bg=HEADER_BG, fg="#6fd19a",
                 font=FONT_SEMI).pack(side="left", padx=(12, 8), pady=8)
        tk.Label(bar, textvariable=counter_var, bg=HEADER_BG, fg=HEADER_SUB,
                 font=FONT_SM).pack(side="left", pady=8)

        body = tk.Frame(dw, bg=SURFACE)
        body.pack(fill="both", expand=True)
        title_var = tk.StringVar()
        text_var = tk.StringVar()
        tk.Label(body, textvariable=title_var, bg=SURFACE, fg=PRIMARY,
                 font=("Segoe UI Semibold", 13), anchor="w", justify="left").pack(
            fill="x", padx=16, pady=(12, 2))
        tk.Label(body, textvariable=text_var, bg=SURFACE, fg=INK, font=FONT, anchor="nw",
                 justify="left", wraplength=w - 34).pack(fill="both", expand=True, padx=16)

        pbar = ttk.Progressbar(dw, mode="determinate", maximum=100,
                               style="Brand.Horizontal.TProgressbar")
        pbar.pack(fill="x")

        ctl = tk.Frame(dw, bg=SURFACE)
        ctl.pack(fill="x", pady=(6, 10))
        pause_var = tk.StringVar(value="⏸  Pause")

        def close():
            if st["after"]:
                try:
                    dw.after_cancel(st["after"])
                except Exception:
                    pass
            state["demo_win"] = None
            dw.destroy()

        def show(i):
            if i >= len(scenes):
                close()
                return
            i = max(0, i)
            st["i"], st["prog"] = i, 0.0
            pbar["value"] = 0
            tab, title, text, action = scenes[i]
            try:
                main_nb.select(tab)
                if action:
                    action()
            except Exception:
                pass
            counter_var.set(f"Step {i + 1} of {len(scenes)}")
            title_var.set(title)
            text_var.set(text)

        def tick():
            if not dw.winfo_exists():
                return
            if not st["paused"]:
                st["prog"] += TICK / SCENE_MS
                pbar["value"] = min(100, st["prog"] * 100)
                if st["prog"] >= 1.0:
                    goto(st["i"] + 1)
                    return
            st["after"] = dw.after(TICK, tick)

        def goto(i):
            if st["after"]:
                try:
                    dw.after_cancel(st["after"])
                except Exception:
                    pass
                st["after"] = None
            show(i)
            if dw.winfo_exists():
                st["after"] = dw.after(TICK, tick)

        def toggle_pause():
            st["paused"] = not st["paused"]
            pause_var.set("▶  Play" if st["paused"] else "⏸  Pause")

        def _btn(parent, text, cmd, primary=False):
            return tk.Button(
                parent, text=text, command=cmd, relief="flat", font=FONT_SM,
                padx=10, pady=4, cursor="hand2",
                bg=PRIMARY if primary else "#e4eaf3", fg="#ffffff" if primary else INK,
                activebackground=PRIMARY_DARK if primary else "#d3ddec",
                activeforeground="#ffffff" if primary else INK,
            )

        _btn(ctl, "✕  Close", close).pack(side="right", padx=(6, 12))
        _btn(ctl, "Next  ▶", lambda: goto(st["i"] + 1), primary=True).pack(side="right", padx=6)
        tk.Button(ctl, textvariable=pause_var, command=toggle_pause, relief="flat",
                  font=FONT_SM, padx=10, pady=4, cursor="hand2", bg="#e4eaf3", fg=INK,
                  activebackground="#d3ddec").pack(side="right", padx=6)
        _btn(ctl, "◀  Prev", lambda: goto(st["i"] - 1)).pack(side="right", padx=6)

        dw.protocol("WM_DELETE_WINDOW", close)
        goto(0)

    # Optional launch hook: open straight to a given tab (handy for demos/tests).
    _tab = os.environ.get("TOKENOPT_UI_TAB", "").lower()
    if _tab in ("skills", "feature-dev", "2"):
        main_nb.select(skills_tab)
    elif _tab in ("dashboard", "dash", "3"):
        main_nb.select(dash_tab)

    # Optional: auto-start the guided demo (Help → Guided Demo).
    if os.environ.get("TOKENOPT_UI_DEMO", "").lower() in ("1", "true", "yes"):
        root.after(500, _play_demo)

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
