// shell.ini parsing + path resolution for the native shell.
#include "config.h"

#include <windows.h>

#include <algorithm>
#include <cctype>
#include <cwchar>
#include <fstream>
#include <string>
#include <vector>

#include "common.h"

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

// Expand %VAR% references (and leave unknown ones untouched).
std::string ExpandEnv(const std::string& in) {
    if (in.find('%') == std::string::npos) return in;
    std::wstring w = Utf8ToWide(in);
    DWORD need = ExpandEnvironmentStringsW(w.c_str(), nullptr, 0);
    if (need == 0) return in;
    std::wstring out(need, L'\0');
    DWORD got = ExpandEnvironmentStringsW(w.c_str(), out.data(), need);
    if (got == 0 || got > need) return in;
    out.resize(wcslen(out.c_str()));
    return WideToUtf8(out);
}

int ParseInt(const std::string& v, int def) {
    try {
        size_t used = 0;
        int n = std::stoi(Trim(v), &used);
        return n;
    } catch (...) {
        return def;
    }
}

std::string DefaultDataDir() {
    std::string s = ExpandEnv("%APPDATA%\\ETS-Replica");
    if (s.empty() || s == "%APPDATA%\\ETS-Replica") {
        // Fallback when APPDATA is not set: <exeDir>\appdata
        s = JoinPath(GetModuleDir(), "appdata");
    }
    return s;
}

} // namespace

bool Config::Load() {
    appDir = GetModuleDir();
    iniPath = JoinPath(appDir, "shell.ini");

    // Defaults.
    appName = "E\u542c\u8bf4 \u00b7 \u590d\u523b\u7248";
    homeUrl.clear();
    windowWidth = 1280;
    windowHeight = 800;
    logLevel = 1;
    std::string rawDataDir;

    // --- parse shell.ini (tolerant: unknown keys / comments are ignored) ---
    std::ifstream in(Utf8ToWide(iniPath), std::ios::binary);
    if (in) {
        std::string line;
        bool first = true;
        while (std::getline(in, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (first) {
                first = false;
                if (line.size() >= 3 && (unsigned char)line[0] == 0xEF &&
                    (unsigned char)line[1] == 0xBB && (unsigned char)line[2] == 0xBF) {
                    line.erase(0, 3);
                }
            }
            std::string t = Trim(line);
            if (t.empty() || t[0] == '#' || t[0] == ';' || t[0] == '[') continue;
            size_t eq = t.find('=');
            if (eq == std::string::npos) eq = t.find(':');
            if (eq == std::string::npos) continue;
            std::string key = Lower(Trim(t.substr(0, eq)));
            std::string value = Trim(t.substr(eq + 1));
            if (value.size() >= 2 && ((value.front() == '"' && value.back() == '"') ||
                                      (value.front() == '\'' && value.back() == '\''))) {
                value = value.substr(1, value.size() - 2);
            }
            if (key == "appname") appName = value.empty() ? appName : value;
            else if (key == "homeurl") homeUrl = value;
            else if (key == "windowwidth") windowWidth = ParseInt(value, windowWidth);
            else if (key == "windowheight") windowHeight = ParseInt(value, windowHeight);
            else if (key == "datadir") rawDataDir = value;
            else if (key == "loglevel") logLevel = ParseInt(value, logLevel);
        }
    }

    if (appName.empty()) appName = "E\u542c\u8bf4 \u00b7 \u590d\u523b\u7248";
    windowWidth = std::clamp(windowWidth, 400, 10000);
    windowHeight = std::clamp(windowHeight, 300, 10000);
    logLevel = std::clamp(logLevel, 0, 3);

    // --- resolve directories ---
    if (rawDataDir.empty()) {
        dataDir = DefaultDataDir();
    } else {
        dataDir = ExpandEnv(rawDataDir);
        // Relative DataDir values are resolved against the exe directory.
        if (!(dataDir.size() > 1 && dataDir[1] == ':') && dataDir[0] != '\\' && dataDir[0] != '/') {
            dataDir = JoinPath(appDir, dataDir);
        }
    }
    // normalize separators and drop any trailing separator
    for (char& c : dataDir) {
        if (c == '/') c = '\\';
    }
    while (!dataDir.empty() && dataDir.back() == '\\') dataDir.pop_back();
    if (dataDir.empty()) dataDir = DefaultDataDir();

    cacheDir = JoinPath(dataDir, "cache");
    logDir = JoinPath(dataDir, "logs");
    webView2Dir = JoinPath(dataDir, "WebView2");

    EnsureDir(dataDir);
    EnsureDir(cacheDir);
    EnsureDir(logDir);
    EnsureDir(webView2Dir);
    return true;
}

bool Config::IsRemoteHome() const {
    if (homeUrl.empty()) return false;
    std::string u = Trim(homeUrl);
    if (!StartsWithNoCase(u, "http://") && !StartsWithNoCase(u, "https://")) return false;

    // extract host between "://" and the next '/', ':' or '?'
    size_t pos = u.find("://");
    if (pos == std::string::npos) return false;
    size_t start = pos + 3;
    size_t end = start;
    while (end < u.size() && u[end] != '/' && u[end] != ':' && u[end] != '?' && u[end] != '#') ++end;
    std::string host = Lower(u.substr(start, end - start));
    return host != "app.ets.local";
}

std::string Config::StartUrl() const {
    if (IsRemoteHome()) return homeUrl;
    return "https://app.ets.local/index.html";
}

std::string Config::AssetsWebDir() const { return JoinPath(appDir, "assets\\web"); }

} // namespace ets
