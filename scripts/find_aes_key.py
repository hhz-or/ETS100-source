import re, base64, os

root = r"D:\ets-rea\work\frontend\bundles"
p = os.path.join(root, "001_statics.ets100.com__ets-student-pc-web__assets__index-dc0257dd.js")
b = open(p, "rb").read()

print("=== k_serves occurrences ===")
for m in list(re.finditer(rb"k_serves", b))[:10]:
    print("off", m.start(), b[max(0, m.start() - 400):m.start() + 400].decode("utf-8", "replace").replace("\n", " ")[:800])
    print("---")

print("\n=== envConfig definition ===")
for m in list(re.finditer(rb"function envConfig|envConfig\s*=", b))[:5]:
    print(b[max(0, m.start() - 300):m.start() + 1200].decode("utf-8", "replace").replace("\n", " ")[:1500])
    print("---")

print("\n=== VITE_ key-value map ===")
for m in list(re.finditer(rb"VITE_[A-Z_]+", b))[:40]:
    s = m.group(0).decode()
    print(s, "at", m.start())
