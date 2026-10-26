import sys
from pathlib import Path

from studies.db import backend, connect, load_env
from studies.normalize import load_certification


def main() -> None:
    cert_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "data/certifications/aws-certified-gen-ai-developer")
    load_env()
    conn = connect()
    print(f"Banco: {backend(conn)}")
    print(load_certification(conn, cert_dir))


if __name__ == "__main__":
    main()
