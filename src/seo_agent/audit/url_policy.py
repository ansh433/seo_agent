"""URL normalization, site scoping, and outbound-address safety checks."""

from __future__ import annotations

import asyncio
import ipaddress
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

from seo_agent.audit.models import SiteScope

DnsResolver = Callable[[str, int], Awaitable[Sequence[str]]]

_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_HTTP_DEFAULT_PORTS = {"http": 80, "https": 443}


class UrlPolicyError(ValueError):
    """Raised when a URL is malformed, out of scope, or unsafe to fetch."""


@dataclass(frozen=True, slots=True)
class UrlPolicy:
    """Reusable per-audit policy that validates every URL immediately before I/O."""

    scope: SiteScope
    resolver: DnsResolver

    @classmethod
    async def for_url(
        cls,
        initial_url: str,
        *,
        resolver: DnsResolver | None = None,
    ) -> tuple[str, UrlPolicy]:
        """Normalize and validate the initial URL, returning it with its policy."""
        normalized = normalize_url(initial_url)
        policy = cls(
            scope=create_site_scope(normalized),
            resolver=resolver or resolve_hostname,
        )
        await policy.validate_for_fetch(normalized)
        return normalized, policy

    async def validate_for_fetch(self, url: str) -> str:
        """Require an in-scope URL whose current DNS answers are all public."""
        normalized = require_in_scope(url, self.scope)
        await require_public_address(normalized, resolver=self.resolver)
        return normalized


