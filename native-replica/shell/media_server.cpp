// Local HTTP media server (Winsock, 127.0.0.1:random) for <audio>/<img> playback.
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cwctype>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

#include "common.h"
#include "media_server.h"
#include "ws_log.h"

namespace ets {
namespace {

constexpr int kClientRecvTimeoutMs = 5000;
constexpr size_t kMaxRequestBytes = 16 * 1024;

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

std::wstring LowerW(const std::wstring& w) {
    std::wstring out = w;
    for (wchar_t& c : out) c = (wchar_t)std::towlower((wint_t)c);
    return out;
}

int HexVal(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

std::string UrlDecode(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (size_t i = 0; i < s.size(); ++i) {
        char c = s[i];
        if (c == '%' && i + 2 < s.size()) {
            int hi = HexVal(s[i + 1]), lo = HexVal(s[i + 2]);
            if (hi >= 0 && lo >= 0) {
                out.push_back((char)((hi << 4) | lo));
                i += 2;
                continue;
            }
        }
        out.push_back(c);
    }
    return out;
}

bool SendAll(SOCKET s, const char* data, size_t len) {
    size_t sent = 0;
    while (sent < len) {
        size_t chunk = std::min<size_t>(len - sent, 1u << 20);
        int n = send(s, data + sent, (int)chunk, 0);
        if (n <= 0) return false;
        sent += (size_t)n;
    }
    return true;
}

void SendSimple(SOCKET s, const char* status, const std::string& body, bool headOnly) {
    std::string resp = std::string("HTTP/1.1 ") + status +
                       "\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: " +
                       std::to_string(body.size()) +
                       "\r\nAccess-Control-Allow-Origin: *\r\nCache-Control: no-store\r\n"
                       "Connection: close\r\n\r\n";
    if (!headOnly) resp += body;
    SendAll(s, resp.data(), resp.size());
}

const char* ContentTypeFor(const std::string& path) {
    size_t dot = path.find_last_of('.');
    if (dot == std::string::npos) return "application/octet-stream";
    std::string ext = Lower(path.substr(dot + 1));
    if (ext == "mp3") return "audio/mpeg";
    if (ext == "m4a") return "audio/mp4";
    if (ext == "aac") return "audio/aac";
    if (ext == "wav") return "audio/wav";
    if (ext == "ogg") return "audio/ogg";
    if (ext == "flac") return "audio/flac";
    if (ext == "mp4") return "video/mp4";
    if (ext == "webm") return "video/webm";
    if (ext == "jpg" || ext == "jpeg") return "image/jpeg";
    if (ext == "png") return "image/png";
    if (ext == "gif") return "image/gif";
    if (ext == "webp") return "image/webp";
    if (ext == "svg") return "image/svg+xml";
    if (ext == "bmp") return "image/bmp";
    if (ext == "json") return "application/json; charset=utf-8";
    if (ext == "txt") return "text/plain; charset=utf-8";
    if (ext == "html" || ext == "htm") return "text/html; charset=utf-8";
    if (ext == "js") return "text/javascript; charset=utf-8";
    if (ext == "css") return "text/css; charset=utf-8";
    return "application/octet-stream";
}

std::string ReadRequest(SOCKET s) {
    std::string data;
    char buf[2048];
    while (data.size() < kMaxRequestBytes) {
        int n = recv(s, buf, (int)sizeof(buf), 0);
        if (n <= 0) break;
        data.append(buf, (size_t)n);
        if (data.find("\r\n\r\n") != std::string::npos) break;
    }
    return data;
}

// Returns the value of a header from the raw request text ("" when absent).
std::string HeaderValue(const std::string& request, const std::string& name) {
    size_t pos = request.find("\r\n");
    if (pos == std::string::npos) return {};
    const std::string needle = Lower(name) + ":";
    while (pos != std::string::npos) {
        size_t lineStart = pos + 2;
        size_t lineEnd = request.find("\r\n", lineStart);
        if (lineEnd == std::string::npos) lineEnd = request.size();
        std::string line = request.substr(lineStart, lineEnd - lineStart);
        std::string low = Lower(line);
        if (low.rfind(needle, 0) == 0) return Trim(line.substr(needle.size()));
        pos = (lineEnd == request.size()) ? std::string::npos : lineEnd;
    }
    return {};
}

bool ParseRange(const std::string& value, long long size, long long* start, long long* length) {
    std::string v = Trim(value);
    if (!StartsWithNoCase(v, "bytes=")) return false;
    v = Trim(v.substr(6));
    if (v.find(',') != std::string::npos) return false; // multi-range unsupported
    size_t dash = v.find('-');
    if (dash == std::string::npos) return false;
    std::string a = Trim(v.substr(0, dash));
    std::string b = Trim(v.substr(dash + 1));
    if (a.empty() && b.empty()) return false;
    if (size <= 0) return false;

    if (a.empty()) { // suffix range: last N bytes
        long long n = std::atoll(b.c_str());
        if (n <= 0) return false;
        if (n > size) n = size;
        *start = size - n;
        *length = n;
        return true;
    }
    long long s = std::atoll(a.c_str());
    if (s < 0 || s >= size) return false;
    long long e = b.empty() ? size - 1 : std::atoll(b.c_str());
    if (e < s) return false;
    if (e >= size) e = size - 1;
    *start = s;
    *length = e - s + 1;
    return true;
}

} // namespace

MediaServer::~MediaServer() { Stop(); }

bool MediaServer::Start(const std::string& cacheDir, Logger* logger) {
    cacheDir_ = cacheDir;
    logger_ = logger;
    EnsureDir(cacheDir_);

    WSADATA wsa{};
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        if (logger_) logger_->Error("media", "WSAStartup failed");
        return false;
    }

    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) {
        if (logger_) logger_->Error("media", "socket() failed");
        WSACleanup();
        return false;
    }

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = 0;
    if (bind(s, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == SOCKET_ERROR ||
        listen(s, SOMAXCONN) == SOCKET_ERROR) {
        if (logger_) logger_->Error("media", "bind/listen failed");
        closesocket(s);
        WSACleanup();
        return false;
    }

    int len = sizeof(addr);
    if (getsockname(s, reinterpret_cast<sockaddr*>(&addr), &len) == 0) {
        port_.store((int)ntohs(addr.sin_port));
    }
    listenSock_.store(static_cast<std::uintptr_t>(s));
    stop_.store(false);
    running_.store(true);
    acceptThread_ = std::thread([this]() { AcceptLoop(); });
    if (logger_) {
        logger_->Info("media", "media server listening on http://127.0.0.1:" +
                                   std::to_string(port_.load()) + " (cache=" + cacheDir_ + ")");
    }
    return true;
}

void MediaServer::Stop() {
    if (!running_.exchange(false)) {
        if (stop_.exchange(true)) return;
    }
    stop_.store(true);
    const std::uintptr_t listenSock = listenSock_.exchange(
        static_cast<std::uintptr_t>(~std::uintptr_t(0)));
    if (listenSock != static_cast<std::uintptr_t>(~std::uintptr_t(0))) {
        closesocket(static_cast<SOCKET>(listenSock));
    }
    if (acceptThread_.joinable()) acceptThread_.join();
    WSACleanup();
}

void MediaServer::AcceptLoop() {
    SOCKET listenSock = static_cast<SOCKET>(listenSock_.load());
    while (!stop_.load()) {
        SOCKET client = accept(listenSock, nullptr, nullptr);
        if (client == INVALID_SOCKET) {
            if (stop_.load()) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        std::thread([this, client]() { HandleClient((std::uintptr_t)client); }).detach();
    }
}

std::string MediaServer::ResolveFile(const std::string& requestedPath, bool* forbidden,
                                     bool* missing) const {
    *forbidden = false;
    *missing = false;
    if (requestedPath.empty() || requestedPath.find('\0') != std::string::npos) {
        *forbidden = true;
        return {};
    }

    std::string p = requestedPath;
    std::replace(p.begin(), p.end(), '\\', '/');

    std::error_code ec;
    const std::filesystem::path cachePath = std::filesystem::path(Utf8ToWide(cacheDir_));
    const std::filesystem::path cacheCanon = std::filesystem::weakly_canonical(cachePath, ec);
    const std::filesystem::path cacheBase =
        ec ? cachePath : cacheCanon;

    bool isAbsolute = false;
    if (p.size() >= 2 && std::isalpha((unsigned char)p[0]) && p[1] == ':') isAbsolute = true;
    if (!p.empty() && (p[0] == '/' || p[0] == '\\')) isAbsolute = true;

    std::filesystem::path full;
    if (isAbsolute) {
        full = std::filesystem::weakly_canonical(std::filesystem::path(Utf8ToWide(p)), ec);
        if (ec) {
            *missing = true;
            return {};
        }
    } else {
        std::filesystem::path rel;
        size_t i = 0;
        while (i <= p.size()) {
            size_t slash = p.find('/', i);
            std::string comp = p.substr(i, (slash == std::string::npos) ? std::string::npos : slash - i);
            i = (slash == std::string::npos) ? p.size() + 1 : slash + 1;
            if (comp.empty() || comp == ".") continue;
            if (comp == ".." || comp.find(':') != std::string::npos) {
                *forbidden = true;
                return {};
            }
            rel /= std::filesystem::path(Utf8ToWide(comp));
        }
        if (rel.empty()) {
            *forbidden = true;
            return {};
        }
        full = std::filesystem::weakly_canonical(cacheBase / rel, ec);
        if (ec) {
            *missing = true;
            return {};
        }
    }

    // The resolved file must live strictly under CacheDir.
    std::wstring fullW = LowerW(full.wstring());
    std::wstring baseW = LowerW(cacheBase.wstring());
    while (!baseW.empty() && (baseW.back() == L'\\' || baseW.back() == L'/')) baseW.pop_back();
    if (fullW.size() <= baseW.size() || fullW.compare(0, baseW.size(), baseW) != 0) {
        *forbidden = true;
        return {};
    }
    wchar_t boundary = fullW[baseW.size()];
    if (boundary != L'\\' && boundary != L'/') {
        *forbidden = true;
        return {};
    }

    if (!std::filesystem::is_regular_file(full, ec) || ec) {
        *missing = true;
        return {};
    }
    return WideToUtf8(full.wstring());
}

std::string MediaServer::UrlEncode(const std::string& s) {
    static const char* hex = "0123456789ABCDEF";
    std::string out;
    out.reserve(s.size() * 3);
    for (unsigned char c : s) {
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
            c == '-' || c == '_' || c == '.' || c == '~' || c == '/') {
            out.push_back((char)c);
        } else {
            out.push_back('%');
            out.push_back(hex[c >> 4]);
            out.push_back(hex[c & 0x0F]);
        }
    }
    return out;
}

std::string MediaServer::MakeUrl(const std::string& path, std::string* error) const {
    auto fail = [&](const std::string& why) -> std::string {
        if (error) *error = why;
        return {};
    };
    if (port_.load() <= 0 || !running_.load()) return fail("media server is not running");
    std::string p = Trim(path);
    if (p.empty()) return fail("empty media path");
    if (p.find('\0') != std::string::npos) return fail("invalid media path");
    std::replace(p.begin(), p.end(), '\\', '/');

    std::error_code ec;
    const std::filesystem::path cachePath = std::filesystem::path(Utf8ToWide(cacheDir_));
    std::filesystem::path cacheCanon = std::filesystem::weakly_canonical(cachePath, ec);
    if (ec) cacheCanon = cachePath;

    bool isAbsolute = false;
    if (p.size() >= 2 && std::isalpha((unsigned char)p[0]) && p[1] == ':') isAbsolute = true;
    if (!p.empty() && (p[0] == '/' || p[0] == '\\')) isAbsolute = true;

    std::string rel;
    if (isAbsolute) {
        std::filesystem::path full = std::filesystem::weakly_canonical(
            std::filesystem::path(Utf8ToWide(p)), ec);
        if (ec) return fail("media path does not exist: " + p);
        std::wstring fullW = LowerW(full.wstring());
        std::wstring baseW = LowerW(cacheCanon.wstring());
        while (!baseW.empty() && (baseW.back() == L'\\' || baseW.back() == L'/')) baseW.pop_back();
        if (fullW.size() <= baseW.size() || fullW.compare(0, baseW.size(), baseW) != 0) {
            return fail("media path is outside the cache directory");
        }
        wchar_t boundary = fullW[baseW.size()];
        if (boundary != L'\\' && boundary != L'/') {
            return fail("media path is outside the cache directory");
        }
        std::filesystem::path relPath = std::filesystem::relative(full, cacheCanon, ec);
        if (ec) return fail("cannot relativize media path");
        rel = WideToUtf8(relPath.generic_wstring());
    } else {
        size_t i = 0;
        while (i <= p.size()) {
            size_t slash = p.find('/', i);
            std::string comp = p.substr(i, (slash == std::string::npos) ? std::string::npos : slash - i);
            i = (slash == std::string::npos) ? p.size() + 1 : slash + 1;
            if (comp.empty() || comp == ".") continue;
            if (comp == ".." || comp.find(':') != std::string::npos) {
                return fail("invalid relative media path");
            }
            if (!rel.empty()) rel += '/';
            rel += comp;
        }
        if (rel.empty()) return fail("empty media path");
    }

    if (error) error->clear();
    return "http://127.0.0.1:" + std::to_string(port_.load()) + "/media?p=" + UrlEncode(rel);
}

void MediaServer::HandleClient(std::uintptr_t socketHandle) {
    SOCKET client = static_cast<SOCKET>(socketHandle);
    DWORD timeout = kClientRecvTimeoutMs;
    setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout),
               sizeof(timeout));
    setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout),
               sizeof(timeout));

    const std::string request = ReadRequest(client);
    if (request.empty()) {
        closesocket(client);
        return;
    }

    // ---- request line ----
    size_t lineEnd = request.find("\r\n");
    std::string firstLine = request.substr(0, lineEnd == std::string::npos ? request.size() : lineEnd);
    std::vector<std::string> parts;
    size_t pos = 0;
    while (pos <= firstLine.size()) {
        size_t sp = firstLine.find(' ', pos);
        std::string tok = firstLine.substr(pos, sp == std::string::npos ? std::string::npos : sp - pos);
        if (!tok.empty()) parts.push_back(tok);
        if (sp == std::string::npos) break;
        pos = sp + 1;
    }
    if (parts.size() < 2) {
        SendSimple(client, "400 Bad Request", "bad request", false);
        closesocket(client);
        return;
    }
    std::string method = parts[0];
    const bool headOnly = (method == "HEAD");
    if (method != "GET" && !headOnly) {
        SendSimple(client, "405 Method Not Allowed", "method not allowed", false);
        closesocket(client);
        return;
    }

    std::string target = parts[1];
    size_t q = target.find('?');
    std::string path = (q == std::string::npos) ? target : target.substr(0, q);
    std::string query = (q == std::string::npos) ? std::string() : target.substr(q + 1);
    size_t hash = path.find('#');
    if (hash != std::string::npos) path = path.substr(0, hash);

    if (path == "/" || path == "/health" || path == "/healthz") {
        SendSimple(client, "200 OK", "ok", headOnly);
        closesocket(client);
        return;
    }
    if (path != "/media") {
        SendSimple(client, "404 Not Found", "not found", headOnly);
        closesocket(client);
        return;
    }

    // ---- query: p=<urlencoded relative path> ----
    std::string encodedPath;
    size_t qpos = 0;
    while (qpos <= query.size()) {
        size_t amp = query.find('&', qpos);
        std::string pair = query.substr(qpos, amp == std::string::npos ? std::string::npos : amp - qpos);
        size_t eq = pair.find('=');
        if (eq != std::string::npos) {
            if (pair.substr(0, eq) == "p") {
                encodedPath = pair.substr(eq + 1);
                break;
            }
        }
        if (amp == std::string::npos) break;
        qpos = amp + 1;
    }
    if (encodedPath.empty()) {
        SendSimple(client, "400 Bad Request", "missing p parameter", headOnly);
        closesocket(client);
        return;
    }

    bool forbidden = false;
    bool missing = false;
    const std::string filePath = ResolveFile(UrlDecode(encodedPath), &forbidden, &missing);
    if (forbidden) {
        SendSimple(client, "403 Forbidden", "forbidden", headOnly);
        closesocket(client);
        return;
    }
    if (filePath.empty() || missing) {
        SendSimple(client, "404 Not Found", "not found", headOnly);
        closesocket(client);
        return;
    }

    std::error_code ec;
    const std::uintmax_t fileSize = std::filesystem::file_size(Utf8ToWide(filePath), ec);
    if (ec) {
        SendSimple(client, "500 Internal Server Error", "cannot stat file", headOnly);
        closesocket(client);
        return;
    }
    const long long size = (long long)fileSize;

    long long rangeStart = 0;
    long long rangeLength = size;
    bool partial = false;
    const std::string rangeHeader = HeaderValue(request, "Range");
    if (!rangeHeader.empty()) {
        long long rs = 0, rl = 0;
        if (ParseRange(rangeHeader, size, &rs, &rl)) {
            rangeStart = rs;
            rangeLength = rl;
            partial = true;
        }
    }

    std::string header;
    header.reserve(512);
    header += partial ? "HTTP/1.1 206 Partial Content\r\n" : "HTTP/1.1 200 OK\r\n";
    header += std::string("Content-Type: ") + ContentTypeFor(filePath) + "\r\n";
    header += "Content-Length: " + std::to_string(rangeLength) + "\r\n";
    header += "Accept-Ranges: bytes\r\n";
    if (partial) {
        header += "Content-Range: bytes " + std::to_string(rangeStart) + "-" +
                  std::to_string(rangeStart + rangeLength - 1) + "/" + std::to_string(size) +
                  "\r\n";
    }
    header += "Access-Control-Allow-Origin: *\r\n";
    header += "Cache-Control: no-cache\r\n";
    header += "Connection: close\r\n\r\n";
    if (!SendAll(client, header.data(), header.size())) {
        closesocket(client);
        return;
    }

    if (!headOnly && rangeLength > 0) {
        std::ifstream in(Utf8ToWide(filePath), std::ios::binary);
        if (in) {
            in.seekg((std::streamoff)rangeStart, std::ios::beg);
            std::vector<char> buf(64 * 1024);
            long long remaining = rangeLength;
            while (remaining > 0 && in) {
                size_t want = (size_t)std::min<long long>(remaining, (long long)buf.size());
                in.read(buf.data(), (std::streamsize)want);
                std::streamsize got = in.gcount();
                if (got <= 0) break;
                if (!SendAll(client, buf.data(), (size_t)got)) break;
                remaining -= (long long)got;
            }
        }
    }
    closesocket(client);
}

} // namespace ets
