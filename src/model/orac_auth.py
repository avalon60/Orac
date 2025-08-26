# model/orac_auth.py  (additions)

import json, hmac, base64, hashlib, time
from dataclasses import dataclass
from typing import Optional, Callable

def _canonical_json(obj) -> bytes:
  return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")

@dataclass
class AuthResult:
  user: Optional[str]
  ok: bool
  reason: Optional[str] = None
  roles: tuple[str, ...] = ()

class FrameAuthProvider:
  def authenticate(self, frame: dict) -> AuthResult:
    raise NotImplementedError

class ZenFrameAuth(FrameAuthProvider):
  """
  Verify meta.auth for frames signed as:
    user|ts|nonce|route|sha256(payload)
  """
  def __init__(self, shared_secret: bytes, skew_secs: int = 300, nonce_seen: Optional[Callable[[str,int], bool]] = None):
    self.secret = shared_secret
    self.skew = skew_secs
    self.nonce_seen = nonce_seen

  def authenticate(self, frame: dict) -> AuthResult:
    try:
      meta = frame.get("meta") or {}
      auth = meta.get("auth") or {}
      route = frame.get("route") or ""
      payload = frame.get("payload") or {}
      user  = str(auth.get("user") or "")
      ts    = auth.get("ts")
      nonce = str(auth.get("nonce") or "")
      sig   = str(auth.get("sig") or "")
      if not (user and ts and nonce and sig and route):
        return AuthResult(None, False, "missing auth fields")

      now = int(time.time())
      tsi = int(ts)
      if abs(now - tsi) > self.skew:
        return AuthResult(None, False, "timestamp skew")

      if self.nonce_seen and not self.nonce_seen(nonce, tsi):
        return AuthResult(None, False, "replay")

      body_hash = hashlib.sha256(_canonical_json(payload)).hexdigest()
      to_sign = f"{user}|{tsi}|{nonce}|{route}|{body_hash}".encode("utf-8")
      expected = base64.b64encode(hmac.new(self.secret, to_sign, hashlib.sha256).digest()).decode("ascii")

      if not hmac.compare_digest(expected, sig):
        return AuthResult(None, False, "bad signature")

      return AuthResult(user=user, ok=True, roles=("user",))
    except Exception as e:
      return AuthResult(None, False, f"exception: {e}")

class FrameAuthChain(FrameAuthProvider):
  def __init__(self, providers: list[FrameAuthProvider]):
    self.providers = providers
  def authenticate(self, frame: dict) -> AuthResult:
    for p in self.providers:
      res = p.authenticate(frame)
      if res.ok:
        return res
    return AuthResult(None, False, "no provider accepted")
