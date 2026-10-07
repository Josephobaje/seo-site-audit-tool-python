from seoaudit.checks import Issue, page_issues, score, site_issues
from seoaudit.parser import PageData, normalize_url, parse_page

HTML = """<html lang="en"><head><title> My   Page </title>
<meta name="Description" content="A page about things.">
<link rel="canonical" href="/canon"><meta name="viewport" content="width=device-width"></head>
<body><h1>Hello</h1><h2>A</h2><h4>Skipped</h4><img src="a.png"><img src="b.png" alt="B">
<a href="/x">x</a><a href="/x#frag">x again</a><a href="https://other.com/y">y</a><a href="mailto:a@b.c">m</a>
<script>var hidden = "words words words";</script><p>one two three</p></body></html>"""


def codes(issues):
    return {i.code for i in issues}


def test_parse_page_extracts_fields():
    p = parse_page(HTML, "https://site.com/page")
    assert p.title == "My Page"
    assert p.meta_description == "A page about things."
    assert p.canonical == "https://site.com/canon"
    assert p.lang == "en" and p.has_viewport
    assert p.h1 == ["Hello"] and p.headings == [1, 2, 4]
    assert p.images_missing_alt == ["https://site.com/a.png"] and p.image_count == 2
    assert p.internal_links == ["https://site.com/x"]  # fragment de-duplicated
    assert p.external_links == ["https://other.com/y"]
    assert "hidden" not in str(p.word_count) and p.word_count < 15  # scripts excluded


def test_normalize_url():
    assert normalize_url("HTTPS://Site.COM#top") == "https://site.com/"


def test_page_issue_rules():
    p = parse_page(HTML, "https://site.com/page")
    c = codes(page_issues(p))
    assert {"title-short", "description-short", "heading-skip", "img-alt-missing", "thin-content", "og-missing"} <= c
    assert "h1-missing" not in c and "viewport-missing" not in c


def test_missing_everything():
    c = codes(page_issues(parse_page("<html><body><p>hi</p></body></html>", "u")))
    assert {"title-missing", "description-missing", "h1-missing", "viewport-missing", "lang-missing", "canonical-missing"} <= c


def test_non_html_resource_is_skipped():
    assert page_issues(PageData(url="u", status=200)) == []


def test_http_error_page():
    assert codes(page_issues(PageData(url="u", status=404))) == {"http-error"}


def test_duplicates_across_pages():
    a = PageData(url="a", status=200, title="Same", meta_description="Desc")
    b = PageData(url="b", status=200, title="same", meta_description="Other")
    issues = site_issues([a, b])
    assert [i.code for i in issues] == ["title-duplicate", "title-duplicate"]


def test_score():
    assert score([], 1) == 100
    issues = [Issue("u", "error", "x", "", ""), Issue("u", "warning", "y", "", "")]
    assert score(issues, 1) == 79
    assert score(issues * 20, 1) == 0
