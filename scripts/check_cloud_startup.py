"""Brief localhost-only startup probe; never deploys or reads operational storage."""

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="contractorflow-startup-") as folder:
        unused_database = Path(folder) / "must-not-create.db"
        environment = dict(
            os.environ,
            CONTRACTORFLOW_DB_PATH=str(unused_database),
            CONTRACTORFLOW_DELIVERY_MODE="smtp",
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "cloud_demo/streamlit_app.py",
                "--server.address=127.0.0.1",
                f"--server.port={port}",
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
        try:
            deadline = time.monotonic() + 25
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Demo server exited before startup completed.")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1) as response:
                        assert response.status == 200
                        assert response.read().strip() == b"ok"
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Demo startup timed out.")
                    time.sleep(0.2)
            with urlopen(f"http://127.0.0.1:{port}/", timeout=3) as response:
                assert response.status == 200
            assert not unused_database.exists()
            print(
                "Cloud entry point startup and HTTP health passed on localhost. AppTest separately covers page execution."
            )
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                else:
                    os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
