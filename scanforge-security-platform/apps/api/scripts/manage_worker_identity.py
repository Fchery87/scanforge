import argparse
import asyncio
from uuid import UUID

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.worker_identities import WorkerIdentityService

DEFAULT_WORKER_CAPABILITIES = (
    "scans:read",
    "scans:write",
    "scan:execute",
    "repositories:clone",
    "artifacts:write",
    "findings:write",
    "notifications:write",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage organization-scoped worker credentials.")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create a worker identity and show its credential once.")
    create.add_argument("organization_id", type=UUID)
    create.add_argument("name")
    create.add_argument("--capability", action="append", dest="capabilities")

    inspect = commands.add_parser("inspect", help="Show non-secret worker identity metadata.")
    inspect.add_argument("worker_id", type=UUID)

    disable = commands.add_parser("disable", help="Revoke a worker identity.")
    disable.add_argument("worker_id", type=UUID)

    rotate = commands.add_parser("rotate", help="Replace a worker credential and show it once.")
    rotate.add_argument("worker_id", type=UUID)
    return parser.parse_args()


def print_identity(identity) -> None:
    print(f"Worker identity: {identity.id}")
    print(f"Organization: {identity.organization_id}")
    print(f"Name: {identity.name}")
    print(f"Capabilities: {', '.join(identity.capabilities_json)}")
    print(f"Disabled: {'yes' if identity.disabled_at else 'no'}")
    print(f"Last seen: {identity.last_seen_at or 'never'}")


async def manage_identity() -> None:
    args = parse_args()
    if not settings.WORKER_CREDENTIAL_PEPPER:
        raise RuntimeError("WORKER_CREDENTIAL_PEPPER must be configured")

    async with AsyncSessionLocal() as db:
        service = WorkerIdentityService(db, settings.WORKER_CREDENTIAL_PEPPER)
        if args.command == "create":
            identity, credential = service.create_identity(
                organization_id=args.organization_id,
                name=args.name,
                capabilities=args.capabilities or DEFAULT_WORKER_CAPABILITIES,
            )
            await db.commit()
            print(f"Worker identity {identity.id} created for organization {args.organization_id}.")
            print(f"Credential (shown once): {credential}")
            return

        if args.command == "inspect":
            inspected_identity = await service.get_identity(args.worker_id)
            if inspected_identity is None:
                raise RuntimeError("Worker identity was not found")
            print_identity(inspected_identity)
            return

        if args.command == "disable":
            disabled_identity = await service.disable_identity(args.worker_id)
            if disabled_identity is None:
                raise RuntimeError("Worker identity was not found")
            print(f"Worker identity {disabled_identity.id} disabled.")
            return

        replacement, credential = await service.rotate_identity(args.worker_id)
        print(f"Worker identity {args.worker_id} disabled and replaced by {replacement.id}.")
        print(f"Credential (shown once): {credential}")


if __name__ == "__main__":
    asyncio.run(manage_identity())
