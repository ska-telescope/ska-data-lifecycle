"""Locust migration test script."""

import os
import re
import sys
import git

# As the test package is not part of the package deployment,
# need to add root directory to Python path.
_git_repo = git.Repo(os.path.abspath(__file__), search_parent_directories=True)
_git_root = _git_repo.git.rev_parse("--show-toplevel")
sys.path.append(_git_root)

from datetime import datetime

from bench import get_data_item, load_yaml, run_bench, setup_clients
from locust import HttpUser, events, run_single_user, task
from locust.exception import StopUser


@events.init_command_line_parser.add_listener
def init_parser(parser):
    """Add custom configuration option."""
    parser.add_argument("--migration_config",
                        env_var="LOCUST_MIGRATION_CONFIG",
                        help="Migration Config")
    parser.add_argument("--output_file",
                        env_var="LOCUST_MIGRATION_OUTPUT",
                        help="Statistics output",
                        default="./bench.json")


class Migrate(HttpUser):
    """Migration test class."""

    def on_start(self):
        """Startup function called once when a Locust user starts."""
        self.bench_config = load_yaml(self.environment.parsed_options.migration_config)
        setup_clients(self.bench_config["dlm"]["url"], self.bench_config["dlm"]["token"])

    def migration_status(self, record):
        """Migration callback service."""
        data_item = get_data_item(record["oid"], record["destination_storage_id"])
        dt = datetime.fromisoformat(
            re.sub(r'\.(\d{1,6})\d*', r'.\1', record["job_status"]["startTime"].replace("Z", "+00:00"))
        )  # Handle ISO format
        request_meta = {
            "request_type": "migration",
            "name": data_item[0]["uri"] if data_item else record["oid"],
            "start_time": dt.timestamp() * 1000.0,
            "response_time": float(record["job_stats"]["transferTime"]) * 1000.0,
            "response_length": int(record["job_stats"]["totalBytes"]),
            "response": None,
            "context": {},
            "exception": None,
        }
        self.environment.events.request.fire(**request_meta)

    @task
    def migration_test(self):
        """Simulate the registration of data from multiple clients in parallel."""
        run_bench(
            bench_config=self.bench_config,
            output_file_path=self.environment.parsed_options.output_file,
            migration_polltime=self.bench_config["dlm"]["migration_polltime"],
            migration_callback=self.migration_status,
        )
        raise StopUser()  # only want to run once


if __name__ == "__main__":
    run_single_user(Migrate)
