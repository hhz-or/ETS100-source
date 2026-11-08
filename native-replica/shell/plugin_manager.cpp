// Plugin manager implementation (ABI from shared/stic_plugin.h).
#include "plugin_manager.h"

#include <windows.h>

#include <algorithm>
#include <chrono>
#include <cctype>
#include <filesystem>
#include <string>
#include <thread>
#include <vector>

#include "common.h"
#include "ws_log.h"

namespace ets {
namespace {

struct KnownPlugin {
    const char* key;
    const char* dir;
};

const KnownPlugin kKnownPlugins[] = {
    {"EtsHelper", "etshelper"}, {"FileHelper", "filehelper"}, {"HttpHelper", "httphelper"},
    {"SQLitePln", "sqlitepln"}, {"ShellHelper", "shellhelper"}, {"SevenZip", "sevenzip"},
    {"SysConfig", "sysconfig"}, {"soundhelper", "soundhelper"},
};

PluginManager* g_manager = nullptr;

std::string Lower(std::string s) {
    for (char& c : s) c = (char)std::tolower((unsigned char)c);
    return s;
}

std::string Trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && (unsigned char)s[a] <= ' ') ++a;
    while (b > a && (unsigned char)s[b - 1] <= ' ') --b;
    return s.substr(a, b - a);
}

} // namespace

PluginManager::~PluginManager() {
    if (!shuttingDown_.load()) Shutdown();
}

bool PluginManager::Init(const CoreContext& ctx) {
    if (initialized_.exchange(true)) return true;
    g_manager = this;
    ctx_ = ctx;

    hostAppDir_ = ctx.appDir;
    hostDataDir_ = ctx.dataDir;
    hostCacheDir_ = ctx.cacheDir;
    hostHomeUrl_ = ctx.homeUrl;

    host_ = PlnHost{};
    host_.size = (unsigned int)sizeof(PlnHost);
    host_.Log = &PluginManager::PluginLogThunk;
    host_.WLog = &PluginManager::PluginWLogThunk;
    host_.Exec = &PluginManager::HostExecThunk;
    host_.AppDir = hostAppDir_.c_str();
    host_.DataDir = hostDataDir_.c_str();
    host_.CacheDir = hostCacheDir_.c_str();
    host_.HomeUrl = hostHomeUrl_.c_str();

    int loaded = 0;
    for (const auto& known : kKnownPlugins) {
        if (LoadOne(known.key, known.dir)) ++loaded;
    }
    if (ctx_.logger) {
        ctx_.logger->Info("plugin", "plugin host initialized (loaded " + std::to_string(loaded) +
                                         "/" + std::to_string((int)(sizeof(kKnownPlugins) /
                                                                    sizeof(kKnownPlugins[0]))) +
                                         ")");
    }
    LogPluginStatus();
    return true;
}

PluginManager::Plugin* PluginManager::LoadOne(const std::string& key, const std::string& dirName) {
    const std::string dirPath = JoinPath(ctx_.appDir, std::string("plugins\\") + dirName);
    const std::string preferred = dirName + ".dll";

    std::string dllPath;
    std::error_code ec;
    const std::filesystem::path dp(Utf8ToWide(dirPath));
    if (std::filesystem::is_directory(dp, ec)) {
        std::string firstDll;
        for (const auto& entry : std::filesystem::directory_iterator(dp, ec)) {
            std::error_code fileEc;
            if (!entry.is_regular_file(fileEc)) continue;
            const std::string fileName = WideToUtf8(entry.path().filename().wstring());
            const std::string lowerName = Lower(fileName);
            if (lowerName.size() < 4 || lowerName.compare(lowerName.size() - 4, 4, ".dll") != 0) {
                continue;
            }
            const std::string full = WideToUtf8(entry.path().wstring());
            if (lowerName == Lower(preferred)) {
                dllPath = full;
                break;
            }
            if (firstDll.empty()) firstDll = full;
        }
        if (dllPath.empty()) dllPath = firstDll;
    }

    if (dllPath.empty()) {
        if (ctx_.logger) {
            ctx_.logger->Debug("plugin", key + ": no DLL found under " + dirPath + " (skipped)");
        }
        return nullptr;
    }

    HMODULE module = LoadLibraryW(Utf8ToWide(dllPath).c_str());
    if (!module) {
        if (ctx_.logger) {
            ctx_.logger->Warn("plugin", key + ": LoadLibrary failed (" +
                                           std::to_string(GetLastError()) + ") " + dllPath);
        }
        return nullptr;
    }

    auto* p = new Plugin();
    p->key = key;
    p->dirName = dirName;
    p->dllPath = dllPath;
    p->module = module;
    p->initFn = reinterpret_cast<decltype(p->initFn)>(GetProcAddress(module, "PlnInitiliaze"));
    p->setParamFn = reinterpret_cast<decltype(p->setParamFn)>(GetProcAddress(module, "PlnSetParam"));
    p->onMsgFn =
        reinterpret_cast<decltype(p->onMsgFn)>(GetProcAddress(module, "PlnOnProcessMessage"));
    p->uninitFn = reinterpret_cast<decltype(p->uninitFn)>(GetProcAddress(module, "PlnUnInitialize"));

    if (!p->initFn || !p->onMsgFn) {
        if (ctx_.logger) {
            ctx_.logger->Warn("plugin", key + ": missing exports PlnInitiliaze/PlnOnProcessMessage (" +
                                           dllPath + ")");
        }
        FreeLibrary(module);
        delete p;
        return nullptr;
    }

    // Optional host callbacks ("LOG"/"WLOG") are injected before initialization.
    if (p->setParamFn) {
        p->setParamFn("LOG", reinterpret_cast<void*>(&PluginManager::PluginLogThunk));
        p->setParamFn("WLOG", reinterpret_cast<void*>(&PluginManager::PluginWLogThunk));
    }

    try {
        p->initFn(&host_);
    } catch (...) {
        if (ctx_.logger) ctx_.logger->Warn("plugin", key + ": PlnInitiliaze threw an exception");
    }
    p->alive = true;

    {
        std::lock_guard<std::mutex> lk(mapMutex_);
        byKey_[Lower(key)] = p;
        byKey_[Lower(dirName)] = p;
        const std::filesystem::path stem = std::filesystem::path(Utf8ToWide(dllPath)).stem();
        byKey_[Lower(WideToUtf8(stem.wstring()))] = p;
        plugins_.push_back(p);
    }
    if (ctx_.logger) {
        ctx_.logger->Info("plugin", key + ": loaded " + dllPath);
    }
    return p;
}

