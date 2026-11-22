/* Only paired Internet groups extend the anonymous native discovery datagram.
 * The receiver strips the extension before native validation and replay. */
enum {
    MENU_ROOM_DISCOVERY_STOCK_SIZE = BODY_AT + GAME_ID_SIZE,
    MENU_ROOM_DISCOVERY_TAG_SIZE = 4,
    MENU_ROOM_DISCOVERY_SIZE = MENU_ROOM_DISCOVERY_STOCK_SIZE + MENU_ROOM_DISCOVERY_TAG_SIZE + MENU_ROOM_TICKET_LENGTH,
};

static const unsigned char menu_room_discovery_tag[MENU_ROOM_DISCOVERY_TAG_SIZE] = {'A', 'G', 'R', '1'};

static const unsigned char *menu_room_read_discovery_ticket(const unsigned char *packet, int length)
{
    if (length != MENU_ROOM_DISCOVERY_SIZE || packet[9] != DISCOVERY ||
        memcmp(packet + MENU_ROOM_DISCOVERY_STOCK_SIZE, menu_room_discovery_tag,
               sizeof menu_room_discovery_tag) != 0)
        return NULL;
    return packet + MENU_ROOM_DISCOVERY_STOCK_SIZE + sizeof menu_room_discovery_tag;
}

static void menu_room_write_discovery(unsigned char *wire, const unsigned char *packet, const char *ticket)
{
    memcpy(wire, packet, MENU_ROOM_DISCOVERY_STOCK_SIZE);
    memcpy(wire + MENU_ROOM_DISCOVERY_STOCK_SIZE, menu_room_discovery_tag, sizeof menu_room_discovery_tag);
    memcpy(wire + MENU_ROOM_DISCOVERY_STOCK_SIZE + sizeof menu_room_discovery_tag, ticket, MENU_ROOM_TICKET_LENGTH);
}

__declspec(dllexport) int WSAAPI AnnoMenuSendRoomDiscovery(
    SOCKET socket, const char *data, int length, int flags, const struct sockaddr *address, int address_length)
{
    const TrialSettings *const plan = settings();
    const unsigned char *const packet = (const unsigned char *)data;
    const struct sockaddr_in *const to = (const struct sockaddr_in *)address;
    if (plan->role == TRIAL_GUEST && menu_room_transport(plan) && menu_internet_room(plan) &&
        packet && length == MENU_ROOM_DISCOVERY_STOCK_SIZE && !get16(packet) && get16(packet + 2) == length &&
        !packet[8] && packet[9] == DISCOVERY &&
        to && address_length == sizeof(*to) && to->sin_family == AF_INET &&
        to->sin_addr.s_addr == plan->peer && to->sin_port == htons(OWN_HOST_PORT)) {
        unsigned char extended[MENU_ROOM_DISCOVERY_SIZE];
        menu_room_write_discovery(extended, packet, plan->internet_tickets[0]);
        const int sent = sendto(socket, (const char *)extended, sizeof extended, flags, address, address_length);
        return sent == SOCKET_ERROR ? SOCKET_ERROR : length;
    }
    return sendto(socket, data, length, flags, address, address_length);
}
