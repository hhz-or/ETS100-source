#pragma once
// Shared helpers for shell + plugins (UTF-8, JSON, crypto, files).
#include <string>
#include <vector>
#include <cstdint>
#include "json.hpp"
#include "stic_plugin.h"

namespace ets {

using json = nlohmann::json;

// --- text ---
std::string WideToUtf8(const std::wstring& w);
std::wstring Utf8ToWide(const std::string& s);

// --- encoding ---
std::string Base64Encode(const void* data, size_t len);
std::string Base64Encode(const std::string& s);
std::vector<uint8_t> Base64Decode(const std::string& s);

// --- crypto (BCrypt) ---
std::string Md5Hex(const std::string& data);
std::string Sha1Hex(const std::string& data);
std::string AesEcbEncryptB64(const std::string& plainUtf8, const std::string& key16);
std::string AesEcbDecryptB64(const std::string& b64, const std::string& key16);

// --- files ---
bool ReadFileBytes(const std::string& pathUtf8, std::vector<uint8_t>& out);
bool WriteFileBytes(const std::string& pathUtf8, const void* data, size_t len);
bool FileExists(const std::string& pathUtf8);
bool EnsureDir(const std::string& pathUtf8);
std::string GetModuleDir();
std::string JoinPath(const std::string& a, const std::string& b);
std::string Guid();

// --- plugin host glue ---
extern PlnHost* g_host;
void HostLog(int level, const std::string& msg);
inline void LogInfo(const std::string& m) { HostLog(0, m); }
inline void LogWarn(const std::string& m) { HostLog(1, m); }
inline void LogError(const std::string& m) { HostLog(2, m); }

// reply helper: always JSON
std::string OkReply(const std::string& extraJson = "");
std::string ErrReply(int code, const std::string& msg);
std::string NotImplementedReply();

} // namespace ets
