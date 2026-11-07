// plugin shellhelper — machine information, volume, processes
// ABI: shared/stic_plugin.h ; contract: CONTRACT.md §6
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
// winsock2.h must precede windows.h so that IP_ADAPTER_ADDRESSES is declared
// (iptypes.h exposes it only under _WINSOCK2API_).
#include <winsock2.h>

#include "common.h"

#include <windows.h>
#include <iphlpapi.h>
#include <mmsystem.h>
#include <tlhelp32.h>

#include <cctype>
#include <cstdio>
#include <string>
#include <vector>

#pragma comment(lib, "iphlpapi.lib")
#pragma comment(lib, "winmm.lib")
#pragma comment(lib, "advapi32.lib")

namespace {

PLN_LOG g_log = nullptr;
PLN_LOG g_wlog = nullptr;

std::string g_appDir;
std::string g_dataDir;
std::string g_cacheDir;
std::string g_homeUrl;

constexpr const char* kVersion = "1.0.0";

void Log(const std::string& msg) {
    if (g_log) g_log(0, msg.c_str());
}
void LogWarn(const std::string& msg) {
    if (g_wlog) g_wlog(1, msg.c_str());
    else if (g_log) g_log(1, msg.c_str());
}

std::string ArgStr(const ets::json& args, const char* key, const std::string& def = "") {
    auto it = args.find(key);
    if (it == args.end() || it->is_null()) return def;
    if (it->is_string()) return it->get<std::string>();
    if (it->is_boolean()) return it->get<bool>() ? "true" : "false";
    if (it->is_number_integer()) return std::to_string(it->get<long long>());
    if (it->is_number_unsigned()) return std::to_string(it->get<unsigned long long>());
    if (it->is_number_float()) {
        char buf[64] = {};
        snprintf(buf, sizeof(buf), "%.17g", it->get<double>());
        return buf;
    }
    if (it->is_object() || it->is_array()) return it->dump();
    return def;
}

std::string Trim(const std::string& s) {
    size_t b = 0, e = s.size();
    while (b < e && (unsigned char)s[b] <= ' ') ++b;
    while (e > b && (unsigned char)s[e - 1] <= ' ') --e;
    return s.substr(b, e - b);
}

// ---- machine info -----------------------------------------------------------

struct OsVersionInfo {
    DWORD size;
    DWORD major;
    DWORD minor;
    DWORD build;
    DWORD platform;
    wchar_t csd[128];
};

std::string WindowsVersionString() {
    OsVersionInfo vi = {};
    vi.size = sizeof(vi);
    using RtlGetVersionFn = LONG(WINAPI*)(OsVersionInfo*);
    HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    bool got = false;
    if (ntdll) {
        auto fn = (RtlGetVersionFn)GetProcAddress(ntdll, "RtlGetVersion");
        if (fn && fn(&vi) == 0) got = true;
    }
    if (!got) {
        OSVERSIONINFOW ovi = {};
        ovi.dwOSVersionInfoSize = sizeof(ovi);
#pragma warning(push)
#pragma warning(disable : 4996)
        if (GetVersionExW(&ovi)) {
            vi.major = ovi.dwMajorVersion;
            vi.minor = ovi.dwMinorVersion;
            vi.build = ovi.dwBuildNumber;
            got = true;
        }
#pragma warning(pop)
    }
    if (!got) return "unknown";
    return std::to_string((unsigned long)vi.major) + "." + std::to_string((unsigned long)vi.minor) + "." +
           std::to_string((unsigned long)vi.build);
}

std::string ComputerName() {
    wchar_t buf[256] = {};
    DWORD n = _countof(buf);
    if (!GetComputerNameW(buf, &n)) return "";
    return ets::WideToUtf8(std::wstring(buf, n));
}

std::string UserName() {
    wchar_t buf[256] = {};
    DWORD n = _countof(buf);
    if (!GetUserNameW(buf, &n)) return "";
    if (n > 0) --n; // includes the terminating NUL
    return ets::WideToUtf8(std::wstring(buf, n));
}

std::string ProcessFileName() {
    wchar_t buf[MAX_PATH * 2] = {};
    DWORD n = GetModuleFileNameW(nullptr, buf, _countof(buf));
    if (n == 0 || n >= _countof(buf)) return "";
    std::wstring path(buf, n);
    size_t slash = path.find_last_of(L"\\/");
    return ets::WideToUtf8(slash == std::wstring::npos ? path : path.substr(slash + 1));
}

// Enumerates usable (up + non-loopback) unicast addresses.
struct AdapterInfo {
    int count = 0;
    std::string ipv4;
};

AdapterInfo QueryAdapters() {
    AdapterInfo out;
    ULONG size = 16 * 1024;
    std::vector<uint8_t> buf(size);
    ULONG flags = GAA_FLAG_SKIP_ANYCAST | GAA_FLAG_SKIP_MULTICAST | GAA_FLAG_SKIP_DNS_SERVER;
    ULONG rc = GetAdaptersAddresses(AF_UNSPEC, flags, nullptr,
                                    reinterpret_cast<IP_ADAPTER_ADDRESSES*>(buf.data()), &size);
    if (rc == ERROR_BUFFER_OVERFLOW) {
        buf.resize(size);
        rc = GetAdaptersAddresses(AF_UNSPEC, flags, nullptr,
                                  reinterpret_cast<IP_ADAPTER_ADDRESSES*>(buf.data()), &size);
    }
    if (rc != NO_ERROR) return out;
    std::string physicalIp;
    for (auto* a = reinterpret_cast<IP_ADAPTER_ADDRESSES*>(buf.data()); a; a = a->Next) {
        if (a->OperStatus != IfOperStatusUp) continue;
        if (a->IfType == IF_TYPE_SOFTWARE_LOOPBACK) continue;
        const bool physical = a->IfType == IF_TYPE_ETHERNET_CSMACD || a->IfType == IF_TYPE_IEEE80211;
        bool any = false;
        bool tookV4 = false;
        for (auto* ua = a->FirstUnicastAddress; ua; ua = ua->Next) {
            if (!ua->Address.lpSockaddr) continue;
            any = true;
            if (ua->Address.lpSockaddr->sa_family == AF_INET && !tookV4) {
                auto* sin = reinterpret_cast<sockaddr_in*>(ua->Address.lpSockaddr);
                const unsigned char* b = reinterpret_cast<const unsigned char*>(&sin->sin_addr);
                char ip[32] = {};
                snprintf(ip, sizeof(ip), "%u.%u.%u.%u", (unsigned)b[0], (unsigned)b[1], (unsigned)b[2],
                         (unsigned)b[3]);
                if (physical) {
                    if (physicalIp.empty()) physicalIp = ip;
                } else if (out.ipv4.empty()) {
                    out.ipv4 = ip;
                }
                tookV4 = true;
            }
        }
        if (any) ++out.count;
    }
    if (!physicalIp.empty()) out.ipv4 = physicalIp; // prefer Ethernet/Wi-Fi over VPN/TUN adapters
    return out;
}

struct DiskInfo {
    uint64_t totalBytes = 0;
    uint64_t freeBytes = 0;
};

DiskInfo QuerySystemDisk() {
    DiskInfo d;
    wchar_t winDir[MAX_PATH] = {};
    if (!GetWindowsDirectoryW(winDir, MAX_PATH)) return d;
    wchar_t root[4] = {winDir[0], L':', L'\\', 0};
    ULARGE_INTEGER freeAvail = {}, total = {}, totalFree = {};
    if (GetDiskFreeSpaceExW(root, &freeAvail, &total, &totalFree)) {
        d.totalBytes = total.QuadPart;
        d.freeBytes = totalFree.QuadPart;
    }
    return d;
}

std::string MachineGuid() {
    wchar_t buf[256] = {};
    DWORD bytes = sizeof(buf);
    if (RegGetValueW(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Microsoft\\Cryptography", L"MachineGuid",
                     RRF_RT_REG_SZ, nullptr, buf, &bytes) == ERROR_SUCCESS) {
        std::wstring s(buf);
        return Trim(ets::WideToUtf8(s));
    }
    return "";
}

std::string VolumeSerialOfSystemDrive() {
    wchar_t winDir[MAX_PATH] = {};
    if (!GetWindowsDirectoryW(winDir, MAX_PATH)) return "";
    wchar_t root[4] = {winDir[0], L':', L'\\', 0};
    DWORD serial = 0;
    if (GetVolumeInformationW(root, nullptr, 0, &serial, nullptr, nullptr, nullptr, 0))
        return std::to_string((unsigned long)serial);
    return "";
}

std::string UniqueId() {
    std::string basis = MachineGuid();
    if (basis.empty()) {
        basis = ComputerName() + "|" + VolumeSerialOfSystemDrive() + "|" + UserName();
    }
    return ets::Sha1Hex(basis);
}

bool RunHidden(const std::wstring& cmdlineIn, DWORD waitMs, DWORD& exitCode, std::string& err) {
    std::wstring cmd = cmdlineIn;
    std::vector<wchar_t> mutableCmd(cmd.begin(), cmd.end());
    mutableCmd.push_back(L'\0');

    STARTUPINFOW si = {};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi = {};
    if (!CreateProcessW(nullptr, mutableCmd.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr,
                        nullptr, &si, &pi)) {
        err = "CreateProcess failed: " + std::to_string((unsigned long)GetLastError());
        return false;
    }
    DWORD rc = WaitForSingleObject(pi.hProcess, waitMs);
    exitCode = 0;
    if (rc == WAIT_OBJECT_0) GetExitCodeProcess(pi.hProcess, &exitCode);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return true;
}

std::wstring QuoteIfNeeded(const std::string& pathUtf8) {
    std::wstring w = ets::Utf8ToWide(pathUtf8);
    if (w.empty()) return w;
    if (w.front() == L'"') return w;
    if (w.find(L' ') == std::wstring::npos && w.find(L'\t') == std::wstring::npos) return w;
    return L"\"" + w + L"\"";
}

// "C:\Windows\System32\notepad.exe" -> "notepad.exe" (taskkill image name)
std::string BaseName(const std::string& path) {
    size_t p = path.find_last_of("\\/");
    return p == std::string::npos ? path : path.substr(p + 1);
}

std::vector<std::string> CollectProcessList(const ets::json& args) {
    std::vector<std::string> out;
    auto addFromObject = [&out](const ets::json& o) {
        static const char* keys[] = {"path", "exePath", "processPath", "exe", "name"};
        for (const char* k : keys) {
            auto it = o.find(k);
            if (it != o.end() && it->is_string()) {
                std::string v = Trim(it->get<std::string>());
                if (!v.empty()) out.push_back(v);
                return;
            }
        }
    };
    auto it = args.find("process_list");
    if (it != args.end()) {
        if (it->is_array()) {
            for (const auto& e : *it) {
                if (e.is_string()) {
                    std::string v = Trim(e.get<std::string>());
                    if (!v.empty()) out.push_back(v);
                } else if (e.is_object()) {
                    addFromObject(e);
                }
            }
        } else if (it->is_string()) {
            std::string v = Trim(it->get<std::string>());
            if (!v.empty()) out.push_back(v);
        }
    }
    if (out.empty()) {
        for (const char* k : {"path", "exePath", "processPath", "exe", "processName", "name"}) {
            auto e = args.find(k);
            if (e != args.end() && e->is_string()) {
                std::string v = Trim(e->get<std::string>());
                if (!v.empty()) {
                    out.push_back(v);
                    break;
                }
            }
        }
    }
    return out;
}

std::string Handle(const std::string& action, const ets::json& args) {
    using ets::json;

    if (action == "getpcinfo") {
        const AdapterInfo adapters = QueryAdapters();
        const DiskInfo disk = QuerySystemDisk();
        SYSTEM_INFO si = {};
        GetSystemInfo(&si);
        MEMORYSTATUSEX ms = {};
        ms.dwLength = sizeof(ms);
        GlobalMemoryStatusEx(&ms);

        json r;
        r["AppTitle"] = "E听说";
        r["ClientType"] = "PC";
        r["CopyRight"] = "Copyright (c) 2026 ETS-Replica";
        r["Name"] = UserName();
        r["computername"] = ComputerName();
        r["OsBit"] = sizeof(void*) == 8 ? "64" : "32";
        r["SystemVersion"] = WindowsVersionString();
        r["ProcessName"] = ProcessFileName();
        r["DwNum"] = std::to_string((unsigned long)si.dwNumberOfProcessors);
        r["HDD"] = std::to_string((unsigned long long)(disk.totalBytes / (1024ull * 1024ull * 1024ull)));
        r["IP2"] = adapters.ipv4;
        r["Version"] = kVersion;
        r["Memory"] = std::to_string((unsigned long long)(ms.ullTotalPhys / (1024ull * 1024ull * 1024ull)));
        return r.dump();
    }

    if (action == "getconfig") {
        json r;
        r["appDir"] = g_appDir;
        r["dataDir"] = g_dataDir;
        r["cacheDir"] = g_cacheDir;
        r["homeUrl"] = g_homeUrl;
        r["version"] = kVersion;
        return r.dump();
    }

    if (action == "getvolume") {
        DWORD vol = 0;
        MMRESULT rc = waveOutGetVolume(0, &vol);
        if (rc != MMSYSERR_NOERROR) return ets::ErrReply(-1, "waveOutGetVolume failed");
        const DWORD left = vol & 0xFFFF;
        const int percent = (int)((left * 100 + 0x7FFF) / 0xFFFF);
        json r;
        r["volume"] = percent;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "setvolume") {
        int percent = 50;
        if (args.contains("volume") && args["volume"].is_number())
            percent = (int)args["volume"].get<double>();
        if (percent < 0) percent = 0;
        if (percent > 100) percent = 100;
        const DWORD v = (DWORD)(((uint64_t)percent * 0xFFFF + 50) / 100);
        MMRESULT rc = waveOutSetVolume(0, v | (v << 16));
        if (rc != MMSYSERR_NOERROR) return ets::ErrReply(-1, "waveOutSetVolume failed");
        json r;
        r["volume"] = percent;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "checkadapter") {
        const AdapterInfo a = QueryAdapters();
        json r;
        if (a.count > 0) {
            r["rncode"] = 1;
            r["rnmsg"] = "网卡正常.";
            r["count"] = a.count;
        } else {
            r["rncode"] = 0;
            r["rnmsg"] = "网卡异常.";
            r["count"] = 0;
        }
        return r.dump();
    }

    if (action == "getuniqueid") {
        json r;
        r["id"] = UniqueId();
        r["code"] = 0;
        return r.dump();
    }

    if (action == "startprocess") {
        const std::vector<std::string> procs = CollectProcessList(args);
        if (procs.empty()) return ets::ErrReply(-1, "process not specified");
        json pids = json::array();
        std::string firstErr;
        for (const auto& p : procs) {
            std::wstring cmd = QuoteIfNeeded(p);
            std::vector<wchar_t> mutableCmd(cmd.begin(), cmd.end());
            mutableCmd.push_back(L'\0');
            STARTUPINFOW si = {};
            si.cb = sizeof(si);
            PROCESS_INFORMATION pi = {};
            if (!CreateProcessW(nullptr, mutableCmd.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr,
                                nullptr, &si, &pi)) {
                if (firstErr.empty())
                    firstErr = "start failed (" + std::to_string((unsigned long)GetLastError()) + "): " + p;
                continue;
            }
            pids.push_back((long long)pi.dwProcessId);
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
        }
        if (pids.empty()) return ets::ErrReply(-1, firstErr.empty() ? "start failed" : firstErr);
        json r;
        r["code"] = 0;
        r["pids"] = pids;
        return r.dump();
    }

    if (action == "stopprocess") {
        const std::vector<std::string> procs = CollectProcessList(args);
        if (procs.empty()) return ets::ErrReply(-1, "process not specified");
        int failed = 0;
        std::string firstErr;
        for (const auto& p : procs) {
            std::wstring cmd;
            bool numeric = !p.empty();
            for (char c : p) {
                if (!isdigit((unsigned char)c)) {
                    numeric = false;
                    break;
                }
            }
            if (numeric) cmd = L"taskkill /F /PID " + ets::Utf8ToWide(p);
            else cmd = L"taskkill /F /IM " + QuoteIfNeeded(BaseName(p));
            DWORD exitCode = 0;
            std::string err;
            if (!RunHidden(cmd, 10000, exitCode, err)) {
                ++failed;
                if (firstErr.empty()) firstErr = err;
                continue;
            }
            // taskkill: 128 means "process not found" (already stopped) — treat as success.
            if (exitCode != 0 && exitCode != 128) {
                ++failed;
                if (firstErr.empty()) firstErr = "taskkill exit " + std::to_string((unsigned long)exitCode);
            }
        }
        if (failed > 0 && failed == (int)procs.size())
            return ets::ErrReply(-1, firstErr.empty() ? "stop failed" : firstErr);
        json r;
        r["code"] = 0;
        r["failed"] = failed;
        return r.dump();
    }

    if (action == "processexist") {
        const std::vector<std::string> procs = CollectProcessList(args);
        if (procs.empty()) return ets::ErrReply(-1, "process not specified");
        std::string target = BaseName(procs.front());
        for (char& c : target) c = (char)tolower((unsigned char)c);
        bool found = false;
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if (snap != INVALID_HANDLE_VALUE) {
            PROCESSENTRY32W pe = {};
            pe.dwSize = sizeof(pe);
            if (Process32FirstW(snap, &pe)) {
                do {
                    std::string name = ets::WideToUtf8(pe.szExeFile);
                    for (char& c : name) c = (char)tolower((unsigned char)c);
                    if (name == target || name == target + ".exe") {
                        found = true;
                        break;
                    }
                } while (Process32NextW(snap, &pe));
            }
            CloseHandle(snap);
        }
        json r;
        r["result"] = found;
        return r.dump();
    }

    // cmd / gettoken / initActAuth / ... are not implemented
    LogWarn("shellhelper: not implemented action: " + action);
    return ets::NotImplementedReply();
}

} // namespace

