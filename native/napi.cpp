#include "engine.h"
#include <napi/native_api.h>
#include <map>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <vector>

namespace {
using hmosffmpeg::Task;
using Key = std::pair<napi_env, int32_t>;
std::mutex guard;
std::map<Key, std::shared_ptr<Task>> tasks;
struct Work { napi_async_work work{}; napi_deferred deferred{}; Key key; std::shared_ptr<Task> task; std::string result, error; };
void ok(napi_status s) { if(s != napi_ok) throw std::runtime_error("NAPI operation failed"); }
std::string string(napi_env env, napi_value value) {
    size_t size; ok(napi_get_value_string_utf8(env, value, nullptr, 0, &size));
    if(size > 65536) throw std::runtime_error("Argument too large");
    std::vector<char> buffer(size + 1); ok(napi_get_value_string_utf8(env, value, buffer.data(), buffer.size(), &size));
    std::string out(buffer.data(), size);
    if(out.find('\0') != std::string::npos) throw std::runtime_error("NUL in argument");
    return out;
}
napi_value text(napi_env env, const std::string& s) { napi_value v; ok(napi_create_string_utf8(env, s.c_str(), s.size(), &v)); return v; }
napi_value fail(napi_env env, const char* message) { napi_throw_error(env, nullptr, message); return nullptr; }
napi_value buildInfo(napi_env env, napi_callback_info) {
    try { return text(env, hmosffmpeg::buildInfo()); } catch(const std::exception& e) { return fail(env, e.what()); }
}
napi_value capabilities(napi_env env, napi_callback_info) {
    try { return text(env, hmosffmpeg::capabilities()); } catch(const std::exception& e) { return fail(env, e.what()); }
}
napi_value start(napi_env env, napi_callback_info info) {
    auto w = std::make_unique<Work>(); bool inserted = false;
    try {
        napi_value argv[9]; size_t argc = 9; void* mode = nullptr; ok(napi_get_cb_info(env, info, &argc, argv, nullptr, &mode));
        auto task = std::make_shared<Task>();
        int32_t id;
        if(mode) {
            if(argc != 3) throw std::runtime_error("Expected id, argument array and timeout seconds");
            ok(napi_get_value_int32(env, argv[0], &id));
            bool array = false; ok(napi_is_array(env, argv[1], &array));
            if(!array) throw std::runtime_error("Command arguments must be an array");
            uint32_t length; ok(napi_get_array_length(env, argv[1], &length));
            if(length == 0 || length > 256) throw std::runtime_error("Expected 1 to 256 command arguments");
            size_t total = 0;
            for(uint32_t i = 0; i < length; ++i) {
                napi_value item; ok(napi_get_element(env, argv[1], i, &item));
                task->commandArguments.push_back(string(env, item));
                total += task->commandArguments.back().size();
                if(total > 1024 * 1024) throw std::runtime_error("Command too large");
            }
            ok(napi_get_value_int32(env, argv[2], &task->timeoutSeconds));
            if(task->timeoutSeconds < 1 || task->timeoutSeconds > 3600) throw std::runtime_error("Timeout must be 1 to 3600 seconds");
            task->operation = "command";
#ifndef HMOS_COMMAND_TEST
            throw std::runtime_error("This HAR was built without the experimental command engine");
#endif
        } else {
            if(argc != 9) throw std::runtime_error("Expected nine operation arguments");
            ok(napi_get_value_int32(env, argv[0], &id));
            task->operation = string(env, argv[1]); task->input = string(env, argv[2]); task->output = string(env, argv[3]);
            task->videoCodec = string(env, argv[4]); task->audioCodec = string(env, argv[5]);
            task->videoFilter = string(env, argv[6]); task->audioFilter = string(env, argv[7]); task->caFile = string(env, argv[8]);
            if(task->operation != "probe" && task->operation != "remux" && task->operation != "transcode") throw std::runtime_error("Unsupported operation");
            if(task->input.empty()) throw std::runtime_error("Input required");
            if((task->videoCodec.empty() || task->videoCodec == "copy") && !task->videoFilter.empty()) throw std::runtime_error("Video filter requires encoder");
            if((task->audioCodec.empty() || task->audioCodec == "copy") && !task->audioFilter.empty()) throw std::runtime_error("Audio filter requires encoder");
        }
        w->key = {env, id}; w->task = task;
        { std::lock_guard<std::mutex> lock(guard);
          for(const auto& entry : tasks)
              if(task->operation == "command" || entry.second->operation == "command")
                  throw std::runtime_error("Command tests require exclusive access; wait for active tasks");
          if(tasks.size() >= 4 || tasks.count(w->key)) throw std::runtime_error("Too many tasks or duplicate session id");
          tasks.emplace(w->key, task); inserted = true; }
        napi_value promise; ok(napi_create_promise(env, &w->deferred, &promise));
        ok(napi_create_async_work(env, nullptr, text(env, "hmosffmpeg"),
            [](napi_env, void* data) {
                auto* w = static_cast<Work*>(data);
                try {
                    if(w->task->operation == "command") w->result = hmosffmpeg::executeCommand(*w->task);
                    else if(w->task->operation == "probe") w->result = hmosffmpeg::probe(*w->task);
                    else { hmosffmpeg::convert(*w->task); w->result = "{}"; }
                } catch(const std::exception& e) { w->error = e.what(); }
            },
            [](napi_env env, napi_status status, void* data) {
                std::unique_ptr<Work> w(static_cast<Work*>(data));
                { std::lock_guard<std::mutex> lock(guard); tasks.erase(w->key); }
                if(!env) return;
                if(status != napi_ok && w->error.empty()) w->error = "Async work cancelled";
                try {
                    if(w->error.empty()) ok(napi_resolve_deferred(env, w->deferred, text(env, w->result)));
                    else { napi_value error; ok(napi_create_error(env, nullptr, text(env, w->error), &error)); ok(napi_reject_deferred(env, w->deferred, error)); }
                } catch(...) { /* environment may be shutting down */ }
                napi_delete_async_work(env, w->work);
            }, w.get(), &w->work));
        ok(napi_queue_async_work(env, w->work)); w.release(); return promise;
    } catch(const std::exception& e) {
        if(inserted) { std::lock_guard<std::mutex> lock(guard); tasks.erase(w->key); }
        if(w->work) napi_delete_async_work(env, w->work);
        return fail(env, e.what());
    }
}
napi_value control(napi_env env, napi_callback_info info) {
    try {
        napi_value argv[2]; size_t argc = 2; ok(napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr));
        if(argc != 2) throw std::runtime_error("Expected session id and cancel flag");
        int32_t id; bool cancel; ok(napi_get_value_int32(env, argv[0], &id)); ok(napi_get_value_bool(env, argv[1], &cancel));
        int64_t progress = -1;
        { std::lock_guard<std::mutex> lock(guard); auto it = tasks.find({env,id});
          if(it != tasks.end()) { if(cancel) it->second->cancelled = true; progress = it->second->processedUs.load(); } }
        napi_value value; ok(napi_create_int64(env, progress, &value)); return value;
    } catch(const std::exception& e) { return fail(env, e.what()); }
}
napi_value init(napi_env env, napi_value exports) {
    napi_property_descriptor properties[] = {
        {"getBuildInfo", nullptr, buildInfo, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getCapabilities", nullptr, capabilities, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"run", nullptr, start, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"execute", nullptr, start, nullptr, nullptr, nullptr, napi_default, reinterpret_cast<void*>(1)},
        {"control", nullptr, control, nullptr, nullptr, nullptr, napi_default, nullptr}
    };
    napi_define_properties(env, exports, sizeof(properties)/sizeof(properties[0]), properties);
    napi_add_env_cleanup_hook(env, [](void* p) {
        std::lock_guard<std::mutex> lock(guard);
        for(auto& entry : tasks) if(entry.first.first == static_cast<napi_env>(p)) entry.second->cancelled = true;
    }, env);
    return exports;
}
napi_module module = {1, 0, nullptr, init, "hmosffmpeg", nullptr, {0}};
}
extern "C" __attribute__((constructor)) void RegisterHmosFFmpeg() { napi_module_register(&module); }
