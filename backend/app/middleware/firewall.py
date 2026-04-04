from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from backend.app.services.audit import resolve_client_ip, set_audit_context
from backend.app.services.security_events import (
    SecurityEventCategory,
    SecurityEventOutcome,
    SecurityEventSeverity,
    log_security_event,
)

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"allow", "deny"}
VALID_MODES = {"simulate", "enforce"}


@dataclass(frozen=True)
class FirewallRule:
    name: str
    action: str
    methods: frozenset[str]
    path_prefixes: tuple[str, ...]
    ip_networks: tuple[Any, ...]
    description: str | None = None


@dataclass(frozen=True)
class FirewallConfig:
    default_action: str
    rules: tuple[FirewallRule, ...]


@dataclass(frozen=True)
class FirewallDecision:
    action: str
    matched: bool
    rule_name: str
    description: str | None
    client_ip: str | None


def _normalize_action(value: str | None, *, default: str = "allow") -> str:
    normalized = (value or default).strip().lower()
    if normalized not in VALID_ACTIONS:
        return default
    return normalized


def _normalize_mode(value: str | None) -> str:
    normalized = (value or "simulate").strip().lower()
    if normalized not in VALID_MODES:
        return "simulate"
    return normalized


def _normalize_methods(values: Any) -> frozenset[str]:
    if not values:
        return frozenset()
    return frozenset(str(value).strip().upper() for value in values if str(value).strip())


def _normalize_path_prefixes(values: Any) -> tuple[str, ...]:
    prefixes: list[str] = []
    for value in values or []:
        normalized = str(value).strip()
        if not normalized:
            continue
        prefixes.append(normalized if normalized.startswith("/") else f"/{normalized}")
    return tuple(prefixes)


def _parse_networks(values: Any) -> tuple[Any, ...]:
    networks: list[Any] = []
    for value in values or []:
        try:
            networks.append(ip_network(str(value).strip(), strict=False))
        except ValueError:
            logger.warning("Skipping invalid firewall CIDR entry: %s", value)
    return tuple(networks)


def _path_matches(path: str, prefixes: tuple[str, ...]) -> bool:
    if not prefixes:
        return True

    for prefix in prefixes:
        normalized_prefix = prefix.rstrip("/") or "/"
        if path == normalized_prefix or path.startswith(f"{normalized_prefix}/"):
            return True
    return False


def _load_firewall_config(config_path: str | Path, default_action: str) -> FirewallConfig:
    path = Path(config_path)
    resolved_default_action = _normalize_action(default_action)
    if not path.exists():
        logger.warning("Firewall config file not found at %s. Using empty ruleset.", path)
        return FirewallConfig(default_action=resolved_default_action, rules=())

    try:
        raw_payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to load firewall config from %s. Using empty ruleset.", path)
        return FirewallConfig(default_action=resolved_default_action, rules=())

    if not isinstance(raw_payload, dict):
        logger.warning("Firewall config payload at %s must be a JSON object.", path)
        return FirewallConfig(default_action=resolved_default_action, rules=())

    config_default_action = _normalize_action(
        raw_payload.get("default_action"),
        default=resolved_default_action,
    )
    rules: list[FirewallRule] = []

    for raw_rule in raw_payload.get("rules", []):
        if not isinstance(raw_rule, dict):
            continue
        if not raw_rule.get("enabled", True):
            continue

        name = str(raw_rule.get("name") or "unnamed-rule").strip() or "unnamed-rule"
        action = _normalize_action(raw_rule.get("action"), default="deny")
        rules.append(
            FirewallRule(
                name=name,
                action=action,
                methods=_normalize_methods(raw_rule.get("methods")),
                path_prefixes=_normalize_path_prefixes(raw_rule.get("path_prefixes")),
                ip_networks=_parse_networks(raw_rule.get("ip_cidrs")),
                description=(str(raw_rule.get("description")).strip() or None)
                if raw_rule.get("description") is not None
                else None,
            )
        )

    return FirewallConfig(default_action=config_default_action, rules=tuple(rules))


class FirewallMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        enabled: bool = True,
        mode: str = "simulate",
        config_path: str = "infra/firewall/rules.json",
        default_action: str = "allow",
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.mode = _normalize_mode(mode)
        self.config_path = config_path
        self.default_action = _normalize_action(default_action)
        self.config = _load_firewall_config(config_path, self.default_action)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        decision = self._evaluate_request(request)
        request.state.firewall_decision = decision

        if decision.action != "deny":
            return await call_next(request)

        set_audit_context(
            request,
            details={
                "firewall_rule": decision.rule_name,
                "firewall_mode": self.mode,
                "firewall_client_ip": decision.client_ip,
                "firewall_description": decision.description,
                "firewall_simulated": self.mode == "simulate",
            },
        )

        if self.mode == "simulate":
            log_security_event(
                request=request,
                event_type="firewall.rule_simulated",
                category=SecurityEventCategory.FIREWALL,
                severity=SecurityEventSeverity.MEDIUM,
                outcome=SecurityEventOutcome.SIMULATED,
                description="Firewall simulation matched a deny rule.",
                details={
                    "firewall_rule": decision.rule_name,
                    "firewall_description": decision.description,
                    "client_ip": decision.client_ip,
                },
                resource_type="network",
            )
            logger.warning(
                "Firewall simulation matched deny rule '%s' for %s %s from %s",
                decision.rule_name,
                request.method,
                request.url.path,
                decision.client_ip or "unknown",
            )
            response = await call_next(request)
            response.headers["X-Firewall-Simulated"] = "true"
            response.headers["X-Firewall-Rule"] = decision.rule_name
            return response

        logger.warning(
            "Firewall blocked %s %s from %s using rule '%s'",
            request.method,
            request.url.path,
            decision.client_ip or "unknown",
            decision.rule_name,
        )
        set_audit_context(
            request,
            action="firewall.block",
            resource_type="network",
        )
        log_security_event(
            request=request,
            event_type="firewall.rule_blocked",
            category=SecurityEventCategory.FIREWALL,
            severity=SecurityEventSeverity.HIGH,
            outcome=SecurityEventOutcome.BLOCKED,
            description="Firewall blocked a request because a deny rule matched.",
            details={
                "firewall_rule": decision.rule_name,
                "firewall_description": decision.description,
                "client_ip": decision.client_ip,
            },
            resource_type="network",
        )
        return JSONResponse(
            status_code=403,
            content={
                "detail": "Request blocked by firewall policy.",
                "firewall_rule": decision.rule_name,
                "firewall_mode": self.mode,
                "client_ip": decision.client_ip,
            },
            headers={"X-Firewall-Rule": decision.rule_name},
        )

    def _evaluate_request(self, request: Request) -> FirewallDecision:
        client_ip = resolve_client_ip(request)
        request_path = request.url.path
        request_method = request.method.upper()
        parsed_ip = None
        if client_ip:
            try:
                parsed_ip = ip_address(client_ip)
            except ValueError:
                logger.warning("Unable to parse client IP for firewall evaluation: %s", client_ip)

        for rule in self.config.rules:
            if rule.methods and request_method not in rule.methods:
                continue
            if not _path_matches(request_path, rule.path_prefixes):
                continue
            if rule.ip_networks:
                if parsed_ip is None:
                    continue
                if not any(parsed_ip in network for network in rule.ip_networks):
                    continue

            return FirewallDecision(
                action=rule.action,
                matched=True,
                rule_name=rule.name,
                description=rule.description,
                client_ip=client_ip,
            )

        return FirewallDecision(
            action=self.config.default_action,
            matched=False,
            rule_name="default_action",
            description="Default firewall action applied because no explicit rule matched.",
            client_ip=client_ip,
        )
