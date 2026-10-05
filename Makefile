# Builds the two shared libraries that conv_bench.py loads with ctypes.
#
#   make          build build/libconv_c.so and build/libconv_asm.so
#   make clean    remove build/
#
# To cross-compile from a PC instead of the Pi:
#   make CC=aarch64-linux-gnu-gcc

CC     ?= gcc
CFLAGS := -O2 -Wall -Wextra -fPIC -shared
BUILD  := build

all: $(BUILD)/libconv_c.so $(BUILD)/libconv_asm.so

# C version, optimized by the compiler (-O2).
$(BUILD)/libconv_c.so: src/conv.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

# Hand-written assembly. gcc runs the assembler for us.
$(BUILD)/libconv_asm.so: src/conv_asm.S | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(BUILD)

.PHONY: all clean
