#pragma once
// Plugin manager: loads plugins/<name>/<name>.dll and dispatches JSON messages.
#include <atomic>
#include <condition_variable>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <vector>

#include "core_api.h"
#include "stic_plugin.h"

namespace ets {

class PluginManager {
public:
    using Callback = std::function<void(const std::string& uid, const std::string& data)>;

    PluginManager() = default;
    ~PluginManager();
    PluginManager(const PluginManager&) = delete;
    PluginManager& operator=(const PluginManager&) = delete;

    // Scans <exeDir>\plugins\<name>\, loads every known plugin DLL and calls PlnInitiliaze.
    bool Init(const CoreContext& ctx);
    // Waits for in-flight calls, calls PlnUnInitialize and frees the DLLs.
    void Shutdown();

    // Dispatches one message. `cb` is invoked exactly once: from a worker thread
    // when the plugin answers, or immediately when the plugin is unavailable.
    void ProcessMessage(const std::string& pluginKey, const std::string& action,
                        const std::string& argsJson, const std::string& uid, Callback cb);

    bool Has(const std::string& pluginKey) const;
    std::vector<std::string> LoadedKeys() const;
    void LogPluginStatus();

    // ABI thunks invoked by plugin DLLs (possibly from worker threads).
    static void __stdcall PluginLogThunk(int level, const char* msg);
    static void __stdcall PluginWLogThunk(int level, const char* msg);
    static void __stdcall HostExecThunk(const char* action, const char* args, PLN_CALLBACK cb,
                                        const char* uid);
    static void __stdcall PluginResultThunk(const char* uid, const char* data);

private:
    struct Plugin {
        std::string key;      // canonical pluginKey (frontend convention)
        std::string dirName;  // plugins/<dirName>
        std::string dllPath;
        HMODULE module = nullptr;
        void (*initFn)(PlnHost*) = nullptr;
        void (*setParamFn)(const char*, void*) = nullptr;
        void (*onMsgFn)(const char*, const char*, PLN_CALLBACK, const char*) = nullptr;
        void (*uninitFn)() = nullptr;
        std::mutex callMutex;  // serializes calls into one plugin
        bool alive = false;
    };

    Plugin* FindLocked(const std::string& pluginKey) const;
    Plugin* LoadOne(const std::string& key, const std::string& dirName);
    void UnloadAll();

    mutable std::mutex mapMutex_;
    std::map<std::string, Plugin*> byKey_;  // lowercase pluginKey -> plugin
    std::vector<Plugin*> plugins_;

    mutable std::mutex pendingMutex_;
    std::map<std::string, Callback> pending_;

    std::mutex activeMutex_;
    std::condition_variable activeCv_;
    int activeCalls_ = 0;
    std::atomic<bool> shuttingDown_{false};
    std::atomic<bool> initialized_{false};

    CoreContext ctx_;
    PlnHost host_{};
    std::string hostAppDir_;
    std::string hostDataDir_;
    std::string hostCacheDir_;
    std::string hostHomeUrl_;
};

} // namespace ets
