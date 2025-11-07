"""High-level protocol structures wrapping the supervisor protobuf schema."""

from __future__ import annotations

import base64
import datetime as dt
import enum
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

ISO8601 = "%Y-%m-%dT%H:%M:%S.%fZ"


class ProtocolVersion(str, enum.Enum):
    """Known protocol versions."""

    V1_0 = "1.0"


class RequestAction(str, enum.Enum):
    """Supported supervisor actions."""

    PING = "ping"
    STATUS = "status"
    SHUTDOWN = "shutdown"
    RESTART_SERVICE = "restart-service"
    RELOAD_CONFIG = "reload-config"


class ErrorCode(str, enum.Enum):
    """Error taxonomy for supervisor responses."""

    UNAUTHORIZED = "unauthorized"
    INVALID_ARGUMENT = "invalid-argument"
    NOT_FOUND = "not-found"
    TIMEOUT = "timeout"
    INTERNAL = "internal"
    CONCURRENCY_LIMIT = "concurrency-limit"


@dataclass(slots=True)
class ClientInfo:
    """Information about the IPC client."""

    pid: int
    user: str
    version: str
    capabilities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AuthToken:
    """Authentication metadata for supervisor calls."""

    token: str
    scheme: str = "hmac"


@dataclass(slots=True)
class SupervisorRequest:
    """In-memory representation of a supervisor request."""

    action: RequestAction
    protocol_version: ProtocolVersion = ProtocolVersion.V1_0
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: dt.datetime = field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    options: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    streaming: bool = False
    timeout_ms: Optional[int] = None
    client_info: Optional[ClientInfo] = None
    auth: Optional[AuthToken] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serialisable dictionary."""

        payload = {
            "message_type": "request",
            "protocol_version": self.protocol_version.value,
            "request_id": self.request_id,
            "timestamp": self.timestamp.strftime(ISO8601),
            "action": self.action.value,
            "options": self.options,
            "filters": self.filters,
            "streaming": self.streaming,
            "timeout_ms": self.timeout_ms,
        }
        if self.client_info:
            payload["client_info"] = {
                "pid": self.client_info.pid,
                "user": self.client_info.user,
                "version": self.client_info.version,
                "capabilities": list(self.client_info.capabilities),
            }
        if self.auth:
            payload["auth"] = {
                "token": self.auth.token,
                "scheme": self.auth.scheme,
            }
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "SupervisorRequest":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError("invalid json") from exc
        try:
            action = RequestAction(data["action"])
        except (KeyError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("invalid action") from exc

        timestamp_raw = data.get("timestamp")
        timestamp = (
            dt.datetime.strptime(timestamp_raw, ISO8601).replace(tzinfo=dt.timezone.utc)
            if timestamp_raw
            else dt.datetime.now(dt.timezone.utc)
        )

        client_info_payload = data.get("client_info")
        client_info = None
        if client_info_payload:
            client_info = ClientInfo(
                pid=int(client_info_payload.get("pid", 0)),
                user=client_info_payload.get("user", ""),
                version=client_info_payload.get("version", ""),
                capabilities=list(client_info_payload.get("capabilities", [])),
            )

        auth_payload = data.get("auth")
        auth = None
        if auth_payload:
            token = auth_payload.get("token")
            if not token:
                raise ValueError("auth token missing")
            auth = AuthToken(token=token, scheme=auth_payload.get("scheme", "hmac"))

        return cls(
            action=action,
            protocol_version=ProtocolVersion(
                data.get("protocol_version", ProtocolVersion.V1_0.value)
            ),
            request_id=data.get("request_id", str(uuid.uuid4())),
            timestamp=timestamp,
            options=data.get("options", {}),
            filters=data.get("filters", {}),
            streaming=data.get("streaming", False),
            timeout_ms=data.get("timeout_ms"),
            client_info=client_info,
            auth=auth,
        )


@dataclass(slots=True)
class StreamChunk:
    """Streaming response chunk."""

    request_id: str
    server_timestamp: dt.datetime
    payload: bytes
    final_chunk: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_type": "stream-chunk",
            "request_id": self.request_id,
            "server_timestamp": self.server_timestamp.strftime(ISO8601),
            "payload": base64.b64encode(self.payload).decode("ascii"),
            "final_chunk": self.final_chunk,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "StreamChunk":
        data = json.loads(payload)
        server_timestamp = dt.datetime.strptime(
            data["server_timestamp"], ISO8601
        ).replace(tzinfo=dt.timezone.utc)
        raw_payload = base64.b64decode(data.get("payload", ""))
        return cls(
            request_id=data["request_id"],
            server_timestamp=server_timestamp,
            payload=raw_payload,
            final_chunk=data.get("final_chunk", False),
        )


@dataclass(slots=True)
class SupervisorResponse:
    """In-memory representation of a supervisor response."""

    request_id: str
    status: str
    protocol_version: ProtocolVersion = ProtocolVersion.V1_0
    server_timestamp: dt.datetime = field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    progress: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "message_type": "response",
            "protocol_version": self.protocol_version.value,
            "request_id": self.request_id,
            "server_timestamp": self.server_timestamp.strftime(ISO8601),
            "status": self.status,
        }
        if self.progress is not None:
            payload["progress"] = self.progress
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "SupervisorResponse":
        data = json.loads(payload)
        server_timestamp = dt.datetime.strptime(
            data["server_timestamp"], ISO8601
        ).replace(tzinfo=dt.timezone.utc)
        progress = data.get("progress")
        result = data.get("result")
        error = data.get("error")
        protocol_version = ProtocolVersion(
            data.get("protocol_version", ProtocolVersion.V1_0.value)
        )
        return cls(
            request_id=data["request_id"],
            status=data["status"],
            protocol_version=protocol_version,
            server_timestamp=server_timestamp,
            progress=progress,
            result=result,
            error=error,
        )


SupervisorMessage = SupervisorRequest | SupervisorResponse
