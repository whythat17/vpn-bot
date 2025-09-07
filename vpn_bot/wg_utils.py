# vpn_bot/wg_utils.py
import base64, os
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")

def gen_wg_keypair() -> tuple[str, str]:
    """
    Возвращает (private_key_base64, public_key_base64) как в WireGuard.
    Это эквивалент wg genkey | wg pubkey
    """
    priv = X25519PrivateKey.generate()
    pub = priv.public_key()
    priv_b64 = _b64(priv.private_bytes(
        encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["serialization"]).serialization.Encoding.Raw,
        format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["serialization"]).serialization.PrivateFormat.Raw,
        encryption_algorithm=__import__("cryptography.hazmat.primitives.serialization", fromlist=["serialization"]).serialization.NoEncryption(),
    ))
    pub_b64 = _b64(pub.public_bytes(
        encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["serialization"]).serialization.Encoding.Raw,
        format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["serialization"]).serialization.PublicFormat.Raw,
    ))
    return priv_b64, pub_b64
