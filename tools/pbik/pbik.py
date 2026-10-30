r"""Run pbik without installing: python tools\pbik\pbik.py <command> ..."""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pbikit.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