extern "C" __declspec(dllexport) void PlnInitiliaze(PlnHost* host) {
    ets::g_host = host;
    if (!host) return;
    if (host->AppDir) g_appDir = host->AppDir;
    if (host->DataDir) g_dataDir = host->DataDir;
    if (host->CacheDir) g_cacheDir = host->CacheDir;
    if (host->HomeUrl) g_homeUrl = host->HomeUrl;
    Log("shellhelper: initialized");
}

extern "C" __declspec(dllexport) void PlnSetParam(const char* key, void* fn) {
    if (!key) return;
    const std::string k(key);
    if (k == "LOG") g_log = reinterpret_cast<PLN_LOG>(fn);
    else if (k == "WLOG") g_wlog = reinterpret_cast<PLN_LOG>(fn);
}

extern "C" __declspec(dllexport) void PlnOnProcessMessage(const char* action, const char* argsJson,
                                                          PLN_CALLBACK cb, const char* uid) {
    std::string out;
    try {
        ets::json args = ets::json::object();
        const char* raw = argsJson ? argsJson : "";
        if (*raw) {
            auto parsed = ets::json::parse(raw);
            if (parsed.is_object()) args = std::move(parsed);
        }
        out = Handle(action ? action : "", args);
    } catch (const std::exception& e) {
        out = ets::ErrReply(-1, e.what());
    } catch (...) {
        out = ets::ErrReply(-1, "unknown error");
    }
    if (cb) cb(uid ? uid : "", out.c_str());
}

extern "C" __declspec(dllexport) void PlnUnInitialize(void) {
    g_log = nullptr;
    g_wlog = nullptr;
    ets::g_host = nullptr;
}
