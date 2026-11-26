#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "python/module_extension/private/tests/dynamic_deps/counter.h"

static PyObject* increment(PyObject* self, PyObject* args) {
    return PyLong_FromLong(increment_counter());
}

static PyMethodDef IncrementMethods[] = {
    {"increment", increment, METH_NOARGS, "Increment the shared counter"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef incrementmodule = {
    PyModuleDef_HEAD_INIT, "increment_ext", NULL, -1, IncrementMethods};

PyMODINIT_FUNC PyInit_increment_first(void) {
    return PyModule_Create(&incrementmodule);
}
