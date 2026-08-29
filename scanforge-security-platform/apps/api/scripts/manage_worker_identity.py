#!/usr/bin/env python3
"""Provision, rotate, or disable organization-scoped worker credentials."""
import argparse
import asyncio
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.services.worker_identities import WorkerIdentityService


async def run(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as db:
        service = WorkerIdentityService(db)
        if args.command == "create":
            identity, credential = await service.create(
                UUID(args.organization_id), args.name, set(args.capability)
            )
            print(f"worker_id={identity.id}")
            print(f"credential={credential}")
        elif args.command == "rotate":
            result = await service.rotate(UUID(args.worker_id))
            if not result:
                raise SystemExit("worker identity not found or disabled")
            identity, credential = result
            print(f"worker_id={identity.id}")
            print(f"credential={credential}")
        elif not await service.disable(UUID(args.worker_id)):
            raise SystemExit("worker identity not found")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("organization_id")
    create.add_argument("name")
    create.add_argument("--capability", action="append", default=[])
    rotate = commands.add_parser("rotate")
    rotate.add_argument("worker_id")
    disable = commands.add_parser("disable")
    disable.add_argument("worker_id")
    return root


if __name__ == "__main__":
    asyncio.run(run(parser().parse_args()))
