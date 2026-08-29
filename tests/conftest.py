import os

TEST_WORKSPACE_CREDENTIAL = "oscillink-test-workspace-credential"


def pytest_configure() -> None:
    os.environ["OSCILLINK_AGENT_WORKSPACE_CREDENTIAL"] = TEST_WORKSPACE_CREDENTIAL
