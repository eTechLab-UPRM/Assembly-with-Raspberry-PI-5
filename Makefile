# Builds the shared libraries that conv_bench.py loads with ctypes.
#
#   make          build everything into build/
#   make clean    remove build/
#
# To cross-compile from a PC instead of the Pi:
#   make CC=aarch64-linux-gnu-gcc

CC     ?= gcc
CFLAGS := -O2 -Wall -Wextra -fPIC -shared
BUILD  := build

all: $(BUILD)/libconv_c.so $(BUILD)/libconv_student_c.so $(BUILD)/libconv_student_v1.so \
     $(BUILD)/libconv_asm.so $(BUILD)/libconv_student.so

# C v1, optimized by the compiler (-O2).
$(BUILD)/libconv_c.so: src/conv.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

# C v2, the one students write. As for v3 below, the old library is deleted
# first. Unused variables are not reported: the starting file is empty.
$(BUILD)/libconv_student_c.so: src/conv_student_c.c | $(BUILD)
	rm -f $@
	$(CC) $(CFLAGS) -Wno-unused-parameter -Wno-unused-variable -o $@ $<

# Assembly v1: students write its second half. Rebuilt from scratch too.
$(BUILD)/libconv_student_v1.so: src/conv_student_v1.S | $(BUILD)
	rm -f $@
	$(CC) $(CFLAGS) -o $@ $<

# Hand-written assembly, versions v2 and v4. gcc runs the assembler.
$(BUILD)/libconv_asm.so: src/conv_asm.S | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

# Version v3, the one students write, in its own library. The old library is
# deleted first, so a file that fails to assemble shows up as NOT BUILT
# instead of silently running the previous version.
$(BUILD)/libconv_student.so: src/conv_student.S | $(BUILD)
	rm -f $@
	$(CC) $(CFLAGS) -o $@ $<

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(BUILD)

.PHONY: all clean
