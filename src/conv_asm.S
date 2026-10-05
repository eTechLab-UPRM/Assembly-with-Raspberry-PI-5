/*
 * conv_asm.S - 2D convolution in ARM64 (AArch64) assembly.
 *
 * Same operation as src/conv.c, written by hand:
 *
 *   out[y][x] = sum over ky, kx in 0..2 of  in[y + ky][x + kx] * k[ky][kx]
 *
 * C prototype:
 *
 *   void conv_asm(const int32_t *in, int32_t *out, const int32_t *k,
 *                 long h, long w);
 *
 * What assembly lets us do that the C version (gcc -O2) does not:
 *
 *   1. NEON SIMD. A NEON register (v0..v31) is 128 bits = 4 int32 "lanes",
 *      and one instruction works on all 4 lanes at once. We compute
 *      4 output pixels per loop iteration:
 *
 *        ldr  q16, [x7]                  q16 = in[y][x .. x+3]  (4 pixels)
 *        mla  v20.4s, v16.4s, v0.s[1]    acc[i] += pixel[i] * k[1], i = 0..3
 *
 *   2. The 9 kernel coefficients stay in registers for the whole run
 *      instead of being read from memory for every pixel.
 *
 *   3. No index multiplications. Three pointers walk the three image rows
 *      under the kernel and just move right; "str q20, [x1], #16" stores
 *      and advances the output pointer in one instruction.
 *
 * When fewer than 4 columns are left at the end of a row, a scalar loop
 * finishes them one pixel at a time (the "tail"). It uses MADD:
 * acc + a * b in a single instruction.
 *
 * Calling convention (AAPCS64), what we rely on:
 *   - Arguments arrive in x0..x4:  x0 = in, x1 = out, x2 = k, x3 = h, x4 = w.
 *   - x0..x17 and v0..v7, v16..v31 are scratch: we may overwrite them.
 *   - x19..x28 must be preserved, so we save x19 and x20 on the stack.
 *   - wN is the low 32 bits of xN. Pixels are 32-bit, so pixel math uses
 *     wN; addresses and counters use xN (64-bit).
 *
 * Registers:
 *   x0  = start of the current top row       x1 = out pointer (advances)
 *   x7, x8, x2 = p0, p1, p2: rows y, y+1, y+2 under the kernel
 *   x3  = output rows left    x4 = row stride in bytes (w * 4)
 *   x5  = output width (ow)   x6 = output columns left in this row
 *   v0.s[0..3] = k[0..3]   v1.s[0..3] = k[4..7]   v2.s[0] = k[8]
 *   v16..v18 = 4 pixels each   v20 = 4 accumulators (4 output pixels)
 *   w9..w17 = k[0..8] (scalar copies for the tail)
 *   w19 = scalar accumulator   w20 = scalar pixel
 */

        .text
        .global conv_asm
        .type   conv_asm, %function
conv_asm:
        cmp     x3, #3                  // image smaller than the kernel?
        b.lt    9f                      //   then there is nothing to do
        cmp     x4, #3
        b.lt    9f
        stp     x19, x20, [sp, #-16]!   // save the callee-saved registers we use

        ld1     {v0.4s, v1.4s}, [x2]    // k[0..7] into the lanes of v0 and v1
        ldr     s2, [x2, #32]           // k[8] into lane 0 of v2
        ldp     w9,  w10, [x2]          // k[0..8] also in scalar registers
        ldp     w11, w12, [x2, #8]
        ldp     w13, w14, [x2, #16]
        ldp     w15, w16, [x2, #24]
        ldr     w17, [x2, #32]

        sub     x3, x3, #2              // rows left = oh = h - 2
        sub     x5, x4, #2              // ow = w - 2
        lsl     x4, x4, #2              // stride = w * 4 bytes

        // ---- for each output row -------------------------------------
1:      mov     x7, x0                  // p0 = row y
        add     x8, x7, x4              // p1 = row y + 1
        add     x2, x8, x4              // p2 = row y + 2
        mov     x6, x5                  // columns left = ow

        // ---- 4 output pixels at a time (NEON) ------------------------
2:      cmp     x6, #4                  // 4 or more columns left?
        b.lt    3f                      //   no: go to the scalar tail

        ldr     q16, [x7]               // row y:   pixels at x, x+1, x+2
        ldur    q17, [x7, #4]           //   (ldur: offset not a multiple of 16)
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

        // ---- tail: the last 0..3 pixels of the row, one at a time ----
3:      cbz     x6, 5f
4:      ldr     w20, [x7], #4           // row y:   in[y][x], then p0 += 4
        mul     w19, w20, w9            //   acc  = pixel * k[0]
        ldr     w20, [x7]
        madd    w19, w20, w10, w19      //   acc += pixel * k[1]
        ldr     w20, [x7, #4]
        madd    w19, w20, w11, w19      //   acc += pixel * k[2]
        ldr     w20, [x8], #4           // row y+1
        madd    w19, w20, w12, w19
        ldr     w20, [x8]
        madd    w19, w20, w13, w19
        ldr     w20, [x8, #4]
        madd    w19, w20, w14, w19
        ldr     w20, [x2], #4           // row y+2
        madd    w19, w20, w15, w19
        ldr     w20, [x2]
        madd    w19, w20, w16, w19
        ldr     w20, [x2, #4]
        madd    w19, w20, w17, w19
        str     w19, [x1], #4           // *out++ = acc
        subs    x6, x6, #1              // columns left--, sets the Z flag
        b.ne    4b

5:      add     x0, x0, x4              // next top row
        subs    x3, x3, #1              // rows left--
        b.ne    1b

        ldp     x19, x20, [sp], #16     // restore callee-saved registers
9:      ret
        .size   conv_asm, .-conv_asm

/* No executable stack needed (silences a linker warning). */
        .section .note.GNU-stack, "", %progbits
