"""Hide reserved no-login identifiers from partner contact email responses.

Run on the server with --apply. Keeps the original image and source for rollback;
does not deploy the other working-tree changes or change database schemas.
"""

import argparse
import ast
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MARKER = "    # Load generated attributes explicitly before response serialization.\n"
SMOKE = 'import asyncio\nfrom sqlalchemy import select\nfrom app.database import async_session\nfrom app.models.partner import Partner\nfrom app.services.partner_service import _partner_to_read\nasync def main():\n    async with async_session() as session:\n        partner = await session.scalar(select(Partner).where(Partner.deleted_at.is_(None)).limit(1))\n        assert partner is not None\n        assert _partner_to_read(partner, email="partner-43@no-login.invalid").email is None\n        assert _partner_to_read(partner, email="").email is None\n        assert _partner_to_read(partner, email="real@example.com").email == "real@example.com"\n    print("SMOKE_OK: reserved internal identifiers hidden; real emails preserved")\nasyncio.run(main())\n'


def patch_source(source):
    old = "        email=email,\n"
    new = '        email=None if not email or email.endswith("@no-login.invalid") else email,\n'
    if new in source:
        return source
    if source.count(old) != 1:
        raise ValueError("Unexpected partner mapper; no changes made")
    result = source.replace(old, new, 1)
    ast.parse(result)
    return result


def run(args, *, cwd, capture=False, input_text=None):
    result = subprocess.run(
        args, cwd=cwd, text=True, input=input_text,
        stdout=subprocess.PIPE if capture else None, check=True,
    )
    return result.stdout.strip() if capture else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--app-dir", type=Path, default=Path("/srv/personal_partner_account"))
    args = parser.parse_args()
    root = args.app_dir.resolve()
    source = root / "backend/app/services/partner_service.py"
    original_source = source.read_bytes()
    fixed_source = patch_source(original_source.decode()).encode()
    if not args.apply:
        print("Source checked. Run with --apply to back up, patch, deploy, and verify.")
        return

    compose = ["docker", "compose", "-f", "docker-compose.prod.yml"]

    def command(command_args, **kwargs):
        return run(command_args, cwd=root, **kwargs)

    container = command(compose + ["ps", "-q", "backend"], capture=True)
    if not container or "\n" in container:
        raise RuntimeError("Expected one running backend container; no changes made")
    metadata = json.loads(command(["docker", "inspect", container], capture=True))[0]
    image_name = metadata["Config"]["Image"]
    if "@" in image_name or image_name.startswith("sha256:"):
        raise RuntimeError("Expected a tagged backend image; no changes made")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = root.parent / "uritech-internal-partner-contact-fixes" / stamp
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(source, backup / "repository-partner_service.py")
    command(["docker", "cp", container + ":/app/app/services/partner_service.py",
             str(backup / "runtime-partner_service.py")])
    runtime_original = (backup / "runtime-partner_service.py").read_text()
    runtime_fixed = patch_source(runtime_original)
    old_tag = "uritech-internal-contact-backup:" + stamp.lower()
    command(["docker", "image", "tag", metadata["Image"], old_tag])
    (backup / "rollback.json").write_text(json.dumps({"image": image_name, "backup_image": old_tag}, indent=2))

    context = backup / "build"
    context.mkdir()
    (context / "partner_service.py").write_text(runtime_fixed)
    (context / "Dockerfile").write_text(
        "FROM " + old_tag + "\nCOPY partner_service.py /app/app/services/partner_service.py\n"
    )
    print("Backup:", backup, flush=True)
    switched = False
    source_written = False
    try:
        command(["docker", "build", "--pull=false", "--network=none", "-t", image_name, str(context)])
        switched = True
        if source.read_bytes() != original_source:
            raise RuntimeError("Repository source changed during preparation")
        if fixed_source != original_source:
            source.write_bytes(fixed_source)
            source_written = True
        command(compose + ["up", "-d", "--no-deps", "--no-build", "--force-recreate",
                           "--wait", "--wait-timeout", "120", "backend"])
        command(compose + ["exec", "-T", "backend", "python", "-"], input_text=SMOKE)
    except Exception:
        print("Installation failed; restoring the previous backend", flush=True)
        if source_written and source.read_bytes() == fixed_source:
            source.write_bytes(original_source)
        if switched:
            command(["docker", "image", "tag", old_tag, image_name])
            command(compose + ["up", "-d", "--no-deps", "--no-build", "--force-recreate",
                               "--wait", "--wait-timeout", "120", "backend"])
        raise
    print("FIX_OK: backend healthy, internal contact presentation verified. Backup:", backup)


if __name__ == "__main__":
    main()
