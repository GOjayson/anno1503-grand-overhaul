.include "common.inc"

BEGIN ui_create
mov rbx, rcx
call NATIVE_INIT
test eax, eax
js create_done
mov esi, 16
create_loop:
mov QWORD PTR [rsp+0x20], 0
mov rcx, rbx
mov edx, 0xb07
cmp esi, 20
jb create_kind
mov edx, 0xb17
cmp esi, 26
jb create_kind
mov edx, 0xb1c
create_kind:
lea r8, [rsp+0x20]
mov r9, [rbx+0x6c8]
mov rax, [rbx]
call [rax+0x178]
test eax, eax
js create_done
mov rdi, [rsp+0x20]
test rdi, rdi
jz create_error
mov rcx, rbx
mov rdx, rdi
mov r8d, esi
mov rax, [rbx]
call [rax+0x50]
cmp eax, 65535
je create_error
mov rcx, rdi
mov edx, esi
mov rax, [rdi]
call [rax+0x80]
cmp esi, 20
jae create_decoration
lea rax, [rip+callback2]
cmp esi, 16
je callback_selected
lea rax, [rip+callback3]
cmp esi, 17
je callback_selected
lea rax, [rip+callback4]
cmp esi, 18
je callback_selected
lea rax, [rip+callback5]
callback_selected:
mov [rdi+0x50], rax
mov [rdi+0x58], rbx
mov rcx, rdi
mov rdx, [rbx+0x710]
mov rax, [rdi]
call [rax+0x58]
# A tGadFlipWare needs its separate crossed-out overlay initialized.
# Copy the already resolved native overlay ID from the original Fish button.
mov rax, [rbx+0x750]
mov rax, [rax+6*8]
mov rax, [rax+0xb8]
mov edx, DWORD PTR [rax+0xa0]
mov rcx, rdi
call NATIVE_SET_OVERLAY
mov rcx, rdi
mov rdx, [rbx+0x738]
mov rax, [rdi]
call [rax+0x58]
mov rcx, rdi
mov edx, 50
mov r8d, 50
mov rax, [rdi]
call [rax+0xa8]
jmp create_park
create_decoration:
mov rcx, rdi
mov rdx, [rbx+0x710]
cmp esi, 26
jb create_parent
mov rdx, [rbx+0x730]
create_parent:
mov rax, [rdi]
call [rax+0x58]
mov rcx, rdi
mov edx, 71
mov r8d, 34
cmp esi, 26
jb create_size
mov edx, 40
mov r8d, 15
create_size:
mov rax, [rdi]
call [rax+0xa8]
cmp esi, 26
jb create_frame
mov QWORD PTR [rsp+0x38], 2
mov edx, 0x1c6
jmp create_property
create_frame:
# The resource lookup takes the access name inline in its output variant.
lea rcx, [rip+single_price_frame]
lea rdx, [rsp+0x38]
xor eax, eax
create_copy_name:
mov r8b, BYTE PTR [rcx+rax]
mov BYTE PTR [rdx+rax], r8b
inc eax
test r8b, r8b
jnz create_copy_name
mov rcx, [rbx+0x710]
mov edx, 0xa
lea r8, [rsp+0x30]
mov rax, [rcx]
call [rax+0x98]
mov edx, 0x198
create_property:
mov DWORD PTR [rsp+0x30], 0
lea r8, [rsp+0x30]
mov rcx, rdi
mov rax, [rdi]
call [rax+0xa0]
create_park:
mov rcx, rdi
mov edx, -10000
mov r8d, -10000
mov rax, [rdi]
call [rax+0xc0]
mov QWORD PTR [rsp+0x38], rbx
mov DWORD PTR [rsp+0x30], 0
lea r8, [rsp+0x30]
mov edx, 0x19d
mov rcx, rdi
mov rax, [rdi]
call [rax+0xa0]
inc esi
cmp esi, 32
jb create_loop
xor eax, eax
jmp create_done
create_error:
mov eax, 0x80004005
create_done:
END ui_create

