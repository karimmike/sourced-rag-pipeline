import pytest

from knowledge_agent.connectors.base import Connector


def test_connector_without_fetch_cannot_be_created():
    class NoFetch(Connector):
        name = "no_fetch"

    with pytest.raises(TypeError):
        NoFetch()
