import argparse
import json
import sys

import yaml
from uvicorn.importer import import_from_string

parser = argparse.ArgumentParser(prog="extract_openapi.py")
parser.add_argument("app", help='App import string. Eg. "main:app"', default="main:app")
parser.add_argument("--app-dir", help="Directory containing the app", default=None)
parser.add_argument("--out", help="Output file ending in .json or .yaml", default="openapi.yaml")


def extract_openapi(
    app_module: str = "main.app", app_dir: str | None = None, out: str = "openapi.yaml"
):
    if app_dir is not None:
        print(f"adding {app_dir} to sys.path")
        sys.path.insert(0, app_dir)

    print(f"importing app from {app_module}")
    app = import_from_string(app_module)
    openapi = app.openapi()
    version = openapi.get("openapi", "unknown version")

    print(f"writing openapi spec v{version}")
    with open(out, "w") as f:
        if out.endswith(".json"):
            json.dump(openapi, f, indent=2)
        else:
            yaml.dump(openapi, f, sort_keys=False)

    print(f"spec written to {out}")


if __name__ == "__main__":
    args = parser.parse_args()
    extract_openapi(args.app, args.app_dir, args.out)
