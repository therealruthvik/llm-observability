#!/usr/bin/env python3
"""Pre-deploy checklist. Exit code 1 = fail."""

import ast
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

PASS = "\033[32m[PASS]\033[0m"
FAIL = "\033[31m[FAIL]\033[0m"
WARN = "\033[33m[WARN]\033[0m"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"{PASS} {label}")
    else:
        print(f"{FAIL} {label}" + (f": {detail}" if detail else ""))
        failures.append(label)


def warn(label: str, detail: str = "") -> None:
    print(f"{WARN} {label}" + (f": {detail}" if detail else ""))


print("\n=== LLM Observability Preflight ===\n")

# 1. Syntax check all Python sources
src_files = list(Path("src").rglob("*.py"))
syntax_ok = True
for f in src_files:
    try:
        ast.parse(f.read_text())
    except SyntaxError as e:
        check(f"Syntax: {f}", False, str(e))
        syntax_ok = False
if syntax_ok:
    check(f"Syntax check ({len(src_files)} files)", True)

# 2. Dependency conflict check — scoped to our packages only
our_packages = set()
req_path = Path("requirements.txt")
if req_path.exists():
    for line in req_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pkg = re.split(r"[>=<!;\[]", line)[0].strip().lower().replace("-", "_")
            our_packages.add(pkg)

result = subprocess.run(
    [sys.executable, "-m", "pip", "check"],
    capture_output=True,
    text=True,
)
our_conflicts = [
    ln for ln in result.stdout.splitlines()
    if any(p in ln.lower().replace("-", "_") for p in our_packages)
]
check("Dependency conflicts (our packages)", not our_conflicts, "; ".join(our_conflicts))

# 3. Key imports
for pkg in ["fastapi", "prometheus_client", "anthropic", "openai", "google.genai"]:
    try:
        importlib.import_module(pkg)
        check(f"Import: {pkg}", True)
    except ImportError as e:
        check(f"Import: {pkg}", False, str(e))

# 4. Config module loads
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("cost_calculator", "src/observer/cost_calculator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    check("Config module: cost_calculator", True)
except Exception as e:
    check("Config module: cost_calculator", False, str(e))

# 5. Required env vars
required_vars = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]

dotenv_path = Path(".env")
if dotenv_path.exists():
    for line in dotenv_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

for var in required_vars:
    val = os.environ.get(var, "")
    check(f"Env var: {var}", bool(val), "not set or empty")

# 6. No deprecated model names in config files
deprecated = ["gpt-4", "claude-2", "claude-instant", "text-davinci", "gemini-pro-vision"]
config_files = list(Path(".").rglob("*.py")) + list(Path(".").rglob("*.yml")) + list(Path(".").rglob("*.yaml"))
found_deprecated = False
for f in config_files:
    if ".git" in str(f) or ".venv" in str(f):
        continue
    try:
        content = f.read_text()
        for d in deprecated:
            # word-boundary match: "gpt-4" must not be followed by alphanumeric (avoids "gpt-4o")
            pattern = re.escape(d) + r'(?![a-zA-Z0-9])'
            if re.search(pattern, content):
                warn(f"Deprecated model name '{d}' in {f}")
                found_deprecated = True
    except Exception:
        pass
if not found_deprecated:
    check("No deprecated model names", True)

# 7. LLM clients not instantiated at import time
agent_file = Path("src/agents/demo_agents.py")
if agent_file.exists():
    content = agent_file.read_text()
    module_level_inits = [
        "anthropic.AsyncAnthropic()" in content.split("def ")[0],
        "AsyncOpenAI()" in content.split("def ")[0],
        "genai.GenerativeModel(" in content.split("def ")[0],
    ]
    check("Lazy LLM client init", not any(module_level_inits))
else:
    warn("agents/demo_agents.py not found — skipping lazy-init check")

# 8. Ignore files exist and cover heavyweight artifacts
for fname, required_exclusions in [
    (".dockerignore", [".env", ".venv", "__pycache__"]),
    (".gitignore", [".env", ".venv", "__pycache__"]),
]:
    p = Path(fname)
    if not p.exists():
        check(f"{fname} exists", False)
        continue
    content = p.read_text()
    missing = [e for e in required_exclusions if e not in content]
    check(f"{fname} covers artifacts", not missing, f"missing: {missing}")

print("\n=== Result ===\n")
if failures:
    print(f"{FAIL} {len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
else:
    print(f"{PASS} All checks passed. Safe to deploy.")
    sys.exit(0)
