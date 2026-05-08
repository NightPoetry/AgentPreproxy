from agentpreproxy.config import Config, set_config


def pytest_configure():
    set_config(Config(debug=True, log_level="DEBUG"))
