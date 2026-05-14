from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from flask import current_app


def _settings() -> dict:
    cfg = current_app.config
    return {
        "endpoint": cfg["S3_ENDPOINT"],
        "access_key": cfg["S3_ACCESS_KEY"],
        "secret_key": cfg["S3_SECRET_KEY"],
        "bucket": cfg["S3_BUCKET"],
        "region": cfg["S3_REGION"],
        "secure": bool(cfg["S3_SECURE"]),
    }


@lru_cache(maxsize=1)
def _build_client(endpoint: str, access_key: str, secret_key: str, region: str, secure: bool):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        use_ssl=secure,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def get_client():
    s = _settings()
    return _build_client(
        s["endpoint"],
        s["access_key"],
        s["secret_key"],
        s["region"],
        s["secure"],
    )


def ensure_bucket():
    s = _settings()
    client = get_client()
    bucket = s["bucket"]
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError:
        pass
    client.create_bucket(Bucket=bucket)


def upload_bytes(key: str, payload: bytes, content_type: str = "application/octet-stream"):
    ensure_bucket()
    bucket = _settings()["bucket"]
    client = get_client()
    client.put_object(
        Bucket=bucket,
        Key=key.lstrip("/"),
        Body=payload,
        ContentType=content_type,
    )


def download_bytes(key: str) -> bytes:
    bucket = _settings()["bucket"]
    client = get_client()
    obj = client.get_object(Bucket=bucket, Key=key.lstrip("/"))
    body = obj.get("Body")
    return body.read() if body else b""


def s3_uri(key: str) -> str:
    bucket = _settings()["bucket"]
    return f"s3://{bucket}/{key.lstrip('/')}"
