"""Apply only the partner-response loading fix to the running backend image.

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
SMOKE = '''import asyncio
from uuid import uuid4
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.schemas.partner import PartnerCreate
from app.services import partner_service
from app.services.partner_service import create_partner

async def main():
    # The diagnostic transaction must not leave an independently committed audit row.
    partner_service.audit_log = lambda **_kwargs: None
    email = "partner-fix-" + uuid4().hex + "@example.com"
    async with async_session() as session:
        try:
            result = await create_partner(session, PartnerCreate(
                email=email, password=uuid4().hex,
                company_name="Rollback-only regression check",
                director_name="Regression check", phone="+70000000000",
                court_fee_per_client=1700000, payment_term_days=10,
            ))
            assert result.id and result.updated_at and result.email == email
            assert result.court_fee_per_client == 1700000
            assert result.payment_term_days == 10
            print("Creation and response: OK")
        finally:
            await session.rollback()
    async with async_session() as session:
        assert await session.scalar(select(User.id).where(User.email == email)) is None
    print("SMOKE_OK: test transaction rolled back, no test partner saved")

asyncio.run(main())
'''


def patch_source(source):
    tree = ast.parse(source)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_partner"
    )
    lines = source.splitlines(keepends=True)
    section = "".join(lines[function.lineno - 1:function.end_lineno])
    if MARKER in section:
        return source
    # Also accept the same fix already applied manually inside this function.
    audit = section.find('    audit_log(action="create_partner",')
    if audit < 0:
        raise ValueError("Expected create_partner audit marker not found; no changes made")
    before_audit = section[:audit]
    schedule = before_audit.rfind("schedule_partner_creation(")
    if "await session.refresh(partner)" in before_audit[schedule:]:
        return source
    anchor = function.lineno - 1 + before_audit.count("\n")
    lines.insert(anchor, MARKER + "    await session.flush()\n    await session.refresh(partner)\n\n")
    result = "".join(lines)
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
    backup = root.parent / "uritech-partner-create-fixes" / stamp
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(source, backup / "repository-partner_service.py")
    command(["docker", "cp", container + ":/app/app/services/partner_service.py",
             str(backup / "runtime-partner_service.py")])
    runtime_original = (backup / "runtime-partner_service.py").read_text()
    runtime_fixed = patch_source(runtime_original)
    old_tag = "uritech-partner-create-backup:" + stamp.lower()
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
    print("FIX_OK: backend healthy, partner creation verified. Backup:", backup)


if __name__ == "__main__":
    main()
