/* The room admits UDP endpoints that completed TCP pairing. Internet
 * discovery also proves which paired player is behind a shared public address. */
enum {
    MENU_ROOM_NEXT_SEAT = MENU_ROOM_SEATS,
    MENU_ROOM_NO_SEAT,
    MENU_ROOM_SOCKET_ROWS = 0xdbc,
    MENU_ROOM_SOCKET_ROW_SIZE = 0x18,
    MENU_ROOM_SOCKET_ROW_INDEX = 0x14,
    MENU_ROOM_SOCKET_MUTEX = 0x5a8,
    MENU_ROOM_JOIN_NAME_SIZE = 28,
    MENU_ROOM_JOIN_NAME_START = 30,
};

static struct {
    SOCKET listener;
    uint16_t discovered_port[MENU_ROOM_SEATS - 1];
} menu_room_admission;

static uint32_t menu_room_guest_address(const TrialSettings *plan, unsigned int peer)
{
    return peer ? plan->extra_guests[peer - 1].address : plan->peer;
}

static const char *menu_room_guest_name(const TrialSettings *plan, unsigned int peer)
{
    return peer ? plan->extra_guests[peer - 1].name : plan->guest_name;
}

static bool menu_room_has_source(const TrialSettings *plan, uint32_t address)
{
    if (!menu_room_transport(plan) || plan->role != TRIAL_HOST || !address || address == plan->local)
        return false;
    for (unsigned int peer = 0; peer <= plan->extra_guest_count; ++peer) {
        if (address == menu_room_guest_address(plan, peer))
            return true;
    }
    return false;
}

/* Call under the native queue mutex. A JOIN has no ticket and must reuse the
 * source endpoint that proved it during discovery. */
static unsigned int menu_room_find_peer(const TrialSettings *plan, const struct sockaddr_in *sender,
                                       const unsigned char *ticket)
{
    const bool internet = menu_internet_room(plan);
    for (unsigned int peer = 0; peer <= plan->extra_guest_count; ++peer) {
        if (sender->sin_addr.s_addr != menu_room_guest_address(plan, peer))
            continue;
        if (!internet || (ticket ?
            memcmp(ticket, plan->internet_tickets[peer], MENU_ROOM_TICKET_LENGTH) == 0 :
            menu_room_admission.discovered_port[peer] == sender->sin_port))
            return peer;
    }
    return MENU_ROOM_NO_SEAT;
}

static void menu_room_reset_listener(SOCKET listener)
{
    menu_room_admission.listener = listener;
    memset(menu_room_admission.discovered_port, 0, sizeof menu_room_admission.discovered_port);
}

static HANDLE menu_room_acquire(const unsigned char *server)
{
    const HANDLE mutex = *(const HANDLE *)(server + MENU_ROOM_SOCKET_MUTEX);
    if (!mutex)
        return NULL;
    const DWORD state = WaitForSingleObject(mutex, 100);
    if (state == WAIT_OBJECT_0)
        return mutex;
    if (state == WAIT_ABANDONED)
        ReleaseMutex(mutex);
    return NULL;
}

static const unsigned char *menu_room_socket_row(const unsigned char *server, unsigned int row)
{
    return server + MENU_ROOM_SOCKET_ROWS + MENU_ROOM_SOCKET_ROW_SIZE * row;
}

/* Read the installed stock row under the server mutex. */
static const char *menu_room_row_name(const TrialSettings *plan, const unsigned char *bytes,
                                      unsigned int seat, unsigned int *peer)
{
    const struct sockaddr_in *const endpoint = (const struct sockaddr_in *)bytes;
    if (endpoint->sin_family != AF_INET || !endpoint->sin_port || get32(bytes + MENU_ROOM_SOCKET_ROW_INDEX) != seat)
        return NULL;
    *peer = menu_room_find_peer(plan, endpoint, NULL);
    return *peer != MENU_ROOM_NO_SEAT && menu_room_admission.discovered_port[*peer] == endpoint->sin_port ?
        menu_room_guest_name(plan, *peer) : NULL;
}

