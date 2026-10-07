import json

from seoaudit.audit import run_audit
from seoaudit.cli import main


def by_page(result, suffix):
    return {i.code for i in result.issues if i.url.endswith(suffix)}


def test_crawl_and_audit_fixture_site(site_url):
    result = run_audit(site_url, max_pages=20, delay=0)
    urls = {p.url.replace(site_url, "/") for p in result.pages}
    assert {"/", "/about.html", "/services.html", "/blog/", "/missing-page.html"} <= urls

    assert any(i.code == "broken-link" and "missing-page.html" in i.message for i in result.issues)
    about = by_page(result, "/about.html")
    assert {"h1-multiple", "img-alt-missing", "viewport-missing", "lang-missing", "description-missing",
            "title-short", "heading-skip", "title-duplicate"} <= about
    services = by_page(result, "/services.html")
    assert {"h1-missing", "noindex", "title-duplicate"} <= services
    assert "description-short" in by_page(result, "/blog/")
    home = by_page(result, site_url[:-1] + "/")
    assert "thin-content" not in home and "h1-missing" not in home
    assert 0 < result.score < 100


def test_max_pages_limit(site_url):
    assert len(run_audit(site_url, max_pages=2, delay=0).pages) == 2


def test_cli_reports(site_url, tmp_path, capsys):
    html, js, csv = tmp_path / "r.html", tmp_path / "r.json", tmp_path / "r.csv"
    code = main([site_url, "--delay", "0", "-o", str(html), "-o", str(js), "-o", str(csv), "--min-score", "99"])
    assert code == 1
    data = json.loads(js.read_text())
    assert data["pages_crawled"] >= 5 and data["counts"]["error"] >= 1
    assert "SEO audit" in html.read_text()
    assert csv.read_text(encoding="utf-8-sig").startswith("severity,url,code")
    assert "Score:" in capsys.readouterr().out


def test_cli_rejects_bad_url(capsys):
    assert main(["example.com"]) == 2
