// A minimal `py_cc_extension` used to test ruff isort classification of
// compiled Python modules. Ruff only parses source text — it never loads
// the resulting `.so` — so the module body is deliberately trivial.

#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject* identity(PyObject* self, PyObject* args) {
    PyObject* value = NULL;
    if (!PyArg_ParseTuple(args, "O", &value)) {
        return NULL;
    }
    Py_INCREF(value);
    return value;
}

static PyMethodDef Methods[] = {
    {"identity", identity, METH_VARARGS, "Return the argument unchanged."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "native_module", NULL, -1, Methods,
};

PyMODINIT_FUNC PyInit_native_module(void) {
    return PyModule_Create(&moduledef);
}
