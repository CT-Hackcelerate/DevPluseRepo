"""Repository indexer — extract symbols with real ``file:line`` locations.

A lightweight, dependency-free indexer (no tree-sitter / ctags required). It
walks a directory, reads source files, and extracts top-level and nested symbol
definitions with the exact line number they occur on. Python gets an AST-based
pass (accurate); other languages fall back to language-specific regexes.

The index maps a symbol *name* to one or more ``CodeSymbol`` locations, so the
anchoring step can resolve a plan reference like "the auth service" to a real
``src/services/auth.py:142``.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field

# Extensions we attempt to index, and the regex fallback per family.
_REGEX_DEFS: dict[str, list[re.Pattern]] = {
    ".js": [
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
        re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)"),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
    ],
    ".ts": [
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
        re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"),
        re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)"),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
    ],
    ".java": [
        re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?class\s+([A-Za-z_]\w*)"),
        re.compile(r"^\s*(?:public|private|protected)\s+[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\("),
    ],
    ".go": [
        re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"),
        re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+struct"),
    ],
    ".rb": [
        re.compile(r"^\s*def\s+([A-Za-z_]\w*[!?]?)"),
        re.compile(r"^\s*class\s+([A-Za-z_]\w*)"),
    ],
    ".cs": [
        re.compile(r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?class\s+([A-Za-z_]\w*)"),
        re.compile(r"^\s*(?:public|private|protected|internal)\s+[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\("),
    ],
}
# TS uses the JS family too where sensible; map .tsx/.jsx/.mjs.
_REGEX_DEFS[".tsx"] = _REGEX_DEFS[".ts"]
_REGEX_DEFS[".jsx"] = _REGEX_DEFS[".js"]
_REGEX_DEFS[".mjs"] = _REGEX_DEFS[".js"]

_INDEXABLE = {".py", *_REGEX_DEFS.keys()}

# Directories that are never worth indexing.
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".tokenopt_cache", ".mypy_cache", ".pytest_cache", ".idea", ".vscode",
    "target", "bin", "obj",
}


@dataclass(frozen=True)
class CodeSymbol:
    """A single definition anchored to a real location."""

    name: str
    kind: str          # "function" | "class" | "method" | "interface" | ...
    path: str          # repo-relative path with forward slashes
    line: int          # 1-based line number

    @property
    def anchor(self) -> str:
        return f"{self.path}:{self.line}"

    def render(self) -> str:
        return f"{self.kind} {self.name} @ {self.anchor}"


@dataclass
class CodebaseIndex:
    """A searchable index of symbols across a repository."""

    root: str
    symbols: list[CodeSymbol] = field(default_factory=list)
    _by_name: dict[str, list[CodeSymbol]] = field(default_factory=dict, repr=False)

    def add(self, symbol: CodeSymbol) -> None:
        self.symbols.append(symbol)
        self._by_name.setdefault(symbol.name.lower(), []).append(symbol)

    def lookup(self, name: str) -> list[CodeSymbol]:
        """Exact (case-insensitive) name lookup."""
        return list(self._by_name.get(name.lower(), []))

    def search(self, term: str, limit: int = 5) -> list[CodeSymbol]:
        """Fuzzy substring/token search over symbol names.

        Ranks exact matches first, then prefix, then substring, so the most
        specific anchor is offered before looser guesses.
        """
        term_l = term.lower()
        exact: list[CodeSymbol] = []
        prefix: list[CodeSymbol] = []
        substr: list[CodeSymbol] = []
        for sym in self.symbols:
            name_l = sym.name.lower()
            if name_l == term_l:
                exact.append(sym)
            elif name_l.startswith(term_l):
                prefix.append(sym)
            elif term_l in name_l:
                substr.append(sym)
        return (exact + prefix + substr)[:limit]

    def __len__(self) -> int:
        return len(self.symbols)


def _rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def _index_python(source: str, rel_path: str) -> list[CodeSymbol]:
    """AST-based Python symbol extraction (accurate line numbers)."""
    out: list[CodeSymbol] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out

    def visit(node: ast.AST, in_class: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if in_class else "function"
                out.append(CodeSymbol(child.name, kind, rel_path, child.lineno))
                visit(child, in_class=False)
            elif isinstance(child, ast.ClassDef):
                out.append(CodeSymbol(child.name, "class", rel_path, child.lineno))
                visit(child, in_class=True)
            else:
                visit(child, in_class)

    visit(tree, in_class=False)
    return out


def _index_regex(source: str, rel_path: str, ext: str) -> list[CodeSymbol]:
    """Regex-based symbol extraction for non-Python files."""
    out: list[CodeSymbol] = []
    patterns = _REGEX_DEFS.get(ext, [])
    for lineno, line in enumerate(source.splitlines(), start=1):
        for pat in patterns:
            m = pat.match(line)
            if m:
                kind = "class" if "class" in pat.pattern else (
                    "interface" if "interface" in pat.pattern else "function"
                )
                out.append(CodeSymbol(m.group(1), kind, rel_path, lineno))
                break
    return out


def build_index(root: str, *, max_file_bytes: int = 1_000_000) -> CodebaseIndex:
    """Walk ``root`` and build a symbol index of all supported source files."""
    index = CodebaseIndex(root=root)
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk doesn't descend into them.
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _INDEXABLE:
                continue
            full = os.path.join(dirpath, fname)
            try:
                if os.path.getsize(full) > max_file_bytes:
                    continue
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    source = fh.read()
            except OSError:
                continue
            rel_path = _rel(root, full)
            if ext == ".py":
                syms = _index_python(source, rel_path)
            else:
                syms = _index_regex(source, rel_path, ext)
            for sym in syms:
                index.add(sym)
    return index
