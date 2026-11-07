// EtsReplica shell: Win32 window + WebView2 host + bridge/plugin/media/log lifecycle.
//
// Threading contract:
//   * UI thread: Win32 message loop, all WebView2 COM calls.
//   * plugin worker threads: PlnOnProcessMessage; callbacks are marshalled back to
//     the UI thread with PostMessage(WM_APP_BRIDGE_CALLBACK).
#include <windows.h>
#include <shellapi.h>
#include <objbase.h>
#include <WebView2.h>
#include <WebView2EnvironmentOptions.h>
#include <wrl/client.h>

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <string>

#include "bridge.h"
#include "common.h"
#include "config.h"
#include "media_server.h"
#include "plugin_manager.h"
#include "ws_log.h"

namespace {

// ---------------------------------------------------------------------------
// JS shim injected into every page (CONTRACT.md section 4)
// ---------------------------------------------------------------------------
const char* const kBridgeScript = R"JS(
(function () {
  if (window.__ETS_SHIM_INSTALLED__) return;
  window.__ETS_SHIM_INSTALLED__ = true;
  window.cef = window.cef || {};
  var callbacks = {};
  window.CEF_CB = callbacks;

  function guid() {
    try {
      if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
      }
    } catch (e) {}
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      var v = c === 'x' ? r : ((r & 0x3) | 0x8);
      return v.toString(16);
    });
  }

  function encodeArgs(args) {
    if (args === undefined || args === null) return "";
    if (typeof args === 'string') return args;
    try { return JSON.stringify(args); } catch (e) { return ""; }
  }

  cef.message = {
    sendMessage: function (uid, pluginKey, actionKey, args) {
      try {
        window.chrome.webview.postMessage(JSON.stringify({
          uid: String(uid),
          plugin: String(pluginKey),
          action: String(actionKey),
          args: encodeArgs(args)
        }));
      } catch (e) { console.error('cef.message.sendMessage failed', e); }
    },
    setMessageCallback: function (uid, cb) { callbacks[uid] = cb; },
    removeMessageCallback: function (uid) { delete callbacks[uid]; },
    createGuid: guid,
    getExePath: function () { return ""; },
    getAppConfig: function () { return "{}"; },
    getHomeUrl: function () { return ""; },
    openFile: function () {},
    openFileCallback: function () {},
    setRpkPwd: function () {},
    setRpkInfo: function () {},
    setRpkInfoList: function () {},
    releaseAllDb3: function () {},
    setZoomLevel: function () { return true; },
    getZoomLevel: function () { return 100; },
    setCpkPwd: function () {},
    setProxy: function () {}
  };

  if (window.chrome && window.chrome.webview) {
    window.chrome.webview.addEventListener('message', function (ev) {
      try {
        var m = (typeof ev.data === 'string') ? JSON.parse(ev.data) : ev.data;
        if (m && m.type === 'callback') {
          var cb = callbacks[m.uid];
          if (typeof cb === 'function') cb(m.data);
        }
      } catch (e) { console.error('cef callback error', e); }
    });
  }
})();
)JS";

// ---------------------------------------------------------------------------
// Minimal COM handler helpers (no WRL dependency)
// ---------------------------------------------------------------------------
template <typename TInterface>
struct ComHandler : public TInterface {
    std::atomic<ULONG> refs_{1};

    ULONG STDMETHODCALLTYPE AddRef() override { return ++refs_; }

    ULONG STDMETHODCALLTYPE Release() override {
        ULONG remaining = --refs_;
        if (remaining == 0) delete this;
        return remaining;
    }

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == __uuidof(TInterface) || riid == IID_IUnknown) {
            *ppv = static_cast<TInterface*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
};

struct EnvironmentCompletedHandler
    : ComHandler<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler> {
    std::function<HRESULT(HRESULT, ICoreWebView2Environment*)> fn;
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode,
                                     ICoreWebView2Environment* createdEnvironment) override {
        if (fn) fn(errorCode, createdEnvironment);
        Release();
        return S_OK;
    }
};

