#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "python/module_extension/private/tests/data/greeting.h"

static PyObject* greet(PyObject* self, PyObject* args) {
    return PyUnicode_FromString(greeting());
}

static PyMethodDef WithDataMethods[] = {
    {"greet", greet, METH_NOARGS, "Return a greeting"}, {NULL, NULL, 0, NULL}};

static struct PyModuleDef withdatamodule = {PyModuleDef_HEAD_INIT, "with_data",
                                            NULL, -1, WithDataMethods};

PyMODINIT_FUNC PyInit_with_data(void) {
    return PyModule_Create(&withdatamodule);
}