static bool menu_room_all_admitted(const TrialSettings *plan, const unsigned char *server)
{
    if (!server || !menu_room_transport(plan) || plan->role != TRIAL_HOST)
        return false;
    const HANDLE mutex = menu_room_acquire(server);
    if (!mutex)
        return false;
    const unsigned char *const first = menu_room_socket_row(server, 0);
    const struct sockaddr_in *const host = (const struct sockaddr_in *)first;
    bool complete = host->sin_family == AF_INET && host->sin_port && host->sin_addr.s_addr == plan->local &&
        !get32(first + MENU_ROOM_SOCKET_ROW_INDEX);
    unsigned int seen = 0;
    for (unsigned int seat = 1; complete && seat < plan->player_count; ++seat) {
        unsigned int peer = 0;
        complete = menu_room_row_name(plan, menu_room_socket_row(server, seat), seat, &peer) &&
            !(seen & (1u << peer));
        seen |= 1u << peer;
    }
    for (unsigned int seat = plan->player_count; complete && seat < MENU_ROOM_SEATS; ++seat)
        complete = !get16(menu_room_socket_row(server, seat) + 2);
    ReleaseMutex(mutex);
    return complete;
}

static bool menu_room_join_name(const unsigned char *packet, unsigned int length, const char *name)
{
    if (!valid_trial_name(name))
        return false;
    const size_t characters = strlen(name);
    const size_t bytes = 2 * characters;
    if (characters > MENU_ROOM_NAME_LENGTH || length < MENU_ROOM_JOIN_NAME_START + bytes ||
        packet[MENU_ROOM_JOIN_NAME_SIZE] != bytes)
        return false;
    for (size_t index = 0; index < characters; ++index) {
        if (get16(packet + MENU_ROOM_JOIN_NAME_START + 2 * index) != (unsigned char)name[index])
            return false;
    }
    return true;
}

/* Called under the native server queue mutex, before linking the request. */
static unsigned int menu_room_queue_seat(const unsigned char *server, const unsigned char *packet,
                                         unsigned int length, int kind, const struct sockaddr_in *sender,
                                         const unsigned char *ticket, unsigned int *admitted_peer)
{
    const TrialSettings *const plan = settings();
    const bool internet = menu_internet_room(plan);
    if (sender->sin_family != AF_INET || !sender->sin_port || (kind != DISCOVERY && kind != JOIN) ||
        !menu_room_has_source(plan, sender->sin_addr.s_addr) ||
        ((ticket != NULL) != (internet && kind == DISCOVERY)))
        return MENU_ROOM_NO_SEAT;
    const unsigned int peer = menu_room_find_peer(plan, sender, ticket);
    if (peer == MENU_ROOM_NO_SEAT)
        return MENU_ROOM_NO_SEAT;
    const uint16_t port = menu_room_admission.discovered_port[peer];
    if ((port && port != sender->sin_port) ||
        (kind == JOIN && (!port || !menu_room_join_name(packet, length, menu_room_guest_name(plan, peer)))))
        return MENU_ROOM_NO_SEAT;
    if (internet && ticket && !port) {
        /* A second ticket cannot claim an already paired endpoint. */
        for (unsigned int other = 0; other <= plan->extra_guest_count; ++other) {
            if (sender->sin_addr.s_addr == menu_room_guest_address(plan, other) &&
                sender->sin_port == menu_room_admission.discovered_port[other])
                return MENU_ROOM_NO_SEAT;
        }
    }

    /* This first-free scan matches the stock JOIN consumer. No row means
     * the peer is pending even if its request was previously enqueued. */
    if (!get16(menu_room_socket_row(server, 0) + 2))
        return MENU_ROOM_NO_SEAT;
    unsigned int first_free = MENU_ROOM_NO_SEAT;
    for (unsigned int row = 1; row < MENU_ROOM_SEATS; ++row) {
        const unsigned char *const bytes = menu_room_socket_row(server, row);
        const struct sockaddr_in *const endpoint = (const struct sockaddr_in *)bytes;
        if (!endpoint->sin_port) {
            if (first_free == MENU_ROOM_NO_SEAT)
                first_free = row;
        } else if (endpoint->sin_addr.s_addr == sender->sin_addr.s_addr &&
                   (!internet || endpoint->sin_port == sender->sin_port)) {
            /* The first JOIN reply may have been lost. The native duplicate
             * path acknowledges the existing row without adding another. */
            if (kind == JOIN && row < plan->player_count && endpoint->sin_family == AF_INET &&
                endpoint->sin_port == sender->sin_port && get32(bytes + MENU_ROOM_SOCKET_ROW_INDEX) == row) {
                *admitted_peer = peer;
                return row;
            }
            return MENU_ROOM_NO_SEAT;
        }
    }
    *admitted_peer = peer;
    return first_free < plan->player_count ? first_free : MENU_ROOM_NO_SEAT;
}

