/*
 * conv.c - 2D convolution in plain C.
 *
 * This is the C level of the Python -> C -> assembly lab. The Makefile
 * compiles it with gcc -O2 into build/libconv_c.so.
 *
 * Two versions, identical except for the ORDER of the two outer loops:
 *
 *   conv_c_cols  x outside, y inside: walks the image column by column.
 *   conv_c_rows  y outside, x inside: walks the image row by row.
 *
 * Both compute exactly the same output. The difference is how they move
 * through memory (see "Why the loop order matters" below).
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

/*
 * Why the loop order matters
 *
 * C stores the image row by row: in[r][c] is at index r * w + c, so the
 * pixels of one row sit next to each other in memory. The CPU never reads a
 * single pixel from RAM: it brings a whole 64-byte cache line (16 pixels)
 * into its cache, so the next pixels of the same row are already there.
 *
 *   conv_c_rows: consecutive output pixels are neighbours in the same row,
 *                so each cache line brought from RAM is used 16 times.
 *   conv_c_cols: consecutive output pixels are one whole row apart
 *                (w * 4 bytes), so almost every access needs another cache
 *                line, and the lines are often gone before they are reused.
 */

/* Version 1: column order. Only the two outer "for" lines are swapped. */
void conv_c_cols(const int32_t *in, int32_t *out, const int32_t *k, long h, long w)
{
    if (h < KSIZE || w < KSIZE)
        return;

    long oh = h - (KSIZE - 1);   /* output height */
    long ow = w - (KSIZE - 1);   /* output width  */

    for (long x = 0; x < ow; x++) {           /* every output column ...   */
        for (long y = 0; y < oh; y++) {       /* ... every output row      */
            int32_t acc = 0;
            for (long ky = 0; ky < KSIZE; ky++)       /* every kernel row */
                for (long kx = 0; kx < KSIZE; kx++)   /* every kernel col */
                    acc += in[(y + ky) * w + (x + kx)] * k[ky * KSIZE + kx];
            out[y * ow + x] = acc;
        }
    }
}

/* Version 2: row order, the order the image is stored in memory. */
void conv_c_rows(const int32_t *in, int32_t *out, const int32_t *k, long h, long w)
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
