#include "engine.h"
#include <chrono>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <vector>
#ifdef HMOS_COMMAND_TEST
#include "command/command.h"
#endif

namespace hmosffmpeg {
namespace {
struct Context {
    Task& task;
    std::chrono::steady_clock::time_point deadline;
};
std::string json(const std::string& value) {
    std::ostringstream out;
    out << '"';
    const char hex[] = "0123456789abcdef";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c < 32) out << "\\u00" << hex[c >> 4] << hex[c & 15];
        else out << c;
    }
    return out.str() + '"';
}
}
std::string commandLogSnapshot(Task& task) {
    std::lock_guard<std::mutex> lock(task.logMutex);
    return "{\"logs\":" + json(task.commandLogs) + ",\"logsTruncated\":" +
        (task.logsTruncated ? "true" : "false") + "}";
}
std::string executeCommand(Task& task) {
#ifndef HMOS_COMMAND_TEST
    (void)task;
    throw std::runtime_error("Command execution requires the experimental command-test HAR");
#else
    if (task.cancelled) return "{\"exitCode\":255,\"cancelled\":true,\"timedOut\":false,\"logs\":\"\",\"logsTruncated\":false}";
    Context context{task, std::chrono::steady_clock::now() + std::chrono::seconds(task.timeoutSeconds)};
    std::vector<std::string> values{"ffmpeg", "-nostdin", "-nostats"};
    for (const auto& value : task.commandArguments) {
        if (value == "-stdin" || value == "-report" || value == "-timelimit" ||
            value == "-cpuflags" || value == "-cpucount" || value == "-max_alloc" ||
            value == "-progress" || value == "-" || value.rfind("pipe:", 0) == 0 ||
            value.rfind("fd:", 0) == 0 || value.rfind("-vstats", 0) == 0)
            throw std::runtime_error("Option requiring process-wide state or standard IO is disabled in this test API: " + value);
        values.push_back(value);
    }
    std::vector<char*> argv;
    for (auto& value : values) argv.push_back(value.data());
    argv.push_back(nullptr);
    int code = hmos_command_run(static_cast<int>(values.size()), argv.data(),
        [](void* p) -> int { auto& c = *static_cast<Context*>(p);
            return c.task.cancelled || std::chrono::steady_clock::now() >= c.deadline; },
        [](void* p, int64_t pts) { if (pts >= 0) static_cast<Context*>(p)->task.processedUs = pts; },
        [](void* p, const char* message) { auto& c = *static_cast<Context*>(p);
            std::lock_guard<std::mutex> lock(c.task.logMutex);
            constexpr size_t limit = 256 * 1024;
            size_t size = std::char_traits<char>::length(message);
            size_t remaining = limit - c.task.commandLogs.size();
            size_t count = size < remaining ? size : remaining;
            // Keep the bounded buffer at a UTF-8 character boundary.
            if (count < size) while (count && (static_cast<unsigned char>(message[count]) & 0xc0) == 0x80) --count;
            c.task.commandLogs.append(message, count);
            if (size > remaining) c.task.logsTruncated = true;
        }, &context);
    if (code == -16) throw std::runtime_error("Another command is running");
    bool timedOut = std::chrono::steady_clock::now() >= context.deadline;
    return "{\"exitCode\":" + std::to_string(code) + ",\"cancelled\":" + (task.cancelled ? "true" : "false")
        + ",\"timedOut\":" + (timedOut ? "true" : "false") + ",\"logs\":" + json(task.commandLogs)
        + ",\"logsTruncated\":" + (task.logsTruncated ? "true" : "false") + '}';
#endif
}
}
