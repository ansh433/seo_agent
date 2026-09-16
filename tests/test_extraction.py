"""Offline tests for compact page and site-file extraction."""

from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from seo_agent.audit.extraction import (
    extract_page_signals,
    parse_robots_txt,
    parse_sitemap_xml,
)
from seo_agent.audit.models import CollectionStatus, RedirectHop, RobotsDirective
from seo_agent.audit.url_policy import create_site_scope


@dataclass
class FakeResource:
    """Small HTTP-response stand-in used without network access."""

    requested_url: str
    final_url: str
    status_code: int
    headers: Mapping[str, str]
    body: str
    redirect_chain: tuple[RedirectHop, ...] = ()

    def text(self) -> str:
        return self.body


PAGE_HTML = """
<!doctype html>
<html>
  <head>
    <title>  Example   Platform </title>
    <meta name="description" content=" A useful SaaS platform. ">
    <meta name="robots" content="index, nofollow">
    <meta name="googlebot" content="max-snippet: -1">
    <link rel="canonical alternate" href="/canonical#section">
    <script>window.example = true;</script>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {"@type": "Organization", "@id": "https://example.com/#org",
           "name": "Example Inc", "url": "https://example.com/",
           "sameAs": ["https://social.example/example"],
           "contactPoint": {"@type": "ContactPoint", "name": "Support"}},
          {"@type": ["WebSite", "Thing"], "name": "Example"}
        ]
      }
    </script>
    <script type="application/ld+json">{"@type": </script>
  </head>
  <body>
    <nav><a href="/pricing">Pricing nav</a></nav>
    <main>
      <h1> Ship <span>better</span> software </h1>
      <h2>For teams</h2>
      <p>Meaningful product explanation.</p>
      <a href="/pricing#plans" rel="nofollow sponsored"> View pricing </a>
      <a href="https://www.example.com/docs">Docs</a>
      <a href="https://outside.example/path">Outside</a>
      <a href="mailto:hello@example.com">Email</a>
      <footer>Boilerplate footer</footer>
    </main>
  </body>
</html>
"""


@pytest.mark.unit
def test_extracts_compact_page_signals_from_resource() -> None:
    resource = FakeResource(
        requested_url="https://example.com/product",
        final_url="https://example.com/product",
        status_code=200,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "X-Robots-Tag": "googlebot: noindex, noarchive",
        },
        body=PAGE_HTML,
    )

    signals = extract_page_signals(
        resource,
        scope=create_site_scope("https://example.com"),
    )

    assert signals.url == "https://example.com/product"
    assert signals.final_url == "https://example.com/product"
    assert signals.status_code == 200
    assert signals.title == "Example Platform"
    assert signals.meta_description == "A useful SaaS platform."
    assert signals.canonical_url == "https://example.com/canonical"
    assert signals.meta_robots == ["index", "nofollow", "max-snippet:-1"]
    assert signals.x_robots_tag == ["noindex", "noarchive"]
    assert [(heading.level, heading.text) for heading in signals.headings] == [
        (1, "Ship better software"),
        (2, "For teams"),
    ]
    assert [link.url for link in signals.internal_links] == [
        "https://example.com/pricing",
        "https://www.example.com/docs",
    ]
    assert signals.internal_links[0].anchor_text == "Pricing nav"
    assert signals.internal_links[1].anchor_text == "Docs"
    assert signals.json_ld[0].valid is True
    assert signals.json_ld[0].block_index == 0
    assert signals.json_ld[0].schema_types == [
        "Organization",
        "WebSite",
        "Thing",
        "ContactPoint",
    ]
    assert signals.json_ld[0].entity_name == "Example Inc"
    assert signals.json_ld[0].properties == {"sameAs": ["https://social.example/example"]}
    assert signals.json_ld[1].valid is False
    assert signals.json_ld[1].block_index == 1
    assert signals.json_ld[1].error is not None
    assert signals.page_context == (
        "Ship better software For teams Meaningful product explanation. "
        "View pricing Docs Outside Email"
    )
    assert signals.collection_status == CollectionStatus.COMPLETE
    assert signals.collection_error is None
    assert "html" not in signals.model_dump()


@pytest.mark.unit
def test_extracts_from_raw_arguments_and_marks_partial_collection() -> None:
    signals = extract_page_signals(
        url="https://example.com/a",
        html=b"".join(
            (
                b"<html><head><link rel='canonical' href='javascript:bad'>",
                b"</head><body>x</body></html>",
            )
        ),
        status_code=200,
        headers={"content-type": "application/octet-stream"},
        body_truncated=True,
    )

    assert signals.collection_status == CollectionStatus.PARTIAL
    assert signals.canonical_url is None
    assert signals.collection_error is not None
    assert "truncated" in signals.collection_error
    assert "Canonical URL was invalid" in signals.collection_error
    assert "not HTML" in signals.collection_error


