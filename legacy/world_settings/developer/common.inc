.intel_syntax noprefix
.section .text
.macro BEGIN name
.balign 16
.global \name, \name\()_prolog_end, \name\()_end
.type \name, @function
\name:
push rbx
push rsi
push rdi
push r12
push r13
push r14
push r15
sub rsp, 128
\name\()_prolog_end:
.endm
.macro END name
add rsp, 128
pop r15
pop r14
pop r13
pop r12
pop rdi
pop rsi
pop rbx
ret
\name\()_end:
.size \name, .-\name
.endm
