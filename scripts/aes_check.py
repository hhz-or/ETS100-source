import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding


def aes_ecb_dec(b64, key):
    ct = base64.b64decode(b64)
    c = Cipher(algorithms.AES(key.encode()), modes.ECB())
    d = c.decryptor()
    pt = d.update(ct) + d.finalize()
    u = padding.PKCS7(128).unpadder()
    return u.update(pt) + u.finalize()


def aes_ecb_enc(s, key):
    p = padding.PKCS7(128).padder()
    data = p.update(s.encode()) + p.finalize()
    c = Cipher(algorithms.AES(key.encode()), modes.ECB())
    e = c.encryptor()
    return base64.b64encode(e.update(data) + e.finalize()).decode()


K_SERVES = "f05323cb91d422b2"
K = "ldlflfgirerjfkcf"

samples = ["C7sSWV8WdvF1ZHa46AwfVQ=="]
for s in samples:
    for k in (K_SERVES, K):
        try:
            print(k, s, "-> [已解密，明文不打印] len=", len(aes_ecb_dec(s, k)))
        except Exception as e:
            print(k, s, "ERR", type(e).__name__, e)

# search all logs for b64-looking phone/password fields to decrypt more samples
import re, json
txt = open(r"ETS\logs\ets_2026-11-4.log", "rb").read().decode("utf-8", "replace")
vals = set(re.findall(r'"(?:phone|encrypted_phone|bind_mobile|password)":"([A-Za-z0-9+/=]{16,64})"', txt))
print("\ncandidate fields:", len(vals))
for v in list(vals)[:10]:
    out = []
    for k in (K_SERVES, K):
        try:
            out.append((k, aes_ecb_dec(v, k)))
        except Exception:
            out.append((k, "ERR"))
    print(v, [(kk, "OK len=%d" % len(vv) if isinstance(vv, bytes) else vv) for kk, vv in out])

# roundtrip test
print("\nroundtrip:", aes_ecb_enc("1**********", K_SERVES))
