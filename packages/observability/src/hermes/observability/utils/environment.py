import sys


def is_production_environment() -> bool:
    """
    Determines if the current execution environment is production.
    Returns True if running on Linux, False otherwise.
    """
    return sys.platform.startswith("linux")
