/*
 * conv.c - 2D convolution in plain C.
 *
 * This is the C level of the Python -> C -> assembly lab. The Makefile
 * compiles it with gcc -O2 into build/libconv_c.so.
 *
 * Operation (the same in every version of this lab):
 *
 *   out[y][x] = sum over ky, kx in 0..2 of  in[y + ky][x + kx] * k[ky][kx]
 *
 *   - in  : h x w image, int32, stored row by row (row-major)
 *   - k   : 3 x 3 kernel, int32, row-major
 *   - out : (h - 2) x (w - 2) image, int32, row-major ("valid" convolution:
 *           no padding, so the output is 2 pixels smaller in each direction)
 *
 * Like most deep-learning libraries, the kernel is not flipped (strictly
 * speaking this is a cross-correlation). The loops are the same either way.
 */
#include <stdint.h>

#define KSIZE 3

void conv_c(const int32_t *in, int32_t *out, const int32_t *k, long h, long w)
{
    if (h < KSIZE || w < KSIZE)
        return;

    long oh = h - (KSIZE - 1);   /* output height */
    long ow = w - (KSIZE - 1);   /* output width  */

    for (long y = 0; y < oh; y++) {           /* every output row ...      */
        for (long x = 0; x < ow; x++) {       /* ... every output column   */
            int32_t acc = 0;
            for (long ky = 0; ky < KSIZE; ky++)       /* every kernel row */
                for (long kx = 0; kx < KSIZE; kx++)   /* every kernel col */
                    acc += in[(y + ky) * w + (x + kx)] * k[ky * KSIZE + kx];
            out[y * ow + x] = acc;
        }
    }
}
