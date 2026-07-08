"""
ChefMate-Agent — API Routes

All AI communication is server-side via REST — no browser SDKs required.

Endpoints
---------
  POST /api/chat        — send a user message, receive AI text back as JSON
  POST /api/chat/clear  — reset the server-side Orchestrate thread
  GET  /api/health      — liveness probe
  GET  /api/debug       — live connectivity test (checks .env + IAM + all 7 strategies)
"""

import logging
from flask import Blueprint, request, jsonify
from services.orchestrate_service import orchestrate_service, get_iam_token, _safe_text
from utils.helpers import sanitize_input, build_error_response, build_success_response
import requests as _requests

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

@api_bp.route("/chat", methods=["POST"])
def chat():
    """
    Request body (JSON):
        { "message": "<user text>", "conversation_id": "<optional id>" }

    Success response (200):
        {
            "success":    true,
            "response":   "<AI text>",
            "thread_id":  "<Orchestrate thread id>",
            "timestamp":  "..."
        }

    Error response (400 / 502):
        {
            "success": false,
            "error":   "<detailed error — includes IBM status, code, message, URL, body>",
            "timestamp": "..."
        }
    """
    body            = request.get_json(silent=True) or {}
    raw_message     = body.get("message", "")
    conversation_id = body.get("conversation_id", "default")

    if not raw_message or not raw_message.strip():
        return jsonify(build_error_response("Message cannot be empty.", 400)[0]), 400

    clean_message = sanitize_input(raw_message)
    result        = orchestrate_service.send_message(clean_message, conversation_id)

    if result["success"]:
        return jsonify(
            build_success_response({
                "response":  result["response"],
                "thread_id": result.get("thread_id"),
            })
        ), 200

    # Surface the full IBM error string to the browser for easy debugging
    error_msg = result.get("error") or "An unexpected error occurred."
    return jsonify(build_error_response(error_msg, 502)[0]), 502


# ---------------------------------------------------------------------------
# POST /api/chat/clear
# ---------------------------------------------------------------------------

@api_bp.route("/chat/clear", methods=["POST"])
def clear_chat():
    """
    Drop the cached Orchestrate thread for *conversation_id*.
    The next message will create a brand-new thread.
    """
    body            = request.get_json(silent=True) or {}
    conversation_id = body.get("conversation_id", "default")
    orchestrate_service.clear_session(conversation_id)
    return jsonify(build_success_response({"message": "Thread cleared."})), 200


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health():
    """Simple liveness probe used by deployment platforms."""
    return jsonify({"status": "ok", "service": "ChefMate-Agent"}), 200


# ---------------------------------------------------------------------------
# GET /api/debug  — live connectivity diagnostic (all 7 strategies)
# ---------------------------------------------------------------------------

@api_bp.route("/debug", methods=["GET"])
def debug():
    """
    Run a live end-to-end connectivity check and return a JSON report.
    Open http://localhost:5000/api/debug in your browser to diagnose issues.

    Checks performed
    ----------------
    1. Config — are all required .env variables set?
    2. IAM    — does the API key successfully obtain a token?
    3. All 7 Orchestrate strategy URLs — which endpoints respond?

    Returns 200 with a "checks" list regardless of failures so you can
    see all results at once.
    """
    from config import config as cfg

    checks = []

    # ── 1. Config check ─────────────────────────────────────────────────────
    missing = []
    if not cfg.ORCHESTRATE_API_KEY or cfg.ORCHESTRATE_API_KEY.startswith("your_"):
        missing.append("ORCHESTRATE_API_KEY")
    if not cfg.ORCHESTRATE_AGENT_ID or cfg.ORCHESTRATE_AGENT_ID.startswith("your_"):
        missing.append("ORCHESTRATE_AGENT_ID")
    if not cfg.ORCHESTRATE_URL:
        missing.append("ORCHESTRATE_URL")

    checks.append({
        "name":   "Config (.env)",
        "ok":     len(missing) == 0,
        "detail": f"Missing or placeholder: {missing}" if missing else
                  f"URL={cfg.ORCHESTRATE_URL}  AgentID={cfg.ORCHESTRATE_AGENT_ID}",
    })

    if missing:
        return jsonify({"checks": checks,
                        "hint": "Fill in .env before running further checks."}), 200

    # ── 2. IAM token check ──────────────────────────────────────────────────
    token = None
    try:
        token = get_iam_token()
        checks.append({
            "name":   "IAM authentication",
            "ok":     True,
            "detail": "Bearer token obtained successfully.",
        })
    except Exception as exc:
        checks.append({
            "name":   "IAM authentication",
            "ok":     False,
            "detail": str(exc),
        })
        return jsonify({"checks": checks,
                        "hint": "Fix ORCHESTRATE_API_KEY in .env."}), 200

    # ── 3. Orchestrate endpoint probes (all 7 strategies) ───────────────────
    base    = cfg.ORCHESTRATE_URL.rstrip("/")
    agentId = cfg.ORCHESTRATE_AGENT_ID
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    test_msg = "hello"

    probes = [
        # (label, url, payload)
        (
            "Strategy-1  POST /v1/chat/completions (OpenAI-compat)",
            f"{base}/v1/chat/completions",
            {"model": agentId, "messages": [{"role": "user", "content": test_msg}]},
        ),
        (
            "Strategy-2  POST /v1/chat?agentId (messages array)",
            f"{base}/v1/chat?agentId={agentId}",
            {"messages": [{"role": "user", "content": test_msg}]},
        ),
        (
            "Strategy-3  POST /v1/agents/{id}/chat",
            f"{base}/v1/agents/{agentId}/chat",
            {"messages": [{"role": "user", "content": test_msg}]},
        ),
        (
            "Strategy-4a POST /v1/chat/threads (create thread)",
            f"{base}/v1/chat/threads",
            {},
        ),
        (
            "Strategy-5  POST /v1/chat?agentId (input.text wrapper)",
            f"{base}/v1/chat?agentId={agentId}",
            {"input": {"text": test_msg}},
        ),
        (
            "Strategy-6  POST /v2/chat?agentId",
            f"{base}/v2/chat?agentId={agentId}",
            {"messages": [{"role": "user", "content": test_msg}]},
        ),
        (
            "Strategy-7a POST /v1/sessions (create session)",
            f"{base}/v1/sessions",
            {"agentId": agentId},
        ),
    ]

    for label, url, payload in probes:
        try:
            resp = _requests.post(url, json=payload, headers=headers, timeout=20)
            body_text = _safe_text(resp)
            checks.append({
                "name":   label,
                "ok":     resp.ok,
                "status": resp.status_code,
                "url":    url,
                "body":   body_text[:500],
            })
            logger.info("[debug] %s → %s  %s", label, resp.status_code, body_text[:120])
        except Exception as exc:
            checks.append({
                "name":   label,
                "ok":     False,
                "status": None,
                "url":    url,
                "body":   str(exc),
            })

    any_ok = any(c.get("ok") for c in checks[2:])   # skip config & IAM checks
    hint   = (
        "✅ At least one strategy succeeded — look for ok=true in checks above. "
        "The working strategy will be cached automatically."
        if any_ok else
        "❌ All endpoint probes failed. "
        "Read each 'body' field — the IBM error message will tell you the correct path. "
        "Check ORCHESTRATE_URL and ORCHESTRATE_AGENT_ID in .env."
    )
    return jsonify({
        "checks":           checks,
        "hint":             hint,
        "working_strategy": orchestrate_service._working_strategy,
        "base_url":         base,
        "agent_id":         agentId,
    }), 200