struct ControllerCompletedHandler
    : ComHandler<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler> {
    std::function<HRESULT(HRESULT, ICoreWebView2Controller*)> fn;
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode,
                                     ICoreWebView2Controller* createdController) override {
        if (fn) fn(errorCode, createdController);
        Release();
        return S_OK;
    }
};

struct WebMessageHandler : ComHandler<ICoreWebView2WebMessageReceivedEventHandler> {
    std::function<HRESULT(ICoreWebView2*, ICoreWebView2WebMessageReceivedEventArgs*)> fn;
    HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2* sender,
                                     ICoreWebView2WebMessageReceivedEventArgs* args) override {
        if (fn) return fn(sender, args);
        return S_OK;
    }
};

struct NewWindowHandler : ComHandler<ICoreWebView2NewWindowRequestedEventHandler> {
    std::function<HRESULT(ICoreWebView2*, ICoreWebView2NewWindowRequestedEventArgs*)> fn;
    HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2* sender,
                                     ICoreWebView2NewWindowRequestedEventArgs* args) override {
        if (fn) return fn(sender, args);
        return S_OK;
    }
};

struct ProcessFailedHandler : ComHandler<ICoreWebView2ProcessFailedEventHandler> {
    std::function<HRESULT(ICoreWebView2*, ICoreWebView2ProcessFailedEventArgs*)> fn;
    HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2* sender,
                                     ICoreWebView2ProcessFailedEventArgs* args) override {
        if (fn) return fn(sender, args);
        return S_OK;
    }
};

struct NavigationCompletedHandler : ComHandler<ICoreWebView2NavigationCompletedEventHandler> {
    std::function<HRESULT(ICoreWebView2*, ICoreWebView2NavigationCompletedEventArgs*)> fn;
    HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2* sender,
                                     ICoreWebView2NavigationCompletedEventArgs* args) override {
        if (fn) return fn(sender, args);
        return S_OK;
    }
};

std::wstring HResultText(HRESULT hr) {
    wchar_t buf[32] = {};
    std::swprintf(buf, 32, L"0x%08lX", (unsigned long)hr);
    return buf;
}

// ---------------------------------------------------------------------------
// Application context
// ---------------------------------------------------------------------------
struct AppContext {
    HWND hwnd = nullptr;
    ets::Config cfg;
    ets::Logger* logger = nullptr;
    ets::MediaServer* media = nullptr;
    ets::PluginManager* plugins = nullptr;
    ets::Bridge* bridge = nullptr;

    ICoreWebView2Environment* environment = nullptr;
    ICoreWebView2Controller* controller = nullptr;
    ICoreWebView2* webview = nullptr;

    WebMessageHandler* msgHandler = nullptr;
    NewWindowHandler* newWindowHandler = nullptr;
    ProcessFailedHandler* processFailedHandler = nullptr;
    NavigationCompletedHandler* navHandler = nullptr;

    EventRegistrationToken msgToken{};
    EventRegistrationToken newWindowToken{};
    EventRegistrationToken processFailedToken{};
    EventRegistrationToken navToken{};

    bool shuttingDown = false;
    bool webviewFailed = false;

    ets::CoreContext MakeCore() const {
        ets::CoreContext core;
        core.appDir = cfg.appDir;
        core.dataDir = cfg.dataDir;
        core.cacheDir = cfg.cacheDir;
        core.homeUrl = cfg.homeUrl;
        core.version = "1.0.0";
        core.logger = logger;
        core.media = media;
        return core;
    }
};

AppContext* g_app = nullptr;

void DoShutdown(AppContext* app);
LRESULT CALLBACK WndProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam);

