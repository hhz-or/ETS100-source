p=r".\docs\06_data.md"
s=open(p,encoding="utf-8").read()
fixes=[
("与 IndexedDB `wordDict`（28,322 条）互为源/缓存（差 1 条，词表版本差异）。",
 "与 IndexedDB `wordDict`（按含 `AudioUrl_EN` 计 28,322 条）规模一致，推断为同一词表的包内源文件/前端缓存两份。"),
("→ 按 `stid` 升序把 8 个 content 包依次绑定 `st1..st8`；",
 "→ 按 `stid` 升序把 8 个 content 包依次绑定 `st1..st8`（推断）；"),
]
for a,b in fixes:
    if a not in s: print("NOT FOUND:",a[:70])
    s=s.replace(a,b)
open(p,"w",encoding="utf-8").write(s)
print("ok")
