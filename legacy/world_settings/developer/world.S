.include "common.inc"

# Native tProdStand remains 0x38 bytes. Bytes 0x28..0x2d are six
# independent switches; 0x30 is still the original linked pointer.
BEGIN market_enabled
mov rbx, rcx
mov edi, edx
xor esi, esi
xor r12d, r12d
enabled_loop:
mov rcx, [rbx+0x20]
mov edx, esi
mov rax, [rcx]
call [rax+0x160]
test eax, eax
jz enabled_next
cmp edi, 142
je enabled_any
cmp eax, edi
jne enabled_next
movzx eax, BYTE PTR [rbx+rsi+0x28]
jmp enabled_done
enabled_any:
cmp BYTE PTR [rbx+rsi+0x28], 0
je enabled_next
mov r12d, 1
enabled_next:
inc esi
cmp esi, 6
jb enabled_loop
mov eax, r12d
enabled_done:
END market_enabled

BEGIN market_set_enabled
mov rbx, rcx
mov edi, edx
xor r13d, r13d
test r8d, r8d
setne r13b
mov edx, 142
call market_enabled
mov r12d, eax
xor esi, esi
set_loop:
mov rcx, [rbx+0x20]
mov edx, esi
mov rax, [rcx]
call [rax+0x160]
test eax, eax
jz set_next
cmp eax, edi
jne set_next
mov BYTE PTR [rbx+rsi+0x28], r13b
jmp set_changed
set_next:
inc esi
cmp esi, 6
jb set_loop
jmp set_done
set_changed:
mov rcx, rbx
mov edx, 142
call market_enabled
mov rcx, rbx
mov edx, r12d
mov r8d, eax
call NATIVE_NOTIFY
set_done:
xor eax, eax
END market_set_enabled

BEGIN market_load_flags
mov rbx, rcx
mov edi, edx
xor esi, esi
load_loop:
mov rcx, [rbx+0x20]
mov edx, esi
mov rax, [rcx]
call [rax+0x160]
test eax, eax
jz load_next
mov rcx, rbx
mov edx, eax
mov r8d, edi
mov ecx, esi
shr r8d, cl
and r8d, 1
mov rcx, rbx
call market_set_enabled
load_next:
inc esi
cmp esi, 6
jb load_loop
END market_load_flags

.balign 16
.global market_pack_flags
.type market_pack_flags,@function
market_pack_flags:
mov r10, rcx
xor eax, eax
xor ecx, ecx
pack_loop:
movzx r11d, BYTE PTR [r10+rcx+0x28]
and r11d, 1
shl r11d, cl
or eax, r11d
inc ecx
cmp ecx, 6
jb pack_loop
mov rcx, r10
ret

