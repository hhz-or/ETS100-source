#pragma once
// JS <-> host <-> plugin message routing.
#include <windows.h>
#include <WebView2.h>

#include <string>

#include "core_api.h"

namespace ets {

class Logger;
class PluginManager;

// Payload posted from arbitrary plugin worker threads to the UI thread.
struct BridgeCallbackPayload {
    std::string uid;
    std::string data;
};

// WM_APP + 1 is reserved for plugin callback marshalling.
constexpr UINT WM_APP_BRIDGE_CALLBACK = WM_APP + 1;

class Bridge {
public:
    Bridge(HWND hwnd, ICoreWebView2* webview, const CoreContext& core, PluginManager* plugins);
    ~Bridge();
    Bridge(const Bridge&) = delete;
    Bridge& operator=(const Bridge&) = delete;

    // Called on the UI thread from WebMessageReceived with the raw message JSON.
    void OnWebMessageJson(const std::wstring& messageJson);

    // Called on the UI thread from WM_APP_BRIDGE_CALLBACK.
    void OnCallbackPosted(const std::string& uid, const std::string& data);

    // Thread-safe: posts the callback to the UI thread, then to the page.
    void PostCallback(const std::string& uid, const std::string& data);

    // Drops the WebView reference (UI thread, during shutdown).
    void Detach();

private:
    void DeliverOnUiThread(const std::string& uid, const std::string& data);

    HWND hwnd_ = nullptr;
    ICoreWebView2* webview_ = nullptr;
    CoreContext core_;
    PluginManager* plugins_ = nullptr;
    Logger* logger_ = nullptr;
};

} // namespace ets
