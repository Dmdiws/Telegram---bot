import json
import logging
import time

import jwt
import requests
from yandex_cloud_ml_sdk import YCloudML

from config import get_settings

logger = logging.getLogger(__name__)

IAM_TOKEN_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"


def _iam_token_from_service_account_key(key_file_path: str) -> str:
    with open(key_file_path, "r", encoding="utf-8") as f:
        key_data = json.load(f)

    now = int(time.time())
    payload = {
        "aud": IAM_TOKEN_URL,
        "iss": key_data["service_account_id"],
        "iat": now,
        "exp": now + 3600,
    }
    encoded_jwt = jwt.encode(
        payload,
        key_data["private_key"],
        algorithm="PS256",
        headers={"kid": key_data["id"]},
    )

    response = requests.post(IAM_TOKEN_URL, json={"jwt": encoded_jwt}, timeout=15)
    response.raise_for_status()
    return response.json()["iamToken"]


def _resolve_auth() -> str:
    settings = get_settings()

    if settings.yc_api_key:
        return settings.yc_api_key

    if settings.yc_service_account_key_file:
        logger.warning(
            "Аутентификация через YC_SERVICE_ACCOUNT_KEY_FILE даёт IAM-токен, "
            "который живёт не дольше 12 часов. Для долгоживущего процесса "
            "проще и надёжнее задать YC_API_KEY в .env."
        )
        return _iam_token_from_service_account_key(settings.yc_service_account_key_file)

    raise RuntimeError(
        "Не задан ни YC_API_KEY, ни YC_SERVICE_ACCOUNT_KEY_FILE в .env — "
        "нечем аутентифицироваться в Yandex Cloud."
    )


_settings = get_settings()
_sdk = YCloudML(folder_id=_settings.yc_folder_id, auth=_resolve_auth())

_doc_model = _sdk.models.text_embeddings("text-search-doc")
_query_model = _sdk.models.text_embeddings("text-search-query")


def embed_document(text: str) -> list[float]:
    return list(_doc_model.run(text))


def embed_query(text: str) -> list[float]:
    return list(_query_model.run(text))