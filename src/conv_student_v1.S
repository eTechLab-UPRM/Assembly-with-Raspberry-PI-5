/*
 * conv_student_v1.S - YOUR assembly version: conv_asm_v1 (brute force).
 *
 * You do not need to edit this file by hand: Part 4 of lab.ipynb has your
 * part of the function in a notebook cell, and build_v1() writes it between
 * the two "YOUR CODE" markers below, builds it and measures it.
 *
 * ASM v1 is a direct ARM64 translation of C v2, the row-order C version you
 * wrote in Part 3: the same four loops, and every array index computed from
 * scratch with MUL, exactly as the C source says.
 *
 *   for y in 0..oh-1:                       label loop_y:  an output row
 *     for x in 0..ow-1:                     label loop_x:  an output pixel
 *       acc = 0
 *       for ky in 0..2:                     label loop_ky: a kernel row
 *         for kx in 0..2:                   label loop_kx: a kernel column
 *           acc += in[(y+ky)*w + (x+kx)] * k[ky*3 + kx]
 *       out[y*ow + x] = acc
 *
 * Everything is written except the core of the work: loading the kernel
 * coefficient, the multiply-add, and storing the output pixel. Until you
 * write it, the "ASM v1 brute (yours)" row says MISMATCH.
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
        b.lt    done                    //   then there is nothing to do
        cmp     x4, #3
        b.lt    done
        sub     x5, x3, #2              // oh = h - 2
        sub     x6, x4, #2              // ow = w - 2

        mov     x8, #0                  // y = 0
loop_y:
        mov     x7, #0                  //   x = 0
loop_x:
        mov     w9, #0                  //     acc = 0
        mov     x10, #0                 //     ky = 0
loop_ky:
        mov     x11, #0                 //       kx = 0
loop_kx:
        add     x12, x8, x10            //         y + ky
        mul     x12, x12, x4            //         (y + ky) * w
        add     x13, x7, x11            //         x + kx
        add     x12, x12, x13           //         index into in[]
        ldr     w14, [x0, x12, lsl #2]  //         pixel = in[index]   (lsl #2: * 4 bytes)

        // ---- YOUR CODE STARTS HERE ----
        // Step 1. Load the coefficient k[ky * 3 + kx] into w16.
        //    RISC-V: li t3, 3 / mul t3, s2, t3 / add t3, t3, s3 / slli + add + lw

        // Step 2. acc += pixel * coef   (acc is w9, pixel is w14, coef is w16)

        // ---- Given: the two kernel loops end here (do not change) ----
        add     x11, x11, #1            //         kx++
        cmp     x11, #3
        b.lt    loop_kx                 //         next kx while kx < 3
        add     x10, x10, #1            //       ky++
        cmp     x10, #3
        b.lt    loop_ky                 //       next ky while ky < 3

        // Step 3. out[y * ow + x] = acc
        //    RISC-V: mul t0, s1, s6 / add t0, t0, s0 / slli + add + sw
        // ---- YOUR CODE ENDS HERE ----

        add     x7, x7, #1              //     x++
        cmp     x7, x6
        b.lt    loop_x                  //     next x while x < ow
        add     x8, x8, #1              //   y++
        cmp     x8, x5
        b.lt    loop_y                  //   next y while y < oh
done:
        ret
        .size   conv_asm_v1, .-conv_asm_v1

/* No executable stack needed (silences a linker warning). */
        .section .note.GNU-stack, "", %progbits
