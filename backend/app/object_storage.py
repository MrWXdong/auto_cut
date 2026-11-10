from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlparse

import httpx

from app.config import Settings


class ObjectStorage(Protocol):
    async def put_file(self, path: Path, key: str) -> None: ...

    async def delete_key(self, key: str) -> None: ...

    async def delete_prefix(self, prefix: str) -> None: ...

    def presigned_url(self, key: str) -> str: ...


@dataclass(frozen=True)
class S3Config:
    endpoint_url: str
    bucket: str
    access_key: str
    secret_key: str
    region: str = "auto"
    prefix: str = "autocut"
    path_style: bool = True
    presign_seconds: int = 3600


class S3ObjectStorage:
    """Minimal S3-compatible storage using AWS Signature V4."""

    def __init__(self, config: S3Config) -> None:
        self.config = config
        self.endpoint = config.endpoint_url.rstrip("/")
        parsed = urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("S3 endpoint must be a valid http/https URL")
        if not config.bucket or not config.access_key or not config.secret_key:
            raise ValueError("S3 bucket, access key and secret key are required")

    @staticmethod
    def _sha256(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _signature_key(secret: str, date: str, region: str) -> bytes:
        date_key = hmac.new(
            f"AWS4{secret}".encode(),
            date.encode(),
            hashlib.sha256,
        ).digest()
        region_key = hmac.new(date_key, region.encode(), hashlib.sha256).digest()
        service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
        return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()

    @staticmethod
    def _canonical_query(params: dict[str, str]) -> str:
        return "&".join(
            f"{quote(key, safe='-_.~')}={quote(value, safe='-_.~')}"
            for key, value in sorted(params.items())
        )

    def _host(self) -> str:
        parsed = urlparse(self.endpoint)
        if self.config.path_style:
            return parsed.netloc
        return f"{self.config.bucket}.{parsed.netloc}"

    def _url(self, key: str) -> str:
        parsed = urlparse(self.endpoint)
        encoded_key = quote(f"{self.config.prefix}/{key}".lstrip("/"), safe="/~")
        if self.config.path_style:
            return f"{parsed.scheme}://{parsed.netloc}/{self.config.bucket}/{encoded_key}"
        return f"{parsed.scheme}://{self.config.bucket}.{parsed.netloc}/{encoded_key}"

    def _authorization(
        self,
        method: str,
        url: str,
        payload_hash: str,
        now: datetime,
    ) -> dict[str, str]:
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        host = urlparse(url).netloc
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        parsed = urlparse(url)
        canonical_request = "\n".join(
            [
                method,
                parsed.path or "/",
                parsed.query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        scope = f"{date_stamp}/{self.config.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                self._sha256(canonical_request.encode()),
            ]
        )
        signature = hmac.new(
            self._signature_key(self.config.secret_key, date_stamp, self.config.region),
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "Host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={self.config.access_key}/{scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
        }

    @staticmethod
    def _file_digest(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    @staticmethod
    async def _file_stream(path: Path):
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                yield chunk

    async def put_file(self, path: Path, key: str) -> None:
        payload_hash, size = self._file_digest(path)
        url = self._url(key)
        headers = self._authorization("PUT", url, payload_hash, datetime.now(UTC))
        headers["Content-Length"] = str(size)
        headers["Content-Type"] = "application/octet-stream"
        async with httpx.AsyncClient(timeout=600) as client:
            response = await client.put(url, headers=headers, content=self._file_stream(path))
            response.raise_for_status()

    async def delete_key(self, key: str) -> None:
        url = self._url(key)
        payload_hash = self._sha256(b"")
        headers = self._authorization("DELETE", url, payload_hash, datetime.now(UTC))
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.delete(url, headers=headers)
            if response.status_code not in {200, 204, 404}:
                response.raise_for_status()

    async def delete_prefix(self, prefix: str) -> None:
        # Minimal implementation: caller usually provides explicit keys.
        await self.delete_key(prefix)

    def presigned_url(self, key: str) -> str:
        url = self._url(key)
        parsed = urlparse(url)
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        scope = f"{date_stamp}/{self.config.region}/s3/aws4_request"
        query = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self.config.access_key}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(max(60, self.config.presign_seconds)),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = self._canonical_query(query)
        canonical_request = "\n".join(
            [
                "GET",
                parsed.path or "/",
                canonical_query,
                f"host:{parsed.netloc}\n",
                "host",
                "UNSIGNED-PAYLOAD",
            ]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                self._sha256(canonical_request.encode()),
            ]
        )
        signature = hmac.new(
            self._signature_key(self.config.secret_key, date_stamp, self.config.region),
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{url}?{canonical_query}&X-Amz-Signature={signature}"


def build_object_storage(settings: Settings) -> ObjectStorage | None:
    if settings.object_storage_backend.lower() != "s3":
        return None
    if not all(
        [
            settings.s3_endpoint_url,
            settings.s3_bucket,
            settings.s3_access_key,
            settings.s3_secret_key,
        ]
    ):
        return None
    return S3ObjectStorage(
        S3Config(
            endpoint_url=settings.s3_endpoint_url,
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            region=settings.s3_region,
            prefix=settings.s3_prefix,
            path_style=settings.s3_path_style,
            presign_seconds=settings.s3_presign_seconds,
        )
    )
