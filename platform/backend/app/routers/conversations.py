import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import Db, Org, OrgContext
from app.models import ConversationMessage, RepConversation, User
from app.schemas import ConversationMessageOut, ConversationOut

router = APIRouter(prefix="/api/org/conversations", tags=["conversations"])


def _visible_to(org: OrgContext):
    """Managers see the whole team's chats; reps see only their own."""
    query = select(RepConversation).where(RepConversation.organization_id == org.org_id)
    return query if org.can_manage else query.where(RepConversation.rep_user_id == org.user.id)


@router.get("")
async def list_conversations(db: Db, org: Org) -> list[ConversationOut]:
    rows = await db.execute(
        _visible_to(org)
        .add_columns(User.full_name, User.phone_e164)
        .join(User, RepConversation.rep_user_id == User.id)
        .order_by(RepConversation.last_inbound_at.desc().nulls_last())
    )
    return [
        ConversationOut(
            id=conversation.id,
            rep_user_id=conversation.rep_user_id,
            rep_name=name,
            rep_phone=phone,
            last_inbound_at=conversation.last_inbound_at,
        )
        for conversation, name, phone in rows
    ]


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: uuid.UUID,
    db: Db,
    org: Org,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ConversationMessageOut]:
    conversation = await db.scalar(_visible_to(org).where(RepConversation.id == conversation_id))
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    messages = await db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
    )
    return [ConversationMessageOut.model_validate(m) for m in reversed(messages.all())]
