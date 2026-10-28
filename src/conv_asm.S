/*
 * conv_asm.S - 2D convolution in ARM64 (AArch64) assembly.
 *
 * The same operation as src/conv.c, written by hand in steps. Each version
 * changes one idea compared to the previous one:
 *
 *   conv_asm_v1  Brute force   A direct translation of the C loops: every
 *                              array index is recomputed with MUL. YOU write
 *                              half of it: src/conv_student_v1.S
 *   conv_asm_v2  Pointers      No index arithmetic inside the loop: pointers
 *                              walk the image, the kernel stays in registers.
 *   conv_asm_v3  MAC           v2 with each MUL + ADD pair fused into one
 *                              MADD. YOU write this one: src/conv_student.S
 *   conv_asm_v4  NEON SIMD     4 output pixels per iteration with 128-bit
 *                              vector registers.
 *
 * Operation (see src/conv.c):
 *
 *   out[y][x] = sum over ky, kx in 0..2 of  in[y + ky][x + kx] * k[ky][kx]
 *
 * C prototype shared by every version:
 *
 *   void conv_asm_vN(const int32_t *in, int32_t *out, const int32_t *k,
 *                    long h, long w);
 *
 * Calling convention (AAPCS64), what we rely on:
 *   - Arguments arrive in x0..x4:  x0 = in, x1 = out, x2 = k, x3 = h, x4 = w.
 *   - x0..x17 and v0..v7, v16..v31 are scratch: we may overwrite them.
 *   - x19..x28 must be preserved: a function that uses them saves them on
 *     the stack first and restores them before returning.
 *   - wN is the low 32 bits of xN. Pixels are 32-bit, so pixel arithmetic
 *     uses wN; addresses and counters use xN (64-bit).
 */

        .text

/* ------------------------------------------------------------------------
 * conv_asm_v2 - pointers (no index arithmetic in the loop)
 *
 * Same result as v1 (src/conv_student_v1.S) with much less work per output pixel:
 *   - The 9 kernel coefficients are loaded ONCE into registers w9..w17.
 *   - No index multiplications: three pointers (p0, p1, p2) sit on the three
 *     image rows under the kernel and simply move 4 bytes to the right.
 *     "ldr w20, [x7], #4" loads AND advances the pointer (post-increment).
 *   - The two small kernel loops are unrolled: 9 loads, 9 multiplies.
 *   - Loops count down to zero, so SUBS sets the flags and no CMP is needed.
 *
 * Each tap still takes two arithmetic instructions: MUL, then ADD.
 *
 * Registers:
 *   x0  = start of the current top row        x1 = out pointer (advances)
 *   x7, x8, x2 = p0, p1, p2 (rows y, y+1, y+2) x3 = output rows left
 *   x4  = row stride in bytes (w * 4)         x5 = ow   x6 = columns left
 *   w9..w17 = k[0..8]                          w19 = acc   w20 = pixel/product
 * ------------------------------------------------------------------------ */
        .global conv_asm_v2
        .type   conv_asm_v2, %function
