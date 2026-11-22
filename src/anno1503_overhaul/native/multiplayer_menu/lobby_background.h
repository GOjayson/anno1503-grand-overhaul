/* The direct modal needs its stock artwork installed on its own draw layer
 * before widgets repaint the shared startup surfaces. */
enum {
    MENU_LOBBY_INITIALIZE_SLOT = 0x1b0,
    MENU_LOBBY_DRAW_LAYER = 0x21a8,
    MENU_LOBBY_TEXTURE_LIBRARY = 0xc6fe8,
    MENU_LOBBY_BACKDROP_NAME = 0xa4140,
    MENU_LOBBY_BACKDROP_ID = 338,
    MENU_FRAME_DYNAMIC_CAST = 0x99bf0,
    MENU_DRAW_LAYER_TYPE = 0xc5ba0,
    MENU_DRAW_LAYER_GFX_TYPE = 0xc5bc8,
    MENU_DISPLAY_INSTANCE_IMPORT = 0x9e2d0,
    MENU_DISPLAY_CLEAR_IMPORT = 0x9e0f8,
    MENU_DISPLAY_CLEAR_RVA = 0x5d500,
    MENU_DISPLAY_TEXTURE_LIBRARY_VTABLE = 0xf605c8,
    MENU_DISPLAY_TEXTURE_LOOKUP = 0x61c40,
    MENU_DISPLAY_TEXTURE_BY_ID = 0x61580,
    MENU_DISPLAY_DRAW_LAYER_VTABLE = 0xf620f8,
    MENU_DISPLAY_GFX_LAYER_VTABLE = 0xf620d0,
    MENU_DISPLAY_SET_GFX_TEXTURE = 0x3b210,
    MENU_DISPLAY_RENDERER = 0xe0,
    MENU_RENDERER_TEXTURES = 0x1d0,
    MENU_RENDERER_TEXTURE_SIZE = 0xa0,
    MENU_RENDERER_TEXTURE_COUNT = 0x29d0,
    MENU_TEXTURE_PIXELS = 0x20,
    MENU_TEXTURE_WIDTH = 0x38,
    MENU_TEXTURE_HEIGHT = 0x3c,
    MENU_TEXTURE_BYTES_PER_PIXEL = 0x44,
};

typedef void (*MenuClearTexture)(unsigned char *texture);
typedef void (*MenuSetBackdrop)(void *layer, void *texture);

typedef struct {
    uint64_t unused;
    union { char name[32]; int32_t id; } value;
} MenuTextureLookup;

_Static_assert(offsetof(MenuTextureLookup, value) == 8, "Native texture lookup layout");

static const void *menu_lobby_texture_pixels(const unsigned char *texture)
{
    if (get32(texture + MENU_TEXTURE_WIDTH) != 800 || get32(texture + MENU_TEXTURE_HEIGHT) != 600 ||
        get32(texture + MENU_TEXTURE_BYTES_PER_PIXEL) != 4)
        return NULL;
    return *(const void *const *)(texture + MENU_TEXTURE_PIXELS);
}

static bool menu_clear_lobby_background(unsigned char *renderer, MenuClearTexture clear)
{
    if (!renderer || get32(renderer + MENU_RENDERER_TEXTURE_COUNT) < 2)
        return false;
    unsigned char *const background = renderer + MENU_RENDERER_TEXTURES;
    unsigned char *const controls = background + MENU_RENDERER_TEXTURE_SIZE;
    const void *const background_pixels = menu_lobby_texture_pixels(background);
    const void *const control_pixels = menu_lobby_texture_pixels(controls);
    if (!background_pixels || !control_pixels || background_pixels == control_pixels)
        return false;

    /* Use the same clear as the stock paint path. Leave texture visibility
     * and all render suppression flags to the native modal. */
    clear(background);
    clear(controls);
    return true;
}

static void menu_repaint_lobby_background(unsigned char *renderer, MenuClearTexture clear,
                                          void *layer, void *texture, MenuSetBackdrop set)
{
    if (layer && texture && menu_clear_lobby_background(renderer, clear))
        set(layer, texture);
}

static void menu_restore_stock_lobby_art(unsigned char *lobby, unsigned char *frame, unsigned char *display)
{
    if (!display)
        return;
    const void *const instance_import = *(const void *const *)(frame + MENU_DISPLAY_INSTANCE_IMPORT);
    const MenuClearTexture clear = *(MenuClearTexture *)(frame + MENU_DISPLAY_CLEAR_IMPORT);
    if (instance_import != display + DISPLAY_INSTANCE || (const void *)clear != display + MENU_DISPLAY_CLEAR_RVA)
        return;
    unsigned char *const instance = *(unsigned char *const *)instance_import;
    void *const library = *(void **)(frame + MENU_LOBBY_TEXTURE_LIBRARY);
    void *const draw_layer = *(void **)(lobby + MENU_LOBBY_DRAW_LAYER);
    if (!instance || !library || !draw_layer ||
        *(void **)library != display + MENU_DISPLAY_TEXTURE_LIBRARY_VTABLE ||
        *(void **)draw_layer != display + MENU_DISPLAY_DRAW_LAYER_VTABLE)
        return;

    /* Match how the stock Host/Join selector binds its frame-local graphic
     * layer. Unlike the lobby's original preparation, use the resolved ID. */
    void *(*const cast)(void *, LONG, void *, void *, int) =
        (void *(*)(void *, LONG, void *, void *, int))(frame + MENU_FRAME_DYNAMIC_CAST);
    void *const gfx_layer = cast(draw_layer, 0, frame + MENU_DRAW_LAYER_TYPE, frame + MENU_DRAW_LAYER_GFX_TYPE, 0);
    if (!gfx_layer || *(void **)gfx_layer != display + MENU_DISPLAY_GFX_LAYER_VTABLE)
        return;

    int (*const lookup)(void *, unsigned int, MenuTextureLookup *) =
        (int (*)(void *, unsigned int, MenuTextureLookup *))(display + MENU_DISPLAY_TEXTURE_LOOKUP);
    void *(*const texture_by_id)(void *, int) = (void *(*)(void *, int))(display + MENU_DISPLAY_TEXTURE_BY_ID);
    MenuTextureLookup caps = {0};
    memcpy(caps.value.name, frame + MENU_LOBBY_BACKDROP_NAME, sizeof("FARBAUSWAHLMULTISPIELER"));
    if (!lookup(library, 10, &caps) || caps.value.id != MENU_LOBBY_BACKDROP_ID)
        return;
    void *const texture = texture_by_id(library, caps.value.id);
    const MenuSetBackdrop set = (MenuSetBackdrop)(display + MENU_DISPLAY_SET_GFX_TEXTURE);
    /* The setter invalidates the full layer. The stock modal's subsequent
     * activation also queues its full redraw if the layer already had it. */
    menu_repaint_lobby_background(*(unsigned char **)(instance + MENU_DISPLAY_RENDERER), clear,
                                  gfx_layer, texture, set);
}

__declspec(dllexport) void AnnoMenuPrepareLobbyPaint(unsigned char *lobby)
{
    void **const vtable = *(void ***)lobby;
    void (*const initialize)(void *) = (void (*)(void *))vtable[MENU_LOBBY_INITIALIZE_SLOT / sizeof(void *)];
    unsigned char *const frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (frame && (unsigned char *)vtable == frame + LOBBY_VTABLE && use_native_lobby_paint(frame))
        menu_restore_stock_lobby_art(lobby, frame, (unsigned char *)GetModuleHandleW(L"AnnoDisplay.dll"));
    initialize(lobby);
}
