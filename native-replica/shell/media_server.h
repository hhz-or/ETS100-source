#pragma once
// Local HTTP media server: serves files under CacheDir to the WebView.
#include <atomic>
#include <cstdint>
#include <string>
#include <thread>

namespace ets {

class Logger;

class MediaServer {
public:
    MediaServer() = default;
    ~MediaServer();
    MediaServer(const MediaServer&) = delete;
    MediaServer& operator=(const MediaServer&) = delete;

    // Binds 127.0.0.1:0 (random free port) and starts the accept thread.
    bool Start(const std::string& cacheDir, Logger* logger);
    void Stop();

    int port() const { return port_.load(); }
    bool running() const { return running_.load(); }

    // Maps an absolute path under CacheDir (or a path relative to CacheDir) to
    //   http://127.0.0.1:<port>/media?p=<urlencoded relative path>
    // Returns an empty string on failure; *error (optional) receives the reason.
    std::string MakeUrl(const std::string& path, std::string* error) const;

    static std::string UrlEncode(const std::string& utf8);

private:
    void AcceptLoop();
    void HandleClient(std::uintptr_t socketHandle);
    // Returns "" on failure; sets forbidden/missing flags.
    std::string ResolveFile(const std::string& requestedPath, bool* forbidden, bool* missing) const;

    std::string cacheDir_;
    Logger* logger_ = nullptr;
    std::atomic<int> port_{0};
    std::atomic<bool> running_{false};
    std::atomic<bool> stop_{false};
    std::atomic<std::uintptr_t> listenSock_{static_cast<std::uintptr_t>(~std::uintptr_t(0))};
    std::thread acceptThread_;
};

} // namespace ets
