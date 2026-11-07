import sys, json, time, threading
sys.path.insert(0, r"work/pylibs(未发布)")
import frida

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 0
OUT = r"runtime\frida_events.jsonl"
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 20

if not PID:
    print("usage: python frida_runner.py <pid> [seconds]")
    sys.exit(1)

events = []
lock = threading.Lock()
done = threading.Event()


def on_message(message, data):
    with lock:
        events.append(message)
    print(json.dumps(message, ensure_ascii=False)[:1500])


sess = frida.attach(PID)
script = sess.create_script(open(r"scripts\frida_ets.js", encoding="utf-8").read())
script.on("message", on_message)
script.load()
print("attached pid", PID, "— observing for", DURATION, "s")
time.sleep(DURATION)
try:
    sess.detach()
except Exception as e:
    print("detach err", e)
with open(OUT, "w", encoding="utf-8") as f:
    for e in events:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
print("events:", len(events), "->", OUT)
