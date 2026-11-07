#pragma once
// shell.ini configuration for the native shell (EtsReplica.exe).
#include <string>

namespace ets {

struct Config {
    // exe directory (UTF-8, no trailing separator)
    std::string appDir;
    std::string iniPath;

    // shell.ini values (defaults applied when missing)
    std::string appName = "E\u542c\u8bf4 \u00b7 \u590d\u523b\u7248"; // "E<U+542C><U+8BF4> <U+00B7> <U+590D><U+523B><U+7248>"
    std::string homeUrl;
    int windowWidth = 1280;
    int windowHeight = 800;

    // resolved directories (absolute, UTF-8)
    std::string dataDir;      // default: %APPDATA%\ETS-Replica
    std::string cacheDir;     // dataDir\cache
    std::string logDir;       // dataDir\logs
    std::string webView2Dir;  // dataDir\WebView2

    int logLevel = 1;         // 0 debug, 1 info, 2 warn, 3 error

    // Load shell.ini (never fails hard: missing/broken ini -> defaults).
    // Also creates the data/cache/log directories.
    bool Load();

    // true when HomeUrl is set and points at a non-local http(s) page.
    bool IsRemoteHome() const;

    // URL the browser should load on startup.
    std::string StartUrl() const;

    // UTF-8 executable directory (no trailing separator).
    std::string AssetsWebDir() const;
};

} // namespace ets
