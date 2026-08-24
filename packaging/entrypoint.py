import argparse

from quintara.qml_gui import launch

parser = argparse.ArgumentParser(prog="Quintara", description="Quintara desktop application")
parser.add_argument("--root", help=argparse.SUPPRESS)
args = parser.parse_args()
raise SystemExit(launch(args.root))
