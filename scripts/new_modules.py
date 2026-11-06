import os, re, json

CH = r"D:\ets-rea\work\runtime\chunks_full"
targets = ["WordList-bcf43dd5.js", "WordPractice-d0b845cb.js", "WordPracticeResult-af1120b8.js",
           "WordQuestion-b14a59b7.js", "WordQuestionResult-4b370b1e.js", "PKMatch-ae6925c3.js",
           "readAloud-7c86f494.js", "readSentence-a8cded72.js", "readSentenceScoreInfo-587c753e.js",
           "networkSpeedWorker-456d7d90.js", "textInfo-b0b62b17.js", "index-62bff6b1.js", "index-85cbaae4.js"]

ep_pat = re.compile(r'"(/?[a-zA-Z][a-zA-Z0-9_\-]*(?:/[a-zA-Z0-9_\-{}.$]+){1,6})"')
act_pat = re.compile(r'sendMessage\([^,]{0,100},\s*"([A-Za-z0-9_]+)"\s*,\s*"([A-Za-z0-9_]+)"')
cn_pat = re.compile(r"[\u4e00-\u9fff][\u4e00-\u9fff，。！？、：；（）\w]{2,24}")
summary = {}
for name in targets:
    p = os.path.join(CH, name)
    if not os.path.exists(p):
        print("missing", name)
        continue
    t = open(p, encoding="utf-8", errors="replace").read()
    eps = sorted({m.group(1) for m in ep_pat.finditer(t) if not m.group(1).startswith("//")})
    acts = sorted({f"{m.group(1)}.{m.group(2)}" for m in act_pat.finditer(t)})
    cns = [s for s in cn_pat.findall(t) if len(s) >= 3][:12]
    ids = re.findall(r'\bid\s*[:=]\s*"([a-zA-Z_]{3,30})"', t)[:8]
    summary[name] = {"size": len(t), "endpoints": eps[:15], "actions": acts[:20], "cn": cns, "ids": ids}
    print(f"\n=== {name} ({len(t)} B) ===")
    print(" endpoints:", eps[:12])
    print(" actions:", acts[:10])
    print(" cn:", cns[:8])
json.dump(summary, open(r"D:\ets-rea\work\runtime\new_modules_analysis.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# find route paths referencing these components in live main bundle
main = open(os.path.join(CH, "index-e7d07c24.js"), encoding="utf-8", errors="replace").read()
for comp in ["WordList", "WordPractice", "PKMatch", "readAloud", "readSentence"]:
    idx = main.find('"' + comp)
    print(f"\nmain ref {comp}:", "found" if idx >= 0 else "not found",
          main[max(0, idx - 260):idx + 160].replace("\n", " ")[:420] if idx >= 0 else "")
