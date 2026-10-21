/* The C side of a `py_wasm_module`: an embedded CPython behind the exported
 * entry points.
 *
 * `allocate` is the allocator a host places the input buffer with. Each
 * exported function (generated into `exports.c` by the rule) calls
 * `rules_venv_py_wasm_call`, which starts the interpreter if it is not running
 * yet, runs the bootstrap that imports from the embedded bundle, calls the
 * Python function of that name in the entry module with the input as `bytes`,
 * and returns what it produced: `bytes`, or `(bytes, code)` to set the return
 * code. When the module was pre-initialized with Wizer the interpreter is
 * already up when the host calls, and only the function runs.
 *
 * Nothing is torn down between calls; a host that wants each call isolated
 * instantiates the module per call.
 */
#include <Python.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* The `encodings` modules, frozen by freeze_encodings.py: the interpreter
 * imports them while initializing, before the bundle importer exists. */
extern const struct _frozen rules_venv_py_wasm_frozen_modules[];
/* The bundle and the bootstrap, linked in as data by the rule's `embed.S`. */
extern const unsigned char rules_venv_py_wasm_bundle_start[];
extern const unsigned char rules_venv_py_wasm_bundle_end[];
extern const char rules_venv_py_wasm_bootstrap_src[];
/* The entry module, from the rule's `exports.c`. */
extern const char rules_venv_py_wasm_entry_module[];
/* What the interpreter wrote to a standard stream (wasi_stubs.c). */
extern const char* wasi_stub_captured(int fd, size_t* len);

/* Set once the interpreter is up and the entry module imported. */
static int g_ready;
static PyObject* g_entry;

static PyObject* host_bundle(PyObject* self, PyObject* args) {
    (void)self;
    (void)args;
    return PyMemoryView_FromMemory(
        (char*)rules_venv_py_wasm_bundle_start,
        (Py_ssize_t)(rules_venv_py_wasm_bundle_end -
                     rules_venv_py_wasm_bundle_start),
        PyBUF_READ);
}

static PyMethodDef host_methods[] = {
    {"bundle", host_bundle, METH_NOARGS, "The embedded source bundle."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef host_module = {
    PyModuleDef_HEAD_INIT,
    "_host",
    NULL,
    -1,
    host_methods,
    NULL,
    NULL,
    NULL,
    NULL,
};

static PyObject* PyInit__host(void) { return PyModule_Create(&host_module); }

__attribute__((export_name("allocate"))) void* rules_venv_py_wasm_allocate(
    uint32_t size, uint32_t align) {
    (void)align; /* malloc alignment is sufficient for byte buffers */
    return malloc(size ? size : 1);
}

/* Print the raised exception to the captured stderr without exiting, which
 * PyErr_Print would do for SystemExit. */
static void report_exception(void) {
    PyObject* exc = PyErr_GetRaisedException();
    if (exc != NULL) {
        PyErr_DisplayException(exc);
        Py_DECREF(exc);
    }
}

/* Start the interpreter and import the entry module. Returns NULL on success,
 * else a message; details are on the captured stderr. */
static const char* initialize(void) {
    if (g_ready) {
        return NULL;
    }
    PyImport_AppendInittab("_host", PyInit__host);
    PyImport_FrozenModules = rules_venv_py_wasm_frozen_modules;

    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.module_search_paths_set =
        1; /* nothing on sys.path: the bundle finder serves imports */
    config.site_import = 0;
    config.write_bytecode = 0;
    config.install_signal_handlers = 0;
    config.pathconfig_warnings = 0;
    config.buffered_stdio = 0;
    config.use_hash_seed = 1;
    config.hash_seed = 0;
    PyConfig_SetString(&config, &config.program_name, L"py_wasm_module");
    PyConfig_SetString(&config, &config.home, L"/py_wasm_module");

    PyStatus status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        return status.err_msg ? status.err_msg : "Python failed to initialize";
    }

    /* Install the bundle importer; everything after this imports from it. */
    PyObject* globals = PyDict_New();
    PyDict_SetItemString(globals, "__builtins__", PyEval_GetBuiltins());
    PyObject* result = PyRun_String(rules_venv_py_wasm_bootstrap_src,
                                    Py_file_input, globals, globals);
    if (result == NULL) {
        report_exception();
        return "The py_wasm_module bootstrap failed";
    }
    Py_DECREF(result);

    PyObject* prepare = PyDict_GetItemString(globals, "prepare");
    g_entry = prepare ? PyObject_CallFunction(prepare, "s",
                                              rules_venv_py_wasm_entry_module)
                      : NULL;
    if (g_entry == NULL) {
        report_exception();
        return "Importing the entry module failed";
    }
    Py_DECREF(globals);
    g_ready = 1;
    return NULL;
}

/* Wizer calls this once at build time and snapshots the memory afterwards. */
__attribute__((export_name("wizer.initialize"))) void
rules_venv_py_wasm_wizer_initialize(void) {
    const char* error = initialize();
    if (error != NULL) {
        __builtin_trap();
    }
}

static uint32_t fail(const char* message, uint8_t** out_ptr,
                     uint32_t* out_len) {
    size_t err_len;
    const char* err = wasi_stub_captured(2, &err_len);
    size_t msg_len = strlen(message);
    char* buf = malloc(msg_len + err_len + 2);
    memcpy(buf, message, msg_len);
    buf[msg_len] = '\n';
    memcpy(buf + msg_len + 1, err, err_len);
    *out_ptr = (uint8_t*)buf;
    *out_len = (uint32_t)(msg_len + 1 + err_len);
    return 2;
}

uint32_t rules_venv_py_wasm_call(const char* function, const uint8_t* input,
                                 uint32_t input_len, uint8_t** out_ptr,
                                 uint32_t* out_len) {
    const char* error = initialize();
    if (error != NULL) {
        return fail(error, out_ptr, out_len);
    }

    PyObject* callable = PyObject_GetAttrString(g_entry, function);
    if (callable == NULL) {
        report_exception();
        return fail("The entry module has no such function", out_ptr, out_len);
    }
    PyObject* arg =
        PyBytes_FromStringAndSize((const char*)input, (Py_ssize_t)input_len);
    PyObject* result = arg ? PyObject_CallOneArg(callable, arg) : NULL;
    Py_XDECREF(arg);
    Py_DECREF(callable);
    if (result == NULL) {
        report_exception();
        return fail("The function raised an exception", out_ptr, out_len);
    }

    PyObject* payload = result;
    uint32_t code = 0;
    if (PyTuple_Check(result) && PyTuple_GET_SIZE(result) == 2) {
        payload = PyTuple_GET_ITEM(result, 0);
        code = (uint32_t)PyLong_AsUnsignedLong(PyTuple_GET_ITEM(result, 1));
        if (PyErr_Occurred()) {
            report_exception();
            Py_DECREF(result);
            return fail("The return code is not an unsigned integer", out_ptr,
                        out_len);
        }
    }
    Py_buffer view;
    if (PyObject_GetBuffer(payload, &view, PyBUF_SIMPLE) < 0) {
        report_exception();
        Py_DECREF(result);
        return fail("The function did not return bytes or (bytes, code)",
                    out_ptr, out_len);
    }
    uint8_t* buf = malloc(view.len ? (size_t)view.len : 1);
    memcpy(buf, view.buf, (size_t)view.len);
    *out_ptr = buf;
    *out_len = (uint32_t)view.len;
    PyBuffer_Release(&view);
    Py_DECREF(result);
    return code;
}
