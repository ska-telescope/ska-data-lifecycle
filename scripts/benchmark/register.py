"""Locust data registration test script."""
import os
import sys
import git

# As the test package is not part of the package deployment,
# need to add root directory to Python path.
_git_repo = git.Repo(os.path.abspath(__file__), search_parent_directories=True)
_git_root = _git_repo.git.rev_parse("--show-toplevel")
sys.path.append(_git_root)

import uuid

from bench import setup_storage
from locust import HttpUser, events, task

from ska_dlm.typer_types import JsonObjectOption
from tests.integration.client import dlm_storage_client
from tests.integration.client.exception_handler import dlm_raise_for_status


@events.init_command_line_parser.add_listener
def init_parser(parser):
    """Add token configuration option."""
    parser.add_argument("--token", help="Bearer token")


class Register(HttpUser):
    """Register test class."""

    def on_start(self):
        """Startup function called once when a Locust user starts."""
        dlm_storage_client.STORAGE_URL = self.environment.parsed_options.host
        dlm_storage_client.TOKEN = self.environment.parsed_options.token

        storage_config = {
            "location": "test_location",
            "name": "test_source",
            "type": "disk",
            "interface": "posix",
            "root_directory": "/",
            "config": {
                "name": "test_source",
                "type": "alias",
                "parameters": {"remote": "/"},
            },
        }

        setup_storage(storage_config)

    def register_data_item(
        self,
        item_name: str,
        uri: str,
        item_type: str,
        storage_name: str = "",
        storage_id: str = "",
        parents: str | None = None,
        metadata: JsonObjectOption = None,
        do_storage_access_check: bool = False,
    ):
        """Register data item with DLM."""
        params = {k: v for k, v in locals().items() if k != "self"}

        headers = {"Authorization": f"Bearer {self.environment.parsed_options.token}"}
        response = self.client.post(
            "/ingest/register_data_item",
            params=params,
            json=metadata,
            headers=headers,
            timeout=60,
        )
        dlm_raise_for_status(response)
        return response.json()

    @task
    def register_data_item_test(self):
        """Register a simple data item."""
        item_name = uuid.uuid4()
        uri = f"/{item_name}"

        self.register_data_item(
            item_name=item_name,
            uri=uri,
            item_type="file",
            storage_name="test_source",
            do_storage_access_check=False,
        )
