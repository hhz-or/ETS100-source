#pragma once
// Builtin pluginKey "__core" capabilities shared by the JS bridge and plugins.
#include <string>

namespace ets {

class Logger;
class MediaServer;

struct CoreContext {
    std::string appDir;
    std::string dataDir;
    std::string cacheDir;
    std::string homeUrl;
    std::string version = "1.0.0";
    Logger* logger = nullptr;
    MediaServer* media = nullptr;
};

// Handles the builtin pluginKey "__core". `action` is accepted with or without a
// "__core/" prefix. Always returns a JSON string (never empty).
std::string HandleCoreAction(const CoreContext& ctx, const std::string& action,
                             const std::string& argsJson);

} // namespace ets
