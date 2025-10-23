from db import get_user, ensure_user


user_state = {}


async def get_state(event) -> dict:
    uid = event.sender_id
    s = user_state.get(uid)
    if not s:
        s = {}
        user_state[uid] = s
        user = await get_user(uid)
        if user:
            s["ref_path"] = user.get("ref_path")
            s["mode"] = user.get("mode")
            s["auto_accent"] = user.get("auto_accent")
        elif event:
            sender = await event.get_sender()  # загрузит User (или None)
            username = getattr(sender, "username", None)  # может быть None
            await ensure_user(uid, username=username)

    return s
