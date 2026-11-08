.include "common.inc"
.global food_get_ware
.type food_get_ware,@function
food_get_ware:
movzx eax, dl
cmp eax, 2
jb original
cmp eax, 6
jae empty
cmp WORD PTR [rcx+0x20e], 0x1c1a
jne empty
sub eax, 2
lea rdx, [rip+extra_goods]
movzx eax, BYTE PTR [rdx+rax]
ret
original:
movzx eax, BYTE PTR [rcx+rax+0x20e]
ret
empty:
xor eax, eax
ret
extra_goods: .byte 24,40,25,45
.global potato_name,bread_name,meat_name
potato_name: .asciz "KART2"
bread_name: .asciz "BROT2"
meat_name: .asciz "MEAT2"
