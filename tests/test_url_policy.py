"""Unit tests for outbound URL normalization and safety policy."""

from collections.abc import Sequence

import pytest

from seo_agent.audit.url_policy import (
    UrlPolicy,
    UrlPolicyError,
    create_site_scope,
    is_in_scope,
    normalize_url,
    require_public_address,
    validate_outbound_url,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        ("HTTPS://ExAmPle.COM:443/a/./b/../c#part", "https://example.com/a/c"),
        ("http://example.com:80", "http://example.com/"),
        ("http://example.com:8080/path?q=1#ignored", "http://example.com:8080/path?q=1"),
        ("https://BÜCHER.example./", "https://xn--bcher-kva.example/"),
        ("https://[2001:0db8::1]:443/a", "https://[2001:db8::1]/a"),
        ("https://example.com/a//b", "https://example.com/a//b"),
    ],
)
def test_normalize_url(raw_url: str, expected: str) -> None:
    assert normalize_url(raw_url) == expected


@pytest.mark.unit
def test_normalize_relative_url_against_base() -> None:
    assert (
        normalize_url("../pricing#plans", base_url="https://example.com/products/widget/")
        == "https://example.com/products/pricing"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://example.com/file",
        "https://user:secret@example.com/",
        "https://example.com:99999/",
        "https://bad_host.example/",
        "https://example.com\\@127.0.0.1/",
        "https://exa mple.com/",
        "https:///missing-host",
        "https://[fe80::1%25eth0]/",
    ],
)
def test_normalize_url_rejects_invalid_or_ambiguous_inputs(url: str) -> None:
    with pytest.raises(UrlPolicyError):
        normalize_url(url)


@pytest.mark.unit
def test_scope_allows_only_initial_port_and_apex_www_pair() -> None:
    scope = create_site_scope("https://www.example.com/start")

    assert is_in_scope("https://example.com/other", scope)
    assert is_in_scope("https://www.example.com:443/other", scope)
    assert not is_in_scope("http://example.com/other", scope)
    assert not is_in_scope("https://blog.example.com/other", scope)
    assert not is_in_scope("https://www.example.com:444/other", scope)


@pytest.mark.unit
def test_scope_cannot_expand_to_unrelated_redirect_hostname() -> None:
    with pytest.raises(UrlPolicyError, match="scope"):
        create_site_scope(
            "https://example.com/start",
            homepage_url="https://attacker.example/landing",
        )


@pytest.mark.unit
async def test_outbound_validation_resolves_normalized_hostname_and_port() -> None:
    calls: list[tuple[str, int]] = []

    async def resolver(hostname: str, port: int) -> Sequence[str]:
        calls.append((hostname, port))
        return ["93.184.216.34"]

    scope = create_site_scope("https://example.com")

    result = await validate_outbound_url(
        "https://WWW.EXAMPLE.COM:443/a/../pricing#plans",
        scope=scope,
        resolver=resolver,
    )

    assert result == "https://www.example.com/pricing"
    assert calls == [("www.example.com", 443)]


@pytest.mark.unit
async def test_out_of_scope_url_is_rejected_before_dns() -> None:
    called = False

    async def resolver(_hostname: str, _port: int) -> Sequence[str]:
        nonlocal called
        called = True
        return ["93.184.216.34"]

    with pytest.raises(UrlPolicyError, match="scope"):
        await validate_outbound_url(
            "https://evil.example/path",
            scope=create_site_scope("https://example.com"),
            resolver=resolver,
        )

    assert called is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "192.0.2.10",
        "224.0.0.1",
        "0.0.0.0",  # noqa: S104 - URL policy must reject the unspecified address.
        "::1",
        "fe80::1",
        "fc00::1",
        "2001:db8::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "2002:7f00:1::",
    ],
)
async def test_public_address_check_rejects_every_non_global_answer(address: str) -> None:
    async def resolver(_hostname: str, _port: int) -> Sequence[str]:
        return [address]

    with pytest.raises(UrlPolicyError, match="non-public"):
        await require_public_address("https://example.com", resolver=resolver)


@pytest.mark.unit
async def test_public_address_check_rejects_mixed_public_and_private_answers() -> None:
    async def resolver(_hostname: str, _port: int) -> Sequence[str]:
        return ["93.184.216.34", "10.0.0.1"]

    with pytest.raises(UrlPolicyError, match="non-public"):
        await require_public_address("https://example.com", resolver=resolver)


@pytest.mark.unit
async def test_public_address_check_accepts_global_ipv4_and_ipv6() -> None:
    async def resolver(_hostname: str, _port: int) -> Sequence[str]:
        return ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"]

    await require_public_address("https://example.com", resolver=resolver)


@pytest.mark.unit
async def test_literal_private_address_does_not_use_resolver() -> None:
    async def resolver(_hostname: str, _port: int) -> Sequence[str]:
        raise AssertionError("literal addresses must not be resolved")

    with pytest.raises(UrlPolicyError, match="non-public"):
        await require_public_address("http://127.0.0.1", resolver=resolver)


@pytest.mark.unit
async def test_policy_factory_validates_initial_url_and_revalidates_each_target() -> None:
    calls: list[str] = []

    async def resolver(hostname: str, _port: int) -> Sequence[str]:
        calls.append(hostname)
        return ["93.184.216.34"]

    normalized, policy = await UrlPolicy.for_url("https://Example.com", resolver=resolver)
    target = await policy.validate_for_fetch("https://www.example.com/docs")

    assert normalized == "https://example.com/"
    assert target == "https://www.example.com/docs"
    assert calls == ["example.com", "www.example.com"]
