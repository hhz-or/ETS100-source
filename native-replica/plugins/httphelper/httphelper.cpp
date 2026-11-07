// plugin httphelper — HTTP/HTTPS requests + file download via WinHTTP
// ABI: shared/stic_plugin.h ; contract: CONTRACT.md §6
#include "common.h"

#include <windows.h>
#include <winhttp.h>

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#pragma comment(lib, "winhttp.lib")

namespace fs = std::filesystem;

namespace {

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

std::string LowerAscii(std::string s) {
    for (char& c : s) c = (char)std::tolower((unsigned char)c);
    return s;
}

std::string TrimAscii(const std::string& s) {
    size_t b = 0, e = s.size();
    while (b < e && (unsigned char)s[b] <= ' ') ++b;
    while (e > b && (unsigned char)s[e - 1] <= ' ') --e;
    return s.substr(b, e - b);
}

bool IsValidUtf8(const std::string& s) {
    size_t i = 0, n = s.size();
    while (i < n) {
        unsigned char c = (unsigned char)s[i];
        size_t extra = 0;
        if (c < 0x80) { ++i; continue; }
        else if ((c & 0xE0) == 0xC0) { extra = 1; if (c < 0xC2) return false; }
        else if ((c & 0xF0) == 0xE0) { extra = 2; }
        else if ((c & 0xF8) == 0xF0) { extra = 3; if (c > 0xF4) return false; }
        else return false;
        if (i + extra >= n) return false;
        for (size_t k = 1; k <= extra; ++k)
            if (((unsigned char)s[i + k] & 0xC0) != 0x80) return false;
        i += extra + 1;
    }
    return true;
}

// Convert an HTTP response body into UTF-8 text, honouring a GB charset in
// Content-Type when the payload is not already valid UTF-8.
std::string BytesToUtf8(const std::string& bytes, const std::string& contentType) {
    if (bytes.empty()) return bytes;
    const std::string ct = LowerAscii(contentType);
    const bool gb = ct.find("charset=gb") != std::string::npos || ct.find("gb2312") != std::string::npos ||
                    ct.find("gbk") != std::string::npos || ct.find("gb18030") != std::string::npos;
    if (gb) {
        int wn = MultiByteToWideChar(936, 0, bytes.data(), (int)bytes.size(), nullptr, 0);
        if (wn > 0) {
            std::wstring w((size_t)wn, L'\0');
            MultiByteToWideChar(936, 0, bytes.data(), (int)bytes.size(), &w[0], wn);
            return ets::WideToUtf8(w);
        }
    }
    if (IsValidUtf8(bytes)) return bytes;
    // Last resort: interpret as the system ANSI code page rather than emitting
    // invalid UTF-8 (which JSON serialization would reject).
    int wn = MultiByteToWideChar(CP_ACP, 0, bytes.data(), (int)bytes.size(), nullptr, 0);
    if (wn > 0) {
        std::wstring w((size_t)wn, L'\0');
        MultiByteToWideChar(CP_ACP, 0, bytes.data(), (int)bytes.size(), &w[0], wn);
        return ets::WideToUtf8(w);
    }
    return bytes;
}

ets::json ParseHeaders(const std::string& rawUtf8) {
    ets::json h = ets::json::object();
    std::string lastKey;
    bool firstLine = true;
    size_t pos = 0;
    while (pos < rawUtf8.size()) {
        size_t nl = rawUtf8.find("\r\n", pos);
        std::string line = nl == std::string::npos ? rawUtf8.substr(pos) : rawUtf8.substr(pos, nl - pos);
        pos = nl == std::string::npos ? rawUtf8.size() : nl + 2;
        if (line.empty()) continue;
        if (firstLine) { // status line, e.g. "HTTP/1.1 200 OK"
            firstLine = false;
            continue;
        }
        if (line[0] == ' ' || line[0] == '\t') { // folded continuation
            if (!lastKey.empty()) {
                auto hit = h.find(lastKey);
                if (hit != h.end() && hit->is_string())
                    hit->get_ref<std::string&>() += " " + TrimAscii(line);
            }
            continue;
        }
        size_t colon = line.find(':');
        if (colon == std::string::npos) continue;
        std::string key = TrimAscii(line.substr(0, colon));
        std::string val = TrimAscii(line.substr(colon + 1));
        if (key.empty()) continue;
        lastKey = key;
        auto it = h.find(key);
        if (it == h.end()) h[key] = val;
        else if (it->is_string()) it->get_ref<std::string&>() += ", " + val;
    }
    // lowercase aliases (lookup convenience; values identical)
    ets::json out = ets::json::object();
    for (auto it = h.begin(); it != h.end(); ++it) {
        out[it.key()] = it.value();
        std::string low = LowerAscii(it.key());
        if (low != it.key() && !out.contains(low)) out[low] = it.value();
    }
    return out;
}

std::string Win32ErrorText(DWORD code) {
    LPWSTR buf = nullptr;
    DWORD n = FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
                                 FORMAT_MESSAGE_IGNORE_INSERTS,
                             nullptr, code, 0, (LPWSTR)&buf, 0, nullptr);
    std::string msg = "winhttp error " + std::to_string((unsigned long)code);
    if (n && buf) {
        std::wstring w(buf, n);
        while (!w.empty() && (w.back() == L'\r' || w.back() == L'\n' || w.back() == L' ')) w.pop_back();
        msg += ": " + ets::WideToUtf8(w);
    }
    if (buf) LocalFree(buf);
    return msg;
}

