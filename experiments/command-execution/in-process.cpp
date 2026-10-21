#include "engine.h"
#include <chrono>
#include <csignal>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <vector>

static void sentinel(int) {}
int main(int argc, char** argv) {
    if(argc != 2) return 2;
    std::string directory = argv[1], input = directory + "/输入 ; sample.wav";
    std::signal(SIGINT, sentinel);
    auto run = [&](const std::string& name, std::vector<std::string> args, bool cancel = false, int timeout = 30) {
        hmosffmpeg::Task task;
        task.commandArguments = std::move(args); task.timeoutSeconds = timeout;
        std::thread cancellation;
        if(cancel) cancellation = std::thread([&] {
            std::this_thread::sleep_for(std::chrono::milliseconds(250)); task.cancelled = true;
        });
        try {
            std::string result = hmosffmpeg::executeCommand(task);
            if(cancellation.joinable()) cancellation.join();
            std::cout << "{\"name\":\"" << name << "\",\"progressUs\":" << task.processedUs
                      << ",\"result\":" << result << "}\n";
        } catch(...) {
            if(cancellation.joinable()) cancellation.join();
            throw;
        }
    };
    run("version", {"-version"});
    run("invalid", {"-not_an_ffmpeg_option"});
    run("version-after-error", {"-version"});
    run("generate", {"-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "0.2", "-c:a", "pcm_s16le", input});
    for(int i = 0; i < 10; ++i)
        run("repeat-" + std::to_string(i), {"-y", "-i", input, "-c:a", "copy", directory + "/repeat.wav"});
    run("overwrite-reset", {"-i", input, "-c:a", "copy", directory + "/repeat.wav"});
    run("complex-filter", {"-i", input, "-filter_complex", "[0:a]anull[a]", "-map", "[a]", "-c:a", "pcm_s16le", directory + "/filtered.wav"});
    run("cancel", {"-re", "-stream_loop", "-1", "-i", input, "-t", "60", "-c:a", "copy", directory + "/cancel.wav"}, true);
    run("after-cancel", {"-i", input, "-c:a", "copy", directory + "/after-cancel.wav"});
    run("timeout", {"-re", "-stream_loop", "-1", "-i", input, "-t", "60", "-c:a", "copy", directory + "/timeout.wav"}, false, 1);
    run("after-timeout", {"-version"});
    for(const auto& option : {"-stdin", "-report", "-timelimit", "-cpucount", "pipe:1"}) {
        hmosffmpeg::Task task; task.commandArguments = {option};
        bool rejected = false;
        try { hmosffmpeg::executeCommand(task); } catch(const std::runtime_error&) { rejected = true; }
        if(!rejected) throw std::runtime_error("Process-wide option was not rejected");
    }
    if(std::signal(SIGINT, sentinel) != sentinel) throw std::runtime_error("Application signal handler changed");
}
