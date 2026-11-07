#include "common.h"
#include <windows.h>
#include <bcrypt.h>
#include <objbase.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <vector>
#include <random>

#pragma comment(lib, "bcrypt.lib")
#pragma comment(lib, "ole32.lib")

namespace ets {

PlnHost* g_host = nullptr;

std::string WideToUtf8(const std::wstring& w) {
    if (w.empty()) return {};
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string s(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &s[0], n, nullptr, nullptr);
    return s;
}

std::wstring Utf8ToWide(const std::string& s) {
    if (s.empty()) return {};
    int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
    std::wstring w(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), &w[0], n);
    return w;
}

static const char* kB64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string Base64Encode(const void* data, size_t len) {
    const unsigned char* p = (const unsigned char*)data;
    std::string out;
    out.reserve(((len + 2) / 3) * 4);
    for (size_t i = 0; i < len; i += 3) {
        unsigned int v = p[i] << 16;
        if (i + 1 < len) v |= p[i + 1] << 8;
        if (i + 2 < len) v |= p[i + 2];
        out.push_back(kB64[(v >> 18) & 63]);
        out.push_back(kB64[(v >> 12) & 63]);
        out.push_back(i + 1 < len ? kB64[(v >> 6) & 63] : '=');
        out.push_back(i + 2 < len ? kB64[v & 63] : '=');
    }
    return out;
}

std::string Base64Encode(const std::string& s) { return Base64Encode(s.data(), s.size()); }

std::vector<uint8_t> Base64Decode(const std::string& s) {
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T[(unsigned char)kB64[i]] = i;
    std::vector<uint8_t> out;
    int val = 0, bits = -8;
    for (unsigned char c : s) {
        if (c == '=') break;
        if (T[c] < 0) continue;
        val = (val << 6) + T[c];
        bits += 6;
        if (bits >= 0) {
            out.push_back((uint8_t)((val >> bits) & 0xFF));
            bits -= 8;
        }
    }
    return out;
}

static std::string ToHex(const uint8_t* p, size_t n) {
    static const char* h = "0123456789abcdef";
    std::string s;
    s.reserve(n * 2);
    for (size_t i = 0; i < n; i++) { s.push_back(h[p[i] >> 4]); s.push_back(h[p[i] & 15]); }
    return s;
}

static bool HashWith(const wchar_t* alg, const std::string& data, uint8_t* out, ULONG outLen) {
    BCRYPT_ALG_HANDLE hAlg = nullptr;
    BCRYPT_HASH_HANDLE hHash = nullptr;
    if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&hAlg, alg, nullptr, 0))) return false;
    bool ok = false;
    if (BCRYPT_SUCCESS(BCryptCreateHash(hAlg, &hHash, nullptr, 0, nullptr, 0, 0))) {
        if (BCRYPT_SUCCESS(BCryptHashData(hHash, (PUCHAR)data.data(), (ULONG)data.size(), 0)))
            ok = BCRYPT_SUCCESS(BCryptFinishHash(hHash, out, outLen, 0));
        BCryptDestroyHash(hHash);
    }
    BCryptCloseAlgorithmProvider(hAlg, 0);
    return ok;
}

std::string Md5Hex(const std::string& data) {
    uint8_t d[16];
    if (!HashWith(BCRYPT_MD5_ALGORITHM, data, d, 16)) return "";
    return ToHex(d, 16);
}

std::string Sha1Hex(const std::string& data) {
    uint8_t d[20];
    if (!HashWith(BCRYPT_SHA1_ALGORITHM, data, d, 20)) return "";
    return ToHex(d, 20);
}

static bool AesEcbCrypt(const std::string& key16, const std::vector<uint8_t>& in, std::vector<uint8_t>& out, bool encrypt) {
    BCRYPT_ALG_HANDLE hAlg = nullptr;
    BCRYPT_KEY_HANDLE hKey = nullptr;
    bool ok = false;
    if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_AES_ALGORITHM, nullptr, 0))) return false;
    if (BCRYPT_SUCCESS(BCryptSetProperty(hAlg, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_ECB,
                                        sizeof(BCRYPT_CHAIN_MODE_ECB), 0))) {
        std::string k = key16;
        if (k.size() != 16) k.resize(16, 0);
        if (BCRYPT_SUCCESS(BCryptGenerateSymmetricKey(hAlg, &hKey, nullptr, 0, (PUCHAR)k.data(), (ULONG)k.size(), 0))) {
            out.resize(in.size());
            ULONG done = 0;
            NTSTATUS st = encrypt
                ? BCryptEncrypt(hKey, (PUCHAR)in.data(), (ULONG)in.size(), nullptr, nullptr, 0, out.data(), (ULONG)out.size(), &done, 0)
                : BCryptDecrypt(hKey, (PUCHAR)in.data(), (ULONG)in.size(), nullptr, nullptr, 0, out.data(), (ULONG)out.size(), &done, 0);
            if (BCRYPT_SUCCESS(st)) { out.resize(done); ok = true; }
            BCryptDestroyKey(hKey);
        }
    }
    BCryptCloseAlgorithmProvider(hAlg, 0);
    return ok;
}

