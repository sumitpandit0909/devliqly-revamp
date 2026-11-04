"""Admin commands. Create the first Devliqly operator with:

python -m app.cli create-operator --name "Your Name" --email you@devliqly.in
"""

import argparse
import asyncio

from fastapi import HTTPException

from app.accounts import add_user, issue_setup_url
from app.db import get_engine, set_scope, standalone_session
from app.schemas import PersonInput


async def create_operator(name: str, email: str) -> None:
    async with standalone_session() as db:
        await set_scope(db, operator=True)
        user = await add_user(db, PersonInput(full_name=name, email=email), is_operator=True)
        setup_url = await issue_setup_url(db, user.id)
        await db.commit()
    await get_engine().dispose()
    print(f"Operator created. Open this link to choose a password (single use):\n{setup_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    operator = commands.add_parser("create-operator")
    operator.add_argument("--name", required=True)
    operator.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(create_operator(args.name, args.email.lower()))
    except HTTPException as exc:
        raise SystemExit(f"Error: {exc.detail}") from None


if __name__ == "__main__":
    main()