def normalize_url(url: str, *, base_url: str | None = None) -> str:
    """Return a stable HTTP(S) URL without credentials or a fragment."""
    candidate = url.strip()
    if not candidate:
        raise UrlPolicyError("URL must not be empty")
    if _has_forbidden_characters(candidate):
        raise UrlPolicyError("URL contains forbidden characters")
    if base_url is not None:
        candidate = urljoin(normalize_url(base_url), candidate)

    try:
        parts = urlsplit(candidate)
    except ValueError as exc:
        raise UrlPolicyError("URL could not be parsed") from exc

    scheme = parts.scheme.lower()
    if scheme not in _HTTP_DEFAULT_PORTS:
        raise UrlPolicyError("Only HTTP and HTTPS URLs are allowed")
    if parts.username is not None or parts.password is not None:
        raise UrlPolicyError("Credentials in URLs are not allowed")

    hostname = _normalize_hostname(_required_hostname(parts))
    try:
        port = parts.port
    except ValueError as exc:
        raise UrlPolicyError("URL port is invalid") from exc

    if port is not None and not 1 <= port <= 65535:
        raise UrlPolicyError("URL port is invalid")

    netloc_host = f"[{hostname}]" if _is_ipv6_literal(hostname) else hostname
    if port is not None and port != _HTTP_DEFAULT_PORTS[scheme]:
        netloc = f"{netloc_host}:{port}"
    else:
        netloc = netloc_host

    path = _remove_dot_segments(parts.path or "/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def create_site_scope(initial_url: str, *, homepage_url: str | None = None) -> SiteScope:
    """Create the shared audit scope from the initial URL and effective port."""
    requested_url = normalize_url(initial_url)
    normalized_homepage = normalize_url(homepage_url or requested_url)
    initial_parts = urlsplit(requested_url)
    homepage_parts = urlsplit(normalized_homepage)
    initial_hostname = _required_hostname(initial_parts)
    homepage_hostname = _required_hostname(homepage_parts)
    port = initial_parts.port or _HTTP_DEFAULT_PORTS[initial_parts.scheme]
    homepage_port = homepage_parts.port or _HTTP_DEFAULT_PORTS[homepage_parts.scheme]
    if homepage_port != port:
        raise UrlPolicyError("Homepage URL changed the permitted site port")

    hostnames = _equivalent_hostnames(initial_hostname)
    if homepage_hostname not in hostnames:
        raise UrlPolicyError("Homepage URL is outside the permitted site scope")
    return SiteScope(
        requested_url=requested_url,
        homepage_url=normalized_homepage,
        allowed_hosts=sorted(hostnames),
        allowed_port=port,
    )


def is_in_scope(url: str, scope: SiteScope) -> bool:
    """Return whether a URL has an allowed hostname and effective port."""
    try:
        normalized = normalize_url(url)
        parts = urlsplit(normalized)
        hostname = _required_hostname(parts)
        port = parts.port or _HTTP_DEFAULT_PORTS[parts.scheme]
    except (UrlPolicyError, ValueError):
        return False
    return hostname in scope.allowed_hosts and port == scope.allowed_port


def require_in_scope(url: str, scope: SiteScope) -> str:
    """Return a normalized URL or raise when it is outside the audit scope."""
    normalized = normalize_url(url)
    if not is_in_scope(normalized, scope):
        raise UrlPolicyError("URL is outside the permitted site scope")
    return normalized


async def resolve_hostname(hostname: str, port: int) -> tuple[str, ...]:
    """Resolve a hostname asynchronously using the event loop's resolver."""
    try:
        answers = await asyncio.get_running_loop().getaddrinfo(
            hostname,
            port,
            type=0,
            proto=0,
        )
    except OSError as exc:
        raise UrlPolicyError("Hostname could not be resolved") from exc

    return tuple(dict.fromkeys(str(sockaddr[0]) for *_, sockaddr in answers))


async def require_public_address(url: str, *, resolver: DnsResolver | None = None) -> None:
    """Reject a URL unless every resolved address is globally routable."""
    normalized = normalize_url(url)
    parts = urlsplit(normalized)
    hostname = _required_hostname(parts)
    port = parts.port or _HTTP_DEFAULT_PORTS[parts.scheme]
    address_texts: Sequence[str]
    if _is_ip_literal(hostname):
        address_texts = (hostname,)
    else:
        address_texts = await (resolver or resolve_hostname)(hostname, port)

    if not address_texts:
        raise UrlPolicyError("Hostname resolved to no addresses")

    for address_text in address_texts:
        try:
            address = ipaddress.ip_address(address_text)
        except ValueError as exc:
            raise UrlPolicyError("Hostname resolver returned an invalid address") from exc
        if not _is_global_address(address):
            raise UrlPolicyError("URL resolves to a non-public address")


async def validate_outbound_url(
    url: str,
    *,
    scope: SiteScope,
    resolver: DnsResolver | None = None,
) -> str:
    """Validate site scope and DNS safety immediately before an outbound call."""
    normalized = require_in_scope(url, scope)
    await require_public_address(normalized, resolver=resolver)
    return normalized


def _required_hostname(parts: SplitResult) -> str:
    try:
        hostname = parts.hostname
    except ValueError as exc:
        raise UrlPolicyError("URL hostname is invalid") from exc
    if hostname is None or not hostname:
        raise UrlPolicyError("URL must include a hostname")
    return hostname


def _normalize_hostname(hostname: str) -> str:
    raw_hostname = hostname.rstrip(".")
    if not raw_hostname or "%" in raw_hostname:
        raise UrlPolicyError("URL hostname is invalid")
    try:
        address = ipaddress.ip_address(raw_hostname)
    except ValueError:
        try:
            ascii_hostname = raw_hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise UrlPolicyError("URL hostname is invalid") from exc
        if len(ascii_hostname) > 253 or any(
            not _HOST_LABEL.fullmatch(label) for label in ascii_hostname.split(".")
        ):
            raise UrlPolicyError("URL hostname is invalid") from None
        return ascii_hostname
    return address.compressed.lower()


def _has_forbidden_characters(value: str) -> bool:
    return "\\" in value or any(character.isspace() or ord(character) < 32 for character in value)


def _is_ip_literal(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def _equivalent_hostnames(hostname: str) -> set[str]:
    if _is_ip_literal(hostname):
        return {hostname}
    if hostname.startswith("www."):
        return {hostname, hostname.removeprefix("www.")}
    return {hostname, f"www.{hostname}"}


def _is_ipv6_literal(hostname: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(hostname), ipaddress.IPv6Address)
    except ValueError:
        return False


def _is_global_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return _is_global_address(address.ipv4_mapped)
    if isinstance(address, ipaddress.IPv6Address) and address.sixtofour is not None:
        return address.is_global and _is_global_address(address.sixtofour)
    if isinstance(address, ipaddress.IPv6Address) and address.teredo is not None:
        server, client = address.teredo
        return address.is_global and _is_global_address(server) and _is_global_address(client)
    return address.is_global and not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _remove_dot_segments(path: str) -> str:
    """Apply the RFC 3986 dot-segment algorithm without decoding the path."""
    input_path = path
    output: list[str] = []
    while input_path:
        if input_path.startswith("../"):
            input_path = input_path[3:]
        elif input_path.startswith("./"):
            input_path = input_path[2:]
        elif input_path.startswith("/./"):
            input_path = f"/{input_path[3:]}"
        elif input_path == "/.":
            input_path = "/"
        elif input_path.startswith("/../"):
            input_path = f"/{input_path[4:]}"
            if output:
                output.pop()
        elif input_path == "/..":
            input_path = "/"
            if output:
                output.pop()
        elif input_path in {".", ".."}:
            input_path = ""
        else:
            slash_index = input_path.find("/", 1 if input_path.startswith("/") else 0)
            if slash_index == -1:
                output.append(input_path)
                input_path = ""
            else:
                output.append(input_path[:slash_index])
                input_path = input_path[slash_index:]
    normalized = "".join(output)
    return normalized if normalized.startswith("/") else f"/{normalized}"
