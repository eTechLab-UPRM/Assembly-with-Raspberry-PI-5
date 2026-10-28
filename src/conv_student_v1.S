/*
 * conv_student_v1.S - YOUR assembly version: conv_asm_v1 (brute force).
 *
 * You do not need to edit this file by hand: Part 4 of lab.ipynb has your
 * half of the function in a notebook cell, and build_v1() writes it between
 * the two "YOUR CODE" markers below, builds it and measures it.
 *
 * ASM v1 is a direct ARM64 translation of C v2, the row-order C version you
 * wrote in Part 3: the same four loops, and every array index computed from
 * scratch with MUL, exactly as the C source says.
 *
 *   for y in 0..oh-1:                       label 1: start of an output row
 *     for x in 0..ow-1:                     label 2: start of an output pixel
 *       acc = 0
 *       for ky in 0..2:                     label 3: start of a kernel row
 *         for kx in 0..2:                   label 4: start of a kernel column
 *           acc += in[(y+ky)*w + (x+kx)] * k[ky*3 + kx]
 *       out[y*ow + x] = acc
 *
 * The first half (up to loading the pixel) is written below. You write the
 * second half. Until you do, the "ASM v1 brute (yours)" row says MISMATCH.
 *
 * C prototype:
 *
 *   void conv_asm_v1(const int32_t *in, int32_t *out, const int32_t *k,
 *                    long h, long w);
 *
 * Registers (the same roles as the RISC-V comments in src/conv.c):
 *
 *   x0 = in    x1 = out   x2 = k    x3 = h    x4 = w    (the arguments)
 *   x5 = oh    x6 = ow
 *   x7 = x     x8 = y     x10 = ky  x11 = kx  w9 = acc
 *   x12..x16 = temporaries (w14 = the pixel)
 *
 * All of them are scratch registers in ARM64, so nothing has to be saved
 * on the stack.
 */

        .text

        .global conv_asm_v1
        .type   conv_asm_v1, %function
conv_asm_v1:
        cmp     x3, #3                  // image smaller than the kernel?
        b.lt    9f                      //   then there is nothing to do
        cmp     x4, #3
        b.lt    9f
        sub     x5, x3, #2              // oh = h - 2
        sub     x6, x4, #2              // ow = w - 2

        mov     x8, #0                  // y = 0
1:      mov     x7, #0                  //   x = 0
2:      mov     w9, #0                  //     acc = 0
        mov     x10, #0                 //     ky = 0
3:      mov     x11, #0                 //       kx = 0
4:      add     x12, x8, x10            //         y + ky
        mul     x12, x12, x4            //         (y + ky) * w
        add     x13, x7, x11            //         x + kx
        add     x12, x12, x13           //         index into in[]
        ldr     w14, [x0, x12, lsl #2]  //         pixel = in[index]   (lsl #2: * 4 bytes)

        // ---- YOUR CODE STARTS HERE ----
        // 1. Load the coefficient k[ky * 3 + kx] into w16.
        //    RISC-V: li t3, 3 / mul t3, s2, t3 / add t3, t3, s3 / slli + add + lw

        // 2. acc += pixel * coef  (acc is w9, pixel is w14, coef is w16).

        // 3. kx++, and go back to label 4 while kx < 3.

        // 4. ky++, and go back to label 3 while ky < 3.

        // 5. out[y * ow + x] = acc.

        // 6. x++, and go back to label 2 while x < ow.

        // 7. y++, and go back to label 1 while y < oh.
        // ---- YOUR CODE ENDS HERE ----

9:      ret
        .size   conv_asm_v1, .-conv_asm_v1

/* No executable stack needed (silences a linker warning). */
        .section .note.GNU-stack, "", %progbits
