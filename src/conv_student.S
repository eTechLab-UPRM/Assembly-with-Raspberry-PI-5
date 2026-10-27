/*
 * conv_student.S - YOUR assembly version: conv_asm_v3 (MAC).
 *
 * This file starts as an exact copy of conv_asm_v2 from src/conv_asm.S.
 * Run "make" and "python3 conv_bench.py": the "ASM v3 MAC (yours)" row is
 * correct (OK) but no faster than v2, because the code is the same.
 *
 * YOUR TASK
 * ---------
 * In v2 every kernel tap after the first one takes two instructions:
 *
 *         mul     w20, w20, w10           // product = pixel * k[1]
 *         add     w19, w19, w20           // acc     = acc + product
 *
 * This is how you would write it in RISC-V (Ripes) too: RV32IM has no
 * instruction that multiplies and adds at once. ARM64 has one, a
 * multiply-accumulate (MAC) instruction:
 *
 *         madd    Wd, Wn, Wm, Wa          // Wd = Wa + Wn * Wm
 *
 * Replace each of the 8 MUL + ADD pairs marked TODO below with ONE madd
 * instruction that gives the same result. Then:
 *
 *   1. make                                     (rebuild; fix any error)
 *   2. python3 conv_bench.py --skip-python      (quick check)
 *
 * Your row must say OK. Compare its time with ASM v2.
 *
 * Coming from RISC-V? Part 2 of lab.ipynb has a RISC-V (Ripes) -> ARM64
 * table of registers and instructions.
 *
 * Hints: acc lives in w19 and the pixel in w20. Keep the first
 * "mul w19, w20, w9" as it is: it starts the sum (acc = pixel * k[0]).
 * If something goes wrong, "git checkout src/conv_student.S" restores
 * the original file.
 *
 * Same prototype and registers as conv_asm_v2 (see src/conv_asm.S):
 *
 *   void conv_asm_v3(const int32_t *in, int32_t *out, const int32_t *k,
 *                    long h, long w);
 */

        .text

        .global conv_asm_v3
        .type   conv_asm_v3, %function
conv_asm_v3:
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
        mul     w20, w20, w10           // TODO 1: fuse this MUL ...
        add     w19, w19, w20           //         ... and this ADD into one MADD
        ldr     w20, [x7, #4]           //          in[y][x+2]
        mul     w20, w20, w11           // TODO 2: fuse this MUL ...
        add     w19, w19, w20           //         ... and this ADD into one MADD

        ldr     w20, [x8], #4           // row y+1
        mul     w20, w20, w12           // TODO 3: fuse this MUL ...
        add     w19, w19, w20           //         ... and this ADD into one MADD
        ldr     w20, [x8]
        mul     w20, w20, w13           // TODO 4: fuse this MUL ...
        add     w19, w19, w20           //         ... and this ADD into one MADD
        ldr     w20, [x8, #4]
        mul     w20, w20, w14           // TODO 5: fuse this MUL ...
        add     w19, w19, w20           //         ... and this ADD into one MADD

        ldr     w20, [x2], #4           // row y+2
        mul     w20, w20, w15           // TODO 6: fuse this MUL ...
        add     w19, w19, w20           //         ... and this ADD into one MADD
        ldr     w20, [x2]
        mul     w20, w20, w16           // TODO 7: fuse this MUL ...
        add     w19, w19, w20           //         ... and this ADD into one MADD
        ldr     w20, [x2, #4]
        mul     w20, w20, w17           // TODO 8: fuse this MUL ...
        add     w19, w19, w20           //         ... and this ADD into one MADD

        str     w19, [x1], #4           // *out++ = acc
        subs    x6, x6, #1              // columns left--, sets the Z flag
        b.ne    2b

        add     x0, x0, x4              // next top row
        subs    x3, x3, #1              // rows left--
        b.ne    1b

        ldp     x19, x20, [sp], #16     // restore callee-saved registers
9:      ret
        .size   conv_asm_v3, .-conv_asm_v3

/* No executable stack needed (silences a linker warning). */
        .section .note.GNU-stack, "", %progbits
