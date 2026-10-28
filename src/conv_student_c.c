/*
 * conv_student_c.c - YOUR C version: C v2, row order.
 *
 * You do not need to edit this file by hand: Part 3 of lab.ipynb has the
 * function in a notebook cell, and build_c_v2() writes it between the two
 * "YOUR CODE" markers below, builds it and measures it.
 *
 * Until you write it, the "C v2 rows (yours)" row says MISMATCH: the
 * function below computes nothing yet.
 */
#include <stdint.h>

// ---- YOUR CODE STARTS HERE ----
void conv_c_rows(int *in, int *out, int *k, int h, int w)
{
    int oh = h - 2;    // output height
    int ow = w - 2;    // output width

    // Write the convolution here: the same work as C v1 in src/conv.c,
    // walking the image ROW BY ROW. See the hints in the notebook.

}
// ---- YOUR CODE ENDS HERE ----