// ---------------------------------------------------------------------------
// WebView2 setup
// ---------------------------------------------------------------------------
void SetupWebView(AppContext* app) {
    auto* wv = app->webview;
    auto* logger = app->logger;
    if (!wv) return;

    ICoreWebView2Settings* settings = nullptr;
    if (SUCCEEDED(wv->get_Settings(&settings)) && settings) {
        settings->put_IsScriptEnabled(TRUE);
        settings->put_IsStatusBarEnabled(FALSE);
        settings->put_AreDefaultContextMenusEnabled(TRUE);
        settings->put_IsZoomControlEnabled(FALSE);
        settings->Release();
    }

    // Local frontend build output served as https://app.ets.local/
    const std::string webDir = app->cfg.AssetsWebDir();
    ets::EnsureDir(webDir);
    const std::wstring webRoot = ets::Utf8ToWide(webDir);

    bool hostMapped = false;
    ICoreWebView2_3* webview3 = nullptr;
    if (SUCCEEDED(wv->QueryInterface(IID_ICoreWebView2_3, reinterpret_cast<void**>(&webview3))) &&
        webview3) {
        HRESULT hr = webview3->SetVirtualHostNameToFolderMapping(
            L"app.ets.local", webRoot.c_str(), COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_ALLOW);
        hostMapped = SUCCEEDED(hr);
        if (!hostMapped && logger) {
            logger->Warn("webview", "SetVirtualHostNameToFolderMapping failed hr=" +
                                        ets::WideToUtf8(HResultText(hr)));
        }
        webview3->Release();
    } else if (logger) {
        logger->Warn("webview", "ICoreWebView2_3 unavailable; virtual host mapping disabled");
    }

    // CONTRACT.md section 4 shim.
    const std::wstring shim = ets::Utf8ToWide(kBridgeScript);
    HRESULT shimHr = wv->AddScriptToExecuteOnDocumentCreated(shim.c_str(), nullptr);
    if (FAILED(shimHr) && logger) {
        logger->Error("webview", "AddScriptToExecuteOnDocumentCreated failed hr=" +
                                     ets::WideToUtf8(HResultText(shimHr)));
    }

    app->bridge = new ets::Bridge(app->hwnd, wv, app->MakeCore(), app->plugins);

    // Page -> host.
    app->msgHandler = new WebMessageHandler();
    app->msgHandler->fn = [app](ICoreWebView2* /*sender*/,
                               ICoreWebView2WebMessageReceivedEventArgs* args) -> HRESULT {
        LPWSTR raw = nullptr;
        if (FAILED(args->get_WebMessageAsJson(&raw)) || !raw) return S_OK;
        std::wstring text(raw);
        CoTaskMemFree(raw);
        if (app->bridge) app->bridge->OnWebMessageJson(text);
        return S_OK;
    };
    wv->add_WebMessageReceived(app->msgHandler, &app->msgToken);

    // window.open / target=_blank -> external browser.
    app->newWindowHandler = new NewWindowHandler();
    app->newWindowHandler->fn = [app](ICoreWebView2* /*sender*/,
                                      ICoreWebView2NewWindowRequestedEventArgs* args) -> HRESULT {
        LPWSTR uri = nullptr;
        if (SUCCEEDED(args->get_Uri(&uri)) && uri) {
            std::wstring url(uri);
            CoTaskMemFree(uri);
            args->put_Handled(TRUE);
            if (app->logger) {
                app->logger->Info("webview", "external link: " + ets::WideToUtf8(url));
            }
            if (url.rfind(L"http://", 0) == 0 || url.rfind(L"https://", 0) == 0) {
                ShellExecuteW(nullptr, L"open", url.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
            }
        } else {
            args->put_Handled(TRUE);
        }
        return S_OK;
    };
    wv->add_NewWindowRequested(app->newWindowHandler, &app->newWindowToken);

    // Crashes / process failures.
    app->processFailedHandler = new ProcessFailedHandler();
    app->processFailedHandler->fn =
        [app](ICoreWebView2* /*sender*/, ICoreWebView2ProcessFailedEventArgs* args) -> HRESULT {
        COREWEBVIEW2_PROCESS_FAILED_KIND kind = COREWEBVIEW2_PROCESS_FAILED_KIND_BROWSER_PROCESS_EXITED;
        args->get_ProcessFailedKind(&kind);
        if (app->logger) {
            app->logger->Error("webview",
                               "process failed, kind=" + std::to_string((int)kind));
        }
        return S_OK;
    };
    wv->add_ProcessFailed(app->processFailedHandler, &app->processFailedToken);

    // Navigation diagnostics.
    app->navHandler = new NavigationCompletedHandler();
    app->navHandler->fn = [app](ICoreWebView2* /*sender*/,
                                ICoreWebView2NavigationCompletedEventArgs* args) -> HRESULT {
        BOOL success = FALSE;
        args->get_IsSuccess(&success);
        if (!success && app->logger) {
            COREWEBVIEW2_WEB_ERROR_STATUS status = COREWEBVIEW2_WEB_ERROR_STATUS_UNKNOWN;
            args->get_WebErrorStatus(&status);
            app->logger->Warn("webview", "navigation completed with error status=" +
                                             std::to_string((int)status));
        }
        return S_OK;
    };
    wv->add_NavigationCompleted(app->navHandler, &app->navToken);

    // Navigate: local virtual host by default, remote when shell.ini HomeUrl is remote.
    std::wstring navUrl = ets::Utf8ToWide(app->cfg.StartUrl());
    if (!hostMapped && !app->cfg.IsRemoteHome()) {
        std::wstring fileUrl = L"file:///" + webRoot + L"/index.html";
        std::replace(fileUrl.begin(), fileUrl.end(), L'\\', L'/');
        navUrl = fileUrl;
        if (logger) {
            logger->Warn("webview", "virtual host unavailable; falling back to file:// navigation");
        }
    }
    HRESULT navHr = wv->Navigate(navUrl.c_str());
    if (logger) {
        logger->Info("webview", "navigate " + ets::WideToUtf8(navUrl) + " (hr=" +
                                    ets::WideToUtf8(HResultText(navHr)) + ")");
    }
    if (app->controller) app->controller->MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);
}

