import sys
from pathlib import Path

from studies.db import connect
from studies.normalize import load_certification


def main() -> None:
    cert_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "data/certifications/aws-certified-gen-ai-developer")
    conn = connect()
    print(load_certification(conn, cert_dir))


if __name__ == "__main__":
    main()
