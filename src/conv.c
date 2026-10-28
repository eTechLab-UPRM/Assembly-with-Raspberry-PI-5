/*
 * conv.c - 2D convolution in plain C: version C v1, column order.
 *
 * This is the C level of the Python -> C -> assembly lab. The Makefile
 * compiles it with gcc -O2 into build/libconv_c.so. C v2 (row order) is the
 * version YOU write in Part 3 of lab.ipynb (src/conv_student_c.c).
 *
 *   out[y][x] = sum over ky, kx in 0..2 of  in[y + ky][x + kx] * k[ky][kx]
 *
 * Images and kernel are stored row by row in one flat block: in[r][c] is
 * in[r * w + c], out[y][x] is out[y * ow + x], k[ky][kx] is k[ky * 3 + kx].
 * The output is 2 pixels smaller than the image in each direction.
 *
 * The comments on the right show the RISC-V instructions you would write in
 * Ripes for the loops and the operations. Registers:
 *
 *   a0 = in    a1 = out   a2 = k    a4 = w
 *   s0 = x     s1 = y     s2 = ky   s3 = kx   s4 = acc   s5 = oh   s6 = ow
 *   t0..t5 = temporaries
 *
 * (The RISC-V loops test their condition at the end, like most loops in
 * Ripes: images always have at least 3 x 3 pixels, so every loop runs at
 * least once. This RISC-V code was run and gives the same results.)
 */

void conv_c_cols(int *in, int *out, int *k, int h, int w)
{
    int oh = h - 2;                             // output height
    int ow = w - 2;                             // output width

    for (int x = 0; x < ow; x++) {              //     li   s0, 0           # x = 0
                                                // loop_x:
        for (int y = 0; y < oh; y++) {          //     li   s1, 0           # y = 0
                                                // loop_y:
            int acc = 0;                        //     li   s4, 0           # acc = 0
            for (int ky = 0; ky < 3; ky++) {    //     li   s2, 0           # ky = 0
                                                // loop_ky:
                for (int kx = 0; kx < 3; kx++) {//     li   s3, 0           # kx = 0
                                                // loop_kx:
                    acc += in[(y + ky) * w + (x + kx)] * k[ky * 3 + kx];
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
                }                               //     addi s3, s3, 1       # kx++
                                                //     li   t5, 3
                                                //     blt  s3, t5, loop_kx # next kx while kx < 3
            }                                   //     addi s2, s2, 1       # ky++
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
}
