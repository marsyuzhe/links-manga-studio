"""Non-secret app profiles and Windows generic credentials; no plaintext fallback."""
from __future__ import annotations
import ctypes
import hashlib
import ipaddress
import os
import uuid
from ctypes import wintypes
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit


class TranslationError(Exception):
    """A stable safe code, never an HTTP body, key, URL or model output."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderProfile:
    id: str
    name: str
    provider_type: str
    base_url: str = "http://localhost:11434"
    model: str = ""
    timeout: int = 90
    max_retries: int = 3
    temperature: float = .3
    max_concurrency: int = 1
    enabled: bool = True

    @property
    def local(self):
        return self.provider_type in ("ollama", "local_openai")

    def validate(self):
        if self.provider_type not in ("manual", "openai", "ollama", "local_openai"):
            raise TranslationError("unsupported_provider")
        if not self.id or not self.name or len(self.id) > 100:
            raise TranslationError("invalid_profile")
        if not (1 <= self.timeout <= 600 and 0 <= self.max_retries <= 6 and
                0 <= self.temperature <= 2 and 1 <= self.max_concurrency <= 4):
            raise TranslationError("invalid_profile")
        if self.provider_type == "manual":
            return
        url = urlsplit(self.base_url)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or
                url.password or url.query or url.fragment or not self.model.strip()):
            raise TranslationError("invalid_endpoint")
        if self.local:
            try:
                loopback = ipaddress.ip_address(url.hostname).is_loopback
            except ValueError:
                loopback = url.hostname.lower() == "localhost"
            if not loopback:
                raise TranslationError("local_endpoint_only")

    @property
    def consent_id(self):
        return hashlib.sha256((self.id + self.provider_type + self.base_url).encode()).hexdigest()


class WindowsSecrets:
    """Keys remain in Windows Credential Manager, outside project/config/export."""
    PREFIX = "LinksMangaStudio/Translation/"

    def _api(self):
        if os.name != "nt":
            raise TranslationError("credential_store_unavailable")
        class Credential(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                        ("UserName", wintypes.LPWSTR)]
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                ctypes.POINTER(ctypes.POINTER(Credential))]
        api.CredReadW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        return api, Credential

    def set(self, profile_id: str, key: str):
        api, cls = self._api()
        data = key.encode("utf-8")
        if len(data) > 2400:
            raise TranslationError("invalid_key")
        blob = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        record = cls(Type=1, TargetName=self.PREFIX + profile_id,
                     CredentialBlobSize=len(data), CredentialBlob=blob, Persist=2,
                     UserName="Links Manga Studio")
        if not api.CredWriteW(ctypes.byref(record), 0):
            raise TranslationError("credential_store_unavailable")

    def get(self, profile_id: str) -> str:
        api, cls = self._api()
        pointer = ctypes.POINTER(cls)()
        if not api.CredReadW(self.PREFIX + profile_id, 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:
                return ""
            raise TranslationError("credential_store_unavailable")
        try:
            return ctypes.string_at(pointer.contents.CredentialBlob,
                                    pointer.contents.CredentialBlobSize).decode("utf-8")
        finally:
            api.CredFree(pointer)

    def delete(self, profile_id):
        api, _ = self._api()
        if not api.CredDeleteW(self.PREFIX+profile_id, 1, 0) and ctypes.get_last_error() != 1168:
            raise TranslationError("credential_store_unavailable")


class ProfileStore:
    """Persist non-secret profiles; credentials stay outside portable projects and source copies."""
    def __init__(self, config, secrets=None):
        self.config = config
        self.secrets = secrets or WindowsSecrets()

    def list(self):
        return [ProviderProfile(**row) for row in self.config.data.get("translation_profiles", [])]

    def get(self, profile_id, enabled_only=True):
        profile = next((p for p in self.list() if p.id == profile_id), None)
        if profile is None or (enabled_only and not profile.enabled):
            raise TranslationError("profile_unavailable")
        profile.validate()
        return profile

    def save(self, profile: ProviderProfile, key: str | None = None):
        profile.validate()
        if key is not None:
            self.secrets.set(profile.id, key)
        rows = [asdict(p) for p in self.list() if p.id != profile.id]
        self.config.data["translation_profiles"] = rows + [asdict(profile)]
        self.config.save()

    def key(self, profile):
        return self.secrets.get(profile.id) if profile.provider_type in ("openai", "local_openai") else ""

    def consented(self, profile):
        return profile.local or profile.provider_type == "manual" or profile.consent_id in self.config.data.get("translation_cloud_consent", [])

    def consent(self, profile):
        self.config.data.setdefault("translation_cloud_consent", []).append(profile.consent_id)
        self.config.save()


def new_profile(kind="ollama"):
    return ProviderProfile(str(uuid.uuid4()), "Local Ollama" if kind == "ollama" else "Provider", kind,
        "http://localhost:11434" if kind == "ollama" else "http://localhost:1234/v1" if kind == "local_openai" else "https://api.openai.com/v1",
        max_concurrency=2 if kind == "openai" else 1)
