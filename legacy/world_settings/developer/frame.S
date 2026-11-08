.include "common.inc"

# The local and network command validators use definition input-count(0)
# to authorize sale switches. Extend only these two callers; the compiled
# two-byte definition and all unrelated production-count users stay intact.
.global market_command_count
.type market_command_count,@function
market_command_count:
test edx, edx
jnz command_original_count
cmp WORD PTR [rcx+0x20e], 0x1c1a
jne command_original_count
mov eax, 6
ret
command_original_count:
mov rax, [rcx]
jmp [rax+0x1c0]
