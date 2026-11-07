// Logger implementation: local daily files + WinHTTP WebSocket to mq_server:40001.
#include "ws_log.h"

#include <windows.h>
#include <winhttp.h>

#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#include "common.h"

#pragma comment(lib, "winhttp.lib")

namespace ets {
namespace {

// WinHTTP constants kept local so no windows headers leak into ws_log.h.
constexpr wchar_t kDefaultWsHost[] = L"127.0.0.1";
constexpr INTERNET_PORT kWsPort = 40001;
constexpr int kMaxConnectAttempts = 10;
constexpr int kRetryDelayMs = 300;

std::string Join2(const std::string& a, const std::string& b) {
    if (a.empty()) return b;
    if (b.empty()) return a;
    char last = a.back();
    if (last == '\\' || last == '/') return a + b;
    return a + "\\" + b;
}

// Replica mq_server writes its actual port (port probing may bump 40001→40002) to
// mq_server/app.json. Prefer it so logs go to the replica's own relay, not a
// coincidentally running original client's mq_server.
unsigned short DiscoverWsPort(const Config& cfg) {
    std::vector<uint8_t> buf;
    if (ReadFileBytes(Join2(cfg.appDir, "mq_server\\app.json"), buf) && !buf.empty()) {
        try {
            auto j = json::parse(std::string(buf.begin(), buf.end()));
            if (j.is_object() && j.contains("suspensionBallPort") &&
                j["suspensionBallPort"].is_number_integer()) {
                int port = j["suspensionBallPort"].get<int>();
                if (port > 0 && port <= 65535) return static_cast<unsigned short>(port);
            }
        } catch (...) {
            // fall through to default
        }
    }
    return 40001;
}

} // namespace

Logger::~Logger() { Stop(); }

void Logger::Start(const Config& cfg) {
    cfg_ = cfg;
    {
        std::lock_guard<std::mutex> lk(mu_);
        started_ = true;
        stopped_ = false;
        minLevel_ = cfg_.logLevel;
        stop_.store(false);
        wsConnected_.store(false);
    }
    EnsureDir(cfg_.logDir);
    Info("shell", "logger started (dataDir=" + cfg_.dataDir + ", logLevel=" +
                      std::to_string(cfg_.logLevel) + ")");
    SpawnNode();
    connectThread_ = std::thread([this]() { ConnectLoop(); });
}

void Logger::Stop() {
    {
        std::lock_guard<std::mutex> lk(mu_);
        if (stopped_) return;
        stopped_ = true;
    }
    stop_.store(true);

    if (connectThread_.joinable()) connectThread_.join();
    if (recvThread_.joinable()) recvThread_.join();

    {
        std::lock_guard<std::mutex> lk(mu_);
        CloseWsLocked();
        if (shellFile_.is_open()) shellFile_.close();
        if (etsFile_.is_open()) etsFile_.close();
        started_ = false;
    }
    StopNode();
}

const char* Logger::LevelName(int level) {
    switch (level) {
        case kLogDebug: return "DEBUG";
        case kLogInfo: return "INFO";
        case kLogWarn: return "WARN";
        case kLogError: return "ERROR";
        default: return "INFO";
    }
}

std::string Logger::Today() {
    SYSTEMTIME st{};
    GetLocalTime(&st);
    char buf[32] = {};
    std::snprintf(buf, sizeof(buf), "%04d-%d-%d", st.wYear, st.wMonth, st.wDay);
    return buf;
}

std::string Logger::Timestamp() {
    SYSTEMTIME st{};
    GetLocalTime(&st);
    char buf[64] = {};
    std::snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d.%03d", st.wYear, st.wMonth,
                  st.wDay, st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
    return buf;
}

std::string Logger::EtsLogPath() const { return Join2(cfg_.logDir, "ets_" + Today() + ".log"); }
std::string Logger::ShellLogPath() const { return Join2(cfg_.logDir, "shell_" + Today() + ".log"); }

void Logger::AppendFileLine(std::ofstream& f, std::string& dateKey, const std::string& path,
                            const std::string& line) {
    const std::string today = Today();
    if (!f.is_open() || dateKey != today) {
        if (f.is_open()) f.close();
        f.open(Utf8ToWide(path), std::ios::out | std::ios::app | std::ios::binary);
        dateKey = today;
    }
    if (f) {
        f << line << "\r\n";
        f.flush();
    }
}

void Logger::SendOrFallbackLocked(int /*level*/, const char* levelName, const std::string& ts,
                                  const std::string& jsonLine) {
    if (wsConnected_.load() && wsHandle_) {
        std::string payload = jsonLine;
        DWORD rc = WinHttpWebSocketSend((HINTERNET)wsHandle_,
                                        WINHTTP_WEB_SOCKET_UTF8_MESSAGE_BUFFER_TYPE,
                                        (PVOID)payload.data(), (DWORD)payload.size());
        if (rc == ERROR_SUCCESS) return;
        wsConnected_.store(false);
    }
    // Local fallback uses the same format mq_server writes:
    //   [YYYY-MM-DD HH:mm:ss.mmm] [LEVEL] mq_server - received: <json>
    AppendFileLine(etsFile_, etsDate_, EtsLogPath(),
                   "[" + ts + "] [" + levelName + "] mq_server - received: " + jsonLine);
}

void Logger::Log(int level, const std::string& tag, const std::string& msg) {
    if (level < minLevel_) return;

    std::string debugText;
    {
        std::lock_guard<std::mutex> lk(mu_);
        if (!started_ || stopped_) return;

        const std::string ts = Timestamp();
        const char* lv = LevelName(level);

        // shell.log: always written, independent of websocket state.
        AppendFileLine(shellFile_, shellDate_, ShellLogPath(),
                       "[" + ts + "] [" + lv + "] " + tag + " - " + msg);

        json j;
        j["ts"] = ts;
        j["level"] = lv;
        j["tag"] = tag;
        j["msg"] = msg;
        std::string jsonLine = j.dump();
        SendOrFallbackLocked(level, lv, ts, jsonLine);

        if (level >= kLogWarn) debugText = "EtsReplica [" + std::string(lv) + "] " + msg;
    }
    if (!debugText.empty()) OutputDebugStringA((debugText + "\n").c_str());
}

void Logger::SpawnNode() {
    const std::string mainJs = Join2(cfg_.appDir, "mq_server\\main.js");
    if (!FileExists(mainJs)) {
        Debug("shell", "mq_server/main.js not found; node child process skipped");
        return;
    }

    wchar_t nodePath[MAX_PATH * 4] = {};
    if (!SearchPathW(nullptr, L"node.exe", nullptr, MAX_PATH * 4, nodePath, nullptr)) {
        Warn("shell", "node.exe not found on PATH; mq_server will not run (local file logs only)");
        return;
    }

    std::wstring cmdline =
        L"\"" + std::wstring(nodePath) + L"\" \"" + Utf8ToWide(mainJs) + L"\"";
    STARTUPINFOW si{};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    PROCESS_INFORMATION pi{};
    std::wstring cwd = Utf8ToWide(cfg_.appDir);

    BOOL ok = CreateProcessW(nullptr, cmdline.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
                             nullptr, cwd.c_str(), &si, &pi);
    if (!ok) {
        Warn("shell", "failed to start node mq_server (error=" + std::to_string(GetLastError()) + ")");
        return;
    }
    CloseHandle(pi.hThread);
    nodeProcess_ = pi.hProcess;
    nodeThread_ = nullptr;
    Info("shell", "node mq_server started (pid=" + std::to_string(pi.dwProcessId) + ")");
}

void Logger::StopNode() {
    if (!nodeProcess_) return;
    HANDLE h = (HANDLE)nodeProcess_;
    DWORD code = 0;
    if (GetExitCodeProcess(h, &code) && code == STILL_ACTIVE) {
        TerminateProcess(h, 0);
        WaitForSingleObject(h, 2000);
    }
    CloseHandle(h);
    nodeProcess_ = nullptr;
}

void Logger::ConnectLoop() {
    // The replica mq_server picks its port (40001→40002…) and records it in
    // mq_server/app.json. Wait briefly for that file so we connect to our own
    // relay instead of a coincidentally running original client's mq_server.
    if (FileExists(Join2(cfg_.appDir, "mq_server\\main.js"))) {
        const std::string appJson = Join2(cfg_.appDir, "mq_server\\app.json");
        for (int i = 0; i < 30 && !stop_.load(); ++i) {
            if (FileExists(appJson)) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
    for (int attempt = 0; attempt < kMaxConnectAttempts && !stop_.load(); ++attempt) {
        if (TryConnectOnce()) {
            {
                std::lock_guard<std::mutex> lk(mu_);
                if (!wsHandle_) {
                    wsConnected_.store(false);
                    return;
                }
                wsConnected_.store(true);
            }
            Info("shell", "mq_server websocket connected (ws://127.0.0.1:40001)");
            recvThread_ = std::thread([this]() { ReceiveLoop(); });
            return;
        }
        // Slept in small slices so Stop() stays responsive.
        for (int slice = 0; slice < kRetryDelayMs / 50 && !stop_.load(); ++slice) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
    }
    if (!stop_.load()) {
        Warn("shell",
             "mq_server websocket unavailable after " + std::to_string(kMaxConnectAttempts) +
                 " attempts; logging to local logs/ets_YYYY-M-D.log only");
    }
}

bool Logger::TryConnectOnce() {
    HINTERNET session = WinHttpOpen(L"EtsReplica/1.0", WINHTTP_ACCESS_TYPE_NO_PROXY,
                                    WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session) return false;
    WinHttpSetTimeouts(session, 1000, 1000, 1000, 1000);

    HINTERNET conn = WinHttpConnect(session, kDefaultWsHost, DiscoverWsPort(cfg_), 0);
    if (!conn) {
        WinHttpCloseHandle(session);
        return false;
    }
    HINTERNET request = WinHttpOpenRequest(conn, L"GET", L"/", nullptr, WINHTTP_NO_REFERER,
                                           WINHTTP_DEFAULT_ACCEPT_TYPES, 0);
    if (!request) {
        WinHttpCloseHandle(conn);
        WinHttpCloseHandle(session);
        return false;
    }

    bool upgraded = false;
    if (WinHttpSetOption(request, WINHTTP_OPTION_UPGRADE_TO_WEB_SOCKET, nullptr, 0) &&
        WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0, nullptr, 0, 0, 0) &&
        WinHttpReceiveResponse(request, nullptr)) {
        HINTERNET ws = WinHttpWebSocketCompleteUpgrade(request, 0);
        if (ws) {
            std::lock_guard<std::mutex> lk(mu_);
            wsSession_ = session;
            wsConnect_ = conn;
            wsHandle_ = ws;
            session = nullptr;
            conn = nullptr;
            upgraded = true;
        }
    }

    WinHttpCloseHandle(request);
    if (conn) WinHttpCloseHandle(conn);
    if (session) WinHttpCloseHandle(session);
    return upgraded;
}

void Logger::ReceiveLoop() {
    std::vector<char> buf(4096);
    bool cleanStop = false;
    while (!stop_.load()) {
        DWORD bytesRead = 0;
        WINHTTP_WEB_SOCKET_BUFFER_TYPE type = WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE;
        HINTERNET ws = nullptr;
        {
            std::lock_guard<std::mutex> lk(mu_);
            ws = (HINTERNET)wsHandle_;
        }
        if (!ws) break;

        DWORD rc = WinHttpWebSocketReceive(ws, buf.data(), (DWORD)buf.size(), &bytesRead, &type);
        if (rc == ERROR_SUCCESS) {
            if (type == WINHTTP_WEB_SOCKET_CLOSE_BUFFER_TYPE) break;
            continue;
        }
        if (rc == ERROR_WINHTTP_TIMEOUT) continue;
        if (stop_.load()) {
            cleanStop = true;
            break;
        }
        break;
    }
    wsConnected_.store(false);
    if (!cleanStop && !stop_.load()) {
        Warn("shell", "mq_server websocket closed; falling back to local file logs");
    }
}

void Logger::CloseWsLocked() {
    if (wsHandle_) {
        WinHttpWebSocketShutdown((HINTERNET)wsHandle_, WINHTTP_WEB_SOCKET_SUCCESS_CLOSE_STATUS,
                                 nullptr, 0);
        WinHttpCloseHandle((HINTERNET)wsHandle_);
        wsHandle_ = nullptr;
    }
    if (wsConnect_) {
        WinHttpCloseHandle((HINTERNET)wsConnect_);
        wsConnect_ = nullptr;
    }
    if (wsSession_) {
        WinHttpCloseHandle((HINTERNET)wsSession_);
        wsSession_ = nullptr;
    }
    wsConnected_.store(false);
}

} // namespace ets