# Native panel entry points are retained. These wrappers append the extra
# controls' layout/stock refresh without changing any other market view.
BEGIN ui_set_prod
mov rbx, rcx
call NATIVE_SET_PROD
mov r12d, eax
mov rcx, rbx
call ui_refresh_extra
mov eax, r12d
END ui_set_prod

BEGIN ui_update
mov rbx, rcx
call NATIVE_UPDATE
mov r12d, eax
mov rcx, rbx
call ui_refresh_extra
mov eax, r12d
END ui_update

BEGIN ui_tick
mov rbx, rcx
call NATIVE_TICK
mov rcx, rbx
call ui_refresh_extra
END ui_tick

BEGIN ui_layout
mov rbx, rcx
call NATIVE_LAYOUT
mov rcx, rbx
call ui_refresh_extra
END ui_layout

BEGIN ui_refresh_extra
mov rbx, rcx
mov DWORD PTR [rsp+0x30], 0
mov rax, [rbx+0x758]
sub rax, [rbx+0x750]
cmp rax, 256
jb refresh_done
mov r12, [rbx+0x7f8]
test r12, r12
jz refresh_done
mov rcx, r12
mov edx, 2
mov rax, [r12]
call [rax+0x148]
xor r14d, r14d
test eax, eax
setne r14b
mov rcx, rbx
mov edx, r14d
call ui_market_decoration
xor esi, esi
refresh_loop:
lea rax, [rip+widget_indices]
movzx eax, BYTE PTR [rax+rsi]
mov rdx, [rbx+0x750]
mov rdi, [rdx+rax*8]
test rdi, rdi
jz refresh_next
test r14d, r14d
jnz position_food
cmp esi, 2
jb position_original
mov rcx, rdi
xor edx, edx
xor r8d, r8d
mov rax, [rdi]
call [rax+0xa8]
mov edx, -10000
mov r8d, -10000
jmp set_position
position_original:
cvttss2si edx, DWORD PTR [rbx+0x6f8]
cvttss2si r8d, DWORD PTR [rbx+0x6fc]
add r8d, 331
imul eax, esi, 108
lea edx, [rdx+rax+45]
jmp set_position
position_food:
mov rcx, rdi
mov edx, 50
mov r8d, 50
mov rax, [rdi]
call [rax+0xa8]
lea rax, [rip+coordinates]
cvttss2si edx, DWORD PTR [rbx+0x6f8]
cvttss2si r8d, DWORD PTR [rbx+0x6fc]
add edx, DWORD PTR [rax+rsi*8]
add r8d, DWORD PTR [rax+rsi*8+4]
set_position:
mov rcx, rdi
mov rax, [rdi]
call [rax+0xc0]
test r14d, r14d
jz refresh_next
mov rcx, r12
mov edx, esi
mov rax, [r12]
call [rax+0x148]
mov r13d, eax
test eax, eax
jz refresh_next
mov ecx, eax
call ui_find_gfx
mov DWORD PTR [rsp+0x38], eax
lea r8, [rsp+0x30]
mov edx, 0x198
mov rcx, rdi
mov rax, [rdi]
call [rax+0xa0]
lea rax, [rip+GOOD_LABELS]
mov eax, r13d
lea rdx, [rip+GOOD_LABELS]
mov rax, [rdx+rax*8]
test rax, rax
jnz have_label
lea rax, [rip+empty_string]
have_label:
mov [rsp+0x38], rax
lea r8, [rsp+0x30]
mov edx, 0x1c9
mov rcx, rdi
mov rax, [rdi]
call [rax+0xa0]
mov rcx, r12
mov edx, r13d
mov rax, [r12]
call [rax+0x150]
test eax, eax
jns quantity_positive
xor eax, eax
quantity_positive:
shr eax, 8
mov ecx, eax
lea rdx, [rsp+0x40]
mov r8d, 10
call [rip+ITOA_IAT]
lea rax, [rsp+0x40]
mov [rsp+0x38], rax
lea r8, [rsp+0x30]
mov edx, 0x1c4
mov rcx, rdi
mov rax, [rdi]
call [rax+0xa0]
mov rcx, r12
mov edx, r13d
mov rax, [r12]
call [rax+0x190]
test eax, eax
sete al
movzx eax, al
mov DWORD PTR [rsp+0x38], eax
lea r8, [rsp+0x30]
mov edx, 0x1ad
mov rcx, rdi
mov rax, [rdi]
call [rax+0xa0]
refresh_next:
inc esi
cmp esi, 6
jb refresh_loop
mov rcx, rbx
mov edx, r14d
call ui_prices
refresh_done:
xor eax, eax
END ui_refresh_extra

