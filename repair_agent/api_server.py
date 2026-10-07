#!/usr/bin/env python3
"""
RepairAgent API Server
Clean, lightweight server for Quick Debug and Local Folder Repair.
Run: python api_server.py
"""

import os
import sys
import json
import difflib
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS

SCRIPT_DIR = Path(__file__).parent.resolve()
FRONTEND_DIR = SCRIPT_DIR / "frontend"

# ---------------------------------------------------------------------------
# Load Configuration
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load config.json from the script directory."""
    cfg_path = SCRIPT_DIR / "config.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "version": "0.6.5",
        "api_port": 5050,
        "api_host": "0.0.0.0",
        "api_debug": True,
        "openai_models": [],
        "anthropic_models": [],
        "supported_languages": []
    }


CONFIG = _load_config()
API_PORT = int(CONFIG.get("api_port", 5050))
API_HOST = CONFIG.get("api_host", "0.0.0.0")

app = Flask(__name__, static_folder=None)
CORS(app)


# ---------------------------------------------------------------------------
# Frontend Static Serving
# ---------------------------------------------------------------------------

@app.route("/")
def serve_index():
    """Serve index.html with the correct api-port injected."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return "frontend/index.html not found", 404
    cfg = _load_config()
    port = int(cfg.get("api_port", 5050))
    html = index_path.read_text(encoding="utf-8")
    html = html.replace(
        '<meta name="api-port" content="5050" />',
        f'<meta name="api-port" content="{port}" />',
    )
    return Response(html, mimetype="text/html")


@app.route("/<path:filename>")
def serve_frontend_static(filename):
    """Serve CSS/JS/fonts/images safely from the frontend directory."""
    if filename.startswith("api/"):
        return "Not found", 404
    ALLOWED_EXTS = {".css", ".js", ".html", ".ico", ".png", ".jpg", ".jpeg",
                    ".svg", ".woff", ".woff2", ".ttf", ".webp", ".gif"}
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTS:
        return "Not found", 404
    safe = (FRONTEND_DIR / filename).resolve()
    if not str(safe).startswith(str(FRONTEND_DIR)):
        return "Forbidden", 403
    if safe.exists() and safe.is_file():
        return send_from_directory(str(FRONTEND_DIR), filename)
    return "Not found", 404


# ---------------------------------------------------------------------------
# Environment & Key Helpers
# ---------------------------------------------------------------------------

def _parse_dotenv(env_file: Path) -> dict:
    result = {}
    if not env_file.exists():
        return result
    for line in env_file.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _get_key_value(key_name: str) -> str:
    """Return the actual API key string from environment or .env file."""
    val = os.environ.get(key_name, "").strip()
    if val and val != "GLOBAL-API-KEY-PLACEHOLDER":
        return val
    env = _parse_dotenv(SCRIPT_DIR / ".env")
    v = env.get(key_name, "").strip()
    if v and v != "GLOBAL-API-KEY-PLACEHOLDER":
        return v
    return ""


import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# API Routes: Config, Models, Keys, Status
# ---------------------------------------------------------------------------

@app.route("/api/config", methods=["GET"])
def api_config():
    """Return the latest config.json."""
    return jsonify(_load_config())


