"""The public unsubscribe link in follow-up emails. The signed token is the only thing needed."""

from html import escape

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse

from app.db import set_scope
from app.deps import Db
from app.followups import read_unsubscribe_token, record_opt_out
from app.ratelimit import PublicLimit

router = APIRouter(prefix="/u", tags=["unsubscribe"], include_in_schema=False)


def _page(body: str) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html lang="en"><head><meta charset="UTF-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        '<meta name="robots" content="noindex" /><title>Unsubscribe</title>'
        f'<link rel="stylesheet" href="/style.css" /></head><body class="centered"><main class="card">{body}</main>'
        "</body></html>"
    )


def _read(token: str):
    reader = read_unsubscribe_token(token)
    if reader is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link isn't valid")
    return reader


@router.get("/{token}", response_class=HTMLResponse, dependencies=[PublicLimit])
async def confirm_page(token: str) -> HTMLResponse:
    """Asks first, because mail scanners open links on their own."""
    _, email = _read(token)
    return _page(
        f"<h1>Unsubscribe</h1><p>Stop follow-up emails to {escape(email)}?</p>"
        f'<form method="post" action="/u/{escape(token)}"><button type="submit">Unsubscribe</button></form>'
    )


@router.post("/{token}", response_class=HTMLResponse, dependencies=[PublicLimit])
async def unsubscribe(token: str, db: Db) -> HTMLResponse:
    """Also what mail apps' one-click unsubscribe calls."""
    org_id, email = _read(token)
    await set_scope(db, org_id=org_id)
    await record_opt_out(db, org_id, "email", email, "unsubscribe_link")
    await db.commit()
    return _page("<h1>You're unsubscribed</h1><p>You won't get further follow-up emails from us.</p>")
