#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <string>

static PyObject* sum_as_string(PyObject* self, PyObject* args) {
    unsigned long a, b;

    if (!PyArg_ParseTuple(args, "kk", &a, &b)) {
        return NULL;
    }

    std::string result = std::to_string(a + b);
    return PyUnicode_FromString(result.c_str());
}

static PyMethodDef SumMethods[] = {
    {"sum_as_string", sum_as_string, METH_VARARGS,
     "Sum two numbers and return as a string"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef summodule = {PyModuleDef_HEAD_INIT, "sum_ext", NULL,
                                       -1, SumMethods};

PyMODINIT_FUNC PyInit_string_sum_import(void) {
    return PyModule_Create(&summodule);
}
