import time

GROUP_COOLDOWN_SEC = 10
USER_COOLDOWN_SEC = 6

group_last_reply = {}
user_last_reply = {}

def in_cooldown(bucket: dict, key, cooldown: int) -> bool:
    now = time.time()
    last = bucket.get(key, 0)
    return now - last < cooldown

def mark_hit(bucket: dict, key):
    bucket[key] = time.time()

def group_in_cooldown(group_id: int) -> bool:
    return in_cooldown(group_last_reply, group_id, GROUP_COOLDOWN_SEC)

def user_in_cooldown(user_id: int) -> bool:
    return in_cooldown(user_last_reply, user_id, USER_COOLDOWN_SEC)

def mark_group_reply(group_id: int):
    mark_hit(group_last_reply, group_id)

def mark_user_reply(user_id: int):
    mark_hit(user_last_reply, user_id)
