from __future__ import annotations
"""
RADD AI — Arabic Voice Understanding
WhatsApp voice note → Whisper transcription → Arabic text → pipeline.
Uses tempfile to avoid holding large audio bytes in memory.
"""
import tempfile
import structlog
from openai import AsyncOpenAI

from radd.config import settings

logger = structlog.get_logger()


async def transcribe_voice_note(
    audio_data: bytes,
    language: str = "ar",
    audio_format: str = "ogg",
) -> dict:
    """
    Transcribe a voice note using OpenAI Whisper.
    Writes to tempfile to avoid holding audio in memory during API call.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=True) as tmp:
            tmp.write(audio_data)
            tmp.flush()
            tmp.seek(0)
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=tmp,
                language=language,
                response_format="verbose_json",
                prompt="محادثة خدمة عملاء عربية — متجر إلكتروني سعودي",
            )

        text = transcription.text.strip()
        detected_language = getattr(transcription, "language", language)
        duration = getattr(transcription, "duration", 0)

        logger.info(
            "voice.transcribed",
            chars=len(text),
            language=detected_language,
            duration_seconds=duration,
        )

        return {
            "success": True,
            "text": text,
            "language": detected_language,
            "duration_seconds": duration,
            "confidence": "high" if len(text) > 10 else "low",
        }

    except Exception as e:
        logger.error("voice.transcription_failed", error=str(e))
        return {
            "success": False,
            "text": "",
            "error": str(e),
        }


async def process_whatsapp_voice(
    media_id: str,
    wa_token: str,
    language: str = "ar",
) -> dict:
    """
    Download a WhatsApp voice note and transcribe it.
    Returns transcription result with the text to feed into the pipeline.
    """
    import httpx

    headers = {"Authorization": f"Bearer {wa_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Step 1: Get media URL
            meta_resp = await client.get(
                f"https://graph.facebook.com/v20.0/{media_id}",
                headers=headers,
            )
            meta_resp.raise_for_status()
            media_url = meta_resp.json().get("url", "")
            mime_type = meta_resp.json().get("mime_type", "audio/ogg; codecs=opus")

            if not media_url:
                return {"success": False, "text": "", "error": "no_media_url"}

            # Step 2: Download audio
            audio_resp = await client.get(media_url, headers=headers)
            audio_resp.raise_for_status()
            audio_bytes = audio_resp.content

            # Determine format from MIME type
            fmt = "ogg"
            if "mp4" in mime_type or "mpeg" in mime_type:
                fmt = "mp3"
            elif "webm" in mime_type:
                fmt = "webm"
            elif "wav" in mime_type:
                fmt = "wav"

            # Step 3: Transcribe
            return await transcribe_voice_note(audio_bytes, language=language, audio_format=fmt)

        except Exception as e:
            logger.error("voice.whatsapp_download_failed", error=str(e))
            return {"success": False, "text": "", "error": str(e)}


def build_voice_fallback_response(dialect: str = "gulf") -> str:
    """Response when voice transcription fails or is unclear."""
    msgs = {
        "gulf": "سمعت رسالتك الصوتية بس ما قدرت أفهمها بوضوح. تقدر تكتبلي وش تبي؟ 😊",
        "egyptian": "سمعت الرسالة الصوتية بس مش واضحة. تقدر تكتبلي؟ 😊",
        "msa": "تلقيت رسالتك الصوتية ولكن لم أتمكن من فهمها بوضوح. هل يمكنك كتابة استفسارك؟",
    }
    return msgs.get(dialect, msgs["gulf"])