# Houses retain their original two-good selector for all ordinary markets.
# For the Food market, apply the same need scoring, stock threshold, sale
# switch and in-transit exclusion to every exposed good.
BEGIN house_choose_good
mov rbx, rcx
mov r12, rdx
mov r13, r8
mov rcx, rdx
mov edx, 2
mov rax, [rcx]
call [rax+0x148]
test eax, eax
jnz house_six
mov rcx, rbx
mov rdx, r12
mov r8, r13
call NATIVE_HOUSE_CHOOSE
jmp house_done
house_six:
mov DWORD PTR [rsp+0x38], -1
xor esi, esi
house_collect_goods:
mov rcx, r12
mov edx, esi
mov rax, [rcx]
call [rax+0x148]
mov DWORD PTR [rsp+rsi*4+0x20], eax
inc esi
cmp esi, 6
jb house_collect_goods
mov DWORD PTR [rsp+0x40], 0
house_child_loop:
mov eax, DWORD PTR [rsp+0x40]
mov r15, [rbx+rax*8+0x28]
test r15, r15
jz house_child_next
mov rcx, r15
mov rax, [rcx]
call [rax+0xf8]
mov rcx, rax
xor edx, edx
mov rax, [rcx]
call [rax+0x118]
mov DWORD PTR [rsp+0x48], eax
mov DWORD PTR [rsp+0x44], 0
test eax, eax
jle house_child_next
house_cargo_loop:
mov rcx, r15
mov edx, DWORD PTR [rsp+0x44]
mov rax, [rcx]
call [rax+0x110]
test rax, rax
jz house_cargo_next
mov r14, rax
mov rcx, rax
mov rax, [rcx]
call [rax+0x10]
test eax, eax
jle house_cargo_next
mov rcx, r14
mov rax, [rcx]
call [rax+0x8]
xor edx, edx
house_exclude_good:
cmp eax, DWORD PTR [rsp+rdx*4+0x20]
jne house_exclude_next
mov DWORD PTR [rsp+rdx*4+0x20], 0
house_exclude_next:
inc edx
cmp edx, 6
jb house_exclude_good
house_cargo_next:
inc DWORD PTR [rsp+0x44]
mov eax, DWORD PTR [rsp+0x44]
cmp eax, DWORD PTR [rsp+0x48]
jl house_cargo_loop
house_child_next:
inc DWORD PTR [rsp+0x40]
cmp DWORD PTR [rsp+0x40], 4
jb house_child_loop
xor esi, esi
house_good_loop:
mov r14d, DWORD PTR [rsp+rsi*4+0x20]
test r14d, r14d
jz house_good_next
cmp r14d, 96
jae house_good_next
mov r15, [rbx+0x48]
movzx r8d, BYTE PTR [r15+r14+0x3]
movzx eax, BYTE PTR [r15+0x2]
cmp r8d, eax
jae house_good_next
mov DWORD PTR [rsp+0x4c], r8d
cmp WORD PTR [r15+r8*4+0x66], 0
je house_good_next
cmp WORD PTR [rbx+0x52], 0
je house_good_next
mov rcx, rbx
mov rdx, r15
call NATIVE_HOUSE_SCORE
cmp eax, DWORD PTR [rsp+0x38]
jle house_good_next
mov DWORD PTR [rsp+0x3c], eax
mov ecx, DWORD PTR [rsp+0x4c]
movzx r8d, WORD PTR [r15+rcx*4+0x66]
movsx eax, WORD PTR [rbx+0x50]
cdq
and edx, 63
add eax, edx
sar eax, 6
imul eax, r8d
shl eax, 8
cdq
and edx, 4095
add eax, edx
sar eax, 12
mov DWORD PTR [rsp+0x50], eax
mov rcx, r12
mov edx, r14d
mov rax, [rcx]
call [rax+0x150]
cmp eax, DWORD PTR [rsp+0x50]
jle house_good_next
mov rcx, r12
mov edx, r14d
mov rax, [rcx]
call [rax+0x190]
test eax, eax
jz house_good_next
mov eax, DWORD PTR [rsp+0x3c]
mov DWORD PTR [rsp+0x38], eax
test r13, r13
jz house_good_next
mov DWORD PTR [r13], r14d
house_good_next:
inc esi
cmp esi, 6
jb house_good_loop
mov eax, DWORD PTR [rsp+0x38]
house_done:
END house_choose_good

# City sale records cover goods 0..55. The original consumer-only guard
# bypasses stock removal for the three foods using raw/material IDs.
# Keep its exact native accounting/clamping body and broaden only admission.
.balign 16
.global food_record_sale
.type food_record_sale,@function
food_record_sale:
cmp edx, 24
je NATIVE_SALE_BODY
cmp edx, 25
je NATIVE_SALE_BODY
cmp edx, 45
je NATIVE_SALE_BODY
lea eax, [rdx-26]
cmp eax, 14
jbe NATIVE_SALE_BODY
jmp NATIVE_SALE_RETURN

# Native city income used an unrolled list of goods 26..40. Include the
# three additional food IDs, clear each pending sale count once, and let
# the original caller perform rounding, crediting and maintenance costs.
BEGIN food_income_total
mov rbx, rcx
mov r12, rdx
mov r13d, r8d
mov r14d, r9d
mov r15d, 128
xor esi, esi
income_good_loop:
lea rax, [rip+income_goods]
movzx edx, BYTE PTR [rax+rsi]
imul eax, edx, 26
lea rcx, [r12+rax]
movzx eax, WORD PTR [rcx+r13*2+4]
movzx ecx, WORD PTR [rcx+r14*2+18]
add eax, ecx
imul edx, edx, 12
movzx ecx, WORD PTR [rbx+rdx+0x47c]
mov WORD PTR [rbx+rdx+0x47c], 0
imul eax, ecx
add r15d, eax
inc esi
cmp esi, 18
jb income_good_loop
mov eax, r15d
END food_income_total
income_goods: .byte 26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,24,25,45