void PluginManager::Shutdown() {
    if (shuttingDown_.exchange(true)) return;

    // Let in-flight plugin calls finish before unloading the DLLs.
    {
        std::unique_lock<std::mutex> lk(activeMutex_);
        const bool done = activeCv_.wait_for(lk, std::chrono::seconds(5),
                                             [this]() { return activeCalls_ == 0; });
        if (!done && ctx_.logger) {
            ctx_.logger->Warn("plugin", "shutdown: " + std::to_string(activeCalls_) +
                                            " plugin call(s) still running");
        }
    }
    // Async plugins may answer after their worker returned; give pending callbacks a
    // short grace period before the DLLs are unloaded.
    for (int i = 0; i < 250; ++i) {
        {
            std::lock_guard<std::mutex> lk(pendingMutex_);
            if (pending_.empty()) break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    {
        std::lock_guard<std::mutex> lk(pendingMutex_);
        if (!pending_.empty() && ctx_.logger) {
            ctx_.logger->Warn("plugin", "shutdown: dropping " + std::to_string(pending_.size()) +
                                            " pending callback(s)");
        }
        pending_.clear();
    }
    UnloadAll();
    if (g_manager == this) g_manager = nullptr;
    if (ctx_.logger) ctx_.logger->Info("plugin", "plugin host shut down");
}

void PluginManager::UnloadAll() {
    std::vector<Plugin*> plugins;
    {
        std::lock_guard<std::mutex> lk(mapMutex_);
        plugins.swap(plugins_);
        byKey_.clear();
    }
    for (Plugin* p : plugins) {
        if (!p) continue;
        p->alive = false;
        if (p->uninitFn) {
            try {
                p->uninitFn();
            } catch (...) {
            }
        }
        if (p->module) {
            FreeLibrary(p->module);
            p->module = nullptr;
        }
        delete p;
    }
}

PluginManager::Plugin* PluginManager::FindLocked(const std::string& pluginKey) const {
    const std::string key = Lower(Trim(pluginKey));
    auto it = byKey_.find(key);
    if (it != byKey_.end()) return it->second;
    // Tolerate "__core/EtsHelper" style keys and dll-style names.
    const std::string prefix = "__core/";
    if (key.rfind(prefix, 0) == 0) {
        auto it2 = byKey_.find(key.substr(prefix.size()));
        if (it2 != byKey_.end()) return it2->second;
    }
    return nullptr;
}

void PluginManager::ProcessMessage(const std::string& pluginKey, const std::string& action,
                                   const std::string& argsJson, const std::string& uid,
                                   Callback cb) {
    if (shuttingDown_.load()) {
        if (cb) cb(uid, ErrReply(-1, "plugin host is shutting down"));
        return;
    }

    Plugin* p = nullptr;
    {
        std::lock_guard<std::mutex> lk(mapMutex_);
        p = FindLocked(pluginKey);
    }
    if (!p) {
        if (ctx_.logger) ctx_.logger->Warn("plugin", "not loaded: " + pluginKey);
        if (cb) cb(uid, ErrReply(-1, "plugin not loaded: " + pluginKey));
        return;
    }

    {
        std::lock_guard<std::mutex> lk(pendingMutex_);
        auto it = pending_.find(uid);
        if (it != pending_.end()) {
            if (ctx_.logger) {
                ctx_.logger->Warn("plugin", "duplicate pending uid overwritten: " + uid);
            }
            it->second = std::move(cb);
        } else {
            pending_.emplace(uid, std::move(cb));
        }
    }
    {
        std::lock_guard<std::mutex> lk(activeMutex_);
        ++activeCalls_;
    }

    try {
        std::thread([this, p, action, argsJson, uid]() {
            try {
                std::lock_guard<std::mutex> lk(p->callMutex);
                if (p->alive && p->onMsgFn) {
                    p->onMsgFn(action.c_str(), argsJson.c_str(),
                               &PluginManager::PluginResultThunk, uid.c_str());
                } else {
                    PluginResultThunk(uid.c_str(), ErrReply(-1, "plugin unavailable").c_str());
                }
            } catch (...) {
                PluginResultThunk(uid.c_str(), ErrReply(-1, "plugin exception").c_str());
            }
            {
                std::lock_guard<std::mutex> lk(activeMutex_);
                --activeCalls_;
            }
            activeCv_.notify_all();
        }).detach();
    } catch (...) {
        if (ctx_.logger) ctx_.logger->Error("plugin", "failed to start plugin worker thread");
        PluginResultThunk(uid.c_str(), ErrReply(-1, "failed to start worker thread").c_str());
        {
            std::lock_guard<std::mutex> lk(activeMutex_);
            --activeCalls_;
        }
        activeCv_.notify_all();
    }
}

bool PluginManager::Has(const std::string& pluginKey) const {
    std::lock_guard<std::mutex> lk(mapMutex_);
    return FindLocked(pluginKey) != nullptr;
}

std::vector<std::string> PluginManager::LoadedKeys() const {
    std::vector<std::string> keys;
    std::lock_guard<std::mutex> lk(mapMutex_);
    for (Plugin* p : plugins_) {
        if (p) keys.push_back(p->key);
    }
    return keys;
}

void PluginManager::LogPluginStatus() {
    if (!ctx_.logger) return;
    std::vector<std::string> loaded = LoadedKeys();
    std::string list;
    for (const auto& k : loaded) {
        if (!list.empty()) list += ", ";
        list += k;
    }
    ctx_.logger->Info("plugin", loaded.empty() ? "no plugin DLLs loaded"
                                               : "loaded plugin keys: " + list);
    for (const auto& known : kKnownPlugins) {
        if (!Has(known.key)) {
            ctx_.logger->Warn("plugin", std::string("plugin missing (not implemented yet?): ") +
                                            known.key + " -> plugins\\" + known.dir + "\\" +
                                            known.dir + ".dll");
        }
    }
}

// ---- ABI thunks -----------------------------------------------------------

void __stdcall PluginManager::PluginLogThunk(int level, const char* msg) {
    PluginManager* m = g_manager;
    if (!m || !m->ctx_.logger) return;
    m->ctx_.logger->Log(level, "plugin", msg ? msg : "");
}

void __stdcall PluginManager::PluginWLogThunk(int level, const char* msg) {
    PluginManager* m = g_manager;
    if (!m || !m->ctx_.logger) return;
    int lvl = level;
    if (lvl < kLogWarn) lvl = kLogWarn;
    m->ctx_.logger->Log(lvl, "plugin-w", msg ? msg : "");
}

void __stdcall PluginManager::HostExecThunk(const char* action, const char* args,
                                            PLN_CALLBACK cb, const char* uid) {
    PluginManager* m = g_manager;
    std::string result;
    if (!m) {
        result = ErrReply(-1, "plugin host unavailable");
    } else {
        result = HandleCoreAction(m->ctx_, action ? action : "", args ? args : "");
    }
    if (cb) cb(uid ? uid : "", result.c_str());
}

void __stdcall PluginManager::PluginResultThunk(const char* uid, const char* data) {
    if (!uid) return;
    PluginManager* m = g_manager;
    if (!m) return;

    Callback cb;
    bool found = false;
    {
        std::lock_guard<std::mutex> lk(m->pendingMutex_);
        auto it = m->pending_.find(uid);
        if (it != m->pending_.end()) {
            cb = std::move(it->second);
            m->pending_.erase(it);
            found = true;
        }
    }
    if (!found) {
        if (m->ctx_.logger) {
            m->ctx_.logger->Warn("plugin", std::string("unexpected/duplicate callback for uid=") + uid);
        }
        return;
    }
    const std::string payload = data ? data : "{}";
    if (cb) cb(std::string(uid), payload);
}

} // namespace ets