@app.route("/api/status", methods=["GET"])
def api_status():
    """Check environment readiness and configured API keys."""
    has_gemini = bool(_get_key_value("GEMINI_API_KEY"))
    has_groq = bool(_get_key_value("GROQ_API_KEY"))
    has_openai = bool(_get_key_value("OPENAI_API_KEY"))
    has_anthropic = bool(_get_key_value("ANTHROPIC_API_KEY"))

    active_providers = []
    if has_gemini:
        active_providers.append("Gemini (Free)")
    if has_groq:
        active_providers.append("Groq (Free)")
    if has_openai:
        active_providers.append("OpenAI")
    if has_anthropic:
        active_providers.append("Anthropic")

    key_status = ", ".join(active_providers) if active_providers else "No API Key configured"

    checks = {
        "Python 3.10+": {
            "ok": sys.version_info >= (3, 10),
            "detail": f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
        "API Keys": {
            "ok": bool(active_providers),
            "detail": key_status,
        }
    }
    return jsonify({"checks": checks, "ready": bool(active_providers)})


@app.route("/api/models", methods=["GET"])
def api_models():
    """Return available models from config based on configured keys."""
    cfg = _load_config()
    has_gemini = bool(_get_key_value("GEMINI_API_KEY"))
    has_groq = bool(_get_key_value("GROQ_API_KEY"))
    has_openai = bool(_get_key_value("OPENAI_API_KEY"))
    has_anthropic = bool(_get_key_value("ANTHROPIC_API_KEY"))

    models = []
    if has_gemini:
        models.extend(cfg.get("gemini_models", []))
    if has_groq:
        models.extend(cfg.get("groq_models", []))
    if has_openai:
        models.extend(cfg.get("openai_models", []))
    if has_anthropic:
        models.extend(cfg.get("anthropic_models", []))

    # If no keys set, show free Gemini & Groq models first as suggestions
    if not models:
        models = (
            cfg.get("gemini_models", [])
            + cfg.get("groq_models", [])
            + cfg.get("openai_models", [])
            + cfg.get("anthropic_models", [])
        )

    return jsonify({
        "models": models,
        "has_gemini": has_gemini,
        "has_groq": has_groq,
        "has_openai": has_openai,
        "has_anthropic": has_anthropic
    })


@app.route("/api/keys", methods=["POST"])
def api_keys():
    """Save API keys into local .env file."""
    data = request.get_json() or {}
    gemini_key = data.get("gemini_key", "").strip()
    groq_key = data.get("groq_key", "").strip()
    openai_key = data.get("openai_key", "").strip()
    anthropic_key = data.get("anthropic_key", "").strip()

    env_file = SCRIPT_DIR / ".env"
    existing = _parse_dotenv(env_file)

    if gemini_key:
        existing["GEMINI_API_KEY"] = gemini_key
        os.environ["GEMINI_API_KEY"] = gemini_key
    if groq_key:
        existing["GROQ_API_KEY"] = groq_key
        os.environ["GROQ_API_KEY"] = groq_key
    if openai_key:
        existing["OPENAI_API_KEY"] = openai_key
        os.environ["OPENAI_API_KEY"] = openai_key
    if anthropic_key:
        existing["ANTHROPIC_API_KEY"] = anthropic_key
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key

    lines = [f"{k}={v}" for k, v in existing.items()]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return jsonify({"success": True, "saved": list(existing.keys())})


# ---------------------------------------------------------------------------
# Core LLM Engine & Provider Implementations
# ---------------------------------------------------------------------------

def _generate_unified_diff(original: str, modified: str, filename: str = "file") -> str:
    """Generate a clean unified diff string."""
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3,
    )
    return "".join(diff)


def _call_gemini(model: str, api_key: str, system_prompt: str, user_prompt: str) -> str:
    """Call Google Gemini API via REST with structured JSON mode."""
    candidates_models = [model]
    for fallback in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-1.5-pro"]:
        if fallback not in candidates_models:
            candidates_models.append(fallback)

    last_error = None
    for m_name in candidates_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"System Instructions:\n{system_prompt}\n\nTask:\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
                candidates = resp_body.get("candidates", [])
                if candidates:
                    return candidates[0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                msg = err_body
            last_error = f"Gemini API Error ({err.code}): {msg}"
            # If 404, try next model candidate
            if err.code == 404:
                continue
            raise RuntimeError(last_error)
        except Exception as err:
            last_error = str(err)
            continue

    raise RuntimeError(last_error or "Could not connect to Gemini API")


def _call_groq(model: str, api_key: str, system_prompt: str, user_prompt: str) -> str:
    """Call Groq Cloud API via REST (OpenAI-compatible) with JSON mode."""
    m_name = model if ("llama" in model or "mixtral" in model or "gemma" in model) else "llama-3.3-70b-versatile"
    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": m_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            return resp_body["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error", {}).get("message", err_body)
        except Exception:
            msg = err_body
        raise RuntimeError(f"Groq API Error ({err.code}): {msg}")


def _call_llm_json(model: str, system_prompt: str, user_prompt: str) -> dict:
    """Route LLM call to the appropriate provider (Gemini, Groq, Anthropic, OpenAI)."""
    # 1. Google Gemini
    if "gemini" in model.lower():
        api_key = _get_key_value("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "No Gemini API key configured. Get a free key at https://aistudio.google.com/apikey "
                "and paste it in the Settings & Keys tab."
            )
        raw = _call_gemini(model, api_key, system_prompt, user_prompt)

    # 2. Groq (Free fast inference)
    elif "llama" in model.lower() or "groq" in model.lower() or "mixtral" in model.lower():
        api_key = _get_key_value("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "No Groq API key configured. Get a free key at https://console.groq.com/keys "
                "and paste it in the Settings & Keys tab."
            )
        raw = _call_groq(model, api_key, system_prompt, user_prompt)

    # 3. Anthropic (Claude)
    elif "claude" in model.lower():
        api_key = _get_key_value("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "No Anthropic API key configured. Please configure your key in Settings."
            )
        try:
            import anthropic as anthropic_sdk
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

        client = anthropic_sdk.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = resp.content[0].text or ""

    # 4. OpenAI
    else:
        api_key = _get_key_value("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "No OpenAI API key configured. Please configure your key in Settings."
            )
        try:
            import openai as openai_sdk
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

        if hasattr(openai_sdk, "OpenAI"):
            client = openai_sdk.OpenAI(api_key=api_key)
            call_kwargs: dict = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=4096,
            )
            if any(tag in model for tag in ("gpt-4o", "gpt-3.5", "gpt-4-turbo", "gpt-4.1")):
                call_kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**call_kwargs)
            raw = resp.choices[0].message.content or ""
        else:
            openai_sdk.api_key = api_key
            call_kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=3000,
            )
            resp = openai_sdk.ChatCompletion.create(**call_kwargs)
            try:
                raw = resp.choices[0].message.content or ""
            except (AttributeError, TypeError):
                raw = resp["choices"][0]["message"]["content"] or ""

    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        return json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end+1])
        raise