# Move the preview up 20 pixels to clear the six-slot grid. Hide the old
# two-branch connectors and two price labels. Six new text widgets follow
# all six opaque frames in the actual native draw vector.
# Selecting any other stand restores every affected decoration explicitly.
BEGIN ui_market_decoration
mov rbx, rcx
lea r12, [rip+decoration_original]
test edx, edx
jz decoration_selected
lea r12, [rip+decoration_food]
decoration_selected:
xor esi, esi
decoration_loop:
lea rax, [rip+decoration_indices]
movzx eax, BYTE PTR [rax+rsi]
mov rdx, [rbx+0x750]
mov rdi, [rdx+rax*8]
test rdi, rdi
jz decoration_next
mov edx, DWORD PTR [r12+rsi*8]
mov r8d, DWORD PTR [r12+rsi*8+4]
test edx, edx
js decoration_position
cvttss2si eax, DWORD PTR [rbx+0x6f8]
add edx, eax
cvttss2si eax, DWORD PTR [rbx+0x6fc]
add r8d, eax
decoration_position:
mov rcx, rdi
mov rax, [rdi]
call [rax+0xc0]
cmp esi, 4
jb decoration_next
cmp esi, 5
ja decoration_next
mov rcx, rdi
mov edx, 50
mov r8d, 15
mov rax, [rdi]
call [rax+0xa8]
decoration_next:
inc esi
cmp esi, 7
jb decoration_loop
xor eax, eax
END ui_market_decoration

BEGIN ui_prices
mov rbx, rcx
mov DWORD PTR [rsp+0x30], 0
mov r14d, edx
mov r12, [rbx+0x7f8]
# Extra text/background gadgets must also disappear on ordinary stands.
mov esi, 20
price_hide_loop:
mov rax, [rbx+0x750]
mov rcx, [rax+rsi*8]
mov edx, -10000
mov r8d, -10000
mov rax, [rcx]
call [rax+0xc0]
inc esi
cmp esi, 32
jb price_hide_loop
test r14d, r14d
jz prices_done
# Resolve the same city climate and world price level as native View+4ab90.
mov rcx, r12
mov rax, [rcx]
call [rax+0xb0]
mov esi, eax
mov rcx, r12
mov rax, [rcx]
call [rax+0xb8]
mov edi, eax
mov rcx, [rbx+0x7e8]
mov rax, [rcx]
call [rax+0x120]
mov rcx, rax
mov edx, esi
mov r8d, edi
mov rax, [rcx]
call [rax+0x120]
test rax, rax
jz prices_done
mov rcx, rax
mov edx, 7
mov rax, [rcx]
call [rax+0x190]
mov DWORD PTR [rsp+0x60], eax
mov rcx, [rbx+0x7e8]
mov rax, [rcx]
call [rax+0x120]
mov rcx, rax
mov edx, 10
mov rax, [rcx]
call [rax+0xf0]
mov DWORD PTR [rsp+0x64], eax
mov rcx, [rbx+0x7c8]
mov rax, [rcx]
call [rax+0xe0]
mov rcx, rax
mov rax, [rcx]
call [rax+0x10]
mov r15, rax
xor esi, esi
price_loop:
mov rcx, r12
mov edx, esi
mov rax, [rcx]
call [rax+0x148]
imul eax, eax, 26
lea rdx, [r15+rax]
mov eax, DWORD PTR [rsp+0x60]
movzx ecx, WORD PTR [rdx+rax*2+4]
mov eax, DWORD PTR [rsp+0x64]
movzx eax, WORD PTR [rdx+rax*2+18]
add ecx, eax
lea rdx, [rsp+0x40]
mov r8d, 10
call [rip+ITOA_IAT]
lea rax, [rip+price_indices]
movzx eax, BYTE PTR [rax+rsi]
mov rdx, [rbx+0x750]
mov rdi, [rdx+rax*8]
lea rax, [rsp+0x40]
mov QWORD PTR [rsp+0x38], rax
lea r8, [rsp+0x30]
mov edx, 0x1c4
mov rcx, rdi
mov rax, [rdi]
call [rax+0xa0]
mov rcx, rdi
mov edx, 40
mov r8d, 15
mov rax, [rdi]
call [rax+0xa8]
lea rax, [rip+price_coordinates]
cvttss2si edx, DWORD PTR [rbx+0x6f8]
cvttss2si r8d, DWORD PTR [rbx+0x6fc]
add edx, DWORD PTR [rax+rsi*8]
add r8d, DWORD PTR [rax+rsi*8+4]
mov rcx, rdi
mov rax, [rdi]
call [rax+0xc0]
mov rax, [rbx+0x750]
mov rcx, [rax+rsi*8+20*8]
lea rax, [rip+frame_coordinates]
cvttss2si edx, DWORD PTR [rbx+0x6f8]
cvttss2si r8d, DWORD PTR [rbx+0x6fc]
add edx, DWORD PTR [rax+rsi*8]
add r8d, DWORD PTR [rax+rsi*8+4]
mov rax, [rcx]
call [rax+0xc0]
inc esi
cmp esi, 6
jb price_loop
prices_done:
xor eax, eax
END ui_prices

