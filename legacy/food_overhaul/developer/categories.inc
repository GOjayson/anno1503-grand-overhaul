# Goods keep their stock/save IDs. Category menus enumerate this presentation
# order rather than assuming that every consumer good lies between 26 and 40.
# The five foods occupy the first five cells, then the remaining native needs.
.macro CATEGORY_NEXT name, reg
.balign 16
.global \name
.type \name,@function
\name:
cmp \reg,26
je .Lgame\@
cmp \reg,24
je .Lpotato\@
cmp \reg,40
je .Lbread\@
cmp \reg,25
je .Lmeat\@
cmp \reg,45
je .Lcloth\@
cmp \reg,39
je .Lend\@
inc \reg
jmp .Lcompare\@
.Lgame\@: mov \reg,24
jmp .Lcompare\@
.Lpotato\@: mov \reg,40
jmp .Lcompare\@
.Lbread\@: mov \reg,25
jmp .Lcompare\@
.Lmeat\@: mov \reg,45
jmp .Lcompare\@
.Lcloth\@: mov \reg,27
jmp .Lcompare\@
.Lend\@: mov \reg,46
.Lcompare\@:
# Replaces the original inc+cmp exactly; the native JLE consumes these flags.
cmp \reg,45
ret
.size \name,.-\name
.endm
CATEGORY_NEXT category_next_edi, edi
CATEGORY_NEXT category_next_esi, esi

.balign 16
.global category_grid_gfx, category_city_gfx
.type category_grid_gfx,@function
category_grid_gfx:
mov r11d,edi
jmp category_store_gfx
category_city_gfx:
mov r11d,esi
category_store_gfx:
lea r10,[rip+GOOD_GFX]
mov eax,143
category_gfx_loop:
cmp DWORD PTR [r10],r11d
je category_gfx_found
add r10,12
dec eax
jnz category_gfx_loop
mov eax,-1
jmp category_gfx_store
category_gfx_found:
mov eax,DWORD PTR [r10+8]
category_gfx_store:
# Both call sites store a variant at caller RSP+30. Only the displaced
# value write/LEA are replaced; preserve RCX and all nonvolatile registers.
lea r8,[rsp+0x38]
mov DWORD PTR [rsp+0x40],eax
ret

.balign 16
.global consumer_goods
consumer_goods:
.long 26,24,40,25,45,27,28,29,30,31,32,33,34,35,36,37,38,39,0,0
