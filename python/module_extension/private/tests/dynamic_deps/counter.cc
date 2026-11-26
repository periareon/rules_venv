#include "python/module_extension/private/tests/dynamic_deps/counter.h"

static int counter = 0;

int increment_counter() { return ++counter; }
