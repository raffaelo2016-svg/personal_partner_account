"""Access the cabinet server through the runtime's configured SOCKS proxy.

Examples:
    python3 deploy/remote_access.py ssh pwd
    python3 deploy/remote_access.py ssh docker compose -f /srv/personal_partner_account/docker-compose.prod.yml ps
    python3 deploy/remote_access.py upload local-file.py /tmp/local-file.py
    python3 deploy/remote_access.py download /tmp/result.json result.json

Uses normal SSH authentication and host-key verification. No policy changes.
The proxy listener is read on every invocation because its port is temporary.
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

HOST = "root@161.104.52.194"


def connection_options():
    options = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
    proxy = os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")
    if proxy:
        url = urlsplit(proxy)
        if url.scheme not in {"socks5", "socks5h"} or url.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("Expected the runtime's loopback SOCKS5 proxy")
        if url.port is None or url.username or url.password:
            raise ValueError("Unsupported SOCKS proxy configuration")
        options += ["-o", f"ProxyCommand=/usr/bin/nc -w 15 -X 5 -x 127.0.0.1:{url.port} %h %p"]
    return options


def main(argv):
    if not argv:
        raise SystemExit("Usage: remote_access.py ssh COMMAND... | upload LOCAL REMOTE | download REMOTE LOCAL")
    options = connection_options()
    if argv[0] == "ssh" and len(argv) > 1:
        command = ["ssh", *options, HOST, shlex.join(argv[1:])]
    elif argv[0] == "upload" and len(argv) == 3:
        local, remote = argv[1:]
        if not Path(local).is_file() or not remote.startswith("/"):
            raise ValueError("Upload requires an existing local file and an absolute remote path")
        command = ["scp", *options, "--", local, HOST + ":" + remote]
    elif argv[0] == "download" and len(argv) == 3:
        remote, local = argv[1:]
        if not remote.startswith("/"):
            raise ValueError("Download requires an absolute remote path")
        command = ["scp", *options, "--", HOST + ":" + remote, local]
    else:
        raise SystemExit("Invalid arguments")
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
