/* Accept a complete matching native roster snapshot. An unassigned flag can
 * appear more than once, but each picked colour belongs to one transport ID. */
static bool menu_room_reconcile_colors(unsigned char *roster, const unsigned char *records,
                                        unsigned int length, unsigned int seats)
{
    const unsigned int count = length / ROSTER_RECORD_SIZE;
    if (!roster || !records || seats < 2 || seats > MENU_ROOM_SEATS ||
        !count || count > seats || length % ROSTER_RECORD_SIZE)
        return false;

    unsigned char *nodes[MENU_ROOM_SEATS] = {NULL};
    unsigned char *node = *(unsigned char **)(roster + 0x20);
    for (unsigned int index = 0; index < count; ++index) {
        if (!node)
            return false;
        const uint32_t seat = get32(node + 0x20);
        if (seat >= seats || nodes[seat])
            return false;
        nodes[seat] = node;
        node = *(unsigned char **)(node + 8);
    }
    if (node)
        return false;

    unsigned int matched = 0, assigned = 0;
    for (unsigned int index = 0; index < count; ++index) {
        const unsigned char *const record = records + index * ROSTER_RECORD_SIZE;
        const uint32_t seat = get32(record + 0x10);
        const unsigned int color = record[ROSTER_COLOR];
        if (seat >= seats || !nodes[seat] || (matched & (1u << seat)) ||
            !roster_record_matches(record, nodes[seat]))
            return false;
        matched |= 1u << seat;
        if (color == 0xff)
            continue;
        if (!color || color > MENU_ROOM_SEATS || (assigned & (1u << color)))
            return false;
        assigned |= 1u << color;
    }

    for (unsigned int index = 0; index < count; ++index) {
        const unsigned char *const record = records + index * ROSTER_RECORD_SIZE;
        nodes[get32(record + 0x10)][NODE_COLOR] = record[ROSTER_COLOR];
    }
    return true;
}
