"""Combined delivered-food score for the Food 0.6 housing simulation."""
from __future__ import annotations


def combined_score_code() -> bytes:
    """Return the position-independent AMD64 score helper.

    Private ABI: RCX is the house, EDX the owner's unlock mask, R8D is zero
    for growth and one for promotion. EAX returns the native 0–128 score.
    The helper is a stackless leaf using only volatile GPRs and XMM0–XMM5.

    For each eligible current-tier food, use the same floored native supply
    score and demand weight as the Food bar. Aggregate before final division
    and restore the vanilla current/next food demand ratio for promotion.
    """
    return bytes.fromhex(
        # Preflight the current household and needs table.
        "48 85 c9"                     # test rcx, rcx
        "0f 84 0b 01 00 00"            # jz zero
        "0f b7 41 52"                  # movzx eax, word [house+0x52] (population)
        "85 c0"                        # test eax, eax
        "0f 84 ff 00 00 00"            # jz zero
        "4c 8b 49 48"                  # mov r9, [house+0x48] (current needs)
        "4d 85 c9"                     # test r9, r9
        "0f 84 f2 00 00 00"            # jz zero
        "41 80 79 02 12"               # cmp byte [needs+2], 18
        "0f 87 e7 00 00 00"            # ja zero
        "49 83 b9 18 01 00 00 00"      # cmp qword [needs+0x118], 0 (goods)
        "0f 84 d9 00 00 00"            # je zero
        "66 0f 6e c2"                  # movd xmm0, edx (unlocks)
        "66 41 0f 6e c8"               # movd xmm1, r8d (promotion)
        "66 0f 6e d0"                  # movd xmm2, eax (population)
        "45 31 c0"                     # xor r8d, r8d (food index)
        "45 31 d2"                     # xor r10d, r10d (sum of active rates)
        "45 31 db"                     # xor r11d, r11d (sum of weighted scores)

        # check_food: map a good ID into this household's current needs.
        "48 8d 15 bf 00 00 00"         # lea rdx, [rip+food_ids]
        "42 0f b6 04 02"               # movzx eax, byte [rdx+r8]
        "41 0f b6 54 01 03"            # movzx edx, byte [needs+rax+3]
        "41 3a 51 02"                  # cmp dl, byte [needs+2]
        "73 71"                        # jae next_food
        "41 38 44 91 64"               # cmp byte [needs+rdx*4+0x64], al
        "75 6a"                        # jne next_food
        "66 0f 6e da"                  # movd xmm3, edx (need index)
        "6b c0 1a"                     # imul eax, eax, 26 (good record size)
        "49 8b 91 18 01 00 00"         # mov rdx, [needs+0x118]
        "0f b6 44 02 02"               # movzx eax, byte [rdx+rax+2] (unlock bit)
        "83 f8 20"                     # cmp eax, 32
        "73 52"                        # jae next_food
        "66 0f 7e c2"                  # movd edx, xmm0
        "0f a3 c2"                     # bt edx, eax
        "73 49"                        # jnc next_food
        "66 0f 7e d8"                  # movd eax, xmm3
        "41 0f b7 54 81 66"            # movzx edx, word [needs+rax*4+0x66] (rate)
        "85 d2"                        # test edx, edx
        "74 3b"                        # jz next_food

        # Add rate * min(128, stock * 1536 / (population * rate)).
        "41 01 d2"                     # add r10d, edx
        "66 0f 6e e2"                  # movd xmm4, edx
        "0f b7 44 41 54"               # movzx eax, word [house+rax*2+0x54]
        "69 c0 00 06 00 00"            # imul eax, eax, 1536
        "66 48 0f 6e e9"               # movq xmm5, rcx (save house)
        "66 0f 7e d1"                  # movd ecx, xmm2
        "0f af ca"                     # imul ecx, edx
        "31 d2 f7 f1"                  # xor edx, edx; div ecx
        "66 48 0f 7e e9"               # movq rcx, xmm5
        "ba 80 00 00 00"               # mov edx, 128
        "39 d0 0f 47 c2"               # cmp eax, edx; cmova eax, edx
        "66 0f 7e e2"                  # movd edx, xmm4
        "0f af c2 41 01 c3"            # imul eax, edx; add r11d, eax

        # next_food: each active rate is included even at zero stock.
        "41 ff c0 41 83 f8 05"         # inc r8d; cmp r8d, 5
        "0f 82 6a ff ff ff"            # jb check_food
        "45 85 d2 74 28"               # test r10d, r10d; jz zero
        "44 89 d8"                     # mov eax, r11d
        "41 80 39 00 75 0f"            # cmp byte [needs], 0 (Pioneer); jne score
        "66 0f 7e ca 85 d2 74 07"      # movd edx, xmm1; test edx, edx; jz score
        "6b c0 29 45 6b d2 25"         # imul eax, 41; imul r10d, 37

        # score: only Pioneers have a different rate from the next stock tier.
        "31 d2 41 f7 f2"               # xor edx, edx; div r10d
        "ba 80 00 00 00"               # mov edx, 128
        "39 d0 0f 47 c2 c3"            # cmp eax, edx; cmova eax, edx; ret
        "31 c0 c3"                     # zero: xor eax, eax; ret
        "1a 28 18 19 2d"               # food_ids: Fish, Potatoes, Game Meat, Bread, Butcher's Meat
    )
