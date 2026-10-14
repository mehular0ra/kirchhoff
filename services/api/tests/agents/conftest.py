def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls real Vertex AI; run with KIRCHHOFF_LIVE=1")
