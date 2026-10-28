/*
 * conv.c - 2D convolution in plain C: version C v1, column order.
 *
 * This is the C level of the Python -> C -> assembly lab. The Makefile
 * compiles it with gcc -O2 into build/libconv_c.so. C v2 (row order) is the
 * version YOU write in Part 3 of lab.ipynb (src/conv_student_c.c).
 *
 * Operation (the same in every version of this lab):
 *
 *   out[y][x] = sum over ky, kx in 0..2 of  in[y + ky][x + kx] * k[ky][kx]
 *
 *   - in  : h x w image, int32, stored row by row: in[r][c] is in[r * w + c]
 *   - k   : 3 x 3 kernel, int32, row by row:       k[r][c]  is k[r * 3 + c]
 *   - out : (h - 2) x (w - 2) image, int32, row by row ("valid" convolution:
 *           no padding, so the output is 2 pixels smaller in each direction)
 *
 * Every C line is followed, in the comments on the right, by the RISC-V
 * instructions you would write for it in Ripes (RV32IM). Registers:
 *
 *   a0 = in    a1 = out   a2 = k   a3 = h   a4 = w      (the arguments)
 *   s0 = x     s1 = y     s2 = ky  s3 = kx  s4 = acc
 *   s5 = oh    s6 = ow    t0..t5 = temporaries
 *
 * (A real function must also save s0..s6 on the stack at the start and
 * restore them before "ret"; that part is left out here.) This RISC-V code
 * was run and gives the same results as the C code.
 */
#include <stdint.h>

#define KSIZE 3

void conv_c_cols(const int32_t *in, int32_t *out, const int32_t *k, long h, long w)
{
    if (h < KSIZE || w < KSIZE)                 //     li   t0, 3
        return;                                 //     blt  a3, t0, done    # h < 3: return
                                                //     blt  a4, t0, done    # w < 3: return

    long oh = h - (KSIZE - 1);                  //     addi s5, a3, -2      # oh = h - 2
    long ow = w - (KSIZE - 1);                  //     addi s6, a4, -2      # ow = w - 2

    for (long x = 0; x < ow; x++) {             //     li   s0, 0           # x = 0
                                                // loop_x:
        for (long y = 0; y < oh; y++) {         //     li   s1, 0           # y = 0
                                                // loop_y:
            int32_t acc = 0;                    //     li   s4, 0           # acc = 0
            for (long ky = 0; ky < KSIZE; ky++) //     li   s2, 0           # ky = 0
                                                // loop_ky:
                for (long kx = 0; kx < KSIZE; kx++) // li   s3, 0           # kx = 0
                                                // loop_kx:
                    acc += in[(y + ky) * w + (x + kx)] * k[ky * KSIZE + kx];
                                                //     add  t0, s1, s2      # y + ky
                                                //     mul  t0, t0, a4      # (y + ky) * w
                                                //     add  t1, s0, s3      # x + kx
                                                //     add  t0, t0, t1      # index into in[]
                                                //     slli t0, t0, 2       # index * 4 bytes
                                                //     add  t0, a0, t0      # address of the pixel
                                                //     lw   t2, 0(t0)       # pixel
                                                //     li   t3, 3
                                                //     mul  t3, s2, t3      # ky * 3
                                                //     add  t3, t3, s3      # index into k[]
                                                //     slli t3, t3, 2       # index * 4 bytes
                                                //     add  t3, a2, t3      # address of the coefficient
                                                //     lw   t4, 0(t3)       # coef
                                                //     mul  t2, t2, t4      # pixel * coef
                                                //     add  s4, s4, t2      # acc += pixel * coef
                                                //     addi s3, s3, 1       # kx++
                                                //     li   t5, 3
                                                //     blt  s3, t5, loop_kx # next kx while kx < 3
                                                //     addi s2, s2, 1       # ky++
                                                //     blt  s2, t5, loop_ky # next ky while ky < 3
            out[y * ow + x] = acc;              //     mul  t0, s1, s6      # y * ow
                                                //     add  t0, t0, s0      # + x
                                                //     slli t0, t0, 2       # * 4 bytes
                                                //     add  t0, a1, t0      # address of out[y * ow + x]
                                                //     sw   s4, 0(t0)       # store acc
        }                                       //     addi s1, s1, 1       # y++
                                                //     blt  s1, s5, loop_y  # next y while y < oh
    }                                           //     addi s0, s0, 1       # x++
                                                //     blt  s0, s6, loop_x  # next x while x < ow
}                                               // done:
                                                //     ret