conv_asm_v2:
        cmp     x3, #3
        b.lt    9f
        cmp     x4, #3
        b.lt    9f
        stp     x19, x20, [sp, #-16]!   // save the callee-saved registers we use

        ldp     w9,  w10, [x2]          // k[0], k[1]
        ldp     w11, w12, [x2, #8]      // k[2], k[3]
        ldp     w13, w14, [x2, #16]     // k[4], k[5]
        ldp     w15, w16, [x2, #24]     // k[6], k[7]
        ldr     w17, [x2, #32]          // k[8]

        sub     x3, x3, #2              // rows left = oh = h - 2
        sub     x5, x4, #2              // ow = w - 2
        lsl     x4, x4, #2              // stride = w * 4 bytes

1:      mov     x7, x0                  // p0 = row y
        add     x8, x7, x4              // p1 = row y + 1
        add     x2, x8, x4              // p2 = row y + 2
        mov     x6, x5                  // columns left = ow

2:      ldr     w20, [x7], #4           // row y:   in[y][x], then p0 += 4
        mul     w19, w20, w9            //   acc  = pixel * k[0]
        ldr     w20, [x7]               //          in[y][x+1]
        mul     w20, w20, w10           //   product = pixel * k[1]
        add     w19, w19, w20           //   acc += product
        ldr     w20, [x7, #4]           //          in[y][x+2]
        mul     w20, w20, w11
        add     w19, w19, w20

        ldr     w20, [x8], #4           // row y+1
        mul     w20, w20, w12
        add     w19, w19, w20
        ldr     w20, [x8]
        mul     w20, w20, w13
        add     w19, w19, w20
        ldr     w20, [x8, #4]
        mul     w20, w20, w14
        add     w19, w19, w20

        ldr     w20, [x2], #4           // row y+2
        mul     w20, w20, w15
        add     w19, w19, w20
        ldr     w20, [x2]
        mul     w20, w20, w16
        add     w19, w19, w20
        ldr     w20, [x2, #4]
        mul     w20, w20, w17
        add     w19, w19, w20

        str     w19, [x1], #4           // *out++ = acc
        subs    x6, x6, #1              // columns left--, sets the Z flag
        b.ne    2b

        add     x0, x0, x4              // next top row
        subs    x3, x3, #1              // rows left--
        b.ne    1b

        ldp     x19, x20, [sp], #16     // restore callee-saved registers
9:      ret
        .size   conv_asm_v2, .-conv_asm_v2

/* ------------------------------------------------------------------------
 * conv_asm_v3 lives in src/conv_student.S: it is the hands-on exercise.
 * ------------------------------------------------------------------------ */

/* ------------------------------------------------------------------------
 * conv_asm_v4 - NEON SIMD, 4 output pixels per iteration
 *
 * A NEON register (v0..v31) is 128 bits wide = 4 int32 "lanes". One vector
 * instruction does the same operation on all 4 lanes at once:
 *
 *   ldr  q16, [x7]               q16 = in[y][x .. x+3]          (4 pixels)
 *   mla  v20.4s, v16.4s, v0.s[1] acc[i] += pixel[i] * k[1], i = 0..3
 *
 * For 4 neighbouring outputs, tap (ky, kx) needs the 4 pixels starting at
 * row y+ky, column x+kx, so the 9 taps become 9 vector loads (shifted by 0,
 * 4 and 8 bytes) and 9 vector multiply-accumulates: 36 MACs per iteration.
 * LDUR is the load used when the offset is not a multiple of 16.
 *
 * When fewer than 4 columns are left at the end of a row, a scalar loop
 * (v3's loop body, with MADD) finishes them one at a time: the "tail".
 *
 * Registers: as in v2, plus
 *   v0.s[0..3] = k[0..3]   v1.s[0..3] = k[4..7]   v2.s[0] = k[8]
 *   v16..v18 = 4 pixels each   v20 = 4 accumulators (4 output pixels)
 * ------------------------------------------------------------------------ */
        .global conv_asm_v4
        .type   conv_asm_v4, %function
conv_asm_v4:
        cmp     x3, #3
        b.lt    9f
        cmp     x4, #3
        b.lt    9f
        stp     x19, x20, [sp, #-16]!

        ld1     {v0.4s, v1.4s}, [x2]    // k[0..7] into the lanes of v0 and v1
        ldr     s2, [x2, #32]           // k[8] into lane 0 of v2
        ldp     w9,  w10, [x2]          // scalar copies for the tail
        ldp     w11, w12, [x2, #8]
        ldp     w13, w14, [x2, #16]
        ldp     w15, w16, [x2, #24]
        ldr     w17, [x2, #32]

        sub     x3, x3, #2              // rows left = oh
        sub     x5, x4, #2              // ow
        lsl     x4, x4, #2              // stride in bytes

1:      mov     x7, x0                  // p0, p1, p2 as in v2
        add     x8, x7, x4
        add     x2, x8, x4
        mov     x6, x5                  // columns left = ow

2:      cmp     x6, #4                  // 4 or more columns left?
        b.lt    3f                      //   no: go to the scalar tail

        ldr     q16, [x7]               // row y:   pixels at x, x+1, x+2
        ldur    q17, [x7, #4]
        ldur    q18, [x7, #8]
        mul     v20.4s, v16.4s, v0.s[0] // acc  = px * k[0]   (4 lanes)
        mla     v20.4s, v17.4s, v0.s[1] // acc += px * k[1]
        mla     v20.4s, v18.4s, v0.s[2] // acc += px * k[2]

        ldr     q16, [x8]               // row y+1
        ldur    q17, [x8, #4]
        ldur    q18, [x8, #8]
        mla     v20.4s, v16.4s, v0.s[3] // acc += px * k[3]
        mla     v20.4s, v17.4s, v1.s[0] // acc += px * k[4]
        mla     v20.4s, v18.4s, v1.s[1] // acc += px * k[5]

        ldr     q16, [x2]               // row y+2
        ldur    q17, [x2, #4]
        ldur    q18, [x2, #8]
        mla     v20.4s, v16.4s, v1.s[2] // acc += px * k[6]
        mla     v20.4s, v17.4s, v1.s[3] // acc += px * k[7]
        mla     v20.4s, v18.4s, v2.s[0] // acc += px * k[8]

        str     q20, [x1], #16          // store 4 outputs, out += 16 bytes
        add     x7, x7, #16             // move the 3 row pointers 4 pixels right
        add     x8, x8, #16
        add     x2, x2, #16
        sub     x6, x6, #4              // columns left -= 4
        b       2b

3:      cbz     x6, 5f                  // tail: the last 0..3 pixels of the row
4:      ldr     w20, [x7], #4
        mul     w19, w20, w9
        ldr     w20, [x7]
        madd    w19, w20, w10, w19
        ldr     w20, [x7, #4]
        madd    w19, w20, w11, w19
        ldr     w20, [x8], #4
        madd    w19, w20, w12, w19
        ldr     w20, [x8]
        madd    w19, w20, w13, w19
        ldr     w20, [x8, #4]
        madd    w19, w20, w14, w19
        ldr     w20, [x2], #4
        madd    w19, w20, w15, w19
        ldr     w20, [x2]
        madd    w19, w20, w16, w19
        ldr     w20, [x2, #4]
        madd    w19, w20, w17, w19
        str     w19, [x1], #4
        subs    x6, x6, #1
        b.ne    4b

5:      add     x0, x0, x4              // next top row
        subs    x3, x3, #1
        b.ne    1b

        ldp     x19, x20, [sp], #16
9:      ret
        .size   conv_asm_v4, .-conv_asm_v4

/* No executable stack needed (silences a linker warning). */
        .section .note.GNU-stack, "", %progbits
