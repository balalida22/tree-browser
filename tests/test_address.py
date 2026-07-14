from tree_browser.app import HOME_URL, normalise_address


def test_empty_address_goes_home() -> None:
    assert normalise_address("").toString() == HOME_URL


def test_domain_gets_https_scheme() -> None:
    assert normalise_address("example.com").toString() == "https://example.com"


def test_search_term_becomes_google_query() -> None:
    assert normalise_address("tree tabs").toString() == "https://www.google.com/search?q=tree+tabs"
