// plugin filehelper — filesystem helpers (UTF-8 paths, std::filesystem)
// ABI: shared/stic_plugin.h ; contract: CONTRACT.md §6
#include "common.h"

#include <windows.h>

#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>
#include <vector>

namespace fs = std::filesystem;

namespace {

PLN_LOG g_log = nullptr;
PLN_LOG g_wlog = nullptr;

std::string g_appDir;
std::string g_dataDir;

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

fs::path PathOf(const std::string& utf8) { return fs::path(ets::Utf8ToWide(utf8)); }

bool ReadAll(const std::string& path, std::vector<uint8_t>& out) {
    return ets::ReadFileBytes(path, out);
}

std::string Handle(const std::string& action, const ets::json& args) {
    using ets::json;

    if (action == "readfile") {
        const std::string path = ArgStr(args, "filePath");
        if (path.empty()) return ets::ErrReply(-1, "filePath is required");
        std::vector<uint8_t> bytes;
        if (!ReadAll(path, bytes)) return ets::ErrReply(-1, "read file failed: " + path);
        json r;
        r["content"] = std::string(bytes.begin(), bytes.end());
        r["code"] = 0;
        return r.dump();
    }

    if (action == "readbinaryfile" || action == "getbase64") {
        const std::string path = ArgStr(args, "filePath");
        if (path.empty()) return ets::ErrReply(-1, "filePath is required");
        std::vector<uint8_t> bytes;
        if (!ReadAll(path, bytes)) return ets::ErrReply(-1, "read file failed: " + path);
        json r;
        r["base64"] = ets::Base64Encode(bytes.data(), bytes.size());
        r["code"] = 0;
        return r.dump();
    }

    if (action == "writefile") {
        const std::string path = ArgStr(args, "filePath");
        const std::string content = ArgStr(args, "content");
        if (path.empty()) return ets::ErrReply(-1, "filePath is required");
        if (!ets::WriteFileBytes(path, content.data(), content.size()))
            return ets::ErrReply(-1, "write file failed: " + path);
        json r;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "writefilewithbinary") {
        const std::string path = ArgStr(args, "filePath");
        const std::string b64 = ArgStr(args, "base64");
        if (path.empty()) return ets::ErrReply(-1, "filePath is required");
        const std::vector<uint8_t> bytes = ets::Base64Decode(b64);
        if (!ets::WriteFileBytes(path, bytes.data(), bytes.size()))
            return ets::ErrReply(-1, "write file failed: " + path);
        json r;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "existfileorfolder") {
        const std::string path = ArgStr(args, "filePath");
        json r;
        std::error_code ec;
        const fs::path p = PathOf(path);
        bool exists = !path.empty() && fs::exists(p, ec);
        r["result"] = exists;
        uint64_t size = 0;
        if (exists && fs::is_regular_file(p, ec)) {
            std::error_code ec2;
            auto n = fs::file_size(p, ec2);
            if (!ec2) size = (uint64_t)n;
        }
        r["size"] = size;
        return r.dump();
    }

    if (action == "deletefileordirectory") {
        const std::string path = ArgStr(args, "filePath");
        if (path.empty()) return ets::ErrReply(-1, "filePath is required");
        std::error_code ec;
        fs::remove_all(PathOf(path), ec); // absent path is treated as success
        if (ec) return ets::ErrReply(-1, "delete failed: " + ec.message());
        json r;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "createfolder") {
        const std::string path = ArgStr(args, "filePath");
        if (path.empty()) return ets::ErrReply(-1, "filePath is required");
        std::error_code ec;
        fs::create_directories(PathOf(path), ec);
        if (ec) return ets::ErrReply(-1, "create folder failed: " + ec.message());
        json r;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "copyfileordirectory") {
        const std::string src = ArgStr(args, "src", ArgStr(args, "filePath"));
        const std::string dst = ArgStr(args, "dst", ArgStr(args, "toPath"));
        if (src.empty() || dst.empty()) return ets::ErrReply(-1, "src/dst are required");
        std::error_code ec;
        const fs::path s = PathOf(src);
        const fs::path d = PathOf(dst);
        if (!fs::exists(s, ec)) return ets::ErrReply(-1, "source not found: " + src);
        if (fs::is_directory(s, ec)) {
            fs::create_directories(d, ec);
            fs::copy(s, d, fs::copy_options::recursive | fs::copy_options::overwrite_existing, ec);
        } else {
            if (d.has_parent_path()) fs::create_directories(d.parent_path(), ec);
            fs::copy_file(s, d, fs::copy_options::overwrite_existing, ec);
        }
        if (ec) return ets::ErrReply(-1, "copy failed: " + ec.message());
        json r;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "removefiletootherpath") {
        const std::string src = ArgStr(args, "src", ArgStr(args, "filePath"));
        const std::string dst = ArgStr(args, "dst", ArgStr(args, "toPath"));
        if (src.empty() || dst.empty()) return ets::ErrReply(-1, "src/dst are required");
        std::error_code ec;
        const fs::path s = PathOf(src);
        const fs::path d = PathOf(dst);
        if (!fs::exists(s, ec)) return ets::ErrReply(-1, "source not found: " + src);
        if (d.has_parent_path()) fs::create_directories(d.parent_path(), ec);
        fs::rename(s, d, ec);
        if (ec) {
            ec.clear();
            fs::copy(s, d, fs::copy_options::recursive | fs::copy_options::overwrite_existing, ec);
            if (ec) return ets::ErrReply(-1, "move failed: " + ec.message());
            std::error_code ec3;
            fs::remove_all(s, ec3);
        }
        json r;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "getmd5") {
        const std::string path = ArgStr(args, "filePath");
        if (path.empty()) return ets::ErrReply(-1, "filePath is required");
        std::vector<uint8_t> bytes;
        if (!ReadAll(path, bytes)) return ets::ErrReply(-1, "read file failed: " + path);
        json r;
        r["md5"] = ets::Md5Hex(std::string(bytes.begin(), bytes.end()));
        r["code"] = 0;
        return r.dump();
    }

    if (action == "getfoledersize") {
        const std::string path = ArgStr(args, "filePath");
        std::error_code ec;
        const fs::path p = PathOf(path);
        json r;
        if (path.empty() || !fs::exists(p, ec)) {
            r["errorCode"] = -1;
            r["errorMsg"] = "path not found";
            r["size"] = 0;
            return r.dump();
        }
        uint64_t total = 0;
        if (fs::is_regular_file(p, ec)) {
            auto n = fs::file_size(p, ec);
            if (!ec) total = (uint64_t)n;
        } else {
            for (fs::recursive_directory_iterator it(p, fs::directory_options::skip_permission_denied, ec), end;
                 it != end; it.increment(ec)) {
                if (ec) {
                    ec.clear();
                    continue;
                }
                std::error_code ec2;
                if (it->is_regular_file(ec2)) {
                    auto n = it->file_size(ec2);
                    if (!ec2) total += (uint64_t)n;
                }
            }
        }
        r["errorCode"] = 0;
        r["errorMsg"] = "get dir size ok";
        r["size"] = total;
        return r.dump();
    }

    LogWarn("filehelper: unknown action: " + action);
    return ets::NotImplementedReply();
}

} // namespace

extern "C" __declspec(dllexport) void PlnInitiliaze(PlnHost* host) {
    ets::g_host = host;
    if (!host) return;
    if (host->AppDir) g_appDir = host->AppDir;
    if (host->DataDir) g_dataDir = host->DataDir;
    Log("filehelper: initialized");
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
