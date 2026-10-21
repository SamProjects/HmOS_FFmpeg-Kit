#pragma once
#include <atomic>
#include <cstdint>
#include <string>
#include <mutex>
#include <vector>

namespace hmosffmpeg {
struct Task {
    std::atomic<bool> cancelled{false};
    std::atomic<int64_t> processedUs{0};
    std::string operation, input, output, videoCodec, audioCodec, videoFilter, audioFilter, caFile;
    std::vector<std::string> commandArguments;
    int timeoutSeconds = 30;
    std::mutex logMutex;
    std::string commandLogs;
    bool logsTruncated = false;
};
std::string buildInfo();
std::string capabilities();
std::string probe(Task& task);
void convert(Task& task);
std::string executeCommand(Task& task);
std::string commandLogSnapshot(Task& task);
}
