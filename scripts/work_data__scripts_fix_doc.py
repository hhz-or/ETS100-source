p=r".\docs\06_data.md"
s=open(p,encoding="utf-8").read()
fixes=[
("| `sb`/`os` | utf-8 | 8 | `Windows`（OS 类型） | |","| `os` | utf-8 | 8 | `Windows`（OS 类型） | |"),
("（证据：HTTP 缓存 `f_000002` 偏移 ≈0xD93EA，Vite 打包 JS；`work/data/_scripts/_scripts 中已整理为可复现脚本`）","（证据：HTTP 缓存 `f_000002` 偏移 ≈0xD93EA 的 Vite 打包 JS；可复现脚本见 `work/data/_scripts/extract_content.py`）"),
("**276 文件**：根 23 个 html、`css\\`27、`images\\`157（png148/gif9）、`js\\`55、`material\\`13（10 mp3、2 wav、`word\\worddict_data.json` 2,096,868 B）、`config`","**276 文件**：根 23 文件（22 个 html + 无扩展名 `config`）、`css\\`27、`images\\`157（png148/gif9）、`js\\`55、`material\\`13（10 mp3、2 wav、`word\\worddict_data.json` 2,096,868 B）"),
]
for a,b in fixes:
    if a not in s: print("NOT FOUND:",a[:60])
    s=s.replace(a,b)
open(p,"w",encoding="utf-8").write(s)
print("fixed")
