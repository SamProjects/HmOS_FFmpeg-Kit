#include "command_timeout.h"
#include <cassert>
#include <limits>
int main() {
    using namespace hmosffmpeg;
    using namespace std::chrono;
    const CommandDeadline::Clock::time_point start{};
    CommandDeadline unlimited(0, start);
    assert(!unlimited.expired(start));
    assert(!unlimited.expired(start + hours(24 * 365)));
    CommandDeadline twoHours(7200, start);
    assert(!twoHours.expired(start + seconds(3601)));
    assert(!twoHours.expired(start + seconds(7199)));
    assert(twoHours.expired(start + seconds(7200)));
    CommandDeadline normal(300, start);
    assert(!normal.expired(start + seconds(299)));
    assert(normal.expired(start + seconds(300)));
    assert(commandTimeoutSeconds(0) == 0);
    assert(commandTimeoutSeconds(7200) == 7200);
    assert(commandTimeoutSeconds(2147483647.0) == 2147483647);
    for (double value : {-1.0, -0.5, 0.5, 2147483648.0, 4294967296.0,
                         std::numeric_limits<double>::quiet_NaN(),
                         std::numeric_limits<double>::infinity(),
                         -std::numeric_limits<double>::infinity()}) {
        bool rejected = false;
        try { commandTimeoutSeconds(value); } catch (const std::runtime_error&) { rejected = true; }
        assert(rejected);
    }
}
