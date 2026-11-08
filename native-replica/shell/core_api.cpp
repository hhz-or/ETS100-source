// Builtin "__core" actions: info / media_url / log / open_external.
#include "core_api.h"

#include <windows.h>
#include <shellapi.h>

#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

#include "common.h"
#include "media_server.h"
#include "ws_log.h"

namespace ets {
namespace {

std::string Trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && (unsigned char)s[a] <= ' ') ++a;
    while (b > a && (unsigned char)s[b - 1] <= ' ') --b;
    return s.substr(a, b - a);
}

std::string Lower(std::string s) {
    for (char& c : s) c = (char)std::tolower((unsigned char)c);
    return s;
}

bool StartsWithNoCase(const std::string& s, const std::string& prefix) {
    if (s.size() < prefix.size()) return false;
    for (size_t i = 0; i < prefix.size(); ++i) {
        if (std::tolower((unsigned char)s[i]) != std::tolower((unsigned char)prefix[i])) return false;
    }
    return true;
}

json ParseArgs(const std::string& argsJson) {
    if (argsJson.empty()) return json::object();
    json j = json::parse(argsJson, nullptr, false);
    if (j.is_discarded() || !j.is_object()) return json::object();
    return j;
}

std::string StringField(const json& j, const char* key) {
    auto it = j.find(key);
    if (it == j.end() || it->is_null()) return {};
    if (it->is_string()) return it->get<std::string>();
    return it->dump();
}

std::string ErrorReply(const std::string& msg) {
    json j;
    j["code"] = -1;
    j["msg"] = msg;
    return j.dump();
}

std::string NormalizeAction(const std::string& action) {
    std::string a = Lower(Trim(action));
    const std::string prefix = "__core/";
    if (a.rfind(prefix, 0) == 0) a = a.substr(prefix.size());
    return a;
}

std::string HandleInfo(const CoreContext& ctx) {
    json j;
    j["appDir"] = ctx.appDir;
    j["dataDir"] = ctx.dataDir;
    j["cacheDir"] = ctx.cacheDir;
    j["homeUrl"] = ctx.homeUrl;
    j["version"] = ctx.version;
    j["platform"] = "webview2";
    if (ctx.media) j["mediaPort"] = ctx.media->port();
    return j.dump();
}

std::string HandleMediaUrl(const CoreContext& ctx, const json& args) {
    std::string path = StringField(args, "path");
    if (path.empty()) path = StringField(args, "p");
    if (path.empty()) return ErrorReply("media_url: missing 'path'");
    if (!ctx.media) return ErrorReply("media_url: media server not available");
    std::string error;
    const std::string url = ctx.media->MakeUrl(path, &error);
    if (url.empty()) return ErrorReply("media_url: " + error);
    json j;
    j["url"] = url;
    return j.dump();
}

std::string HandleLog(const CoreContext& ctx, const json& args) {
    int level = kLogInfo;
    auto it = args.find("level");
    if (it != args.end()) {
        if (it->is_number_integer()) level = it->get<int>();
        else if (it->is_string()) {
            std::string lv = Lower(it->get<std::string>());
            if (lv == "debug") level = kLogDebug;
            else if (lv == "info") level = kLogInfo;
            else if (lv == "warn" || lv == "warning") level = kLogWarn;
            else if (lv == "error") level = kLogError;
        }
    }
    if (level < kLogDebug) level = kLogDebug;
    if (level > kLogError) level = kLogError;

    std::string tag = StringField(args, "tag");
    if (tag.empty()) tag = "js";
    std::string msg = StringField(args, "msg");
    if (msg.empty()) msg = StringField(args, "message");

    if (ctx.logger) ctx.logger->Log(level, tag, msg);
    json j;
    j["ok"] = true;
    return j.dump();
}

std::string HandleOpenExternal(const CoreContext& /*ctx*/, const json& args) {
    std::string url = StringField(args, "url");
    if (url.empty()) return ErrorReply("open_external: missing 'url'");
    if (!StartsWithNoCase(url, "http://") && !StartsWithNoCase(url, "https://") &&
        !StartsWithNoCase(url, "mailto:")) {
        return ErrorReply("open_external: unsupported url scheme");
    }
    HINSTANCE rc = ShellExecuteW(nullptr, L"open", Utf8ToWide(url).c_str(), nullptr, nullptr,
                                 SW_SHOWNORMAL);
    if (reinterpret_cast<INT_PTR>(rc) <= 32) {
        return ErrorReply("open_external: ShellExecute failed (" +
                          std::to_string((int)(INT_PTR)rc) + ")");
    }
    json j;
    j["ok"] = true;
    return j.dump();
}

std::string HandleTool(const CoreContext& ctx, const json& args) {
    const std::string name = Lower(StringField(args, "name"));
    if (name.empty()) return ErrorReply("tool: missing 'name'");
    auto exists = [](const std::wstring& p) -> bool {
        if (p.empty()) return false;
        DWORD attrs = GetFileAttributesW(p.c_str());
        return attrs != INVALID_FILE_ATTRIBUTES && !(attrs & FILE_ATTRIBUTE_DIRECTORY);
    };
    std::vector<std::wstring> candidates;
    if (name == "ffmpeg" || name == "ffmpeg.exe") {
        wchar_t envBuf[MAX_PATH * 2] = {};
        DWORD n = GetEnvironmentVariableW(L"ETS_FFMPEG", envBuf, _countof(envBuf));
        if (n > 0 && n < _countof(envBuf)) candidates.push_back(envBuf);
        const std::wstring appDir = Utf8ToWide(ctx.appDir);
        candidates.push_back(appDir + L"\\tools\\ffmpeg.exe");
        candidates.push_back(appDir + L"\\ffmpeg\\ffmpeg.exe");
        wchar_t found[MAX_PATH * 2] = {};
        if (SearchPathW(nullptr, L"ffmpeg.exe", nullptr, _countof(found), found, nullptr) > 0) {
            candidates.push_back(found);
        }
    } else {
        return ErrorReply("tool: unsupported tool '" + name + "'");
    }
    for (const auto& c : candidates) {
        if (exists(c)) {
            json j;
            j["code"] = 0;
            j["name"] = name;
            j["path"] = WideToUtf8(c);
            return j.dump();
        }
    }
    json j;
    j["code"] = -1;
    j["name"] = name;
    j["msg"] = "未找到工具 " + name + "：可设置环境变量 ETS_FFMPEG，或把 ffmpeg.exe 放到 <appDir>\\tools\\ 下";
    return j.dump();
}

} // namespace

std::string HandleCoreAction(const CoreContext& ctx, const std::string& action,
                             const std::string& argsJson) {
    try {
        const std::string name = NormalizeAction(action);
        const json args = ParseArgs(argsJson);
        if (name == "info") return HandleInfo(ctx);
        if (name == "media_url") return HandleMediaUrl(ctx, args);
        if (name == "log") return HandleLog(ctx, args);
        if (name == "open_external") return HandleOpenExternal(ctx, args);
        if (name == "tool") return HandleTool(ctx, args);
        return ErrorReply("unknown __core action: " + name);
    } catch (const std::exception& e) {
        return ErrorReply(std::string("__core exception: ") + e.what());
    } catch (...) {
        return ErrorReply("__core exception");
    }
}

} // namespace ets