void CreateWebView2(AppContext* app) {
    const std::string userDataDirUtf8 = ets::JoinPath(app->cfg.dataDir, "WebView2");
    ets::EnsureDir(userDataDirUtf8);
    const std::wstring userDataDir = ets::Utf8ToWide(userDataDirUtf8);

    auto* envHandler = new EnvironmentCompletedHandler();
    envHandler->fn = [app](HRESULT hr, ICoreWebView2Environment* env) -> HRESULT {
        if (FAILED(hr) || !env) {
            if (app->logger) {
                app->logger->Error("webview", "CreateCoreWebView2Environment failed hr=" +
                                                  ets::WideToUtf8(HResultText(hr)));
            }
            app->webviewFailed = true;
            MessageBoxW(app->hwnd,
                        L"WebView2 \u8FD0\u884C\u65F6\u521D\u59CB\u5316\u5931\u8D25\u3002\n"
                        L"\u8BF7\u786E\u8BA4\u5DF2\u5B89\u88C5 Microsoft Edge WebView2 Runtime\u3002",
                        L"EtsReplica", MB_ICONERROR | MB_OK);
            PostQuitMessage(1);
            return S_OK;
        }

        env->AddRef();
        app->environment = env;

        auto* ctrlHandler = new ControllerCompletedHandler();
        ctrlHandler->fn = [app](HRESULT ctrlHr, ICoreWebView2Controller* controller) -> HRESULT {
            if (FAILED(ctrlHr) || !controller) {
                if (app->logger) {
                    app->logger->Error("webview", "CreateCoreWebView2Controller failed hr=" +
                                                      ets::WideToUtf8(HResultText(ctrlHr)));
                }
                app->webviewFailed = true;
                MessageBoxW(app->hwnd, L"WebView2 \u63A7\u4EF6\u521B\u5EFA\u5931\u8D25\u3002",
                            L"EtsReplica", MB_ICONERROR | MB_OK);
                PostQuitMessage(1);
                return S_OK;
            }
            // NOTE: the controller handed to this callback is a *borrowed* reference
            // for this WebView2 runtime (the object is destroyed right after the
            // callback returns unless AddRef'd). Keep our own reference.
            controller->AddRef();
            app->controller = controller;
            RECT rc{};
            GetClientRect(app->hwnd, &rc);
            controller->put_Bounds(rc);
            controller->get_CoreWebView2(&app->webview);
            if (!app->webview) {
                if (app->logger) app->logger->Error("webview", "get_CoreWebView2 returned null");
                app->webviewFailed = true;
                PostQuitMessage(1);
                return S_OK;
            }
            SetupWebView(app);
            return S_OK;
        };
        env->CreateCoreWebView2Controller(app->hwnd, ctrlHandler);
        return S_OK;
    };

    // Optional remote debugging for automated verification / tooling:
    //   set ETS_REPLICA_DEBUG_PORT=9333 before launching the shell.
    Microsoft::WRL::ComPtr<CoreWebView2EnvironmentOptions> options;
    ICoreWebView2EnvironmentOptions* optionsPtr = nullptr;
    {
        const char* debugPort = std::getenv("ETS_REPLICA_DEBUG_PORT");
        if (debugPort && *debugPort) {
            options = Microsoft::WRL::Make<CoreWebView2EnvironmentOptions>();
            if (options) {
                std::wstring args = L"--remote-debugging-port=" + ets::Utf8ToWide(debugPort);
                options->put_AdditionalBrowserArguments(args.c_str());
                optionsPtr = static_cast<ICoreWebView2EnvironmentOptions*>(options.Get());
                if (app->logger) app->logger->Info("webview", "remote debugging enabled: " + std::string(debugPort));
            }
        }
    }

    HRESULT hr = CreateCoreWebView2EnvironmentWithOptions(nullptr, userDataDir.c_str(), optionsPtr,
                                                          envHandler);
    if (FAILED(hr)) {
        if (app->logger) {
            app->logger->Error("webview", "CreateCoreWebView2EnvironmentWithOptions failed hr=" +
                                              ets::WideToUtf8(HResultText(hr)));
        }
        // Callback will not be invoked on a synchronous failure: drop our reference.
        envHandler->Release();
        app->webviewFailed = true;
        MessageBoxW(app->hwnd,
                    L"WebView2 \u8FD0\u884C\u65F6\u521D\u59CB\u5316\u5931\u8D25\u3002\n"
                    L"\u8BF7\u786E\u8BA4\u5DF2\u5B89\u88C5 Microsoft Edge WebView2 Runtime\u3002",
                    L"EtsReplica", MB_ICONERROR | MB_OK);
        PostQuitMessage(1);
    }
}

