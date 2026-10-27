import logging
import requests
from typing import Optional
from dataclasses import dataclass
from utils.log import log_exception

logger = logging.getLogger("QuotaService")

@dataclass
class QuotaStatus:
    username: str = ""
    credits: int = 0
    credits_unlimited: bool = False
    lifetime_requests: int = 0
    last_request_at: str = ""
    error: str = ""
    valid: bool = False

    @property
    def can_proceed(self) -> bool:
        return self.credits_unlimited or self.credits > 0

    @property
    def display_credits(self) -> str:
        if self.credits_unlimited:
            return "Unlimited"
        return str(self.credits)

class QuotaService:
    def __init__(self, server_url: str, session_token: str):
        self.server_url = server_url.rstrip("/")
        self.session_token = session_token
        self._cached_status: Optional[QuotaStatus] = None

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.session_token}",
            "Content-Type": "application/json"
        }

    def refresh(self) -> QuotaStatus:
        try:
            res = requests.get(
                f"{self.server_url}/api/user/credits",
                headers=self._get_headers(),
                timeout=8
            )
            if res.status_code == 200:
                data = res.json()
                status = QuotaStatus(
                    username=data.get("username", ""),
                    credits=data.get("credits", 0),
                    credits_unlimited=bool(data.get("credits_unlimited", False)),
                    lifetime_requests=data.get("lifetime_requests", 0),
                    last_request_at=data.get("last_request_at", ""),
                    valid=True
                )
                self._cached_status = status
                return status
            else:
                return QuotaStatus(error=f"HTTP {res.status_code}", valid=False)
        except requests.exceptions.ConnectionError:
            if self._cached_status:
                return self._cached_status
            return QuotaStatus(error="Server unreachable", valid=False)
        except Exception as e:
            log_exception(logger, "QuotaService", "refresh", e)
            return QuotaStatus(error=str(e), valid=False)

    def check_and_consume(self) -> tuple[bool, str]:
        try:
            res = requests.post(
                f"{self.server_url}/api/user/consume-credit",
                headers=self._get_headers(),
                timeout=8
            )
            if res.status_code == 200:
                data = res.json()
                if data.get("success"):
                    new_credits = data.get("credits", 0)
                    unlimited = data.get("unlimited", False)
                    if self._cached_status:
                        self._cached_status.credits = new_credits
                        self._cached_status.credits_unlimited = unlimited
                        self._cached_status.lifetime_requests += 1
                    return True, "OK"
                else:
                    msg = data.get("message", "Quota check failed.")
                    return False, msg
            elif res.status_code == 402:
                data = res.json()
                msg = data.get("message", "No usage credits remaining.")
                if self._cached_status:
                    self._cached_status.credits = 0
                return False, msg
            elif res.status_code == 401:
                return False, "Session expired."
            else:
                return False, f"Quota error (HTTP {res.status_code})"
        except requests.exceptions.ConnectionError:
            return False, "Server connection failed."
        except Exception as e:
            log_exception(logger, "QuotaService", "check_and_consume", e)
            return False, f"Error: {e}"

    def get_cached_status(self) -> Optional[QuotaStatus]:
        return self._cached_status

    def admin_set_credits(self, target_username: str, amount: int) -> str:
        return self._admin_credit_action(target_username, {"action": "set", "amount": amount})

    def admin_add_credits(self, target_username: str, amount: int) -> str:
        return self._admin_credit_action(target_username, {"action": "add", "amount": amount})

    def admin_set_unlimited(self, target_username: str, unlimited: bool) -> str:
        return self._admin_credit_action(target_username, {"unlimited": unlimited})

    def admin_get_credits(self, target_username: str) -> QuotaStatus:
        try:
            res = requests.get(
                f"{self.server_url}/api/admin/users/{target_username}/credits",
                headers=self._get_headers(),
                timeout=8
            )
            if res.status_code == 200:
                data = res.json()
                return QuotaStatus(
                    username=data.get("username", target_username),
                    credits=data.get("credits", 0),
                    credits_unlimited=bool(data.get("credits_unlimited", False)),
                    lifetime_requests=data.get("lifetime_requests", 0),
                    last_request_at=data.get("last_request_at", ""),
                    valid=True
                )
            else:
                return QuotaStatus(error=f"HTTP {res.status_code}", valid=False)
        except Exception as e:
            log_exception(logger, "QuotaService", "admin_get_credits", e)
            return QuotaStatus(error=str(e), valid=False)

    def _admin_credit_action(self, target_username: str, payload: dict) -> str:
        try:
            res = requests.post(
                f"{self.server_url}/api/admin/users/{target_username}/credits",
                headers=self._get_headers(),
                json=payload,
                timeout=8
            )
            try:
                data = res.json()
            except Exception:
                data = {}
            if res.status_code == 200:
                return data.get("message", "Success.")
            else:
                raise RuntimeError(data.get("message", f"HTTP {res.status_code}"))
        except RuntimeError:
            raise
        except Exception as e:
            log_exception(logger, "QuotaService", "_admin_credit_action", e)
            raise RuntimeError(f"Operation failed: {e}")

CreditStatus = QuotaStatus
CreditService = QuotaService