struct WinHttpHandles {
    HINTERNET session = nullptr;
    HINTERNET connect = nullptr;
    HINTERNET request = nullptr;
    ~WinHttpHandles() {
        if (request) WinHttpCloseHandle(request);
        if (connect) WinHttpCloseHandle(connect);
        if (session) WinHttpCloseHandle(session);
    }
};

bool OpenRequest(const std::string& urlUtf8, const std::string& method, int timeoutMs, WinHttpHandles& hs,
                 std::string& err) {
    std::wstring url = ets::Utf8ToWide(urlUtf8);
    if (url.empty()) {
        err = "url is required";
        return false;
    }

    wchar_t hostBuf[512] = {};
    wchar_t pathBuf[8192] = {};
    wchar_t extraBuf[8192] = {};
    URL_COMPONENTS uc = {};
    uc.dwStructSize = sizeof(uc);
    uc.lpszHostName = hostBuf;
    uc.dwHostNameLength = _countof(hostBuf);
    uc.lpszUrlPath = pathBuf;
    uc.dwUrlPathLength = _countof(pathBuf);
    uc.lpszExtraInfo = extraBuf;
    uc.dwExtraInfoLength = _countof(extraBuf);
    if (!WinHttpCrackUrl(url.c_str(), (DWORD)url.size(), 0, &uc)) {
        err = "invalid url: " + urlUtf8;
        return false;
    }
    const bool secure = uc.nScheme == INTERNET_SCHEME_HTTPS;
    if (uc.nScheme != INTERNET_SCHEME_HTTPS && uc.nScheme != INTERNET_SCHEME_HTTP) {
        err = "unsupported url scheme (only http/https)";
        return false;
    }
    std::wstring target = std::wstring(pathBuf) + extraBuf;

    hs.session = WinHttpOpen(L"ETS-Replica/1.0", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
                             WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hs.session) {
        hs.session = WinHttpOpen(L"ETS-Replica/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                 WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    }
    if (!hs.session) {
        err = Win32ErrorText(GetLastError());
        return false;
    }
    const int t = timeoutMs > 0 ? timeoutMs : 30000;
    WinHttpSetTimeouts(hs.session, t, t, t, t);

    hs.connect = WinHttpConnect(hs.session, hostBuf, uc.nPort, 0);
    if (!hs.connect) {
        err = Win32ErrorText(GetLastError());
        return false;
    }
    std::wstring wmethod = ets::Utf8ToWide(method.empty() ? "GET" : method);
    hs.request = WinHttpOpenRequest(hs.connect, wmethod.c_str(), target.c_str(), nullptr, WINHTTP_NO_REFERER,
                                    WINHTTP_DEFAULT_ACCEPT_TYPES, secure ? WINHTTP_FLAG_SECURE : 0);
    if (!hs.request) {
        err = Win32ErrorText(GetLastError());
        return false;
    }
    DWORD policy = WINHTTP_OPTION_REDIRECT_POLICY_ALWAYS;
    WinHttpSetOption(hs.request, WINHTTP_OPTION_REDIRECT_POLICY, &policy, sizeof(policy));
    return true;
}

std::wstring BuildHeaderBlock(const ets::json& headers, const std::string& body) {
    auto valToStr = [](const ets::json& v) -> std::string {
        if (v.is_string()) return v.get<std::string>();
        if (v.is_boolean()) return v.get<bool>() ? "true" : "false";
        if (v.is_number_integer()) return std::to_string(v.get<long long>());
        if (v.is_number_unsigned()) return std::to_string(v.get<unsigned long long>());
        if (v.is_number_float()) {
            char b[64] = {};
            snprintf(b, sizeof(b), "%.17g", v.get<double>());
            return b;
        }
        return v.dump();
    };

    std::wstring out;
    bool hasContentType = false;
    if (headers.is_object()) {
        for (auto it = headers.begin(); it != headers.end(); ++it) {
            const std::string name = it.key();
            const std::string low = LowerAscii(name);
            if (low == "content-length") continue; // WinHTTP sets it
            if (low == "content-type") hasContentType = true;
            out += ets::Utf8ToWide(name + ": " + valToStr(it.value()) + "\r\n");
        }
    }
    if (!body.empty() && !hasContentType) out += L"Content-Type: application/json; charset=utf-8\r\n";
    return out;
}

bool ReadResponseBody(HINTERNET request, std::string& out, std::string& err) {
    DWORD avail = 0;
    for (;;) {
        if (!WinHttpQueryDataAvailable(request, &avail)) {
            err = Win32ErrorText(GetLastError());
            return false;
        }
        if (avail == 0) break;
        std::string chunk(avail, '\0');
        DWORD read = 0;
        if (!WinHttpReadData(request, chunk.data(), avail, &read)) {
            err = Win32ErrorText(GetLastError());
            return false;
        }
        if (read == 0) break;
        chunk.resize(read);
        out += chunk;
    }
    return true;
}

bool DoRequest(const std::string& url, const std::string& method, const std::string& body,
               const ets::json& headers, int timeoutMs, std::string& statusText, DWORD& status,
               std::string& responseBody, std::string& responseHeaders, std::string& err) {
    WinHttpHandles hs;
    if (!OpenRequest(url, method, timeoutMs, hs, err)) return false;

    const std::wstring hdr = BuildHeaderBlock(headers, body);
    LPVOID bodyPtr = body.empty() ? WINHTTP_NO_REQUEST_DATA : (LPVOID)body.data();
    const DWORD bodyLen = (DWORD)body.size();
    if (!WinHttpSendRequest(hs.request,
                            hdr.empty() ? WINHTTP_NO_ADDITIONAL_HEADERS : hdr.c_str(),
                            hdr.empty() ? 0 : (DWORD)-1L, bodyPtr, bodyLen, bodyLen, 0)) {
        err = Win32ErrorText(GetLastError());
        return false;
    }
    if (!WinHttpReceiveResponse(hs.request, nullptr)) {
        err = Win32ErrorText(GetLastError());
        return false;
    }

    DWORD sc = 0, scLen = sizeof(sc);
    if (!WinHttpQueryHeaders(hs.request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                             WINHTTP_HEADER_NAME_BY_INDEX, &sc, &scLen, WINHTTP_NO_HEADER_INDEX)) {
        err = Win32ErrorText(GetLastError());
        return false;
    }
    status = sc;
    statusText = std::to_string((unsigned long)sc);

    DWORD hdrBytes = 0;
    WinHttpQueryHeaders(hs.request, WINHTTP_QUERY_RAW_HEADERS_CRLF, WINHTTP_HEADER_NAME_BY_INDEX, nullptr,
                        &hdrBytes, WINHTTP_NO_HEADER_INDEX);
    if (hdrBytes > 0) {
        std::wstring raw(hdrBytes / sizeof(wchar_t) + 2, L'\0');
        if (WinHttpQueryHeaders(hs.request, WINHTTP_QUERY_RAW_HEADERS_CRLF, WINHTTP_HEADER_NAME_BY_INDEX,
                                &raw[0], &hdrBytes, WINHTTP_NO_HEADER_INDEX)) {
            const size_t len = raw.find(L'\0');
            if (len != std::wstring::npos) raw.resize(len);
            responseHeaders = ets::WideToUtf8(raw);
        }
    }

    if (!ReadResponseBody(hs.request, responseBody, err)) return false;
    return true;
}

std::string Handle(const std::string& action, const ets::json& args) {
    using ets::json;

    if (action == "request") {
        const std::string url = ArgStr(args, "url");
        if (url.empty()) return ets::ErrReply(-1, "url is required");
        std::string method = ArgStr(args, "method", "GET");
        std::transform(method.begin(), method.end(), method.begin(),
                       [](unsigned char c) { return (char)std::toupper(c); });
        const std::string body = ArgStr(args, "body");
        int timeoutMs = 30000;
        if (args.contains("timeoutMs") && args["timeoutMs"].is_number())
            timeoutMs = (int)args["timeoutMs"].get<double>();
        json headers = json::object();
        if (args.contains("headers") && args["headers"].is_object()) headers = args["headers"];

        std::string statusText, respBody, respHeaders, err;
        DWORD status = 0;
        if (!DoRequest(url, method, body, headers, timeoutMs, statusText, status, respBody, respHeaders, err))
            return ets::ErrReply(-1, err);

        json h = ParseHeaders(respHeaders);
        json r;
        r["status"] = (int)status;
        r["body"] = BytesToUtf8(respBody, ArgStr(h, "content-type"));
        r["headers"] = h;
        return r.dump();
    }

    if (action == "download") {
        const std::string url = ArgStr(args, "url");
        std::string filePath = ArgStr(args, "filePath", ArgStr(args, "path"));
        if (url.empty()) return ets::ErrReply(-1, "url is required");
        if (filePath.empty()) return ets::ErrReply(-1, "filePath is required");

        WinHttpHandles hs;
        std::string err;
        if (!OpenRequest(url, "GET", 60000, hs, err)) return ets::ErrReply(-1, err);
        if (!WinHttpSendRequest(hs.request, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0))
            return ets::ErrReply(-1, Win32ErrorText(GetLastError()));
        if (!WinHttpReceiveResponse(hs.request, nullptr))
            return ets::ErrReply(-1, Win32ErrorText(GetLastError()));

        DWORD sc = 0, scLen = sizeof(sc);
        if (WinHttpQueryHeaders(hs.request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                                WINHTTP_HEADER_NAME_BY_INDEX, &sc, &scLen, WINHTTP_NO_HEADER_INDEX)) {
            if (sc < 200 || sc >= 300) {
                return ets::ErrReply(-1, "http status " + std::to_string((unsigned long)sc));
            }
        }

        const fs::path outPath = fs::path(ets::Utf8ToWide(filePath));
        std::error_code ec;
        if (outPath.has_parent_path()) fs::create_directories(outPath.parent_path(), ec);
        std::ofstream ofs(outPath, std::ios::binary | std::ios::trunc);
        if (!ofs) return ets::ErrReply(-1, "cannot open output file: " + filePath);

        uint64_t total = 0;
        DWORD avail = 0;
        for (;;) {
            if (!WinHttpQueryDataAvailable(hs.request, &avail))
                return ets::ErrReply(-1, Win32ErrorText(GetLastError()));
            if (avail == 0) break;
            std::string chunk(avail, '\0');
            DWORD read = 0;
            if (!WinHttpReadData(hs.request, chunk.data(), avail, &read))
                return ets::ErrReply(-1, Win32ErrorText(GetLastError()));
            if (read == 0) break;
            ofs.write(chunk.data(), (std::streamsize)read);
            if (!ofs) return ets::ErrReply(-1, "write failed: " + filePath);
            total += read;
        }
        ofs.close();

        json r;
        r["code"] = 0;
        r["filePath"] = filePath;
        r["size"] = total;
        return r.dump();
    }

    // upload / downloadresource / downloadsdk / monitornetspeed / isrpkexist / stopdownload
    LogWarn("httphelper: not implemented action: " + action);
    return ets::NotImplementedReply();
}

} // namespace

extern "C" __declspec(dllexport) void PlnInitiliaze(PlnHost* host) {
    ets::g_host = host;
    if (!host) return;
    if (host->AppDir) g_appDir = host->AppDir;
    if (host->DataDir) g_dataDir = host->DataDir;
    Log("httphelper: initialized");
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