# ---------------------------------------------------------------------------
# /api/debug  — Quick Code Debugger (type/paste any snippet)
# ---------------------------------------------------------------------------

@app.route("/api/debug", methods=["POST"])
def api_debug_code():
    """Debug arbitrary code snippet and return structured diagnostics."""
    data = request.get_json() or {}
    code = data.get("code", "").strip()
    language = data.get("language", "python")
    description = data.get("description", "").strip()
    model = data.get("model", "gpt-4o-mini")

    if not code:
        return jsonify({"error": "No code provided"}), 400

    system_prompt = (
        "You are an expert software debugger and code reviewer. "
        "Find ALL bugs in the given code, explain the root cause clearly, "
        "and provide the COMPLETE fixed code (the entire corrected code, not a snippet). "
        "Respond ONLY with a valid JSON object."
    )

    user_prompt = f"Debug the following {language} code.\n\n"
    user_prompt += f"## Code ({language})\n```\n{code}\n```\n\n"
    if description:
        user_prompt += f"## Problem Description / Notes\n{description}\n\n"

    user_prompt += (
        "## Required JSON Response Format\n"
        "{\n"
        '  "bugs_found": [\n'
        '    {\n'
        '      "line": <integer or null>,\n'
        '      "type": "<e.g. Off-by-one, Null Dereference, Memory Leak, Logic Error, Syntax Error>",\n'
        '      "severity": "<critical|high|medium|low>",\n'
        '      "description": "<concise one-sentence description>"\n'
        '    }\n'
        "  ],\n"
        '  "root_cause": "<single sentence summary of the underlying problem>",\n'
        '  "explanation": "<detailed explanation of what is wrong and why>",\n'
        '  "fixed_code": "<complete corrected source code — FULL code>",\n'
        '  "changes": [\n'
        '    {\n'
        '      "what": "<what was changed in the code>",\n'
        '      "why": "<why this change fixes the bug>"\n'
        '    }\n'
        "  ],\n"
        '  "confidence": "<high|medium|low>",\n'
        '  "additional_notes": "<optional suggestions>"\n'
        "}\n\n"
        "Respond with ONLY the JSON object above."
    )

    try:
        result = _call_llm_json(model, system_prompt, user_prompt)
        fixed_code = result.get("fixed_code", "")
        result["diff"] = _generate_unified_diff(code, fixed_code, f"snippet.{language}")
        result["model_used"] = model
        result["language"] = language
        result["original_code"] = code
        return jsonify(result)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Model returned non-JSON response: {exc}"}), 500
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# /api/project/scan — Local Folder Repair: Scan directory & suggest fixes
# ---------------------------------------------------------------------------

