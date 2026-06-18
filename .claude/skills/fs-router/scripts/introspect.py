#!/usr/bin/env python3
"""fs-introspect-repo — deterministic project scan for fs-router.

Equivalent of bmad-ticket-validate's router.py — no LLM here. The LLM
takes the structured JSON we return and turns it into the conversational
"I see your Next.js 16 app at apps/web…" restate that fs-router step 3
needs.

What it detects:
  - Framework: Next.js / Vite / Express / FastAPI / Django / Rails /
    SvelteKit / Remix / Nuxt / Astro / unknown. By package.json deps,
    pyproject.toml deps, Gemfile, etc.
  - Existing SDK usage that matches the intent (stripe-node usage,
    paddle-billing imports, resend-node, clerk, etc.)
  - Package manager + lockfile (npm/pnpm/yarn/bun, pip/uv/poetry,
    bundler, cargo).
  - App-router vs pages-router (Next.js).
  - Env file presence (.env, .env.example, .env.local).
  - Rough size — file count + top 5 languages.

Output: JSON to stdout. Exit 0 on success, non-zero on fatal errors.
Designed to be < 5 seconds even on large repos (skips node_modules,
.git, .next, etc.).

Usage:
  python3 introspect.py --target /path/to/repo --intent "add stripe checkout"
  python3 introspect.py                          # defaults: cwd + ""
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── intent → spec slug mapping (rough; the actual routing happens
# server-side via /api/mcp/route — we only use this to know WHICH SDK
# patterns to look for in the user's code)
_INTENT_TO_SDK_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "stripe": [
        ("stripe", r"\bimport\s+\w+\s+from\s+['\"]stripe['\"]"),
        ("stripe", r"\brequire\(['\"]stripe['\"]\)"),
        ("stripe", r"stripe\.(customers|paymentIntents|charges|subscriptions|webhooks)\."),
        ("stripe", r"\bSTRIPE_SECRET_KEY\b"),
    ],
    "paddle": [
        ("paddle", r"@paddle/paddle-(node|js)"),
        ("paddle", r"\bPADDLE_API_KEY\b"),
        ("paddle", r"paddle\.(transactions|subscriptions|prices)\."),
    ],
    "polar": [
        ("polar", r"@polar-sh/sdk"),
        ("polar", r"\bPOLAR_(ACCESS|API)_TOKEN\b"),
    ],
    "resend": [
        ("resend", r"\bfrom\s+['\"]resend['\"]"),
        ("resend", r"\bRESEND_API_KEY\b"),
        ("resend", r"resend\.emails\.send"),
    ],
    "sendgrid": [
        ("sendgrid", r"@sendgrid/mail"),
        ("sendgrid", r"\bSENDGRID_API_KEY\b"),
    ],
    "clerk": [
        ("clerk", r"@clerk/(nextjs|clerk-sdk|nestjs)"),
        ("clerk", r"\bCLERK_(SECRET|PUBLISHABLE)_KEY\b"),
    ],
    "twilio": [
        ("twilio", r"\bfrom\s+['\"]twilio['\"]"),
        ("twilio", r"\bTWILIO_(ACCOUNT_SID|AUTH_TOKEN)\b"),
    ],
    "openai": [
        ("openai", r"\bfrom\s+['\"]openai['\"]"),
        ("openai", r"openai\.(chat|completions|embeddings)\."),
        ("openai", r"\bOPENAI_API_KEY\b"),
    ],
}

# Dirs we never traverse (size + irrelevance + secrets)
_SKIP_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", ".svelte-kit", ".astro",
    "dist", "build", "out", ".turbo", ".vercel", "venv", ".venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", "target", ".cargo",
    "_bmad", "_bmad-output", ".bmad-tmp", "vendor", ".gradle",
    ".idea", ".vscode", ".cursor",
}

# Source-code-ish extensions (for the SDK regex scan)
_SCAN_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".rb", ".go", ".rs", ".java", ".kt",
    ".env", ".env.example", ".env.local",
}

# Language counter — extensions we recognize
_LANG_BY_EXT = {
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".py": "Python", ".rb": "Ruby", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".swift": "Swift",
    ".html": "HTML", ".css": "CSS", ".scss": "Sass",
    ".sql": "SQL", ".sh": "Shell",
}


def _walk_files(root: Path, limit: int = 5000):
    """Yield (path, rel) for every interesting file, up to `limit`."""
    count = 0
    for path in root.rglob("*"):
        if count >= limit:
            return
        if not path.is_file():
            continue
        # skip dirs by name (rglob doesn't prune, we filter)
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        # skip any dir starting with '.tmp-' or '_tmp' (scratch dirs)
        if any(part.startswith(".tmp-") or part.startswith("_tmp") for part in path.parts):
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        yield path, rel
        count += 1


def detect_framework(root: Path) -> dict:
    """Return {name, version, app_router?, indicators}."""
    out = {"name": "unknown", "version": None, "indicators": []}
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
            out["indicators"].append("package.json")
            # Order matters — more specific first
            if "next" in deps:
                out["name"] = "Next.js"
                out["version"] = deps["next"]
                # App router vs pages router
                if (root / "app").is_dir() or (root / "src" / "app").is_dir():
                    out["app_router"] = True
                elif (root / "pages").is_dir() or (root / "src" / "pages").is_dir():
                    out["app_router"] = False
            elif "@remix-run/react" in deps or "remix" in deps:
                out["name"] = "Remix"
                out["version"] = deps.get("@remix-run/react") or deps.get("remix")
            elif "@sveltejs/kit" in deps:
                out["name"] = "SvelteKit"
                out["version"] = deps["@sveltejs/kit"]
            elif "nuxt" in deps:
                out["name"] = "Nuxt"
                out["version"] = deps["nuxt"]
            elif "astro" in deps:
                out["name"] = "Astro"
                out["version"] = deps["astro"]
            elif "express" in deps:
                out["name"] = "Express"
                out["version"] = deps["express"]
            elif "fastify" in deps:
                out["name"] = "Fastify"
                out["version"] = deps["fastify"]
            elif "hono" in deps:
                out["name"] = "Hono"
                out["version"] = deps["hono"]
            elif "react" in deps:
                out["name"] = "React (raw, no framework)"
                out["version"] = deps["react"]
            elif "vue" in deps:
                out["name"] = "Vue (raw)"
                out["version"] = deps["vue"]
        except Exception:
            pass

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        out["indicators"].append("pyproject.toml")
        try:
            text = pyproject.read_text(encoding="utf-8")
            if re.search(r'fastapi\s*=', text, re.IGNORECASE):
                out["name"] = "FastAPI"
            elif re.search(r'django\s*=', text, re.IGNORECASE):
                out["name"] = "Django"
            elif re.search(r'flask\s*=', text, re.IGNORECASE):
                out["name"] = "Flask"
        except Exception:
            pass

    if (root / "Gemfile").exists():
        out["indicators"].append("Gemfile")
        out["name"] = "Ruby (likely Rails)"
    if (root / "config.ru").exists():
        out["indicators"].append("config.ru")
        if out["name"] == "unknown":
            out["name"] = "Rack"
    if (root / "Cargo.toml").exists():
        out["indicators"].append("Cargo.toml")
        if out["name"] == "unknown":
            out["name"] = "Rust"

    return out


def detect_package_manager(root: Path) -> dict:
    """Return {name, lockfile}."""
    candidates = [
        ("pnpm", "pnpm-lock.yaml"),
        ("bun", "bun.lockb"),
        ("yarn", "yarn.lock"),
        ("npm", "package-lock.json"),
        ("uv", "uv.lock"),
        ("poetry", "poetry.lock"),
        ("pip", "requirements.txt"),
        ("bundler", "Gemfile.lock"),
        ("cargo", "Cargo.lock"),
    ]
    for name, lockfile in candidates:
        if (root / lockfile).exists():
            return {"name": name, "lockfile": lockfile}
    return {"name": "unknown", "lockfile": None}


def _intent_to_targets(intent: str) -> list[str]:
    """Map free-form intent to the SDK slugs we should look for."""
    intent_low = (intent or "").lower()
    hits = []
    for slug in _INTENT_TO_SDK_PATTERNS:
        if slug in intent_low:
            hits.append(slug)
    # If no specific slug found, scan for ALL known SDKs (might catch
    # something the user didn't mention — useful context).
    return hits if hits else list(_INTENT_TO_SDK_PATTERNS.keys())


def scan_sdk_usage(root: Path, intent: str) -> dict:
    """Walk source files, look for SDK patterns matching the intent."""
    targets = _intent_to_targets(intent)
    patterns: list[tuple[str, re.Pattern]] = []
    for t in targets:
        for slug, pat in _INTENT_TO_SDK_PATTERNS.get(t, []):
            patterns.append((slug, re.compile(pat)))

    found: dict[str, list[str]] = {}  # slug → list of relative file paths
    for path, rel in _walk_files(root):
        if path.suffix not in _SCAN_EXTS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for slug, pat in patterns:
            if pat.search(text):
                found.setdefault(slug, []).append(str(rel))
                break  # one hit per file is enough

    return {
        "intent_targets": targets,
        "found_sdks": {slug: sorted(set(paths))[:10] for slug, paths in found.items()},
    }


def scan_env_files(root: Path) -> dict:
    """Note presence of common env files (don't read their contents)."""
    candidates = [".env", ".env.local", ".env.example", ".env.development", ".env.production"]
    present = [c for c in candidates if (root / c).exists()]
    return {"present": present}


def language_breakdown(root: Path, limit: int = 5000) -> dict:
    counts: dict[str, int] = {}
    total = 0
    for path, _ in _walk_files(root, limit=limit):
        lang = _LANG_BY_EXT.get(path.suffix)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
            total += 1
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {"total_source_files": total, "top": [{"lang": l, "count": n} for l, n in top]}


def main():
    ap = argparse.ArgumentParser(description="fs-router repo introspection helper")
    ap.add_argument("--target", default=".", help="Path to scan (default: cwd)")
    ap.add_argument("--intent", default="", help="User's free-form intent — drives which SDKs we look for")
    ap.add_argument("--max-files", type=int, default=5000, help="Cap on files walked")
    args = ap.parse_args()

    root = Path(args.target).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {root}"}), file=sys.stderr)
        sys.exit(2)

    result = {
        "target": str(root),
        "intent": args.intent,
        "framework": detect_framework(root),
        "package_manager": detect_package_manager(root),
        "env_files": scan_env_files(root),
        "sdk_scan": scan_sdk_usage(root, args.intent),
        "language": language_breakdown(root, limit=args.max_files),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
