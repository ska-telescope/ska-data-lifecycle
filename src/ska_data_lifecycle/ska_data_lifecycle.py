"""Main module."""
import logging

logger = logging.getLogger(__name__)


def main():
    """Control the main execution of the program."""
    print("main()")


if __name__ == "__main__":
    # NOTE: we call main() here, and then let main() call asyncio.run()
    #       if we were to call asyncio.run() here, then the meta-gen script cannot be run by poetry
    main()