.balign 16
.global ui_find_gfx
.type ui_find_gfx,@function
ui_find_gfx:
lea rdx, [rip+GOOD_GFX]
mov r8d, 143
gfx_loop:
cmp ecx, DWORD PTR [rdx]
je gfx_found
add rdx, 12
dec r8d
jnz gfx_loop
mov eax, -1
ret
gfx_found:
mov eax, [rdx+8]
ret

.global callback2,callback3,callback4,callback5
callback2: mov edx, 2
jmp ui_toggle
callback3: mov edx, 3
jmp ui_toggle
callback4: mov edx, 4
jmp ui_toggle
callback5: mov edx, 5
jmp ui_toggle

BEGIN ui_toggle
mov rbx, rcx
mov r12, [rbx+0x7f8]
test r12, r12
jz toggle_done
mov rcx, r12
mov rax, [r12]
call [rax+0x148]
mov esi, eax
test eax, eax
jz toggle_done
mov rcx, r12
mov edx, esi
mov rax, [r12]
call [rax+0x190]
xor edi, edi
test eax, eax
sete dil
mov rcx, [rbx+0x7e8]
mov rax, [rcx]
call [rax+0x140]
mov rcx, rax
mov edx, esi
mov r8d, edi
mov r9, r12
mov rax, [rax]
call [rax+0xd8]
toggle_done:
xor eax, eax
END ui_toggle

widget_indices: .byte 6,7,16,17,18,19
.balign 4
coordinates: .long 22,278,97,278,172,278,22,362,97,362,172,362
price_indices: .byte 26,27,28,29,30,31
.balign 4
price_coordinates: .long 37,338,112,338,187,338,37,422,112,422,187,422
frame_coordinates: .long 12,328,87,328,162,328,12,412,87,412,162,412
decoration_indices: .byte 2,3,4,5,8,9,15
.balign 4
decoration_original: .long 60,286,168,286,60,153,55,143,70,393,178,393,35,383
decoration_food: .long -10000,-10000,-10000,-10000,60,133,55,123,-10000,-10000,-10000,-10000,-10000,-10000
empty_string: .byte 0
single_price_frame: .asciz "MARKTSTAND_RAHMEN_1"

.include "categories.inc"