@pytest.mark.unit
def test_missing_body_preserves_collection_failure() -> None:
    signals = extract_page_signals(
        url="https://example.com/unavailable",
        html=None,
        collection_error="request timed out",
    )

    assert signals.collection_status == CollectionStatus.FAILED
    assert signals.collection_error == "request timed out"
    assert signals.title is None


@pytest.mark.unit
def test_context_and_links_are_bounded() -> None:
    signals = extract_page_signals(
        url="https://example.com/",
        html=(
            "<main><p>One two three four five six seven</p>"
            "<a href='/one'>One</a><a href='/two'>Two</a></main>"
        ),
        max_internal_links=1,
        max_context_chars=18,
    )

    assert len(signals.internal_links) == 1
    assert signals.page_context is not None
    assert len(signals.page_context) <= 18
    assert signals.page_context.endswith("…")


@pytest.mark.unit
def test_robots_parser_preserves_groups_and_sitemaps_compactly() -> None:
    robots = parse_robots_txt(
        """
        User-agent: Googlebot
        User-agent: Bingbot
        Disallow: /private
        Allow: /private/public

        User-agent: *
        Disallow:
        Sitemap: /sitemap.xml
        Sitemap: https://example.com/sitemap.xml#fragment
        """,
        url="https://example.com/robots.txt",
    )

    assert robots.available is True
    assert [(rule.user_agent, rule.directive, rule.path) for rule in robots.rules] == [
        ("googlebot", RobotsDirective.DISALLOW, "/private"),
        ("bingbot", RobotsDirective.DISALLOW, "/private"),
        ("googlebot", RobotsDirective.ALLOW, "/private/public"),
        ("bingbot", RobotsDirective.ALLOW, "/private/public"),
        ("*", RobotsDirective.DISALLOW, ""),
    ]
    assert robots.sitemap_urls == ["https://example.com/sitemap.xml"]
    assert robots.parse_error is None


@pytest.mark.unit
def test_robots_parser_reports_limits_and_invalid_sitemap() -> None:
    robots = parse_robots_txt(
        "User-agent: *\nDisallow: /a\nDisallow: /b\nSitemap: javascript:bad",
        url="https://example.com/robots.txt",
        max_rules=1,
    )

    assert len(robots.rules) == 1
    assert robots.parse_error is not None
    assert "truncated" in robots.parse_error
    assert "invalid sitemap" in robots.parse_error


@pytest.mark.unit
def test_unavailable_robots_file_does_not_imply_empty_rules() -> None:
    robots = parse_robots_txt(
        None,
        url="https://example.com/robots.txt",
        status_code=None,
        collection_error="DNS failure",
    )

    assert robots.available is None
    assert robots.rules == []
    assert robots.collection_error == "DNS failure"


@pytest.mark.unit
def test_parses_namespaced_urlset_with_deduplication_and_limit() -> None:
    sitemap = parse_sitemap_xml(
        """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/a#section</loc></url>
          <url><loc>https://example.com/a</loc></url>
          <url><loc>/b</loc></url>
          <url><loc>javascript:bad</loc></url>
        </urlset>
        """,
        url="https://example.com/sitemap.xml",
        max_urls=1,
    )

    assert sitemap.available is True
    assert sitemap.is_index is False
    assert sitemap.page_urls == ["https://example.com/a"]
    assert sitemap.truncated is True
    assert sitemap.parse_error == "Ignored 1 invalid sitemap location(s)"


@pytest.mark.unit
def test_parses_sitemap_index() -> None:
    sitemap = parse_sitemap_xml(
        """
        <sitemapindex>
          <sitemap><loc>https://example.com/one.xml</loc></sitemap>
          <sitemap><loc>https://example.com/two.xml</loc></sitemap>
        </sitemapindex>
        """,
        url="https://example.com/sitemap.xml",
    )

    assert sitemap.is_index is True
    assert sitemap.page_urls == []
    assert sitemap.child_sitemap_urls == [
        "https://example.com/one.xml",
        "https://example.com/two.xml",
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "xml",
    [
        "<urlset><url></urlset>",
        "<!DOCTYPE x [<!ENTITY e SYSTEM 'file:///etc/passwd'>]><urlset>&e;</urlset>",
        "<html><body>not a sitemap</body></html>",
    ],
)
def test_sitemap_parser_safely_reports_malformed_or_unsupported_xml(xml: str) -> None:
    sitemap = parse_sitemap_xml(xml, url="https://example.com/sitemap.xml")

    assert sitemap.available is True
    assert sitemap.page_urls == []
    assert sitemap.child_sitemap_urls == []
    assert sitemap.parse_error is not None
