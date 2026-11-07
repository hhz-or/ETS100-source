// plugin sqlitepln — SQLite database access (vendored sqlite3 amalgamation)
// ABI: shared/stic_plugin.h ; contract: CONTRACT.md §6
#include "common.h"
#include "sqlite3.h"

#include <windows.h>

#include <cstdio>
#include <filesystem>
#include <mutex>
#include <string>
#include <vector>

namespace {

PLN_LOG g_log = nullptr;
PLN_LOG g_wlog = nullptr;

std::string g_appDir;
std::string g_dataDir;

std::mutex g_mutex;
sqlite3* g_db = nullptr;
std::string g_dbPath;

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

std::string DumpJson(const ets::json& j) {
    // SQLite TEXT may contain invalid UTF-8; replace instead of throwing.
    return j.dump(-1, ' ', false, ets::json::error_handler_t::replace);
}

void CloseDbLocked() {
    if (g_db) {
        sqlite3_close_v2(g_db);
        g_db = nullptr;
    }
    g_dbPath.clear();
}

bool EnsureOpenLocked(const std::string& dbPath, std::string& err) {
    if (g_db && !dbPath.empty() && g_dbPath == dbPath) return true;
    if (g_db && dbPath.empty()) return true;
    CloseDbLocked();
    const std::string path = dbPath;
    if (path.empty()) {
        err = "dbPath is required";
        return false;
    }
    sqlite3* db = nullptr;
    // Make sure the parent directory exists (SQLite does not create it).
    try {
        const std::wstring wpath = ets::Utf8ToWide(path);
        std::filesystem::path p(wpath);
        if (p.has_parent_path()) {
            std::error_code ec;
            std::filesystem::create_directories(p.parent_path(), ec);
        }
    } catch (...) {
    }
    int rc = sqlite3_open_v2(path.c_str(), &db,
                             SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX, nullptr);
    if (rc != SQLITE_OK) {
        err = db ? sqlite3_errmsg(db) : sqlite3_errstr(rc);
        if (db) sqlite3_close_v2(db);
        return false;
    }
    sqlite3_busy_timeout(db, 5000);
    sqlite3_exec(db, "PRAGMA journal_mode=WAL;", nullptr, nullptr, nullptr); // best effort
    g_db = db;
    g_dbPath = path;
    return true;
}

bool BindOne(sqlite3_stmt* stmt, int idx, const ets::json& p, std::string& err) {
    int rc = SQLITE_OK;
    if (p.is_null()) {
        rc = sqlite3_bind_null(stmt, idx);
    } else if (p.is_boolean()) {
        rc = sqlite3_bind_int(stmt, idx, p.get<bool>() ? 1 : 0);
    } else if (p.is_number_integer()) {
        rc = sqlite3_bind_int64(stmt, idx, (sqlite3_int64)p.get<long long>());
    } else if (p.is_number_unsigned()) {
        rc = sqlite3_bind_int64(stmt, idx, (sqlite3_int64)p.get<unsigned long long>());
    } else if (p.is_number_float()) {
        rc = sqlite3_bind_double(stmt, idx, p.get<double>());
    } else if (p.is_string()) {
        const std::string& s = p.get_ref<const std::string&>();
        rc = sqlite3_bind_text(stmt, idx, s.data(), (int)s.size(), SQLITE_TRANSIENT);
    } else {
        const std::string s = DumpJson(p);
        rc = sqlite3_bind_text(stmt, idx, s.data(), (int)s.size(), SQLITE_TRANSIENT);
    }
    if (rc != SQLITE_OK) {
        err = g_db ? sqlite3_errmsg(g_db) : sqlite3_errstr(rc);
        return false;
    }
    return true;
}

bool BindParams(sqlite3_stmt* stmt, const ets::json& params, std::string& err) {
    if (params.is_array()) {
        int idx = 1;
        for (const auto& p : params) {
            if (!BindOne(stmt, idx, p, err)) return false;
            ++idx;
        }
        return true;
    }
    if (params.is_object()) {
        for (auto it = params.begin(); it != params.end(); ++it) {
            const std::string& key = it.key();
            int idx = sqlite3_bind_parameter_index(stmt, (":" + key).c_str());
            if (idx == 0) idx = sqlite3_bind_parameter_index(stmt, ("$" + key).c_str());
            if (idx == 0) idx = sqlite3_bind_parameter_index(stmt, ("@" + key).c_str());
            if (idx == 0) continue; // unknown name: ignore rather than fail
            if (!BindOne(stmt, idx, it.value(), err)) return false;
        }
    }
    return true;
}

ets::json ColumnValue(sqlite3_stmt* stmt, int col) {
    using ets::json;
    switch (sqlite3_column_type(stmt, col)) {
        case SQLITE_INTEGER:
            return json((long long)sqlite3_column_int64(stmt, col));
        case SQLITE_FLOAT:
            return json((double)sqlite3_column_double(stmt, col));
        case SQLITE_TEXT: {
            const unsigned char* txt = sqlite3_column_text(stmt, col);
            int n = sqlite3_column_bytes(stmt, col);
            return json(std::string(reinterpret_cast<const char*>(txt), (size_t)(n > 0 ? n : 0)));
        }
        case SQLITE_BLOB: {
            const void* blob = sqlite3_column_blob(stmt, col);
            int n = sqlite3_column_bytes(stmt, col);
            return json(ets::Base64Encode(blob, (size_t)(n > 0 ? n : 0)));
        }
        default:
            return json(nullptr);
    }
}

std::string Handle(const std::string& action, const ets::json& args) {
    using ets::json;

    if (action == "connect") {
        const std::string dbPath = ArgStr(args, "dbPath", ArgStr(args, "path"));
        std::lock_guard<std::mutex> lk(g_mutex);
        std::string err;
        if (!EnsureOpenLocked(dbPath, err)) return ets::ErrReply(-1, err);
        json r;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "disconnect") {
        std::lock_guard<std::mutex> lk(g_mutex);
        CloseDbLocked();
        json r;
        r["code"] = 0;
        return r.dump();
    }

    if (action == "execQuery" || action == "execquery") {
        std::string dbPath = ArgStr(args, "dbPath", ArgStr(args, "path"));
        const std::string sql = ArgStr(args, "sql");
        if (sql.empty()) return ets::ErrReply(-1, "sql is required");
        json params = json::array();
        if (args.contains("params")) params = args["params"];

        std::lock_guard<std::mutex> lk(g_mutex);
        std::string err;
        if (dbPath.empty()) dbPath = g_dbPath;
        if (!EnsureOpenLocked(dbPath, err)) return ets::ErrReply(-1, err);

        sqlite3_stmt* stmt = nullptr;
        if (sqlite3_prepare_v2(g_db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
            const std::string msg = g_db ? sqlite3_errmsg(g_db) : "prepare failed";
            if (stmt) sqlite3_finalize(stmt);
            return ets::ErrReply(-1, msg);
        }
        if (!BindParams(stmt, params, err)) {
            sqlite3_finalize(stmt);
            return ets::ErrReply(-1, err);
        }

        json rows = json::array();
        int rc = SQLITE_OK;
        while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
            json row = json::object();
            const int cols = sqlite3_column_count(stmt);
            for (int c = 0; c < cols; ++c) {
                const char* name = sqlite3_column_name(stmt, c);
                row[name ? name : ("col" + std::to_string(c))] = ColumnValue(stmt, c);
            }
            rows.push_back(std::move(row));
        }
        if (rc != SQLITE_DONE) {
            const std::string msg = g_db ? sqlite3_errmsg(g_db) : "step failed";
            sqlite3_finalize(stmt);
            return ets::ErrReply(-1, msg);
        }
        sqlite3_finalize(stmt);

        json r;
        r["code"] = 0;
        r["rows"] = std::move(rows);
        return DumpJson(r);
    }

    if (action == "execDML" || action == "execdml") {
        std::string dbPath = ArgStr(args, "dbPath", ArgStr(args, "path"));
        const std::string sql = ArgStr(args, "sql");
        if (sql.empty()) return ets::ErrReply(-1, "sql is required");
        json params = json::array();
        if (args.contains("params")) params = args["params"];

        std::lock_guard<std::mutex> lk(g_mutex);
        std::string err;
        if (dbPath.empty()) dbPath = g_dbPath;
        if (!EnsureOpenLocked(dbPath, err)) return ets::ErrReply(-1, err);

        sqlite3_stmt* stmt = nullptr;
        if (sqlite3_prepare_v2(g_db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
            const std::string msg = g_db ? sqlite3_errmsg(g_db) : "prepare failed";
            if (stmt) sqlite3_finalize(stmt);
            return ets::ErrReply(-1, msg);
        }
        if (!BindParams(stmt, params, err)) {
            sqlite3_finalize(stmt);
            return ets::ErrReply(-1, err);
        }
        int rc = SQLITE_OK;
        while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
            // skip rows for DML (e.g. RETURNING clause); DML callers care about changes
        }
        if (rc != SQLITE_DONE) {
            const std::string msg = g_db ? sqlite3_errmsg(g_db) : "step failed";
            sqlite3_finalize(stmt);
            return ets::ErrReply(-1, msg);
        }
        sqlite3_finalize(stmt);

        json r;
        r["code"] = 0;
        r["changes"] = (long long)sqlite3_changes(g_db);
        r["lastInsertRowid"] = (long long)sqlite3_last_insert_rowid(g_db);
        return r.dump();
    }

    LogWarn("sqlitepln: unknown action: " + action);
    return ets::NotImplementedReply();
}

} // namespace

extern "C" __declspec(dllexport) void PlnInitiliaze(PlnHost* host) {
    ets::g_host = host;
    if (!host) return;
    if (host->AppDir) g_appDir = host->AppDir;
    if (host->DataDir) g_dataDir = host->DataDir;
    Log("sqlitepln: initialized");
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
    {
        std::lock_guard<std::mutex> lk(g_mutex);
        CloseDbLocked();
    }
    g_log = nullptr;
    g_wlog = nullptr;
    ets::g_host = nullptr;
}
