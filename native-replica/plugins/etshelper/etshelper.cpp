// plugin etshelper — ETS helper (API body signing + AES + misc)
// ABI: shared/stic_plugin.h ; contract: CONTRACT.md §6
#include "common.h"

#include <windows.h>

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <string>

namespace {

// Keys are part of the reverse-engineered wire protocol (CONTRACT.md §6).
constexpr const char* kKeyV2 = "94cfbda3fbfef02b93693f8bc153be82";
constexpr const char* kKeyV1 = "355ffbe95ccf4e9535a110170b445ab8";
constexpr const char* kKeyServe = "f05323cb91d422b2"; // AES-128 key ("k_serves")

constexpr const char* kPid = "pcWin";
constexpr const char* kKeyId = "202608";

PLN_LOG g_log = nullptr;
PLN_LOG g_wlog = nullptr;

std::string g_appDir;
std::string g_dataDir;

void Log(const std::string& msg) {
    if (g_log) g_log(0, msg.c_str());
}
void LogWarn(const std::string& msg) {
    if (g_wlog) g_wlog(1, msg.c_str());
    else if (g_log) g_log(1, msg.c_str());
}

// Accept both JSON strings and JSON numbers for values that are conceptually
// strings (e.g. "time" is sent as "<ms>" but clients may pass a number).
std::string ArgStr(const ets::json& args, const char* key, const std::string& def = "") {
    auto it = args.find(key);
    if (it == args.end() || it->is_null()) return def;
    if (it->is_string()) return it->get<std::string>();
    if (it->is_boolean()) return it->get<bool>() ? "true" : "false";
    if (it->is_number_integer()) return std::to_string(it->get<long long>());
    if (it->is_number_unsigned()) return std::to_string(it->get<unsigned long long>());
    if (it->is_number_float()) {
        char buf[64] = {};
        snprintf(buf, sizeof(buf), "%.17g", it->get<double>());
        return buf;
    }
    if (it->is_object() || it->is_array()) return it->dump();
    return def;
}

std::string UpperAscii(std::string s) {
    for (char& c : s) c = (char)std::toupper((unsigned char)c);
    return s;
}

std::string AppDataPath() {
    wchar_t buf[MAX_PATH + 1] = {};
    DWORD n = GetEnvironmentVariableW(L"APPDATA", buf, MAX_PATH);
    if (n == 0 || n > MAX_PATH) return "";
    return ets::WideToUtf8(std::wstring(buf, n));
}

std::string Handle(const std::string& action, const ets::json& args) {
    using ets::json;

    if (action == "encode_api_body_v2") {
        const std::string body = ArgStr(args, "body");
        const std::string time = ArgStr(args, "time");
        json r;
        r["pid"] = kPid;
        r["key_id"] = kKeyId;
        r["sign"] = ets::Md5Hex(std::string(kPid) + time + body + kKeyV2);
        r["sign_version"] = "2";
        return r.dump();
    }

    if (action == "encode_api_body" || action == "encode_api_body_v1") {
        const std::string body = ArgStr(args, "body");
        const std::string time = ArgStr(args, "time");
        const std::string sign = ets::Md5Hex(std::string("grlx") + time + body + kKeyV1);
        return json(sign).dump(); // bare JSON string, per CONTRACT §6
    }

    if (action == "encode_api_resp_v2") {
        const std::string response = ArgStr(args, "response");
        json r;
        r["pid"] = kPid;
        r["key_id"] = kKeyId;
        r["sign"] = ets::Md5Hex(std::string(kPid) + response + kKeyV2 + "test");
        r["sign_version"] = "2";
        return r.dump();
    }

    if (action == "aes_ecb_encrypt") {
        const std::string plain = ArgStr(args, "plain");
        const std::string b64 = ets::AesEcbEncryptB64(plain, kKeyServe);
        if (b64.empty() && !plain.empty())
            return ets::ErrReply(-1, "aes_ecb_encrypt failed");
        json r;
        r["b64"] = b64;
        return r.dump();
    }

    if (action == "aes_ecb_decrypt") {
        const std::string b64 = ArgStr(args, "b64");
        const std::string plain = ets::AesEcbDecryptB64(b64, kKeyServe);
        if (plain.empty() && !b64.empty())
            return ets::ErrReply(-1, "aes_ecb_decrypt failed");
        json r;
        r["plain"] = plain;
        return r.dump();
    }

    if (action == "get_appdata_path") {
        return json(AppDataPath()).dump();
    }

    if (action == "log_data") {
        const std::string tag = ArgStr(args, "tag");
        const std::string msg = ArgStr(args, "msg");
        Log("[log_data]" + (tag.empty() ? std::string() : ("[" + tag + "]")) + msg);
        json r;
        r["ok"] = true;
        return r.dump();
    }

    if (action == "check_update") {
        json r;
        r["rncode"] = 0;
        r["rnmsg"] = "no newer version";
        return r.dump();
    }

    LogWarn("etshelper: unknown action: " + action);
    return ets::NotImplementedReply();
}

} // namespace

extern "C" __declspec(dllexport) void PlnInitiliaze(PlnHost* host) {
    ets::g_host = host;
    if (!host) return;
    if (host->AppDir) g_appDir = host->AppDir;
    if (host->DataDir) g_dataDir = host->DataDir;
    Log("etshelper: initialized");
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
            auto parsed = ets::json::parse(raw); // throws on malformed input
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
