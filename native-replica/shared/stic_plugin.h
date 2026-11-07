#pragma once
// ETS native replica — plugin ABI (mirrors the original STIC plugin contract)
#include <windows.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void(__stdcall* PLN_CALLBACK)(const char* uid, const char* data); // data: UTF-8 JSON
typedef void(__stdcall* PLN_LOG)(int level, const char* msg);             // level: 0 info, 1 warn, 2 error
typedef void(__stdcall* PLN_EXEC)(const char* action, const char* args, PLN_CALLBACK cb, const char* uid);

typedef struct PlnHost {
    unsigned int size;   // sizeof(PlnHost)
    PLN_LOG Log;
    PLN_LOG WLog;
    PLN_EXEC Exec;       // host builtin capability (e.g. "__core/media_url")
    const char* AppDir;  // exe directory (UTF-8)
    const char* DataDir; // %APPDATA%/ETS-Replica (UTF-8)
    const char* CacheDir;// DataDir/cache (UTF-8)
    const char* HomeUrl; // shell.ini HomeUrl
} PlnHost;

__declspec(dllexport) void PlnInitiliaze(PlnHost* host); // original spelling preserved
__declspec(dllexport) void PlnSetParam(const char* key, void* fn);
__declspec(dllexport) void PlnOnProcessMessage(const char* action, const char* argsJson, PLN_CALLBACK cb, const char* uid);
__declspec(dllexport) void PlnUnInitialize(void);

#ifdef __cplusplus
}
#endif
