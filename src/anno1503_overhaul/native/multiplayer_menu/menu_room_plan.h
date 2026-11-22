/* The managed room reply extends the reviewed two-peer prefix with at most
 * six additional guests. It is fixed-size and carries no unused data. */
enum { MENU_ROOM_SEATS = 8, MENU_ROOM_NAME_LENGTH = 24, MENU_ROOM_TICKET_LENGTH = 24 };

static bool menu_internet_room(const TrialSettings *plan)
{
    return memcmp(plan->signature, "ANNONETR", 8) == 0;
}

static bool menu_room_transport(const TrialSettings *plan)
{
    return !plan->prefix && (menu_internet_room(plan) || memcmp(plan->signature, "ANNOROOM", 8) == 0) &&
        plan->player_count >= 3 && plan->player_count <= MENU_ROOM_SEATS &&
        ((plan->role == TRIAL_HOST && plan->extra_guest_count == plan->player_count - 2) ||
         (plan->role == TRIAL_GUEST && !plan->extra_guest_count));
}

static bool menu_room_zero(const void *data, size_t length)
{
    const unsigned char *const bytes = data;
    for (size_t index = 0; index < length; ++index) {
        if (bytes[index])
            return false;
    }
    return true;
}

static bool menu_room_name_is_padded(const char name[32], size_t limit)
{
    if (!valid_trial_name(name))
        return false;
    const size_t length = strlen(name);
    return length <= limit && menu_room_zero(name + length + 1, 31 - length);
}

static bool menu_room_ticket_valid(const char ticket[MENU_ROOM_TICKET_LENGTH])
{
    for (size_t index = 0; index < MENU_ROOM_TICKET_LENGTH; ++index) {
        const char value = ticket[index];
        if ((value < '0' || value > '9') && (value < 'a' || value > 'f'))
            return false;
    }
    return true;
}

static bool menu_room_valid_plan(const TrialSettings *plan)
{
    const bool internet = menu_internet_room(plan);
    const bool group = internet || memcmp(plan->signature, "ANNOROOM", 8) == 0;
    const size_t limit = group ? MENU_ROOM_NAME_LENGTH : 31;
    if (!menu_room_name_is_padded(plan->host_name, limit) || !menu_room_name_is_padded(plan->guest_name, limit))
        return false;
    if (group) {
        if (!menu_room_transport(plan) ||
            (!private_range(plan->local) && !(internet && public_unicast(plan->local))) ||
            !(internet ? public_unicast(plan->peer) : private_range(plan->peer) != 0) ||
            plan->local == plan->peer)
            return false;
        for (unsigned int index = 0; index < plan->extra_guest_count; ++index) {
            const uint32_t address = plan->extra_guests[index].address;
            if (!(internet ? public_unicast(address) : private_range(address) != 0) ||
                address == plan->local || (!internet && address == plan->peer) ||
                !menu_room_name_is_padded(plan->extra_guests[index].name, limit))
                return false;
            for (unsigned int earlier = 0; earlier < index; ++earlier) {
                if (!internet && address == plan->extra_guests[earlier].address)
                    return false;
            }
        }
    } else if (plan->player_count != 2 || plan->extra_guest_count || !valid_settings(plan)) {
        return false;
    }

    for (unsigned int index = plan->extra_guest_count; index < MENU_ROOM_SEATS - 2; ++index) {
        if (!menu_room_zero(&plan->extra_guests[index], sizeof plan->extra_guests[index]))
            return false;
    }
    const unsigned int tickets = internet ? 1u + plan->extra_guest_count : 0;
    for (unsigned int index = 0; index < MENU_ROOM_SEATS - 1; ++index) {
        const char *const ticket = plan->internet_tickets[index];
        if (index >= tickets) {
            if (!menu_room_zero(ticket, MENU_ROOM_TICKET_LENGTH))
                return false;
            continue;
        }
        if (!menu_room_ticket_valid(ticket))
            return false;
        for (unsigned int earlier = 0; earlier < index; ++earlier) {
            if (memcmp(ticket, plan->internet_tickets[earlier], MENU_ROOM_TICKET_LENGTH) == 0)
                return false;
        }
    }
    return true;
}
