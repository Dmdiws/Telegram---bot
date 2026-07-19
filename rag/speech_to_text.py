import requests

from config import get_settings

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"


class SpeechRecognitionError(Exception):
    """Ошибка распознавания речи через Yandex SpeechKit."""


def recognize_voice(audio_bytes: bytes, lang: str = "ru-RU") -> str:
    settings = get_settings()

    params = {
        "topic": "general",
        "folderId": settings.yc_folder_id,
        "lang": lang,
        "format": "oggopus",
    }
    headers = {"Authorization": f"Api-Key {settings.yc_api_key}"}

    response = requests.post(
        STT_URL, params=params, headers=headers, data=audio_bytes, timeout=15
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("error_code"):
        raise SpeechRecognitionError(
            f"{payload.get('error_code')}: {payload.get('error_message')}"
        )

    return payload.get("result", "")