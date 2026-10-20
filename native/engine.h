#pragma once
#include <atomic>
#include <cstdint>
#include <string>

namespace hmosffmpeg {
struct Task {
    std::atomic<bool> cancelled{false};
    std::atomic<int64_t> processedUs{0};
    std::string operation, input, output, videoCodec, audioCodec, videoFilter, audioFilter, caFile;
    int timeoutSeconds = 30;
};
std::string buildInfo();
std::string capabilities();
std::string probe(Task& task);
void convert(Task& task);
}
