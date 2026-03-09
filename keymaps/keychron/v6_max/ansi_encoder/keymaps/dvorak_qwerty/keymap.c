/* Copyright 2024 @ Keychron (https://www.keychron.com)
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include QMK_KEYBOARD_H
#include "keychron_common.h"

enum layers {
    DWERTY,  // 0 — Dvorak layout + Qwerty shortcut interception
    QWERTY,  // 1 — Qwerty layout
    DVORAK,  // 2 — Dvorak layout, no shortcut interception
    FN,      // 3 — Fn-held overlay (F-keys, RGB, BT, layout selector)
};

typedef enum {
    LAYOUT_MODE_DWERTY = 0,
    LAYOUT_MODE_QWERTY = 1,
    LAYOUT_MODE_DVORAK = 2,
} layout_mode_t;

#define LAYOUT_MODE_COUNT 3
#define LAYOUT_MODE_MASK  0x03

enum custom_keycodes {
    LAYOUT_TG = NEW_SAFE_RANGE,
    LAYOUT_DVORAK,
    LAYOUT_QWERTY,
    LAYOUT_SEL,
};

#define QD_ARRAY_SIZE(arr) (sizeof(arr) / sizeof((arr)[0]))
#define SHORTCUT_MOD_MASK (MOD_MASK_CTRL | MOD_MASK_ALT | MOD_MASK_GUI)

typedef struct {
    uint16_t dvorak;
    uint16_t qwerty;
} qwerty_shortcut_map_t;

static const qwerty_shortcut_map_t qwerty_shortcut_map[] = {
    {KC_QUOT, KC_Q},
    {KC_COMM, KC_W},
    {KC_DOT, KC_E},
    {KC_P, KC_R},
    {KC_Y, KC_T},
    {KC_F, KC_Y},
    {KC_G, KC_U},
    {KC_C, KC_I},
    {KC_R, KC_O},
    {KC_L, KC_P},
    {KC_SLSH, KC_LBRC},
    {KC_EQL, KC_RBRC},

    {KC_O, KC_S},
    {KC_E, KC_D},
    {KC_U, KC_F},
    {KC_I, KC_G},
    {KC_D, KC_H},
    {KC_H, KC_J},
    {KC_T, KC_K},
    {KC_N, KC_L},
    {KC_S, KC_SCLN},
    {KC_MINS, KC_QUOT},

    {KC_SCLN, KC_Z},
    {KC_Q, KC_X},
    {KC_J, KC_C},
    {KC_K, KC_V},
    {KC_X, KC_B},
    {KC_B, KC_N},
    {KC_W, KC_COMM},
    {KC_V, KC_DOT},
    {KC_Z, KC_SLSH},

    {KC_LBRC, KC_MINS},
    {KC_RBRC, KC_EQL},
};

static uint16_t qwerty_shortcut_active[MATRIX_ROWS][MATRIX_COLS];

// Layout mode persisted in EEPROM user data (low 2 bits)
static layout_mode_t current_layout_mode = LAYOUT_MODE_DWERTY;

static void apply_layout_mode(layout_mode_t mode) {
    current_layout_mode = mode;
    default_layer_set(1UL << mode);
}

static void save_layout_mode(layout_mode_t mode) {
    apply_layout_mode(mode);
    eeconfig_update_user(mode & LAYOUT_MODE_MASK);
}

static layout_mode_t read_layout_mode(void) {
    uint32_t val = eeconfig_read_user() & LAYOUT_MODE_MASK;
    if (val >= LAYOUT_MODE_COUNT) val = LAYOUT_MODE_DWERTY;
    return (layout_mode_t)val;
}

static bool qwerty_shortcuts_layer_active(uint8_t layer) {
    return layer == DWERTY;
}

static bool qwerty_shortcuts_mods_active(uint8_t layer) {
    uint8_t mods = get_mods() | get_oneshot_mods() | get_weak_mods();
    return (mods & SHORTCUT_MOD_MASK) != 0;
}

static uint16_t qwerty_shortcut_lookup(uint16_t keycode) {
    for (size_t i = 0; i < QD_ARRAY_SIZE(qwerty_shortcut_map); ++i) {
        if (qwerty_shortcut_map[i].dvorak == keycode) {
            return qwerty_shortcut_map[i].qwerty;
        }
    }
    return KC_NO;
}

// Layout selector state (active while Fn+Z held)
static bool layout_selector_active = false;
static uint16_t layout_selector_timer = 0;

#define SELECTOR_ANIM_PHASE_MS 50
static const uint8_t selector_led_keys[][2] = {
    {4, 2},  // Z
    {3, 1},  // A
    {3, 2},  // S
    {4, 3},  // X
};
#define SELECTOR_LED_COUNT 4
static const uint8_t selector_brightness[] = {255, 128, 64, 0};

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [DWERTY] = LAYOUT_ansi_109(
        KC_ESC,   KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,    KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,   KC_F12,     KC_MUTE,    KC_PSCR,  KC_CTANA, RGB_MOD,  _______,  _______,  _______,  _______,
        KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,     KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_LBRC,  KC_RBRC,    KC_BSPC,    KC_INS,   KC_HOME,  KC_PGUP,  KC_NUM,   KC_PSLS,  KC_PAST,  KC_PMNS,
        KC_TAB,   KC_QUOT,  KC_COMM,  KC_DOT,   KC_P,     KC_Y,     KC_F,     KC_G,     KC_C,     KC_R,     KC_L,     KC_SLSH,  KC_EQL,     KC_BSLS,    KC_DEL,   KC_END,   KC_PGDN,  KC_P7,    KC_P8,    KC_P9,
        KC_CAPS,  KC_A,     KC_O,     KC_E,     KC_U,     KC_I,     KC_D,     KC_H,     KC_T,     KC_N,     KC_S,     KC_MINS,             KC_ENT,                                   KC_P4,    KC_P5,    KC_P6,    KC_PPLS,
        KC_LSFT,            KC_SCLN,  KC_Q,     KC_J,     KC_K,     KC_X,     KC_B,     KC_M,     KC_W,     KC_V,     KC_Z,                KC_RSFT,              KC_UP,              KC_P1,    KC_P2,    KC_P3,
        KC_LCTL,  KC_LWIN,  KC_LALT,                                KC_SPC,                                 KC_RALT,  KC_RWIN,  MO(FN),     KC_RCTL,    KC_LEFT,  KC_DOWN,  KC_RGHT,  KC_P0,              KC_PDOT,  KC_PENT),
    [QWERTY] = LAYOUT_ansi_109(
        KC_ESC,   KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,    KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,   KC_F12,     KC_MUTE,    KC_PSCR,  KC_CTANA, RGB_MOD,  _______,  _______,  _______,  _______,
        KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,     KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_MINS,  KC_EQL,     KC_BSPC,    KC_INS,   KC_HOME,  KC_PGUP,  KC_NUM,   KC_PSLS,  KC_PAST,  KC_PMNS,
        KC_TAB,   KC_Q,     KC_W,     KC_E,     KC_R,     KC_T,     KC_Y,     KC_U,     KC_I,     KC_O,     KC_P,     KC_LBRC,  KC_RBRC,    KC_BSLS,    KC_DEL,   KC_END,   KC_PGDN,  KC_P7,    KC_P8,    KC_P9,
        KC_CAPS,  KC_A,     KC_S,     KC_D,     KC_F,     KC_G,     KC_H,     KC_J,     KC_K,     KC_L,     KC_SCLN,  KC_QUOT,              KC_ENT,                                   KC_P4,    KC_P5,    KC_P6,    KC_PPLS,
        KC_LSFT,            KC_Z,     KC_X,     KC_C,     KC_V,     KC_B,     KC_N,     KC_M,     KC_COMM,  KC_DOT,   KC_SLSH,              KC_RSFT,              KC_UP,              KC_P1,    KC_P2,    KC_P3,
        KC_LCTL,  KC_LWIN,  KC_LALT,                                KC_SPC,                                 KC_RALT,  KC_RWIN,  MO(FN),     KC_RCTL,    KC_LEFT,  KC_DOWN,  KC_RGHT,  KC_P0,              KC_PDOT,  KC_PENT),
    [DVORAK] = LAYOUT_ansi_109(
        KC_ESC,   KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,    KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,   KC_F12,     KC_MUTE,    KC_PSCR,  KC_CTANA, RGB_MOD,  _______,  _______,  _______,  _______,
        KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,     KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_LBRC,  KC_RBRC,    KC_BSPC,    KC_INS,   KC_HOME,  KC_PGUP,  KC_NUM,   KC_PSLS,  KC_PAST,  KC_PMNS,
        KC_TAB,   KC_QUOT,  KC_COMM,  KC_DOT,   KC_P,     KC_Y,     KC_F,     KC_G,     KC_C,     KC_R,     KC_L,     KC_SLSH,  KC_EQL,     KC_BSLS,    KC_DEL,   KC_END,   KC_PGDN,  KC_P7,    KC_P8,    KC_P9,
        KC_CAPS,  KC_A,     KC_O,     KC_E,     KC_U,     KC_I,     KC_D,     KC_H,     KC_T,     KC_N,     KC_S,     KC_MINS,             KC_ENT,                                   KC_P4,    KC_P5,    KC_P6,    KC_PPLS,
        KC_LSFT,            KC_SCLN,  KC_Q,     KC_J,     KC_K,     KC_X,     KC_B,     KC_M,     KC_W,     KC_V,     KC_Z,                KC_RSFT,              KC_UP,              KC_P1,    KC_P2,    KC_P3,
        KC_LCTL,  KC_LWIN,  KC_LALT,                                KC_SPC,                                 KC_RALT,  KC_RWIN,  MO(FN),     KC_RCTL,    KC_LEFT,  KC_DOWN,  KC_RGHT,  KC_P0,              KC_PDOT,  KC_PENT),
    [FN] = LAYOUT_ansi_109(
        _______,  KC_BRID,  KC_BRIU,  KC_TASK,  KC_FILE,  RGB_VAD,  RGB_VAI,  KC_MPRV,  KC_MPLY,  KC_MNXT,  KC_MUTE,  KC_VOLD,  KC_VOLU,    RGB_TOG,    _______,  _______,  RGB_TOG,  _______,  _______,  _______,  _______,
        _______,  BT_HST1,  BT_HST2,  BT_HST3,  P2P4G,    _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,  _______,  _______,  _______,
        RGB_TOG,  RGB_MOD,  RGB_VAI,  RGB_HUI,  RGB_SAI,  RGB_SPI,  _______,  _______,  _______,  _______,  _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,  _______,  _______,
        _______,  RGB_RMOD, RGB_VAD,  RGB_HUD,  RGB_SAD,  RGB_SPD,  _______,  _______,  _______,  _______,  _______,  _______,              _______,                                  _______,  _______,  _______,  _______,
        _______,            LAYOUT_SEL, _______,  _______,  _______,  BAT_LVL,  NK_TOGG,  _______,  _______,  _______,  _______,              _______,              _______,            _______,  _______,  _______,
        _______,  _______,  _______,                                _______,                                _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,            _______,  _______),
};

#if defined(ENCODER_MAP_ENABLE)
const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][2] = {
    [DWERTY]  = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU)},
    [QWERTY]  = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU)},
    [DVORAK]  = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU)},
    [FN]      = {ENCODER_CCW_CW(RGB_VAD, RGB_VAI)},
};
#endif // ENCODER_MAP_ENABLE
// clang-format on

void eeconfig_init_user(void) {
    eeconfig_update_user(LAYOUT_MODE_DWERTY);
    set_single_persistent_default_layer(DWERTY);
}

void keyboard_post_init_user(void) {
    // Runs after DIP switch init — our saved mode overrides upstream's layer 0/2
    apply_layout_mode(read_layout_mode());
}

layer_state_t layer_state_set_user(layer_state_t state) {
    // Exit layout selector when FN layer deactivates
    if (layout_selector_active && !layer_state_cmp(state, FN)) {
        layout_selector_active = false;
    }
    return state;
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_keychron_common(keycode, record)) {
        return false;
    }

    if (record->event.pressed) {
        if (keycode == LAYOUT_SEL) {
            if (!layout_selector_active) {
                layout_selector_active = true;
                layout_selector_timer = timer_read();
            } else {
                layout_mode_t next = (current_layout_mode + 1) % LAYOUT_MODE_COUNT;
                save_layout_mode(next);
                layout_selector_timer = timer_read();
            }
            return false;
        }
        if (keycode == LAYOUT_TG) {
            if (current_layout_mode == LAYOUT_MODE_QWERTY) {
                save_layout_mode(LAYOUT_MODE_DWERTY);
            } else {
                save_layout_mode(LAYOUT_MODE_QWERTY);
            }
            return false;
        }
        if (keycode == LAYOUT_DVORAK) {
            save_layout_mode(LAYOUT_MODE_DWERTY);
            return false;
        }
        if (keycode == LAYOUT_QWERTY) {
            save_layout_mode(LAYOUT_MODE_QWERTY);
            return false;
        }
    }

    uint8_t row = record->event.key.row;
    uint8_t col = record->event.key.col;

    // Release path must run before modifier checks
    if (!record->event.pressed) {
        if (qwerty_shortcut_active[row][col] != KC_NO) {
            unregister_code16(qwerty_shortcut_active[row][col]);
            qwerty_shortcut_active[row][col] = KC_NO;
            return false;
        }
        return true;
    }

    uint8_t layer = get_highest_layer(layer_state | default_layer_state);

    if (!qwerty_shortcuts_layer_active(layer) || !qwerty_shortcuts_mods_active(layer)) {
        return true;
    }

    uint16_t mapped = qwerty_shortcut_lookup(keycode);
    if (mapped == KC_NO) {
        return true;
    }

    qwerty_shortcut_active[row][col] = mapped;
    register_code16(mapped);
    return false;
}

// Layout mode colour: Red=Dwerty, Blue=Qwerty, Green=Dvorak
static void layout_mode_color(layout_mode_t mode, uint8_t brightness, uint8_t *r, uint8_t *g, uint8_t *b) {
    *r = 0; *g = 0; *b = 0;
    switch (mode) {
        case LAYOUT_MODE_DWERTY: *r = brightness; break;
        case LAYOUT_MODE_QWERTY: *b = brightness; break;
        case LAYOUT_MODE_DVORAK: *g = brightness; break;
    }
}

bool rgb_matrix_indicators_advanced_user(uint8_t led_min, uint8_t led_max) {
    // Layout selector animation: circular Z→A→S→X
    if (layout_selector_active) {
        for (uint8_t i = led_min; i < led_max; i++) {
            rgb_matrix_set_color(i, 0, 0, 0);
        }
        uint16_t elapsed = timer_elapsed(layout_selector_timer);
        uint8_t phase = (elapsed / SELECTOR_ANIM_PHASE_MS) % SELECTOR_LED_COUNT;

        for (uint8_t k = 0; k < SELECTOR_LED_COUNT; k++) {
            uint8_t idx = (phase + SELECTOR_LED_COUNT - k) % SELECTOR_LED_COUNT;
            uint8_t led = g_led_config.matrix_co[selector_led_keys[idx][0]][selector_led_keys[idx][1]];
            if (led != NO_LED && led >= led_min && led < led_max) {
                uint8_t r, g, b;
                layout_mode_color(current_layout_mode, selector_brightness[k], &r, &g, &b);
                rgb_matrix_set_color(led, r, g, b);
            }
        }
        return false;
    }

    // Tab key shows active layout colour
    uint8_t tab_led = g_led_config.matrix_co[2][0];
    if (tab_led >= led_min && tab_led < led_max && tab_led != NO_LED) {
        uint8_t r, g, b;
        layout_mode_color(current_layout_mode, 255, &r, &g, &b);
        rgb_matrix_set_color(tab_led, r, g, b);
    }
    return false;
}