// ---------------------------------------------------------------------------
// Shutdown
// ---------------------------------------------------------------------------
void DoShutdown(AppContext* app) {
    if (!app || app->shuttingDown) return;
    app->shuttingDown = true;
    if (app->logger) app->logger->Info("shell", "shutting down");

    if (app->bridge) {
        app->logger->Debug("shell", "shutdown step: detach bridge");
        app->bridge->Detach();
    }

    if (app->webview) {
        app->logger->Debug("shell", "shutdown step: remove webview handlers");
        if (app->msgHandler) app->webview->remove_WebMessageReceived(app->msgToken);
        if (app->newWindowHandler) app->webview->remove_NewWindowRequested(app->newWindowToken);
        if (app->processFailedHandler) app->webview->remove_ProcessFailed(app->processFailedToken);
        if (app->navHandler) app->webview->remove_NavigationCompleted(app->navToken);
    }
    if (app->msgHandler) {
        app->msgHandler->Release();
        app->msgHandler = nullptr;
    }
    if (app->newWindowHandler) {
        app->newWindowHandler->Release();
        app->newWindowHandler = nullptr;
    }
    if (app->processFailedHandler) {
        app->processFailedHandler->Release();
        app->processFailedHandler = nullptr;
    }
    if (app->navHandler) {
        app->navHandler->Release();
        app->navHandler = nullptr;
    }

    if (app->controller) {
        app->logger->Debug("shell", "shutdown step: controller close");
        app->controller->Close();
    }
    if (app->webview) {
        app->logger->Debug("shell", "shutdown step: release webview");
        app->webview->Release();
        app->webview = nullptr;
    }
    if (app->controller) {
        app->logger->Debug("shell", "shutdown step: release controller");
        app->controller->Release();
        app->controller = nullptr;
    }
    if (app->environment) {
        app->logger->Debug("shell", "shutdown step: release environment");
        app->environment->Release();
        app->environment = nullptr;
    }

    // Plugins first (their logs still reach the logger), then media, then logging.
    if (app->plugins) {
        app->logger->Debug("shell", "shutdown step: plugin host");
        app->plugins->Shutdown();
    }
    if (app->media) {
        app->logger->Debug("shell", "shutdown step: media server");
        app->media->Stop();
    }
    if (app->logger) {
        app->logger->Info("shell", "shutdown complete");
        app->logger->Stop();
    }
}

