"""Benchmark utility main."""

import argparse
import logging
import sys

from scripts.benchmark.bench import open_yaml, run_bench, setup_clients

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Benchmark")
    parser.add_argument("--config", type=str, help="Config file")
    parser.add_argument("--output", type=str, help="JSON file output")

    args = parser.parse_args()
    bench = open_yaml(args.config)
    setup_clients(bench["dlm"]["url"], bench["dlm"]["token"])
    run_bench(
        bench=bench,
        output_file_path=args.output,
        migration_polltime=bench["dlm"]["migration_polltime"],
    )


if __name__ == "__main__":
    main()
