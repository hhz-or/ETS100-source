// plugin sysconfig — system configuration stub (contract: CONTRACT.md §6)
#include "common.h"

#include <windows.h>

#include <string>

namespace {

PLN_LOG g_log = nullptr;
PLN_LOG g_wlog = nullptr;

std::string g_appDir;
std::string g_dataDir;
std::string g_cacheDir;
std::string g_homeUrl;

void Log(const std::string& msg) {
    if (g_log) g_log(0, msg.c_str());
}
void LogWarn(const std::string& msg) {
    if (g_wlog) g_wlog(1, msg.c_str());
    else if (g_log) g_log(1, msg.c_str());
}

std::string Handle(const std::string& action, const ets::json& args) {
    (void)args;
    using ets::json;

    if (action == "init") {
        json r;
        r["ok"] = true;
        return r.dump();
    }

    LogWarn("sysconfig: not implemented action: " + action);
    return ets::NotImplementedReply();
}

} // namespace

extern "C" __declspec(dllexport) void PlnInitiliaze(PlnHost* host) {
    ets::g_host = host;
    if (!host) return;
    if (host->AppDir) g_appDir = host->AppDir;
    if (host->DataDir) g_dataDir = host->DataDir;
    if (host->CacheDir) g_cacheDir = host->CacheDir;
    if (host->HomeUrl) g_homeUrl = host->HomeUrl;
    Log("sysconfig: initialized");
}

extern "C" __declspec(dllexport) void PlnSetParam(const char* key, void* fn) {
    if (!key) return;
    const std::string k(key);
    if (k == "LOG") g_log = reinterpret_cast<PLN_LOG>(fn);
    else if (k == "WLOG") g_wlog = reinterpret_cast<PLN_LOG>(fn);
}

extern "C" __declspec(dllexport) void PlnOnProcessMessage(const char* action, const char* argsJson,
                                                          PLN_CALLBACK cb, const char* uid) {
    std::string out;
    try {
        ets::json args = ets::json::object();
        const char* raw = argsJson ? argsJson : "";
        if (*raw) {
            auto parsed = ets::json::parse(raw);
            if (parsed.is_object()) args = std::move(parsed);
        }
        out = Handle(action ? action : "", args);
    } catch (const std::exception& e) {
        out = ets::ErrReply(-1, e.what());
    } catch (...) {
        out = ets::ErrReply(-1, "unknown error");
    }
    if (cb) cb(uid ? uid : "", out.c_str());
}

extern "C" __declspec(dllexport) void PlnUnInitialize(void) {
    g_log = nullptr;
    g_wlog = nullptr;
    ets::g_host = nullptr;
}