DEFAULT_CODE_EXTENSIONS = {
    ".cpp", ".hpp", ".cc", ".cxx", ".c", ".h",
    ".py", ".pyw",
    ".java",
    ".js", ".jsx", ".ts", ".tsx", ".mjs",
    ".rs", ".go", ".cs", ".rb", ".swift", ".kt", ".php", ".sh"
}

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "venv", ".venv", "env",
    "__pycache__", ".pytest_cache", ".idea", ".vscode", "build", "dist",
    "bin", "obj", "target", "out", ".repairagent_backups"
}

@app.route("/api/project/scan", methods=["POST"])
def api_project_scan():
    """Scan local directory files on laptop, analyze issues, output diffs."""
    data = request.get_json() or {}
    dir_path_str = data.get("directory", "").strip()
    instructions = data.get("instructions", "").strip()
    model = data.get("model", "gpt-4o-mini")
    custom_exts = data.get("extensions")

    if not dir_path_str:
        return jsonify({"error": "Directory path is required"}), 400

    target_dir = Path(dir_path_str).expanduser().resolve()
    if not target_dir.exists():
        return jsonify({"error": f"Directory not found: {target_dir}"}), 404
    if not target_dir.is_dir():
        return jsonify({"error": f"Path is not a directory: {target_dir}"}), 400

    allowed_exts = set(custom_exts) if custom_exts else DEFAULT_CODE_EXTENSIONS

    found_files = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in allowed_exts:
                try:
                    if p.stat().st_size <= 150_000:
                        rel = p.relative_to(target_dir).as_posix()
                        found_files.append((p, rel))
                except Exception:
                    continue

    if not found_files:
        return jsonify({
            "directory": str(target_dir),
            "total_files_scanned": 0,
            "files_with_issues": 0,
            "summary": "No matching source code files found in directory.",
            "issues": []
        })

    found_files = found_files[:20]

    file_payloads = []
    for p, rel in found_files:
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            file_payloads.append({"relative_path": rel, "content": content})
        except Exception:
            continue

    system_prompt = (
        "You are an expert autonomous software repair agent. "
        "Analyze the provided source code files from the user's local project. "
        "Identify bugs, errors, broken logic, memory issues, or requested improvements. "
        "For any file that needs fixing, provide the COMPLETE corrected source code. "
        "If a file has no bugs or requires no changes, do NOT include it in the issues list. "
        "Respond ONLY with a valid JSON object."
    )

    user_prompt = f"Project Directory: {target_dir}\n"
    if instructions:
        user_prompt += f"User Instructions / Problem Description: {instructions}\n\n"
    else:
        user_prompt += "Instructions: Find and fix all bugs, runtime errors, logic flaws, memory leaks, and compilation errors.\n\n"

    user_prompt += "Files in project:\n"
    for fp in file_payloads:
        user_prompt += f"\n--- FILE: {fp['relative_path']} ---\n```{fp['content']}\n```\n"

    user_prompt += (
        "\n## Required JSON Response Format\n"
        "{\n"
        '  "project_summary": "<summary of analysis and overall health of the codebase>",\n'
        '  "total_issues_count": <integer>,\n'
        '  "issues": [\n'
        '    {\n'
        '      "relative_path": "<exact relative path matching the file above>",\n'
        '      "severity": "<critical|high|medium|low>",\n'
        '      "problem": "<concise description of the bug found>",\n'
        '      "root_cause": "<underlying reason for the bug>",\n'
        '      "explanation": "<detailed explanation of what was wrong and how it was fixed>",\n'
        '      "fixed_code": "<the COMPLETE modified file contents — full source code, not snippets>",\n'
        '      "changes": [\n'
        '        {"what": "<specific code change>", "why": "<reason>"}\n'
        '      ]\n'
        '    }\n'
        '  ]\n'
        "}\n\n"
        "Respond ONLY with the JSON object."
    )

    try:
        res = _call_llm_json(model, system_prompt, user_prompt)
        issues = res.get("issues", [])

        orig_map = {fp["relative_path"]: fp["content"] for fp in file_payloads}
        valid_issues = []
        for issue in issues:
            rel = issue.get("relative_path")
            fixed_code = issue.get("fixed_code", "")
            orig_code = orig_map.get(rel, "")

            diff = _generate_unified_diff(orig_code, fixed_code, rel)
            issue["original_code"] = orig_code
            issue["diff"] = diff
            issue["has_diff"] = bool(diff.strip())
            if issue["has_diff"] or fixed_code != orig_code:
                valid_issues.append(issue)

        return jsonify({
            "directory": str(target_dir),
            "total_files_scanned": len(found_files),
            "files_with_issues": len(valid_issues),
            "summary": res.get("project_summary", "Analysis completed."),
            "issues": valid_issues
        })

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# /api/project/apply — 1-Click apply to disk with automatic backup
# ---------------------------------------------------------------------------

