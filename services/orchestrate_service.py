"""
ChefMate-Agent — IBM watsonx Orchestrate Integration Service
============================================================

Architecture
------------
Browser
  └─► POST /api/chat  (Flask)
        └─► IBM Cloud IAM  →  Bearer token
              └─► watsonx Orchestrate REST API  (multi-strategy probe)
                    └─► ChefMate-Agent responds
                          └─► JSON back to Flask → Browser

IBM watsonx Orchestrate API strategies (tried in order)
--------------------------------------------------------
The correct endpoint is discovered automatically on first use and cached
in-process for all subsequent calls.  All strategies use the same
instance-scoped base URL from ORCHESTRATE_URL in .env.

Strategy 1 — OpenAI-compatible chat completions (v1)
    POST {base}/v1/chat/completions
    Body: { "model": "{agent_id}", "messages": [{"role":"user","content":"..."}] }

Strategy 2 — Agent invocation endpoint (v1)
    POST {base}/v1/agents/{agent_id}/chat
    Body: { "messages": [{"role":"user","content":"..."}] }

Authentication
--------------
IBM Cloud IAM API Key  →  POST https://iam.cloud.ibm.com/identity/token
Tokens are cached in-process and silently refreshed 60 s before they expire.

Debugging
---------
Set FLASK_DEBUG=True in .env to see every request/response in the console.
Every error includes: HTTP status, IBM error code, IBM message, URL, body.
"""

import time
import json
import threading
import logging
import requests
from config import config

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# IAM token cache  (thread-safe, auto-refresh)
# ──────────────────────────────────────────────────────────────────────────────

_IAM_URL        = "https://iam.cloud.ibm.com/identity/token"
_REFRESH_BUFFER = 60        # seconds before expiry to force a refresh

_token_cache = {"token": None, "expires_at": 0.0}
_token_lock  = threading.Lock()


def _fetch_iam_token(api_key: str) -> tuple[str, float]:
    """Exchange an IBM Cloud API key for an IAM bearer token."""
    logger.info("[IAM] Fetching token from %s", _IAM_URL)
    logger.info("[IAM] API Key being used: %s...", api_key[:10] if api_key else "None")
    resp = requests.post(
        _IAM_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
        timeout=30,
    )
    logger.info("[IAM] Status: %s", resp.status_code)
    if not resp.ok:
        body = _safe_text(resp)
        logger.error("[IAM] FAILED status=%s body=%s", resp.status_code, body)
        raise RuntimeError(
            f"IAM authentication failed (HTTP {resp.status_code}). "
            f"Check ORCHESTRATE_API_KEY in .env. Response: {body[:300]}"
        )
    data       = resp.json()
    token      = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    expires_at = time.time() + expires_in - _REFRESH_BUFFER
    logger.info("[IAM] Token obtained, valid ~%d s", expires_in - _REFRESH_BUFFER)
    return token, expires_at


def get_iam_token() -> str:
    """Return a valid IAM bearer token, refreshing only when necessary."""
    with _token_lock:
        if _token_cache["token"] is None or time.time() >= _token_cache["expires_at"]:
            tok, exp = _fetch_iam_token(config.ORCHESTRATE_API_KEY)
            _token_cache["token"]      = tok
            _token_cache["expires_at"] = exp
        return _token_cache["token"]


def _invalidate_token():
    """Force token refresh on next call (called after a 401)."""
    with _token_lock:
        _token_cache["token"]      = None
        _token_cache["expires_at"] = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────────────────────────────────────

def _safe_text(resp: requests.Response) -> str:
    try:
        return resp.text[:3000]
    except Exception:
        return "<unreadable>"


