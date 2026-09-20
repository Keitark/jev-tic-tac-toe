from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from tic_lab.benchmark import main


if __name__ == "__main__":
    raise SystemExit(main())
