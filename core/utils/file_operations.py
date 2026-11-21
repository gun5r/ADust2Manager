import os
from typing import Optional


def find_file_case_insensitive(folder: str, filename: str) -> Optional[str]:
    """Path of the first file under folder whose name equals filename ignoring case, else None."""
    wanted = filename.lower()
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower() == wanted:
                return os.path.join(root, f)
    return None
