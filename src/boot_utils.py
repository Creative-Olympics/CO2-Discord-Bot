import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_start_parser():
    "Create a parser for the command-line interface"
    parser = argparse.ArgumentParser()
    parser.add_argument('--beta', '-b', help="Use the beta bot instead of the release", action="store_true")

    return parser

def setup_logger():
    """Setup the logger used by the bot
    It should use both console and a debug file"""
    log = logging.getLogger("cobot")
    log_format = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt="[%d/%m/%Y %H:%M:%S]")

    # file logging
    file_handler = RotatingFileHandler("logs/debug.log", maxBytes=int(1e6), backupCount=2, delay=True)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)

    # console logging
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(log_format)

    log.addHandler(file_handler)
    log.addHandler(stream_handler)

    log.setLevel(logging.DEBUG)
    return log
