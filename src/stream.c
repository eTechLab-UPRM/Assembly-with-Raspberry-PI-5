/*
 * stream.c - helpers for the live video of conv_stream.py (not part of the
 * exercises).
 *
 * At 2592 x 1944 a camera frame has 5 million pixels: converting it with
 * Python loops would take longer than the convolution itself. These three
 * functions do the conversions in C, so the time of each frame is the time
 * of the version being shown.
 *
 * Images are stored row by row. `stride` is the length of a camera row in
 * bytes, which can be larger than the width (the camera pads its rows).
 */
#include <stdint.h>

/* Camera brightness (Y plane, 1 byte per pixel) -> int32 image of h x w,
 * the layout every C and assembly version of the project expects. */
void y_to_i32(const uint8_t *y, long stride, long h, long w, int32_t *out)
{
    for (long r = 0; r < h; r++) {
        const uint8_t *src = y + r * stride;
        int32_t *dst = out + r * w;
        for (long c = 0; c < w; c++)
            dst[c] = src[c];
    }
}

/* Camera image shrunk f times for the screen: the average of each f x f
 * block. out has (h / f) x (w / f) pixels. */
void gray_small(const uint8_t *y, long stride, long h, long w, long f, uint8_t *out)
{
    long sh = h / f, sw = w / f;

    for (long r = 0; r < sh; r++) {
        for (long c = 0; c < sw; c++) {
            unsigned long sum = 0;
            for (long i = 0; i < f; i++)
                for (long j = 0; j < f; j++)
                    sum += y[(r * f + i) * stride + c * f + j];
            out[r * sw + c] = (uint8_t)(sum / (unsigned long)(f * f));
        }
    }
}

/* Output of the convolution (h x w int32) shrunk f times for the screen, as
 * notebook_image() draws it: the strongest edge |value| of each f x f block,
 * so that thin edges do not disappear, then 0 -> white and `top` or more ->
 * black. With top <= 0 the frame's own 99th percentile is used.
 *
 * tmp needs (h / f) x (w / f) int32. Returns the 99th percentile of this
 * frame, so the caller can smooth it from frame to frame. */
long edges_small(const int32_t *in, long h, long w, long f, long top,
                 int32_t *tmp, uint8_t *out)
{
    enum { BINS = 4096 };                   /* the edge kernel gives at most 2040 */
    long hist[BINS] = {0};
    long sh = h / f, sw = w / f, n = sh * sw;

    for (long r = 0; r < sh; r++) {
        for (long c = 0; c < sw; c++) {
            int32_t m = 0;
            for (long i = 0; i < f; i++) {
                const int32_t *row = in + (r * f + i) * w + c * f;
                for (long j = 0; j < f; j++) {
                    int32_t v = row[j] < 0 ? -row[j] : row[j];
                    if (v > m)
                        m = v;
                }
            }
            tmp[r * sw + c] = m;
            hist[m < BINS ? m : BINS - 1]++;
        }
    }

    long p = 0, seen = 0, want = n * 99 / 100;
    while (p < BINS - 1 && seen + hist[p] <= want)
        seen += hist[p++];

    if (top <= 0)
        top = p;
    if (top < 1)
        top = 1;
    for (long i = 0; i < n; i++) {
        long v = (long)tmp[i] * 255 / top;
        out[i] = (uint8_t)(255 - (v > 255 ? 255 : v));
    }
    return p;
}