// ---------------------------------------------------------------------------
// Window procedure
// ---------------------------------------------------------------------------
LRESULT CALLBACK WndProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
        case WM_SIZE:
            // Ignore resize notifications raised while the WebView2 controller is
            // being closed (Close() can synchronously pump window messages).
            if (g_app && !g_app->shuttingDown && g_app->controller &&
                wParam != SIZE_MINIMIZED) {
                RECT rc{};
                GetClientRect(hwnd, &rc);
                g_app->controller->put_Bounds(rc);
            }
            return 0;

        case ets::WM_APP_BRIDGE_CALLBACK: {
            auto* payload = reinterpret_cast<ets::BridgeCallbackPayload*>(lParam);
            if (payload) {
                if (g_app && g_app->bridge) {
                    g_app->bridge->OnCallbackPosted(payload->uid, payload->data);
                }
                delete payload;
            }
            return 0;
        }

        case WM_CLOSE:
            DestroyWindow(hwnd);
            return 0;

        case WM_DESTROY:
            PostQuitMessage(0);
            return 0;

        default:
            break;
    }
    return DefWindowProcW(hwnd, message, wParam, lParam);
}

} // namespace

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------
int APIENTRY wWinMain(HINSTANCE hInstance, HINSTANCE /*hPrevInstance*/, LPWSTR /*lpCmdLine*/,
                      int nCmdShow) {
#ifdef DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
#else
    SetProcessDPIAware();
#endif
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

    // Intentionally heap allocated and never deleted: detached plugin worker
    // threads and WebView2 callbacks may still reference these while the process
    // is exiting.
    auto* app = new AppContext();
    app->cfg.Load();
    g_app = app;

    auto* logger = new ets::Logger();
    app->logger = logger;
    logger->Start(app->cfg);
    logger->Info("shell", "EtsReplica shell starting (appDir=" + app->cfg.appDir + ")");

    auto* media = new ets::MediaServer();
    app->media = media;
    if (!media->Start(app->cfg.cacheDir, logger)) {
        logger->Warn("media", "local media server failed to start; media_url will fail");
    }

    auto* plugins = new ets::PluginManager();
    app->plugins = plugins;
    plugins->Init(app->MakeCore());

    WNDCLASSEXW wc{};
    wc.cbSize = sizeof(wc);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.hCursor = LoadCursorW(nullptr, reinterpret_cast<LPCWSTR>(IDC_ARROW));
    wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
    wc.lpszClassName = L"EtsReplicaMainWindow";
    wc.hIcon = LoadIconW(nullptr, reinterpret_cast<LPCWSTR>(IDI_APPLICATION));
    wc.hIconSm = wc.hIcon;
    if (!RegisterClassExW(&wc)) {
        logger->Error("shell", "RegisterClassExW failed");
        return 1;
    }

    const int screenWidth = GetSystemMetrics(SM_CXSCREEN);
    const int screenHeight = GetSystemMetrics(SM_CYSCREEN);
    const int winWidth = std::min(app->cfg.windowWidth, std::max(400, screenWidth));
    const int winHeight = std::min(app->cfg.windowHeight, std::max(300, screenHeight));
    const int winX = std::max(0, (screenWidth - winWidth) / 2);
    const int winY = std::max(0, (screenHeight - winHeight) / 2);

    const std::wstring title = ets::Utf8ToWide(app->cfg.appName);
    app->hwnd = CreateWindowExW(0, L"EtsReplicaMainWindow", title.c_str(), WS_OVERLAPPEDWINDOW,
                                winX, winY, winWidth, winHeight, nullptr, nullptr, hInstance,
                                nullptr);
    if (!app->hwnd) {
        logger->Error("shell", "CreateWindowExW failed");
        return 1;
    }
    ShowWindow(app->hwnd, (nCmdShow == 0) ? SW_SHOWNORMAL : nCmdShow);
    UpdateWindow(app->hwnd);

    CreateWebView2(app);

    MSG msg{};
    while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    DoShutdown(app);
    CoUninitialize();
    return (int)msg.wParam;
}
