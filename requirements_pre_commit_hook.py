import os
import tempfile
import difflib


def check_requirements():
    # Freeze the current environment's dependencies into a temp file.
    tmp = tempfile.NamedTemporaryFile()
    tmp.close()
    os.system(f"pip freeze > {tmp.name}")

    # Check the diff between the temp requirements file and real requirements.txt.
    with open("requirements.txt", "r") as real_req, open(tmp.name, "r") as tmp_req:
        diff = difflib.context_diff(
            tmp_req.read().splitlines(1), real_req.read().splitlines(1)
        )

    # If the generator is exhausted, then there is no diff.
    # Otherwise, there is a diff.
    _exhausted = object()

    if next(diff, _exhausted) is not _exhausted:
        print("".join(diff))
        raise AssertionError(
            "Mismatch between current environment and frozen requirements.txt. Please update requirements.txt before committing!"
        )


if __name__ == "__main__":
    check_requirements()
