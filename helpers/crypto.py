import hashlib

class CryptoHelper:
    def __init__(self, salt: str = "portal_core_default"):
        self.salt = salt

    def generate_digest(self, data: str) -> str:
        h = hashlib.sha512(self.salt.encode())
        h.update(data.encode())
        return h.hexdigest()

    def compare_digest(self, data: str, digest: str) -> bool:
        return self.generate_digest(data) == digest

class PayloadSigner:
    def __init__(self, key: str):
        self.key = key

    def sign(self, payload: dict) -> str:
        data = str(sorted(payload.items()))
        h = hashlib.sha256(self.key.encode())
        h.update(data.encode())
        return h.hexdigest()

    def verify(self, payload: dict, signature: str) -> bool:
        return self.sign(payload) == signature
