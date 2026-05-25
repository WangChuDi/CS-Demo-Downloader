"""Module entrypoint for `python -m cs_demo_downloader`."""
import sys

from .cli import main


if __name__ == "__main__":
    sys.exit(main())
