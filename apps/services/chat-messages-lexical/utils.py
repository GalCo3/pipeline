from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import ChatMessage


def build_midur_ids(chat_message: ChatMessage) -> list[str] | None:
    """Resolve the midur ids a chat message belongs to.

    A group message is filed under its room; a direct message is filed under
    both participants. Returns None when the message carries too little to
    resolve, so the field stays absent rather than empty.
    """
    room_id = chat_message.room_id

    if chat_message.room_type != "direct":
        return [room_id] if room_id else None

    user_id = chat_message.user.id if chat_message.user else None
    users_num = chat_message.users_count

    if not room_id or not user_id or not users_num:
        return None

    if users_num == 1:
        return [user_id]

    # A direct room id is the two participant ids concatenated, in either
    # order, so cutting this user's id out leaves the other party's.
    before, _, after = room_id.partition(user_id)
    other_user_id = before or after

    return [user_id, other_user_id]
