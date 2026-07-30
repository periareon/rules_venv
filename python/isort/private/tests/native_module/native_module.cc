// A minimal `py_cc_extension` used to test standalone isort classification
// of compiled Python modules. isort walks the staged runfiles tree to
// classify names; the module body is deliberately trivial since the test
// only exercises classification, not runtime behavior.

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