std::string AesEcbEncryptB64(const std::string& plainUtf8, const std::string& key16) {
    std::vector<uint8_t> in(plainUtf8.begin(), plainUtf8.end());
    size_t pad = 16 - (in.size() % 16);
    in.insert(in.end(), pad, (uint8_t)pad); // PKCS7
    std::vector<uint8_t> out;
    if (!AesEcbCrypt(key16, in, out, true)) return "";
    return Base64Encode(out.data(), out.size());
}

std::string AesEcbDecryptB64(const std::string& b64, const std::string& key16) {
    auto ct = Base64Decode(b64);
    if (ct.empty() || ct.size() % 16) return "";
    std::vector<uint8_t> out;
    if (!AesEcbCrypt(key16, ct, out, false)) return "";
    if (!out.empty()) {
        uint8_t pad = out.back();
        if (pad > 0 && pad <= 16 && pad <= out.size()) out.resize(out.size() - pad);
    }
    return std::string(out.begin(), out.end());
}

bool ReadFileBytes(const std::string& pathUtf8, std::vector<uint8_t>& out) {
    std::ifstream f(std::filesystem::path(Utf8ToWide(pathUtf8)), std::ios::binary);
    if (!f) return false;
    out.assign(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
    return true;
}

bool WriteFileBytes(const std::string& pathUtf8, const void* data, size_t len) {
    std::filesystem::path p(Utf8ToWide(pathUtf8));
    std::error_code ec;
    std::filesystem::create_directories(p.parent_path(), ec);
    std::ofstream f(p, std::ios::binary);
    if (!f) return false;
    f.write((const char*)data, (std::streamsize)len);
    return (bool)f;
}

bool FileExists(const std::string& pathUtf8) {
    std::error_code ec;
    return std::filesystem::exists(std::filesystem::path(Utf8ToWide(pathUtf8)), ec);
}

bool EnsureDir(const std::string& pathUtf8) {
    std::error_code ec;
    std::filesystem::create_directories(std::filesystem::path(Utf8ToWide(pathUtf8)), ec);
    return !ec;
}

std::string GetModuleDir() {
    HMODULE h = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCWSTR)&GetModuleDir, &h);
    wchar_t buf[MAX_PATH * 2] = {};
    GetModuleFileNameW(h, buf, MAX_PATH * 2);
    std::filesystem::path p(buf);
    return WideToUtf8(p.parent_path().wstring());
}

std::string JoinPath(const std::string& a, const std::string& b) {
    std::filesystem::path p(std::filesystem::path(Utf8ToWide(a)) / std::filesystem::path(Utf8ToWide(b)));
    return WideToUtf8(p.wstring());
}

std::string Guid() {
    GUID g{};
    CoCreateGuid(&g);
    wchar_t buf[64] = {};
    StringFromGUID2(g, buf, 64);
    std::wstring s(buf);
    // strip braces
    if (!s.empty() && s.front() == L'{') s.erase(s.begin());
    if (!s.empty() && s.back() == L'}') s.pop_back();
    return WideToUtf8(s);
}

void HostLog(int level, const std::string& msg) {
    if (g_host && g_host->Log) {
        if (level >= 1 && g_host->WLog) g_host->WLog(level, msg.c_str());
        else g_host->Log(level, msg.c_str());
    }
}

std::string OkReply(const std::string& extraJson) {
    if (extraJson.empty()) return "{\"code\":0}";
    try {
        auto j = json::parse(extraJson);
        j["code"] = 0;
        return j.dump();
    } catch (...) {
        return "{\"code\":0}";
    }
}

std::string ErrReply(int code, const std::string& msg) {
    json j;
    j["code"] = code;
    j["msg"] = msg;
    return j.dump();
}

std::string NotImplementedReply() {
    json j;
    j["code"] = -2;
    j["msg"] = "not implemented";
    return j.dump();
}

} // namespace ets
