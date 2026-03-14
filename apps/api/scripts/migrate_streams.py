"""
RADD AI — Stream Migration Script
====================================
ينقل الرسائل من الـ streams الجديدة (messages:ws_*) إلى الـ stream القديم (messages).
يُستخدم فقط عند التراجع (rollback) عن Worker v2.

الاستخدام:
    python scripts/migrate_streams.py --direction forward  # old → new
    python scripts/migrate_streams.py --direction rollback  # new → old
"""

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("radd.scripts.migrate_streams")


async def migrate_forward(redis_client):
    """
    ينقل الرسائل من stream واحد (messages) إلى streams لكل workspace.
    """
    old_stream = "messages"
    
    # قراءة كل الرسائل المعلقة
    try:
        messages = await redis_client.xrange(old_stream, "-", "+")
        logger.info(f"Found {len(messages)} messages in old stream")
        
        migrated = 0
        for msg_id, msg_data in messages:
            workspace_id = msg_data.get(b"workspace_id", b"unknown")
            if isinstance(workspace_id, bytes):
                workspace_id = workspace_id.decode("utf-8")
            
            new_stream = f"messages:{workspace_id}"
            await redis_client.xadd(new_stream, msg_data)
            migrated += 1
        
        logger.info(f"Migrated {migrated} messages forward")
        
    except Exception as e:
        logger.error(f"Forward migration failed: {e}")


async def migrate_rollback(redis_client):
    """
    ينقل الرسائل من streams لكل workspace إلى stream واحد (messages).
    يُستخدم عند التراجع عن Worker v2.
    """
    old_stream = "messages"
    
    # اكتشاف كل الـ workspace streams
    try:
        keys = await redis_client.keys("messages:*")
        workspace_streams = [
            k.decode("utf-8") if isinstance(k, bytes) else k
            for k in keys
            if b":" in k if isinstance(k, bytes) else ":" in k
        ]
        
        logger.info(f"Found {len(workspace_streams)} workspace streams")
        
        total_migrated = 0
        for stream_key in workspace_streams:
            messages = await redis_client.xrange(stream_key, "-", "+")
            for msg_id, msg_data in messages:
                await redis_client.xadd(old_stream, msg_data)
                total_migrated += 1
            
            logger.info(f"Migrated {len(messages)} from {stream_key}")
        
        logger.info(f"Rollback complete: {total_migrated} messages moved to '{old_stream}'")
        
    except Exception as e:
        logger.error(f"Rollback migration failed: {e}")


async def check_pending(redis_client):
    """يتحقق من وجود رسائل معلقة (pending) في أي stream."""
    keys = await redis_client.keys("messages*")
    for key in keys:
        k = key.decode("utf-8") if isinstance(key, bytes) else key
        try:
            info = await redis_client.xinfo_stream(k)
            length = info.get("length", 0)
            if length > 0:
                logger.warning(f"Stream {k} has {length} messages")
        except Exception:
            pass


async def main():
    parser = argparse.ArgumentParser(description="RADD Stream Migration")
    parser.add_argument(
        "--direction",
        choices=["forward", "rollback", "check"],
        required=True,
        help="forward: old→new, rollback: new→old, check: show pending",
    )
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    args = parser.parse_args()
    
    import redis.asyncio as aioredis
    r = aioredis.from_url(args.redis_url, decode_responses=False)
    
    if args.direction == "forward":
        await migrate_forward(r)
    elif args.direction == "rollback":
        await migrate_rollback(r)
    elif args.direction == "check":
        await check_pending(r)
    
    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
