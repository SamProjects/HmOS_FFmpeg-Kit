#pragma once
#include <chrono>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace hmosffmpeg {
// Read JS numbers before narrowing: int32 conversion would truncate/wrap them.
inline int commandTimeoutSeconds(double value) {
    if (!std::isfinite(value) || value < 0 || std::floor(value) != value ||
        value > std::numeric_limits<int32_t>::max())
        throw std::runtime_error("Timeout must be an integer from 0 to 2147483647 seconds; 0 disables the total timeout");
    return static_cast<int>(value);
}
class CommandDeadline {
public:
    using Clock = std::chrono::steady_clock;
    explicit CommandDeadline(int seconds, Clock::time_point start = Clock::now())
        : enabled_(commandTimeoutSeconds(seconds) > 0), deadline_(start) {
        if (enabled_) deadline_ += std::chrono::seconds(seconds);
    }
    bool expired(Clock::time_point now = Clock::now()) const {
        return enabled_ && now >= deadline_;
    }
private:
    bool enabled_;
    Clock::time_point deadline_;
};
}
