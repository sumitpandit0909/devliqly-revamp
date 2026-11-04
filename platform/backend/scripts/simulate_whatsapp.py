"""Send a fake WhatsApp event to a running local server, signed the way Meta signs them.

uv run python scripts/simulate_whatsapp.py text --sender +919876543210 --body "Hello"
uv run python scripts/simulate_whatsapp.py photo --sender +919876543210
uv run python scripts/simulate_whatsapp.py text --sender +919876543210 --message-id wamid.same --times 3
uv run python scripts/simulate_whatsapp.py receipt --message-id wamid.abc --status delivered
"""

import argparse
import hashlib
import hmac
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings  # noqa: E402


def build_value(args: argparse.Namespace, line_id: str) -> dict:
    value: dict = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": line_id}}
    if args.kind == "receipt":
        value["statuses"] = [{"id": args.message_id, "status": args.status, "timestamp": str(int(time.time()))}]
        return value
    sender = args.sender.lstrip("+")
    message = {
        "from": sender,
        "id": args.message_id or f"wamid.sim.{uuid.uuid4().hex}",
        "timestamp": str(int(time.time())),
    }
    if args.kind == "text":
        message |= {"type": "text", "text": {"body": args.body}}
    else:
        message |= {"type": "image", "image": {"id": f"media-{uuid.uuid4().hex[:8]}", "mime_type": "image/jpeg"}}
    value["contacts"] = [{"profile": {"name": "Simulated Sender"}, "wa_id": sender}]
    value["messages"] = [message]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["text", "photo", "receipt"])
    parser.add_argument("--sender", default="+919876543210")
    parser.add_argument("--body", default="Hello")
    parser.add_argument("--message-id")
    parser.add_argument("--status", default="delivered")
    parser.add_argument("--times", type=int, default=1, help="Send the same event repeatedly, as a Meta retry would")
    parser.add_argument("--url", default="http://localhost:8000/webhooks/meta")
    args = parser.parse_args()
    if args.kind == "receipt" and not args.message_id:
        parser.error("receipt needs --message-id")

    settings = get_settings()
    body = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "sim", "changes": [{"value": build_value(args, settings.whatsapp_line_id)}]}],
    }
    raw = json.dumps(body).encode()
    signature = "sha256=" + hmac.new(settings.whatsapp_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    for _ in range(args.times):
        response = httpx.post(
            args.url,
            content=raw,
            headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
        )
        print(response.status_code, response.text)


if __name__ == "__main__":
    main()
