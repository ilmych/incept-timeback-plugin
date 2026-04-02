"""Wrapper for QTI and OneRoster API calls with logging and retry."""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path

from .auth import get_session, refresh_session

QTI_BASE = "https://qti.alpha-1edtech.ai/api"
ONEROSTER_BASE = "https://api.alpha-1edtech.ai/ims/oneroster"
ORG_ID = "346488d3-efb9-4f56-95ea-f4a441de2370"

RETRY_CODES = {429, 500, 502, 503, 504}
RETRY_BACKOFF = [5, 15, 30]

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class APIClient:
    """Logged API client with retry logic for Timeback APIs."""

    def __init__(self, prefix: str = "test"):
        self.session = get_session()
        self.prefix = prefix
        self.ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_file = LOG_DIR / f"{prefix}_{self.ts}.jsonl"
        self.call_count = 0
        self.errors = []
        self.successes = []

    def _log(self, entry: dict):
        """Append a log entry."""
        entry["timestamp"] = datetime.now().isoformat()
        entry["call_number"] = self.call_count
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _request(self, method: str, url: str, **kwargs) -> dict:
        """Make an API request with retry and logging."""
        self.call_count += 1
        payload = kwargs.get("json") or kwargs.get("data")

        for attempt in range(3):
            try:
                resp = getattr(self.session, method)(url, timeout=30, **kwargs)

                log_entry = {
                    "method": method.upper(),
                    "url": url,
                    "status": resp.status_code,
                    "attempt": attempt + 1,
                    "payload_preview": str(payload)[:500] if payload else None,
                }

                if resp.status_code == 409:
                    log_entry["result"] = "already_exists"
                    self._log(log_entry)
                    self.successes.append(log_entry)
                    return {"success": True, "already_existed": True, "status": 409,
                            "response": resp.text[:500]}

                if resp.status_code in RETRY_CODES and attempt < 2:
                    log_entry["result"] = "retry"
                    log_entry["response_body"] = resp.text[:500]
                    self._log(log_entry)
                    time.sleep(RETRY_BACKOFF[attempt])
                    self.session = refresh_session(self.session)
                    continue

                if resp.status_code >= 400:
                    log_entry["result"] = "error"
                    log_entry["response_body"] = resp.text[:2000]
                    self._log(log_entry)
                    self.errors.append(log_entry)
                    return {"success": False, "status": resp.status_code,
                            "error": resp.text[:2000], "url": url, "method": method.upper()}

                # Success
                log_entry["result"] = "success"
                self._log(log_entry)
                self.successes.append(log_entry)
                try:
                    return {"success": True, "status": resp.status_code,
                            "data": resp.json()}
                except (json.JSONDecodeError, ValueError):
                    return {"success": True, "status": resp.status_code,
                            "data": resp.text[:2000]}

            except Exception as e:
                log_entry = {
                    "method": method.upper(), "url": url,
                    "attempt": attempt + 1, "result": "exception",
                    "error": str(e),
                }
                self._log(log_entry)
                if attempt < 2:
                    time.sleep(RETRY_BACKOFF[attempt])
                    self.session = refresh_session(self.session)
                    continue
                self.errors.append(log_entry)
                return {"success": False, "error": str(e), "url": url}

    def gen_id(self, suffix: str = "") -> str:
        """Generate a deterministic test ID."""
        short_uuid = uuid.uuid4().hex[:8]
        parts = [f"s4-{self.prefix}", self.ts, suffix, short_uuid]
        return "-".join(p for p in parts if p)

    # --- QTI API ---

    def create_item_json(self, payload: dict) -> dict:
        """POST /assessment-items with JSON payload."""
        return self._request("post", f"{QTI_BASE}/assessment-items", json=payload)

    def create_item_xml(self, xml: str, metadata: dict = None) -> dict:
        """POST /assessment-items with XML payload."""
        payload = {"format": "xml", "xml": xml}
        if metadata:
            payload["metadata"] = metadata
        return self._request("post", f"{QTI_BASE}/assessment-items", json=payload)

    def get_item(self, item_id: str) -> dict:
        """GET /assessment-items/{id}."""
        return self._request("get", f"{QTI_BASE}/assessment-items/{item_id}")

    def update_item(self, item_id: str, xml: str, metadata: dict = None) -> dict:
        """PUT /assessment-items/{id} with XML."""
        payload = {"format": "xml", "xml": xml}
        if metadata:
            payload["metadata"] = metadata
        return self._request("put", f"{QTI_BASE}/assessment-items/{item_id}", json=payload)

    def delete_item(self, item_id: str) -> dict:
        """DELETE /assessment-items/{id}."""
        return self._request("delete", f"{QTI_BASE}/assessment-items/{item_id}")

    def create_stimulus(self, identifier: str, title: str, content: str) -> dict:
        """POST /stimuli."""
        payload = {"identifier": identifier, "title": title, "content": content}
        return self._request("post", f"{QTI_BASE}/stimuli", json=payload)

    def get_stimulus(self, stim_id: str) -> dict:
        """GET /stimuli/{id}."""
        return self._request("get", f"{QTI_BASE}/stimuli/{stim_id}")

    def update_stimulus(self, stim_id: str, title: str, content: str) -> dict:
        """PUT /stimuli/{id}."""
        payload = {"identifier": stim_id, "title": title, "content": content}
        return self._request("put", f"{QTI_BASE}/stimuli/{stim_id}", json=payload)

    def delete_stimulus(self, stim_id: str) -> dict:
        """DELETE /stimuli/{id}."""
        return self._request("delete", f"{QTI_BASE}/stimuli/{stim_id}")

    def create_test(self, payload: dict) -> dict:
        """POST /assessment-tests."""
        return self._request("post", f"{QTI_BASE}/assessment-tests", json=payload)

    def get_test(self, test_id: str) -> dict:
        """GET /assessment-tests/{id}."""
        return self._request("get", f"{QTI_BASE}/assessment-tests/{test_id}")

    def delete_test(self, test_id: str) -> dict:
        """DELETE /assessment-tests/{id}."""
        return self._request("delete", f"{QTI_BASE}/assessment-tests/{test_id}")

    # --- OneRoster API ---

    def create_course(self, payload: dict) -> dict:
        """POST /rostering/v1p2/courses."""
        return self._request("post", f"{ONEROSTER_BASE}/rostering/v1p2/courses", json=payload)

    def get_course(self, course_id: str) -> dict:
        """GET /rostering/v1p2/courses/{id}."""
        return self._request("get", f"{ONEROSTER_BASE}/rostering/v1p2/courses/{course_id}")

    def update_course(self, course_id: str, payload: dict) -> dict:
        """PUT /rostering/v1p2/courses/{id}."""
        return self._request("put", f"{ONEROSTER_BASE}/rostering/v1p2/courses/{course_id}", json=payload)

    def delete_course(self, course_id: str) -> dict:
        """DELETE /rostering/v1p2/courses/{id}."""
        return self._request("delete", f"{ONEROSTER_BASE}/rostering/v1p2/courses/{course_id}")

    def create_component(self, payload: dict) -> dict:
        """POST /rostering/v1p2/courses/components."""
        return self._request("post", f"{ONEROSTER_BASE}/rostering/v1p2/courses/components", json=payload)

    def get_component(self, comp_id: str) -> dict:
        """GET /rostering/v1p2/courses/components/{id}."""
        return self._request("get", f"{ONEROSTER_BASE}/rostering/v1p2/courses/components/{comp_id}")

    def delete_component(self, comp_id: str) -> dict:
        """DELETE /rostering/v1p2/courses/components/{id}."""
        return self._request("delete", f"{ONEROSTER_BASE}/rostering/v1p2/courses/components/{comp_id}")

    def create_resource(self, payload: dict) -> dict:
        """POST /resources/v1p2/resources/ (trailing slash!)."""
        return self._request("post", f"{ONEROSTER_BASE}/resources/v1p2/resources/", json=payload)

    def get_resource(self, res_id: str) -> dict:
        """GET /resources/v1p2/resources/{id}."""
        return self._request("get", f"{ONEROSTER_BASE}/resources/v1p2/resources/{res_id}")

    def delete_resource(self, res_id: str) -> dict:
        """DELETE /resources/v1p2/resources/{id}."""
        return self._request("delete", f"{ONEROSTER_BASE}/resources/v1p2/resources/{res_id}")

    def create_component_resource(self, payload: dict) -> dict:
        """POST /rostering/v1p2/courses/component-resources."""
        return self._request("post", f"{ONEROSTER_BASE}/rostering/v1p2/courses/component-resources", json=payload)

    def get_component_resource(self, link_id: str) -> dict:
        """GET /rostering/v1p2/courses/component-resources/{id}."""
        return self._request("get", f"{ONEROSTER_BASE}/rostering/v1p2/courses/component-resources/{link_id}")

    def delete_component_resource(self, link_id: str) -> dict:
        """DELETE /rostering/v1p2/courses/component-resources/{id}."""
        return self._request("delete", f"{ONEROSTER_BASE}/rostering/v1p2/courses/component-resources/{link_id}")

    # --- Reporting ---

    def summary(self) -> dict:
        """Return summary of all API calls made."""
        return {
            "total_calls": self.call_count,
            "successes": len(self.successes),
            "errors": len(self.errors),
            "error_details": self.errors,
            "log_file": str(self.log_file),
        }