def _safe_json(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {}


def _ibm_error(resp: requests.Response, url: str) -> str:
    """Build a rich error string from an IBM HTTP error response."""
    status = resp.status_code
    body   = _safe_json(resp)
    raw    = _safe_text(resp)

    code = (body.get("code") or body.get("error") or body.get("error_code") or "")
    msg  = (body.get("message") or body.get("error_description")
            or body.get("description") or "")

    parts = [f"HTTP {status}"]
    if code: parts.append(f"IBM code: {code}")
    if msg:  parts.append(f"IBM message: {msg}")
    parts.append(f"URL: {url}")
    parts.append(f"Body: {raw[:600]}")
    return " | ".join(parts)


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def _extract_reply(data: dict) -> str | None:
    """
    Try every known response shape from IBM watsonx Orchestrate and OpenAI-compat APIs.
    Returns None if nothing matches (caller should log and fall back).

    Known shapes:
      OpenAI-compat  { "choices": [{ "message": { "content": "…" } }] }
      { "output": "text" }
      { "output": { "text": "…" } }
      { "output": { "generic": [{ "response_type":"text","text":"…" }] } }
      { "response": "text" }
      { "message": "text" }
      { "text": "text" }
      { "content": "text" }
      { "answer": "text" }
      { "reply": "text" }
      { "result": "text" }
      { "completion": "text" }
      { "generated_text": "text" }
      { "messages": [{ "role":"assistant","content":"…" }] }
      { "data": { "content": "…" } }
      { "data": { "text": "…" } }
      { "result": { "text": "…" } }
      { "result": { "content": "…" } }
    """
    # 1 — OpenAI choices (most common for OpenAI-compat endpoints)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        try:
            c = choices[0]
            # Standard chat completion
            if isinstance(c.get("message"), dict):
                content = c["message"].get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            # delta style (streaming partial — but we get full here)
            if isinstance(c.get("delta"), dict):
                content = c["delta"].get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            # text field (older compat)
            if isinstance(c.get("text"), str) and c["text"].strip():
                return c["text"].strip()
        except (KeyError, IndexError, AttributeError):
            pass

    # 2 — output (string or nested)
    out = data.get("output")
    if isinstance(out, str) and out.strip():
        return out.strip()
    if isinstance(out, dict):
        for k in ("text", "message", "content", "response"):
            v = out.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        generics = out.get("generic", [])
        if isinstance(generics, list):
            parts = [
                g["text"] for g in generics
                if isinstance(g, dict) and g.get("response_type") == "text" and g.get("text")
            ]
            if parts:
                return "\n\n".join(parts)

    # 3 — top-level scalar keys (most common Orchestrate patterns)
    for k in ("response", "message", "text", "content", "answer",
              "reply", "result", "completion", "generated_text"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # 4 — nested result / data objects
    for wrapper_key in ("result", "data", "response"):
        wrapper = data.get(wrapper_key)
        if isinstance(wrapper, dict):
            for inner_key in ("text", "content", "message", "output", "answer", "reply"):
                v = wrapper.get(inner_key)
                if isinstance(v, str) and v.strip():
                    return v.strip()

    # 5 — conversation messages list (last assistant turn)
    messages = data.get("messages")
    if isinstance(messages, list):
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "assistant":
                c = m.get("content", "")
                if isinstance(c, str) and c.strip():
                    return c.strip()
                # content may be a list of blocks
                if isinstance(c, list):
                    texts = [block.get("text", "") for block in c
                             if isinstance(block, dict) and block.get("type") == "text"]
                    joined = "\n".join(t for t in texts if t)
                    if joined.strip():
                        return joined.strip()

    # 6 — body IS a string (plain-text response wrapped in JSON string)
    if isinstance(data, str) and data.strip():
        return data.strip()

    return None


# ──────────────────────────────────────────────────────────────────────────────
# OrchestrateService
# ──────────────────────────────────────────────────────────────────────────────

class OrchestrateService:
    """
    Multi-strategy client for IBM watsonx Orchestrate.

    Probes up to 2 API patterns on first use, remembers which one works,
    and uses it exclusively for all subsequent calls in the same process.
    """

    # Number of strategies we support
    _TOTAL_STRATEGIES = 2

    def __init__(self):
        self.base_url    = config.ORCHESTRATE_URL.rstrip("/")
        self.agent_id    = config.ORCHESTRATE_AGENT_ID
        self.timeout     = config.REQUEST_TIMEOUT
        self.max_retries = config.MAX_RETRIES
        self.retry_delay = config.RETRY_DELAY

        # Caches
        self._working_strategy: int | None = None  # locked once a strategy succeeds

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def send_message(self, user_message: str, conversation_id: str = "default") -> dict:
        """
        Send *user_message* to ChefMate-Agent.

        Returns
        -------
        {
            "success":   bool,
            "response":  str | None,
            "error":     str | None,   # rich IBM error details on failure
            "thread_id": str | None,
        }
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            logger.info(
                "[Orchestrate] attempt %d/%d  conv=%s  msg=%r",
                attempt, self.max_retries, conversation_id, user_message[:60],
            )
            try:
                token  = get_iam_token()
                result = self._call_agent(token, user_message, conversation_id)
                if result:
                    return result          # success

                last_error = "Agent returned an empty or unparseable response."
                logger.warning("[Orchestrate] empty/unparseable response on attempt %d", attempt)

            except _AuthError as exc:
                logger.warning("[Orchestrate] 401 — invalidating token and retrying. %s", exc)
                _invalidate_token()
                last_error = str(exc)

            except _ThreadGoneError as exc:
                logger.warning("[Orchestrate] thread gone (404) — resetting and retrying. %s", exc)
                self._working_strategy = None   # force re-probe
                last_error = str(exc)

            except _IBMError as exc:
                last_error = str(exc)
                logger.error("[Orchestrate] API error on attempt %d: %s", attempt, last_error)

            except RuntimeError as exc:        # IAM failure
                last_error = str(exc)
                logger.error("[Orchestrate] RuntimeError: %s", last_error)

            except requests.exceptions.Timeout:
                last_error = (
                    f"Timeout: Orchestrate did not respond within {self.timeout} s "
                    f"(attempt {attempt}/{self.max_retries})"
                )
                logger.warning("[Orchestrate] %s", last_error)

            except requests.exceptions.ConnectionError as exc:
                last_error = (
                    f"Connection error: cannot reach {self.base_url}. "
                    f"Verify ORCHESTRATE_URL in .env. ({exc})"
                )
                logger.warning("[Orchestrate] %s", last_error)

            except Exception as exc:
                last_error = f"Unexpected error ({type(exc).__name__}): {exc}"
                logger.exception("[Orchestrate] unexpected error on attempt %d", attempt)

            if attempt < self.max_retries:
                sleep_s = self.retry_delay * attempt
                logger.info("[Orchestrate] sleeping %s s before retry.", sleep_s)
                time.sleep(sleep_s)

        logger.error("[Orchestrate] all %d attempts failed: %s", self.max_retries, last_error)
        return {
            "success":   False,
            "response":  None,
            "error":     last_error or "All retry attempts failed.",
            "thread_id": None,
        }

    def clear_session(self, conversation_id: str) -> None:
        """Clear session — next call starts a fresh conversation."""
        logger.info("[Orchestrate] session cleared for conv=%s", conversation_id)

    # ──────────────────────────────────────────────────────────────
    # Strategy dispatcher
    # ──────────────────────────────────────────────────────────────

    def _call_agent(
        self, token: str, message: str, conversation_id: str
    ) -> dict | None:
        """
        Try the working strategy (if known), otherwise probe all strategies.
        Returns a success result dict or None if reply couldn't be parsed.
        Raises _AuthError, _ThreadGoneError, or _IBMError on API failures.
        """
        strategies = (
            [self._working_strategy]
            if self._working_strategy
            else list(range(1, self._TOTAL_STRATEGIES + 1))
        )

        last_exc = None
        for s in strategies:
            try:
                result = self._run_strategy(s, token, message, conversation_id)
                if result:
                    self._working_strategy = s
                    logger.info("[Orchestrate] strategy %d succeeded.", s)
                    return result
                # result is None → unparseable, but not an HTTP error → try next
                logger.warning("[Orchestrate] strategy %d returned unparseable response.", s)
            except (_AuthError, _ThreadGoneError):
                raise          # propagate immediately — these need special handling
            except _IBMError as exc:
                logger.warning("[Orchestrate] strategy %d failed: %s", s, exc)
                last_exc = exc

        if last_exc:
            raise last_exc
        return None

    def _run_strategy(
        self, strategy: int, token: str, message: str, conversation_id: str
    ) -> dict | None:
        """Dispatch to a specific API strategy."""
        dispatch = {
            1: self._strategy_openai_compat,
            2: self._strategy_direct,
        }
        fn = dispatch.get(strategy)
        if fn:
            return fn(token, message)
        return None

    # ──────────────────────────────────────────────────────────────
    # Strategy 1 — OpenAI-compatible chat completions
    # POST /v1/chat/completions
    # Body: { "model": "<agent_id>", "messages": [...] }
    # ──────────────────────────────────────────────────────────────

    def _strategy_openai_compat(self, token: str, message: str) -> dict | None:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model":    self.agent_id,
            "messages": [{"role": "user", "content": message}],
        }
        logger.info("[Strategy-1/OpenAI] POST %s", url)
        resp = requests.post(
            url, json=payload, headers=_auth_headers(token), timeout=self.timeout
        )
        logger.info("[Strategy-1/OpenAI] status=%s body=%s", resp.status_code, _safe_text(resp))
        return self._process_response(resp, url, None)

    # ──────────────────────────────────────────────────────────────
    # Strategy 2 — Direct agent endpoint
    # POST /v1/agents/{agent_id}/chat
    # Body: { "messages": [...] }
    # ──────────────────────────────────────────────────────────────

    def _strategy_direct(self, token: str, message: str) -> dict | None:
        url = f"{self.base_url}/v1/agents/{self.agent_id}/chat"
        payload = {
            "messages": [{"role": "user", "content": message}]
        }
        logger.info("[Strategy-2/Direct] POST %s", url)
        resp = requests.post(
            url, json=payload, headers=_auth_headers(token), timeout=self.timeout
        )
        logger.info("[Strategy-2/Direct] status=%s body=%s", resp.status_code, _safe_text(resp))
        return self._process_response(resp, url, None)

    # ──────────────────────────────────────────────────────────────
    # Shared response processor
    # ──────────────────────────────────────────────────────────────

    def _process_response(
        self,
        resp: requests.Response,
        url:  str,
        thread_id: str | None,
    ) -> dict | None:
        """
        Validate the HTTP response and extract the agent reply.

        Returns a success dict, None (unparseable), or raises _AuthError/_IBMError.
        """
        if resp.status_code == 401:
            raise _AuthError(_ibm_error(resp, url))

        if not resp.ok:
            raise _IBMError(_ibm_error(resp, url))

        data  = resp.json()
        reply = _extract_reply(data)

        if reply is None:
            logger.warning(
                "[Orchestrate] _extract_reply found nothing. Full body: %s",
                json.dumps(data)[:600],
            )
            # Surface the raw body so the developer can see what came back
            reply = (
                "I received a response but could not parse it.\n\n"
                f"**Raw IBM response:**\n```json\n{json.dumps(data, indent=2)[:1000]}\n```"
            )

        return {
            "success":   True,
            "response":  reply,
            "thread_id": thread_id,
            "error":     None,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Typed exceptions for clean control flow
# ──────────────────────────────────────────────────────────────────────────────

class _AuthError(Exception):
    """Raised when Orchestrate returns 401 — triggers token refresh + retry."""

class _ThreadGoneError(Exception):
    """Raised when a cached thread/session returns 404 — triggers reset + retry."""

class _IBMError(Exception):
    """Raised for any other non-2xx Orchestrate response."""


# Module-level singleton — imported by Flask routes
orchestrate_service = OrchestrateService()
