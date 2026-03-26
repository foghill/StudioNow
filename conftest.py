def pytest_configure(config):
    config.addinivalue_line("markers", "reachability: plain HTTP checks, no API key required")
    config.addinivalue_line("markers", "live: runs real scrapers via Firecrawl, requires FIRECRAWL_API_KEY")
