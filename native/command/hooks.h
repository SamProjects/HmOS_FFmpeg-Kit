#pragma once
#include <stdio.h>
#include "command.h"
/* Include stdio before rewriting only the command sources' output calls. */
#define printf hmos_cmd_printf
#define fprintf(stream, ...) hmos_cmd_fprintf((void *)(stream), __VA_ARGS__)
