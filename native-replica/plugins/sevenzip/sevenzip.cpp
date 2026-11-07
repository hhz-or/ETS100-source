// plugin sevenzip — ZIP extraction (miniz + ZipCrypto password recovery)
// ABI: shared/stic_plugin.h ; contract: CONTRACT.md §6
#include "common.h"

#include <windows.h>

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

#include "miniz.h"

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

// ---- little-endian readers --------------------------------------------------

uint16_t Le16(const uint8_t* p) { return (uint16_t)(p[0] | ((uint16_t)p[1] << 8)); }
uint32_t Le32(const uint8_t* p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

// ---- ZipCrypto (traditional PKWARE encryption) ------------------------------

const uint32_t* CrcTable() {
    static uint32_t table[256];
    static std::once_flag once;
    std::call_once(once, [] {
        for (uint32_t i = 0; i < 256; ++i) {
            uint32_t c = i;
            for (int k = 0; k < 8; ++k) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
            table[i] = c;
        }
    });
    return table;
}

uint32_t CrcByte(uint32_t crc, uint8_t b) { return CrcTable()[(crc ^ b) & 0xFF] ^ (crc >> 8); }

struct ZipCryptoState {
    uint32_t k0 = 0x12345678u;
    uint32_t k1 = 0x23456789u;
    uint32_t k2 = 0x34567890u;

    void Update(uint8_t c) {
        k0 = CrcByte(k0, c);
        k1 = (k1 + (k0 & 0xFF)) * 134775813u + 1u;
        k2 = CrcByte(k2, (uint8_t)(k1 >> 24));
    }
    uint8_t StreamByte() const {
        const uint32_t t = (k2 | 2u);
        return (uint8_t)((t * (t ^ 1u)) >> 8);
    }
};

bool ZipCryptoDecrypt(const uint8_t* data, size_t n, uint16_t flags, uint32_t crc, uint16_t dosTime,
                      const std::string& password, std::vector<uint8_t>& out) {
    if (n < 12) return false;
    ZipCryptoState zc;
    for (unsigned char c : password) zc.Update(c);

    uint8_t header[12] = {};
    for (int i = 0; i < 12; ++i) {
        header[i] = (uint8_t)(data[i] ^ zc.StreamByte());
        zc.Update(header[i]);
    }
    // With a data descriptor (bit 3) the check byte is the high byte of the DOS time.
    const uint8_t check = (flags & 0x0008) ? (uint8_t)(dosTime >> 8) : (uint8_t)(crc >> 24);
    if (header[11] != check) return false;

    out.resize(n - 12);
    for (size_t i = 12; i < n; ++i) {
        const uint8_t p = (uint8_t)(data[i] ^ zc.StreamByte());
        zc.Update(p);
        out[i - 12] = p;
    }
    return true;
}

// ---- password recovery from the 336-byte trailer block ----------------------
// docs/06_data.md §4.2: [0:8] company, [8:16] version, [16:144] pwd, [144:176]
// productid, [176:304] keySerialNum, [304:336] thisAnswer.
// password = upper(md5(pwd)) + upper(md5(upper(md5(pwd))))  (64 hex chars)

std::string TrimField(const uint8_t* p, size_t n) {
    size_t len = 0;
    while (len < n && p[len] != 0) ++len;
    std::string s(reinterpret_cast<const char*>(p), len);
    while (!s.empty() && (unsigned char)s.back() <= ' ') s.pop_back();
    size_t b = 0;
    while (b < s.size() && (unsigned char)s[b] <= ' ') ++b;
    return s.substr(b);
}

std::string UpperAscii(std::string s) {
    for (char& c : s) c = (char)std::toupper((unsigned char)c);
    return s;
}

std::vector<std::string> CandidatePasswords(const std::vector<uint8_t>& bytes) {
    std::vector<std::string> out;
    auto add = [&out](const std::string& p) {
        if (!p.empty() && std::find(out.begin(), out.end(), p) == out.end()) out.push_back(p);
    };

    if (bytes.size() >= 336) {
        const uint8_t* t = bytes.data() + bytes.size() - 336;
        const std::string company = TrimField(t, 8);
        const std::string pwd = TrimField(t + 16, 128);
        const std::string product = TrimField(t + 144, 32);
        if (company == "MSTCHINA" && product == "EPLAT" && !pwd.empty()) {
            const std::string n = UpperAscii(ets::Md5Hex(pwd));
            add(n + UpperAscii(ets::Md5Hex(n)));
        }
    }
    // Legacy/short trailer variant (docs §4.2, getPasswordFromResourcePackage):
    // last 40 bytes, skip the first 8 characters, then the same double-MD5 form.
    if (bytes.size() >= 40) {
        const char* tail = reinterpret_cast<const char*>(bytes.data() + bytes.size() - 40);
        std::string text;
        for (int i = 0; i < 40; ++i) {
            const unsigned char c = (unsigned char)tail[i];
            if (c >= 0x20 && c < 0x7F) text.push_back((char)c);
        }
        if (text.size() > 8) {
            const std::string n = UpperAscii(ets::Md5Hex(text.substr(8)));
            add(n + UpperAscii(ets::Md5Hex(n)));
        }
    }
    return out;
}

// ---- inflate / write helpers ------------------------------------------------

bool DecodeEntry(const std::vector<uint8_t>& compressed, uint16_t method, std::vector<uint8_t>& out,
                 std::string& err) {
    if (method == 0) { // stored
        out = compressed;
        return true;
    }
    if (method != 8) { // only store + deflate are supported
        err = "unsupported compression method " + std::to_string((unsigned)method);
        return false;
    }
    size_t outLen = 0;
    void* p = tinfl_decompress_mem_to_heap(compressed.data(), compressed.size(), &outLen, 0);
    if (!p) {
        err = "inflate failed";
        return false;
    }
    const uint8_t* src = reinterpret_cast<const uint8_t*>(p);
    out.assign(src, src + outLen);
    mz_free(p);
    return true;
}

bool WriteBytes(const fs::path& target, const uint8_t* data, size_t n) {
    std::error_code ec;
    if (target.has_parent_path()) fs::create_directories(target.parent_path(), ec);
    std::ofstream f(target, std::ios::binary | std::ios::trunc);
    if (!f) return false;
    if (n) f.write(reinterpret_cast<const char*>(data), (std::streamsize)n);
    return (bool)f;
}

struct ExtractCtx {
    std::ofstream* file;
};

size_t ExtractWriteCb(void* opaque, mz_uint64 ofs, const void* buf, size_t n) {
    auto* ctx = static_cast<ExtractCtx*>(opaque);
    ctx->file->seekp((std::streamoff)ofs, std::ios::beg);
    ctx->file->write(reinterpret_cast<const char*>(buf), (std::streamsize)n);
    return ctx->file->good() ? n : 0;
}

// Reject absolute paths, drive letters and ".." components (zip-slip guard).
bool SafeRelativeName(const std::string& raw, std::string& normalized) {
    normalized.clear();
    for (char c : raw) {
        if (c == '\\') normalized.push_back('/');
        else if (c == '\0') return false;
        else normalized.push_back(c);
    }
    if (normalized.empty()) return false;
    if (normalized[0] == '/') return false;
    if (normalized.size() >= 2 && normalized[1] == ':') return false;
    size_t i = 0;
    while (i <= normalized.size()) {
        size_t j = normalized.find('/', i);
        const std::string comp =
            normalized.substr(i, j == std::string::npos ? std::string::npos : j - i);
        if (comp == "..") return false;
        if (j == std::string::npos) break;
        i = j + 1;
    }
    return true;
}

struct ReaderGuard {
    mz_zip_archive* zip;
    ~ReaderGuard() { mz_zip_reader_end(zip); }
};

// Extracts one encrypted entry using a recovered ZipCrypto password.
bool ExtractEncryptedEntry(mz_zip_archive& zip, const mz_zip_archive_file_stat& st,
                           const std::vector<uint8_t>& bytes, const std::vector<std::string>& passwords,
                           const fs::path& target, std::string& err) {
    const uint64_t lho = st.m_local_header_ofs;
    if (lho + 30 > bytes.size()) {
        err = "corrupt local header offset";
        return false;
    }
    const uint8_t* lh = bytes.data() + lho;
    if (Le32(lh) != 0x04034b50u) {
        err = "bad local header signature";
        return false;
    }
    const uint16_t flags = Le16(lh + 6);
    const uint16_t method = Le16(lh + 8);
    const uint16_t dosTime = Le16(lh + 10);
    const uint16_t nameLen = Le16(lh + 26);
    const uint16_t extraLen = Le16(lh + 28);
    const uint64_t dataOfs = lho + 30 + nameLen + extraLen;
    if (dataOfs > bytes.size() || st.m_comp_size > bytes.size() - dataOfs) {
        err = "truncated entry data";
        return false;
    }
    if (st.m_comp_size < 12) {
        err = "encrypted entry too short";
        return false;
    }
    const uint8_t* cdata = bytes.data() + dataOfs;
    const size_t csize = (size_t)st.m_comp_size;

    std::vector<uint8_t> compressed, plain;
    for (const std::string& pwd : passwords) {
        compressed.clear();
        plain.clear();
        if (!ZipCryptoDecrypt(cdata, csize, flags, st.m_crc32, dosTime, pwd, compressed)) continue;
        std::string derr;
        if (!DecodeEntry(compressed, method, plain, derr)) continue;
        const uint32_t crc = (uint32_t)mz_crc32(MZ_CRC32_INIT, plain.data(), plain.size());
        if (crc != st.m_crc32) continue; // wrong password / corrupt data
        if (!WriteBytes(target, plain.data(), plain.size())) {
            err = "cannot write output file";
            return false;
        }
        return true;
    }
    err = "cannot decrypt entry (no matching password)";
    return false;
}

std::string UnzipArchive(const std::string& zipPath, const std::string& outDir, uint64_t& fileCount) {
    using ets::json;

    std::vector<uint8_t> bytes;
    if (!ets::ReadFileBytes(zipPath, bytes)) throw std::runtime_error("cannot read zip: " + zipPath);
    if (bytes.size() < 22) throw std::runtime_error("file is not a zip archive: " + zipPath);

    mz_zip_archive zip = {};
    if (!mz_zip_reader_init_mem(&zip, bytes.data(), bytes.size(), 0))
        throw std::runtime_error("invalid or unsupported zip archive: " + zipPath);
    ReaderGuard guard{&zip};

    const mz_uint total = mz_zip_reader_get_num_files(&zip);
    std::vector<mz_zip_archive_file_stat> stats;
    stats.reserve(total);
    bool anyEncrypted = false;
    for (mz_uint i = 0; i < total; ++i) {
        mz_zip_archive_file_stat st = {};
        if (!mz_zip_reader_file_stat(&zip, i, &st)) continue;
        stats.push_back(st);
        if (st.m_is_encrypted) anyEncrypted = true;
    }

    std::vector<std::string> passwords;
    if (anyEncrypted) {
        passwords = CandidatePasswords(bytes);
        if (passwords.empty())
            throw std::runtime_error("archive is encrypted but no password trailer was found");
    }

    std::error_code ec;
    fs::create_directories(fs::path(ets::Utf8ToWide(outDir)), ec);

    fileCount = 0;
    for (const auto& st : stats) {
        std::string rel;
        if (!SafeRelativeName(st.m_filename, rel)) {
            LogWarn("sevenzip: skip unsafe path: " + std::string(st.m_filename));
            continue;
        }
        const std::string joined = ets::JoinPath(outDir, rel);
        const fs::path target(ets::Utf8ToWide(joined));

        const bool isDir = st.m_is_directory || (!rel.empty() && rel.back() == '/');
        if (isDir) {
            fs::create_directories(target, ec);
            continue;
        }
        if (target.has_parent_path()) fs::create_directories(target.parent_path(), ec);

        if (!st.m_is_encrypted) {
            std::ofstream ofs(target, std::ios::binary | std::ios::trunc);
            if (!ofs) throw std::runtime_error("cannot write output file: " + joined);
            ExtractCtx ctx{&ofs};
            if (!mz_zip_reader_extract_to_callback(&zip, st.m_file_index, &ExtractWriteCb, &ctx, 0)) {
                throw std::runtime_error(std::string("extract failed: ") + st.m_filename + " (" +
                                         mz_zip_get_error_string(mz_zip_get_last_error(&zip)) + ")");
            }
            ofs.close();
            if (!ofs) throw std::runtime_error("write failed: " + joined);
            ++fileCount;
            continue;
        }

        std::string err;
        if (!ExtractEncryptedEntry(zip, st, bytes, passwords, target, err))
            throw std::runtime_error(err + ": " + st.m_filename);
        ++fileCount;
    }

    json r;
    r["code"] = 0;
    r["files"] = fileCount;
    return r.dump();
}

std::string Handle(const std::string& action, const ets::json& args) {
    if (action == "unzip") {
        const std::string zipPath = ArgStr(args, "zipPath", ArgStr(args, "filePath"));
        const std::string outDir = ArgStr(args, "outDir", ArgStr(args, "dir"));
        if (zipPath.empty()) return ets::ErrReply(-1, "zipPath is required");
        if (outDir.empty()) return ets::ErrReply(-1, "outDir is required");
        uint64_t files = 0;
        return UnzipArchive(zipPath, outDir, files);
    }

    // zip / test are not implemented
    LogWarn("sevenzip: not implemented action: " + action);
    return ets::NotImplementedReply();
}

} // namespace

extern "C" __declspec(dllexport) void PlnInitiliaze(PlnHost* host) {
    ets::g_host = host;
    if (!host) return;
    if (host->AppDir) g_appDir = host->AppDir;
    if (host->DataDir) g_dataDir = host->DataDir;
    Log("sevenzip: initialized");
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
