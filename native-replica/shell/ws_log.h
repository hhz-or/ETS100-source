#pragma once
// Logger: node mq_server child process + WinHTTP WebSocket log sink + local daily logs.
#include <atomic>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>

#include "config.h"

namespace ets {

enum LogSeverity : int { kLogDebug = 0, kLogInfo = 1, kLogWarn = 2, kLogError = 3 };

class Logger {
public:
    Logger() = default;
    ~Logger();
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    // Ensures log directories, spawns `node mq_server/main.js` (when present) and
    // starts the websocket connect thread (10 attempts x 300ms, port 40001).
    void Start(const Config& cfg);
    void Stop();

    // level: 0 debug, 1 info, 2 warn, 3 error (messages below Config::logLevel are dropped).
    void Log(int level, const std::string& tag, const std::string& msg);
    void Debug(const std::string& tag, const std::string& msg) { Log(kLogDebug, tag, msg); }
    void Info(const std::string& tag, const std::string& msg) { Log(kLogInfo, tag, msg); }
    void Warn(const std::string& tag, const std::string& msg) { Log(kLogWarn, tag, msg); }
    void Error(const std::string& tag, const std::string& msg) { Log(kLogError, tag, msg); }

    bool WsConnected() const { return wsConnected_.load(); }
    std::string EtsLogPath() const;
    std::string ShellLogPath() const;

private:
    static const char* LevelName(int level);
    static std::string Today();      // YYYY-M-D  (matches ets_YYYY-M-D.log)
    static std::string Timestamp();  // YYYY-MM-DD HH:mm:ss.mmm

    void AppendFileLine(std::ofstream& f, std::string& dateKey, const std::string& path,
                        const std::string& line);
    void SendOrFallbackLocked(int level, const char* levelName, const std::string& ts,
                              const std::string& jsonLine);

    void SpawnNode();
    void StopNode();
    void ConnectLoop();
    bool TryConnectOnce();
    void ReceiveLoop();
    void CloseWsLocked();

    Config cfg_;
    mutable std::mutex mu_;
    bool started_ = false;
    bool stopped_ = false;
    int minLevel_ = kLogInfo;

    std::atomic<bool> wsConnected_{false};
    std::atomic<bool> stop_{false};

    // local log files (guarded by mu_)
    std::ofstream shellFile_;
    std::ofstream etsFile_;
    std::string shellDate_;
    std::string etsDate_;

    // node child process handles (HANDLE)
    void* nodeProcess_ = nullptr;
    void* nodeThread_ = nullptr;

    // WinHTTP websocket handles (guarded by mu_)
    void* wsSession_ = nullptr;
    void* wsConnect_ = nullptr;
    void* wsHandle_ = nullptr;

    std::thread connectThread_;
    std::thread recvThread_;
};

} // namespace ets
