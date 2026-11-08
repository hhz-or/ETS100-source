// soundhelper.pln — 参考实现：speex 编码（录音链路的核心编码器）
// 动作：encode_speex  参数 {"pcm":"<base64 s16le>", "quality":10, "bitrate":84800}
//       返回 {"spx":"<base64>", "frames":N, "frameBytes":106, "chunkBytes":212, "sampleRate":16000}
// 说明：抓包显示 16kHz mono speex，每帧 106B（quality10 + CBR 84800），每 2 帧一个 212B WS 块。
#include "common.h"
#include <vector>
#include <cstring>
#include "speex/speex.h"

using ets::json;

extern "C" {
__declspec(dllexport) void PlnInitiliaze(PlnHost* host);
__declspec(dllexport) void PlnSetParam(const char* key, void* fn);
__declspec(dllexport) void PlnOnProcessMessage(const char* action, const char* argsJson, PLN_CALLBACK cb, const char* uid);
__declspec(dllexport) void PlnUnInitialize(void);
}

namespace {

std::vector<uint8_t> from_b64(const std::string& s) { return ets::Base64Decode(s); }
std::string to_b64(const std::vector<uint8_t>& v) { return ets::Base64Encode(v.data(), v.size()); }

std::string encode(const std::vector<uint8_t>& pcmBytes, int quality, int bitrate) {
    if (pcmBytes.size() < 2) return ets::ErrReply(-1, "empty pcm");
    void* enc = speex_encoder_init(&speex_wb_mode);
    if (!enc) return ets::ErrReply(-1, "speex_encoder_init failed");
    int q = quality, vbr = 0, rate = 16000, br = bitrate, frameSize = 0;
    speex_encoder_ctl(enc, SPEEX_SET_QUALITY, &q);
    speex_encoder_ctl(enc, SPEEX_SET_VBR, &vbr);
    speex_encoder_ctl(enc, SPEEX_SET_BITRATE, &br);
    speex_encoder_ctl(enc, SPEEX_SET_SAMPLING_RATE, &rate);
    speex_encoder_ctl(enc, SPEEX_GET_FRAME_SIZE, &frameSize);
    if (frameSize <= 0) { speex_encoder_destroy(enc); return ets::ErrReply(-1, "bad frame size"); }

    SpeexBits bits;
    speex_bits_init(&bits);
    std::vector<uint8_t> stream;
    std::vector<int> frameSizes;
    const int16_t* pcm = reinterpret_cast<const int16_t*>(pcmBytes.data());
    size_t samples = pcmBytes.size() / 2;
    size_t frames = 0;
    for (size_t off = 0; off + (size_t)frameSize <= samples; off += frameSize) {
        speex_bits_reset(&bits);
        // 注意：不需要拷贝，speex_encode_int 只读
        speex_encode_int(enc, (short*)&pcm[off], &bits);
        int n = speex_bits_nbytes(&bits);
        std::vector<uint8_t> frame(n);
        speex_bits_write(&bits, (char*)frame.data(), n);
        stream.insert(stream.end(), frame.begin(), frame.end());
        frameSizes.push_back(n);
        frames++;
    }
    speex_bits_destroy(&bits);
    speex_encoder_destroy(enc);

    int maxFrame = 0, minFrame = 1 << 30;
    for (int n : frameSizes) { if (n > maxFrame) maxFrame = n; if (n < minFrame) minFrame = n; }
    json j;
    j["spx"] = to_b64(stream);
    j["frames"] = frames;
    j["frameBytes"] = frameSizes.empty() ? 0 : frameSizes[0];
    j["minFrameBytes"] = frameSizes.empty() ? 0 : minFrame;
    j["maxFrameBytes"] = frameSizes.empty() ? 0 : maxFrame;
    j["chunkBytes"] = 212;
    j["sampleRate"] = 16000;
    j["frameSize"] = frameSize;
    j["quality"] = q;
    j["bitrate"] = br;
    return j.dump();
}

} // namespace

extern "C" __declspec(dllexport) void PlnInitiliaze(PlnHost* host) {
    ets::g_host = host;
    ets::HostLog(0, "soundhelper: init (speex encoder)");
}

extern "C" __declspec(dllexport) void PlnSetParam(const char* key, void* fn) {
    (void)key; (void)fn;
}

extern "C" __declspec(dllexport) void PlnOnProcessMessage(const char* action, const char* argsJson, PLN_CALLBACK cb, const char* uid) {
    std::string out;
    try {
        json args = (argsJson && *argsJson) ? json::parse(argsJson) : json::object();
        std::string act = action ? action : "";
        if (act == "encode_speex") {
            std::string pcmB64 = args.value("pcm", std::string());
            if (pcmB64.empty()) {
                out = ets::ErrReply(-1, "missing pcm(base64)");
            } else {
                int q = args.value("quality", 10);
                int br = args.value("bitrate", 84800);
                out = encode(from_b64(pcmB64), q, br);
            }
        } else if (act == "info") {
            json j; j["code"] = 0; j["codec"] = "speex"; j["sampleRate"] = 16000; j["chunkBytes"] = 212;
            out = j.dump();
        } else {
            out = ets::NotImplementedReply();
        }
    } catch (const std::exception& e) {
        out = ets::ErrReply(-1, std::string("exception: ") + e.what());
    }
    if (cb) cb(uid, out.c_str());
}

extern "C" __declspec(dllexport) void PlnUnInitialize(void) {
    ets::HostLog(0, "soundhelper: uninit");
}