/* Called only after successful insertion while the same queue lock is held. */
static void menu_room_request_queued(int kind, const struct sockaddr_in *sender, unsigned int peer)
{
    if (kind == DISCOVERY)
        menu_room_admission.discovered_port[peer] = sender->sin_port;
}

static unsigned int menu_room_receive_seat(const unsigned char *server, SOCKET listener,
                                           const struct sockaddr_in *sender, bool established)
{
    const TrialSettings *const plan = settings();
    if (listener != menu_room_admission.listener || sender->sin_family != AF_INET || !sender->sin_port ||
        !menu_room_has_source(plan, sender->sin_addr.s_addr))
        return MENU_ROOM_NO_SEAT;
    if (!established)
        return MENU_ROOM_NEXT_SEAT;

    const HANDLE mutex = menu_room_acquire(server);
    if (!mutex)
        return MENU_ROOM_NO_SEAT;
    unsigned int seat = MENU_ROOM_NO_SEAT;
    const unsigned int peer = menu_room_find_peer(plan, sender, NULL);
    if (peer != MENU_ROOM_NO_SEAT && menu_room_admission.discovered_port[peer] == sender->sin_port) {
        for (unsigned int row = 1; row < plan->player_count; ++row) {
            const unsigned char *const bytes = menu_room_socket_row(server, row);
            const struct sockaddr_in *const endpoint = (const struct sockaddr_in *)bytes;
            if (endpoint->sin_family == AF_INET && endpoint->sin_port == sender->sin_port &&
                endpoint->sin_addr.s_addr == sender->sin_addr.s_addr &&
                get32(bytes + MENU_ROOM_SOCKET_ROW_INDEX) == row) {
                seat = row;
                break;
            }
        }
    }
    ReleaseMutex(mutex);
    return seat;
}

static const char *menu_room_roster_name(const TrialSettings *plan, const unsigned char *server,
                                        uint32_t seat, uint32_t local_seat)
{
    if (seat >= plan->player_count)
        return NULL;
    if (!seat)
        return plan->host_name;
    if (plan->role == TRIAL_GUEST && seat == local_seat)
        return plan->guest_name;
    if (plan->role != TRIAL_HOST || !server)
        return NULL;

    /* Guests receive the other guest names through the stock joined roster. */
    const HANDLE mutex = menu_room_acquire(server);
    if (!mutex)
        return NULL;
    unsigned int peer = 0;
    const char *const name = menu_room_row_name(plan, menu_room_socket_row(server, seat), seat, &peer);
    ReleaseMutex(mutex);
    return name;
}

static void menu_room_client_name(const TrialSettings *plan, WCHAR name[32])
{
    const char *const source = plan->role == TRIAL_HOST ? plan->host_name : plan->guest_name;
    for (size_t index = 0; index < 32; ++index) {
        name[index] = (WCHAR)(unsigned char)source[index];
        if (!source[index])
            return;
    }
    name[31] = L'\0';
}
