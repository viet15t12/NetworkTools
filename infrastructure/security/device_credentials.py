"""RSA-OAEP + Fernet envelope encryption for device login passwords."""

from __future__ import annotations

import base64
import json
import os
import threading
from contextlib import closing
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from infrastructure.database import sqlcipher as sqlite3


ENVELOPE_PREFIX = "cams-credential-v1:"
PRIVATE_KEY_NAME = "device_credentials_private.pem"
PUBLIC_KEY_NAME = "device_credentials_public.pem"
_active_vault: "CredentialVault | None" = None
_vault_lock = threading.RLock()


class CredentialVaultError(RuntimeError):
    """Raised for missing, invalid, or unusable CAMS key material."""


def default_key_directory() -> Path:
    if os.name == "nt":
        root = os.environ.get("APPDATA")
        if not root:
            raise CredentialVaultError("APPDATA is unavailable; CAMS cannot store its keypair.")
        return Path(root) / "CAMS" / "keys"
    root = os.environ.get("XDG_CONFIG_HOME")
    return (Path(root) if root else Path.home() / ".config") / "cams" / "keys"


class CredentialVault:
    """Own an application-specific RSA keypair and an unlocked private key."""

    def __init__(self, key_directory: str | Path | None = None) -> None:
        self.key_directory = Path(key_directory or default_key_directory()).expanduser().resolve()
        self.private_key_path = self.key_directory / PRIVATE_KEY_NAME
        self.public_key_path = self.key_directory / PUBLIC_KEY_NAME
        self._private_key: rsa.RSAPrivateKey | None = None
        self._public_key: rsa.RSAPublicKey | None = None

    @property
    def exists(self) -> bool:
        return self.private_key_path.is_file() and self.public_key_path.is_file()

    @property
    def unlocked(self) -> bool:
        return self._private_key is not None and self._public_key is not None

    def create(self, passphrase: str) -> None:
        if not passphrase:
            raise ValueError("The CAMS master passphrase must not be empty.")
        self.key_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.key_directory, 0o700)
        except OSError:
            pass
        if self.private_key_path.exists() or self.public_key_path.exists():
            raise CredentialVaultError("CAMS credential key material already exists.")
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_bytes = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(passphrase.encode("utf-8")),
        )
        public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._write_exclusive(self.private_key_path, private_bytes, 0o600)
        try:
            self._write_exclusive(self.public_key_path, public_bytes, 0o644)
        except Exception:
            self.private_key_path.unlink(missing_ok=True)
            raise
        self._private_key = private_key
        self._public_key = private_key.public_key()

    def unlock(self, passphrase: str) -> None:
        if not self.exists:
            if self.private_key_path.exists() or self.public_key_path.exists():
                raise CredentialVaultError(
                    "The CAMS credential keypair is incomplete. Restore both key files from backup."
                )
            raise CredentialVaultError("The CAMS credential keypair does not exist.")
        try:
            private_key = serialization.load_pem_private_key(
                self.private_key_path.read_bytes(), password=passphrase.encode("utf-8")
            )
            public_key = serialization.load_pem_public_key(self.public_key_path.read_bytes())
        except (OSError, TypeError, ValueError) as exc:
            raise CredentialVaultError("The master passphrase or CAMS keypair is invalid.") from exc
        if not isinstance(private_key, rsa.RSAPrivateKey) or not isinstance(
            public_key, rsa.RSAPublicKey
        ):
            raise CredentialVaultError("The CAMS credential keypair must use RSA.")
        if private_key.public_key().public_numbers() != public_key.public_numbers():
            raise CredentialVaultError("The CAMS public and private keys do not match.")
        self._private_key = private_key
        self._public_key = public_key

    def lock(self) -> None:
        self._private_key = None
        self._public_key = None

    def encrypt(self, plaintext: str) -> str:
        self._require_unlocked()
        if not plaintext:
            return ""
        fernet_key = Fernet.generate_key()
        ciphertext = Fernet(fernet_key).encrypt(plaintext.encode("utf-8"))
        assert self._public_key is not None
        wrapped_key = self._public_key.encrypt(
            fernet_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        envelope = {
            "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
            "wrapped_key": base64.urlsafe_b64encode(wrapped_key).decode("ascii"),
        }
        return ENVELOPE_PREFIX + json.dumps(envelope, separators=(",", ":"), sort_keys=True)

    def decrypt(self, envelope: str) -> str:
        self._require_unlocked()
        if not envelope:
            return ""
        if not envelope.startswith(ENVELOPE_PREFIX):
            raise CredentialVaultError("A plaintext or unsupported device credential was found.")
        try:
            payload = json.loads(envelope[len(ENVELOPE_PREFIX) :])
            wrapped_key = base64.urlsafe_b64decode(payload["wrapped_key"].encode("ascii"))
            ciphertext = base64.urlsafe_b64decode(payload["ciphertext"].encode("ascii"))
            assert self._private_key is not None
            fernet_key = self._private_key.decrypt(
                wrapped_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            return Fernet(fernet_key).decrypt(ciphertext).decode("utf-8")
        except (
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            InvalidToken,
        ) as exc:
            raise CredentialVaultError("The stored device credential cannot be decrypted.") from exc

    def _require_unlocked(self) -> None:
        if not self.unlocked:
            raise CredentialVaultError("The CAMS credential vault is locked.")

    @staticmethod
    def _write_exclusive(path: Path, payload: bytes, mode: int) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise


def configure_active_vault(passphrase: str, key_directory: str | Path | None = None) -> CredentialVault:
    global _active_vault
    vault = CredentialVault(key_directory)
    if vault.exists:
        vault.unlock(passphrase)
    else:
        vault.create(passphrase)
    with _vault_lock:
        if _active_vault is not None:
            _active_vault.lock()
        _active_vault = vault
    return vault


def clear_active_vault() -> None:
    global _active_vault
    with _vault_lock:
        if _active_vault is not None:
            _active_vault.lock()
        _active_vault = None


def _vault() -> CredentialVault:
    with _vault_lock:
        if _active_vault is None:
            raise CredentialVaultError("The CAMS credential vault is locked.")
        return _active_vault


def encrypt_device_password(password: str | None) -> str | None:
    if password is None or password == "":
        return None
    return _vault().encrypt(str(password))


def decrypt_device_password(value: str | None) -> str:
    if value is None or value == "":
        return ""
    return _vault().decrypt(str(value))


def migrate_device_passwords(database_path: str | Path) -> int:
    """Encrypt legacy plaintext t01_devices passwords in one transaction."""
    changed = 0
    with closing(sqlite3.connect(database_path, timeout=30.0)) as connection:
        rows = connection.execute(
            "SELECT host, password FROM t01_devices WHERE password IS NOT NULL AND password <> '';"
        ).fetchall()
        with connection:
            for row in rows:
                password = str(row[1])
                if password.startswith(ENVELOPE_PREFIX):
                    continue
                connection.execute(
                    "UPDATE t01_devices SET password = ? WHERE host = ?;",
                    (_vault().encrypt(password), str(row[0])),
                )
                changed += 1
    return changed


__all__ = [
    "CredentialVault",
    "CredentialVaultError",
    "ENVELOPE_PREFIX",
    "clear_active_vault",
    "configure_active_vault",
    "decrypt_device_password",
    "default_key_directory",
    "encrypt_device_password",
    "migrate_device_passwords",
]
