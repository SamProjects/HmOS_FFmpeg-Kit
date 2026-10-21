#include "engine.h"
#include <atomic>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <thread>
using namespace std::chrono;
int main() {
    std::string line;
    while (std::getline(std::cin,line)) {
        std::istringstream in(line);
        std::string id; int timeout, cancelMs, count; bool repeat, concurrent;
        in >> id >> timeout >> cancelMs >> repeat >> concurrent >> count;
        hmosffmpeg::Task task; task.timeoutSeconds=timeout;
        for (int i=0;i<count;i++) { std::string arg; in >> std::quoted(arg); task.commandArguments.push_back(arg); }
        if (!in) return 2;
        std::atomic<bool> done{false}; std::string result, error;
        auto start=steady_clock::now();
        std::thread worker([&] {
            try { result=hmosffmpeg::executeCommand(task); }
            catch (const std::exception& e) {error=e.what();}
            done=true;
        });
        int reads=0, updates=0; int64_t progress=0; std::string previous; bool cancelled=false, busy=false;
        while (!done) {
            int elapsed=duration_cast<milliseconds>(steady_clock::now()-start).count();
            if (cancelMs>=0 && elapsed>=cancelMs && !cancelled) {
                task.cancelled=true; if(repeat) {task.cancelled=true;task.cancelled=true;} cancelled=true;
            }
            if (concurrent && elapsed>100 && !busy) {
                hmosffmpeg::Task other; other.commandArguments={"-version"};
                try {hmosffmpeg::executeCommand(other);} catch(const std::exception& e) {busy=std::string(e.what()).find("Another command")!=std::string::npos;}
            }
            auto snapshot=hmosffmpeg::commandLogSnapshot(task);
            reads++; if(snapshot!=previous && snapshot.find("ffmpeg")!=std::string::npos) updates++;
            previous=snapshot; progress=std::max(progress,task.processedUs.load());
            std::this_thread::sleep_for(milliseconds(20));
        }
        worker.join();
        auto ms=duration_cast<milliseconds>(steady_clock::now()-start).count();
        // Errors from the command adapter are ASCII option validation diagnostics.
        std::cout << "{\"id\":\"" << id << "\",\"elapsedMs\":" << ms << ",\"liveReads\":" << reads
                  << ",\"liveUpdates\":" << updates << ",\"progressUs\":" << progress << ",\"busyRejected\":" << (busy?"true":"false")
                  << ",\"error\":" << std::quoted(error) << ",\"result\":" << (result.empty()?"null":result) << "}\n" << std::flush;
    }
}
