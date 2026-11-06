import argparse
import json

from .pipeline import run


def main():
    p = argparse.ArgumentParser(
        description="Build retail SQL models, revenue bridge, Excel and management deck"
    )
    p.add_argument("command", choices=["run"], nargs="?", default="run")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--before", default="2011-10")
    p.add_argument("--after", default="2011-11")
    a = p.parse_args()
    print(json.dumps(run(a.refresh, a.before, a.after), indent=2))