@app.route("/api/project/apply", methods=["POST"])
def api_project_apply():
    """Write accepted file fixes to disk and create safety backup."""
    data = request.get_json() or {}
    dir_path_str = data.get("directory", "").strip()
    files = data.get("files", [])

    if not dir_path_str:
        return jsonify({"error": "Directory path is required"}), 400
    if not files:
        return jsonify({"error": "No files to apply"}), 400

    target_dir = Path(dir_path_str).expanduser().resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        return jsonify({"error": f"Invalid directory: {target_dir}"}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = target_dir / ".repairagent_backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    applied = []
    errors = []

    for f_item in files:
        rel = f_item.get("relative_path", "").strip()
        fixed_code = f_item.get("fixed_code")
        if not rel or fixed_code is None:
            continue

        file_path = (target_dir / rel).resolve()
        if not str(file_path).startswith(str(target_dir)):
            errors.append({"file": rel, "error": "Invalid path traversal"})
            continue

        try:
            if file_path.exists():
                rel_backup = backup_dir / rel
                rel_backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, rel_backup)

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(fixed_code, encoding="utf-8")
            applied.append(rel)
        except Exception as exc:
            errors.append({"file": rel, "error": str(exc)})

    manifest = {
        "timestamp": timestamp,
        "applied_files": applied,
        "directory": str(target_dir)
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return jsonify({
        "success": len(applied) > 0,
        "applied_files": applied,
        "backup_timestamp": timestamp,
        "errors": errors
    })


# ---------------------------------------------------------------------------
# /api/project/revert — Revert modified files to backup
# ---------------------------------------------------------------------------

@app.route("/api/project/revert", methods=["POST"])
def api_project_revert():
    """Revert files to the latest backup snapshot."""
    data = request.get_json() or {}
    dir_path_str = data.get("directory", "").strip()
    timestamp = data.get("backup_timestamp", "").strip()
    files = data.get("files", [])

    if not dir_path_str:
        return jsonify({"error": "Directory path is required"}), 400

    target_dir = Path(dir_path_str).expanduser().resolve()
    backups_root = target_dir / ".repairagent_backups"
    if not backups_root.exists():
        return jsonify({"error": "No backups found for this directory"}), 404

    if not timestamp:
        backup_folders = sorted([d for d in backups_root.iterdir() if d.is_dir()])
        if not backup_folders:
            return jsonify({"error": "No backup snapshots available"}), 404
        backup_dir = backup_folders[-1]
    else:
        backup_dir = backups_root / timestamp

    if not backup_dir.exists():
        return jsonify({"error": f"Backup snapshot not found: {timestamp}"}), 404

    reverted = []
    errors = []

    if files:
        for f_item in files:
            rel = f_item if isinstance(f_item, str) else f_item.get("relative_path")
            if not rel:
                continue
            backup_file = backup_dir / rel
            target_file = target_dir / rel
            if backup_file.exists():
                try:
                    shutil.copy2(backup_file, target_file)
                    reverted.append(rel)
                except Exception as exc:
                    errors.append({"file": rel, "error": str(exc)})
    else:
        for root, _, bfiles in os.walk(backup_dir):
            for bf in bfiles:
                if bf == "manifest.json":
                    continue
                bp = Path(root) / bf
                rel = bp.relative_to(backup_dir).as_posix()
                tp = target_dir / rel
                try:
                    tp.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(bp, tp)
                    reverted.append(rel)
                except Exception as exc:
                    errors.append({"file": rel, "error": str(exc)})

    return jsonify({"success": len(reverted) > 0, "reverted_files": reverted, "errors": errors})


# ---------------------------------------------------------------------------
# Server Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cfg = _load_config()
    port = int(cfg.get("api_port", 5050))
    host = cfg.get("api_host", "0.0.0.0")
    debug = bool(cfg.get("api_debug", True))
    display_host = "localhost" if host in ("0.0.0.0", "") else host

    print("=" * 60)
    print(f"  RepairAgent Server  v{cfg.get('version', '0.6.5')}")
    print(f"  Serving UI & API at: http://{display_host}:{port}")
    print("=" * 60)
    app.run(debug=debug, host=host, port=port)
