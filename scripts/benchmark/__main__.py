"""Benchmark utility main."""

import argparse
import logging
import sys

from scripts.benchmark.bench import run_bench

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Benchmark")
    parser.add_argument("--config", type=str, help="Config file")
    parser.add_argument("--output", type=str, help="JSON file output")

    args = parser.parse_args()

    run_bench(args.config, args.output)


if __name__ == "__main__":
    main()
