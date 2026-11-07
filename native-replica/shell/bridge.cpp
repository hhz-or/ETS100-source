// Bridge implementation: parses page messages and marshals callbacks to the UI thread.
#include "bridge.h"

#include <algorithm>
#include <cctype>
#include <string>

#include "common.h"
#include "plugin_manager.h"
#include "ws_log.h"

namespace ets {
namespace {

std::string Lower(std::string s) {
    for (char& c : s) c = (char)std::tolower((unsigned char)c);
    return s;
}

std::string FieldString(const json& j, const char* key) {
    auto it = j.find(key);
    if (it == j.end() || it->is_null()) return {};
    if (it->is_string()) return it->get<std::string>();
    return it->dump();
}

} // namespace

Bridge::Bridge(HWND hwnd, ICoreWebView2* webview, const CoreContext& core, PluginManager* plugins)
    : hwnd_(hwnd), webview_(webview), core_(core), plugins_(plugins), logger_(core.logger) {
    if (webview_) webview_->AddRef();
}

Bridge::~Bridge() { Detach(); }

void Bridge::Detach() {
    if (webview_) {
        webview_->Release();
        webview_ = nullptr;
    }
}

void Bridge::OnWebMessageJson(const std::wstring& messageJson) {
    const std::string utf8 = WideToUtf8(messageJson);
    if (utf8.empty()) return;

    json outer = json::parse(utf8, nullptr, false);
    if (outer.is_discarded()) {
        if (logger_) logger_->Warn("bridge", "received non-JSON web message");
        return;
    }

    // `chrome.webview.postMessage(JSON.stringify(...))` sends a JSON *string*;
    // object payloads are accepted too.
    std::string inner;
    if (outer.is_string()) {
        inner = outer.get<std::string>();
    } else {
        inner = utf8;
    }

    json msg = json::parse(inner, nullptr, false);
    if (msg.is_discarded() || !msg.is_object()) {
        if (logger_) logger_->Warn("bridge", "invalid cef.message payload: " + inner.substr(0, 256));
        return;
    }

    const std::string uid = FieldString(msg, "uid");
    const std::string plugin = FieldString(msg, "plugin");
    const std::string action = FieldString(msg, "action");

    std::string args;
    auto argsIt = msg.find("args");
    if (argsIt != msg.end()) {
        if (argsIt->is_string()) args = argsIt->get<std::string>();
        else if (argsIt->is_null()) args = "";
        else args = argsIt->dump();
    }

    if (uid.empty()) {
        if (logger_) logger_->Warn("bridge", "cef.message without uid (plugin=" + plugin +
                                                 ", action=" + action + ") ignored");
        return;
    }
    if (logger_) {
        logger_->Debug("bridge", "msg uid=" + uid + " plugin=" + plugin + " action=" + action);
    }

    if (Lower(plugin) == "__core") {
        const std::string data = HandleCoreAction(core_, action, args);
        DeliverOnUiThread(uid, data);
        return;
    }

    if (!plugins_) {
        DeliverOnUiThread(uid, ErrReply(-1, "plugin host not available"));
        return;
    }

    // Plugin calls run on worker threads; callbacks are postMessage()d back to the
    // UI thread because WebView2 COM objects are apartment-bound.
    plugins_->ProcessMessage(
        plugin, action, args, uid,
        [this](const std::string& callbackUid, const std::string& data) {
            PostCallback(callbackUid, data);
        });
}

void Bridge::OnCallbackPosted(const std::string& uid, const std::string& data) {
    DeliverOnUiThread(uid, data);
}

void Bridge::PostCallback(const std::string& uid, const std::string& data) {
    auto* payload = new BridgeCallbackPayload{uid, data};
    if (!PostMessageW(hwnd_, WM_APP_BRIDGE_CALLBACK, 0, reinterpret_cast<LPARAM>(payload))) {
        delete payload;
    }
}

void Bridge::DeliverOnUiThread(const std::string& uid, const std::string& data) {
    if (!webview_) return;
    json j;
    j["type"] = "callback";
    j["uid"] = uid;
    j["data"] = data;
    const std::wstring message = Utf8ToWide(j.dump());
    const HRESULT hr = webview_->PostWebMessageAsJson(message.c_str());
    if (FAILED(hr) && logger_) {
        logger_->Warn("bridge", "PostWebMessageAsJson failed (hr=" + std::to_string((long)hr) +
                                     ") uid=" + uid);
    }
}

} // namespace ets
