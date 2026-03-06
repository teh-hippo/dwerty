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
    MAC_BASE,
    MAC_FN,
    WIN_BASE,
    WIN_FN,
    WIN_QWERTY,
    WIN_QWERTY_FN,
};

enum custom_keycodes {
    LAYOUT_TG = NEW_SAFE_RANGE,
    LAYOUT_DVORAK,
    LAYOUT_QWERTY,
    LAYER_DOWN,
    LAYER_UP,
};

#define QD_ARRAY_SIZE(arr) (sizeof(arr) / sizeof((arr)[0]))
// Windows uses Ctrl/Alt/GUI; macOS defaults to Command-only to match Dvorak-Qwerty Command.
#define SHORTCUT_MOD_MASK_WIN (MOD_MASK_CTRL | MOD_MASK_ALT | MOD_MASK_GUI)
#define SHORTCUT_MOD_MASK_MAC (MOD_MASK_GUI)

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

static bool qwerty_shortcuts_layer_active(uint8_t layer) {
    return layer == MAC_BASE || layer == WIN_BASE;
    // Note: WIN_QWERTY intentionally excluded - no shortcut remapping needed
}

static bool is_qwerty_mode(void) {
    uint8_t layer = get_highest_layer(default_layer_state);
    return layer == WIN_QWERTY;
}

static bool is_dvorak_layer(uint8_t layer) {
    return layer == WIN_BASE || layer == MAC_BASE;
}

static bool is_qwerty_layer(uint8_t layer) {
    return layer == WIN_QWERTY;
}

#define LAYER_INDICATOR_TIMEOUT_MS 2000
static bool layer_indicator_active = false;
static uint16_t layer_indicator_timer = 0;
static uint8_t layer_indicator_layer = 0;

static const uint8_t number_row_cols[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

static uint8_t layer_cycle_count(void) {
#ifdef DYNAMIC_KEYMAP_LAYER_COUNT
    return DYNAMIC_KEYMAP_LAYER_COUNT;
#else
    return 6;
#endif
}

static uint8_t layer_cycle_current(void) {
    return get_highest_layer(default_layer_state);
}

static void show_layer_indicator(uint8_t layer) {
    layer_indicator_active = true;
    layer_indicator_timer = timer_read();
    layer_indicator_layer = layer;
}

static uint8_t qwerty_shortcuts_mod_mask(uint8_t layer) {
    if (layer == MAC_BASE) {
        return SHORTCUT_MOD_MASK_MAC;
    }
    if (layer == WIN_BASE) {
        return SHORTCUT_MOD_MASK_WIN;
    }
    return 0;
}

static bool qwerty_shortcuts_mods_active(uint8_t layer) {
    uint8_t mods = get_mods() | get_oneshot_mods() | get_weak_mods();
    return (mods & qwerty_shortcuts_mod_mask(layer)) != 0;
}

static uint16_t qwerty_shortcut_lookup(uint16_t keycode) {
    for (size_t i = 0; i < QD_ARRAY_SIZE(qwerty_shortcut_map); ++i) {
        if (qwerty_shortcut_map[i].dvorak == keycode) {
            return qwerty_shortcut_map[i].qwerty;
        }
    }
    return KC_NO;
}

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [MAC_BASE] = LAYOUT_ansi_109(
        KC_ESC,   KC_BRID,  KC_BRIU,  KC_MCTRL, KC_LNPAD, RGB_VAD,  RGB_VAI,  KC_MPRV,  KC_MPLY,  KC_MNXT,  KC_MUTE,  KC_VOLD,  KC_VOLU,    KC_MUTE,    KC_SNAP,  KC_SIRI,  RGB_MOD,  KC_F13,   KC_F14,   KC_F15,   KC_F16,
        KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,     KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_LBRC,  KC_RBRC,    KC_BSPC,    KC_INS,   KC_HOME,  KC_PGUP,  KC_NUM,   KC_PSLS,  KC_PAST,  KC_PMNS,
        KC_TAB,   KC_QUOT,  KC_COMM,  KC_DOT,   KC_P,     KC_Y,     KC_F,     KC_G,     KC_C,     KC_R,     KC_L,     KC_SLSH,  KC_EQL,     KC_BSLS,    KC_DEL,   KC_END,   KC_PGDN,  KC_P7,    KC_P8,    KC_P9,
        KC_CAPS,  KC_A,     KC_O,     KC_E,     KC_U,     KC_I,     KC_D,     KC_H,     KC_T,     KC_N,     KC_S,     KC_MINS,             KC_ENT,                                   KC_P4,    KC_P5,    KC_P6,    KC_PPLS,
        KC_LSFT,            KC_SCLN,  KC_Q,     KC_J,     KC_K,     KC_X,     KC_B,     KC_M,     KC_W,     KC_V,     KC_Z,                KC_RSFT,              KC_UP,              KC_P1,    KC_P2,    KC_P3,
        KC_LCTL,  KC_LOPTN, KC_LCMMD,                               KC_SPC,                                 KC_RCMMD, KC_ROPTN, MO(MAC_FN), KC_RCTL,    KC_LEFT,  KC_DOWN,  KC_RGHT,  KC_P0,              KC_PDOT,  KC_PENT),
    [MAC_FN] = LAYOUT_ansi_109(
        _______,  KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,    KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,   KC_F12,     RGB_TOG,    _______,  _______,  RGB_TOG,  _______,  _______,  _______,  _______,
        _______,  BT_HST1,  BT_HST2,  BT_HST3,  P2P4G,    _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,  _______,  _______,  _______,
        RGB_TOG,  RGB_MOD,  RGB_VAI,  RGB_HUI,  RGB_SAI,  RGB_SPI,  _______,  _______,  _______,  _______,  _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,  _______,  _______,
        _______,  RGB_RMOD, RGB_VAD,  RGB_HUD,  RGB_SAD,  RGB_SPD,  _______,  _______,  _______,  _______,  _______,  _______,              _______,                                  _______,  _______,  _______,  _______,
        _______,            LAYER_DOWN, LAYER_UP, _______,  _______,  BAT_LVL,  NK_TOGG,  _______,  _______,  _______,  _______,              _______,              _______,            _______,  _______,  _______,  
        _______,  _______,  _______,                                _______,                                _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,            _______,  _______),
    [WIN_BASE] = LAYOUT_ansi_109(
        KC_ESC,   KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,    KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,   KC_F12,     KC_MUTE,    KC_PSCR,  KC_CTANA, RGB_MOD,  _______,  _______,  _______,  _______,
        KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,     KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_LBRC,  KC_RBRC,    KC_BSPC,    KC_INS,   KC_HOME,  KC_PGUP,  KC_NUM,   KC_PSLS,  KC_PAST,  KC_PMNS,
        KC_TAB,   KC_QUOT,  KC_COMM,  KC_DOT,   KC_P,     KC_Y,     KC_F,     KC_G,     KC_C,     KC_R,     KC_L,     KC_SLSH,  KC_EQL,     KC_BSLS,    KC_DEL,   KC_END,   KC_PGDN,  KC_P7,    KC_P8,    KC_P9,
        KC_CAPS,  KC_A,     KC_O,     KC_E,     KC_U,     KC_I,     KC_D,     KC_H,     KC_T,     KC_N,     KC_S,     KC_MINS,             KC_ENT,                                   KC_P4,    KC_P5,    KC_P6,    KC_PPLS,
        KC_LSFT,            KC_SCLN,  KC_Q,     KC_J,     KC_K,     KC_X,     KC_B,     KC_M,     KC_W,     KC_V,     KC_Z,                KC_RSFT,              KC_UP,              KC_P1,    KC_P2,    KC_P3,
        KC_LCTL,  KC_LWIN,  KC_LALT,                                KC_SPC,                                 KC_RALT,  KC_RWIN,  MO(WIN_FN), KC_RCTL,    KC_LEFT,  KC_DOWN,  KC_RGHT,  KC_P0,              KC_PDOT,  KC_PENT),
    [WIN_FN] = LAYOUT_ansi_109(
        _______,  KC_BRID,  KC_BRIU,  KC_TASK,  KC_FILE,  RGB_VAD,  RGB_VAI,  KC_MPRV,  KC_MPLY,  KC_MNXT,  KC_MUTE,  KC_VOLD,  KC_VOLU,    RGB_TOG,    _______,  _______,  RGB_TOG,  _______,  _______,  _______,  _______,
        _______,  BT_HST1,  BT_HST2,  BT_HST3,  P2P4G,    _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,  _______,  _______,  _______,
        RGB_TOG,  RGB_MOD,  RGB_VAI,  RGB_HUI,  RGB_SAI,  RGB_SPI,  _______,  _______,  _______,  _______,  _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,  _______,  _______,
        _______,  RGB_RMOD, RGB_VAD,  RGB_HUD,  RGB_SAD,  RGB_SPD,  _______,  _______,  _______,  _______,  _______,  _______,              _______,                                  _______,  _______,  _______,  _______,
        _______,            LAYER_DOWN, LAYER_UP, _______,  _______,  BAT_LVL,  NK_TOGG,  _______,  _______,  _______,  _______,              _______,              _______,            _______,  _______,  _______,  
        _______,  _______,  _______,                                _______,                                _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,            _______,  _______),
    [WIN_QWERTY] = LAYOUT_ansi_109(
        KC_ESC,   KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,    KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,   KC_F12,     KC_MUTE,    KC_PSCR,  KC_CTANA, RGB_MOD,  _______,  _______,  _______,  _______,
        KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,     KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_MINS,  KC_EQL,     KC_BSPC,    KC_INS,   KC_HOME,  KC_PGUP,  KC_NUM,   KC_PSLS,  KC_PAST,  KC_PMNS,
        KC_TAB,   KC_Q,     KC_W,     KC_E,     KC_R,     KC_T,     KC_Y,     KC_U,     KC_I,     KC_O,     KC_P,     KC_LBRC,  KC_RBRC,    KC_BSLS,    KC_DEL,   KC_END,   KC_PGDN,  KC_P7,    KC_P8,    KC_P9,
        KC_CAPS,  KC_A,     KC_S,     KC_D,     KC_F,     KC_G,     KC_H,     KC_J,     KC_K,     KC_L,     KC_SCLN,  KC_QUOT,              KC_ENT,                                   KC_P4,    KC_P5,    KC_P6,    KC_PPLS,
        KC_LSFT,            KC_Z,     KC_X,     KC_C,     KC_V,     KC_B,     KC_N,     KC_M,     KC_COMM,  KC_DOT,   KC_SLSH,              KC_RSFT,              KC_UP,              KC_P1,    KC_P2,    KC_P3,
        KC_LCTL,  KC_LWIN,  KC_LALT,                                KC_SPC,                                 KC_RALT,  KC_RWIN,  MO(WIN_QWERTY_FN), KC_RCTL,    KC_LEFT,  KC_DOWN,  KC_RGHT,  KC_P0,              KC_PDOT,  KC_PENT),
    [WIN_QWERTY_FN] = LAYOUT_ansi_109(
        _______,  KC_BRID,  KC_BRIU,  KC_TASK,  KC_FILE,  RGB_VAD,  RGB_VAI,  KC_MPRV,  KC_MPLY,  KC_MNXT,  KC_MUTE,  KC_VOLD,  KC_VOLU,    RGB_TOG,    _______,  _______,  RGB_TOG,  _______,  _______,  _______,  _______,
        _______,  BT_HST1,  BT_HST2,  BT_HST3,  P2P4G,    _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,  _______,  _______,  _______,
        RGB_TOG,  RGB_MOD,  RGB_VAI,  RGB_HUI,  RGB_SAI,  RGB_SPI,  _______,  _______,  _______,  _______,  _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,  _______,  _______,
        _______,  RGB_RMOD, RGB_VAD,  RGB_HUD,  RGB_SAD,  RGB_SPD,  _______,  _______,  _______,  _______,  _______,  _______,              _______,                                  _______,  _______,  _______,  _______,
        _______,            LAYER_DOWN, LAYER_UP, _______,  _______,  BAT_LVL,  NK_TOGG,  _______,  _______,  _______,  _______,              _______,              _______,            _______,  _______,  _______,  
        _______,  _______,  _______,                                _______,                                _______,  _______,  _______,    _______,    _______,  _______,  _______,  _______,            _______,  _______)
};

#if defined(ENCODER_MAP_ENABLE)
const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][2] = {
    [MAC_BASE]       = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU)},
    [MAC_FN]         = {ENCODER_CCW_CW(RGB_VAD, RGB_VAI)},
    [WIN_BASE]       = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU)},
    [WIN_FN]         = {ENCODER_CCW_CW(RGB_VAD, RGB_VAI)},
    [WIN_QWERTY]     = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU)},
    [WIN_QWERTY_FN]  = {ENCODER_CCW_CW(RGB_VAD, RGB_VAI)},
};
#endif // ENCODER_MAP_ENABLE
// clang-format on

void eeconfig_init_user(void) {
    // Set Dvorak (WIN_BASE) as factory default
    set_single_persistent_default_layer(WIN_BASE);
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_keychron_common(keycode, record)) {
        return false;
    }

    // Handle layout toggle
    if (record->event.pressed) {
        if (keycode == LAYOUT_TG) {
            if (is_qwerty_mode()) {
                set_single_persistent_default_layer(WIN_BASE);
            } else {
                set_single_persistent_default_layer(WIN_QWERTY);
            }
            return false;
        }
        if (keycode == LAYOUT_DVORAK) {
            set_single_persistent_default_layer(WIN_BASE);
            return false;
        }
        if (keycode == LAYOUT_QWERTY) {
            set_single_persistent_default_layer(WIN_QWERTY);
            return false;
        }
        if (keycode == LAYER_DOWN || keycode == LAYER_UP) {
            uint8_t count = layer_cycle_count();
            uint8_t current = layer_cycle_current();
            uint8_t next = current;
            if (count > 0) {
                if (keycode == LAYER_UP) {
                    next = (current + 1) % count;
                } else {
                    next = (current + count - 1) % count;
                }
            }
            set_single_persistent_default_layer(next);
            show_layer_indicator(next);
            return false;
        }
    }

    uint8_t row = record->event.key.row;
    uint8_t col = record->event.key.col;

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

// RGB indicator: Tab key shows Dwerty/QWERTY layout color
bool rgb_matrix_indicators_advanced_user(uint8_t led_min, uint8_t led_max) {
    if (layer_indicator_active) {
        if (timer_elapsed(layer_indicator_timer) > LAYER_INDICATOR_TIMEOUT_MS) {
            layer_indicator_active = false;
        } else {
            for (uint8_t i = led_min; i < led_max; i++) {
                rgb_matrix_set_color(i, 0, 0, 0);
            }
            uint8_t display = (get_highest_layer(default_layer_state) % QD_ARRAY_SIZE(number_row_cols)) + 1;
            uint8_t col = number_row_cols[display - 1];
            uint8_t led = g_led_config.matrix_co[1][col];
            if (led != NO_LED && led >= led_min && led < led_max) {
                if (is_dvorak_layer(layer_indicator_layer)) {
                    rgb_matrix_set_color(led, 255, 0, 0); // Red for Dwerty
                } else if (is_qwerty_layer(layer_indicator_layer)) {
                    rgb_matrix_set_color(led, 255, 255, 0); // Yellow for QWERTY
                } else {
                    rgb_matrix_set_color(led, 0, 0, 255); // Blue for non-layout layers
                }
            }
            return false;
        }
    }
    // Tab key LED index indicates active layout
    // Tab is typically at row 2, col 0 in the matrix
    uint8_t tab_led = g_led_config.matrix_co[2][0];
    if (tab_led >= led_min && tab_led < led_max && tab_led != NO_LED) {
        uint8_t layer = get_highest_layer(default_layer_state);
        if (is_dvorak_layer(layer)) {
            rgb_matrix_set_color(tab_led, 255, 0, 0); // Red for Dwerty
        } else if (is_qwerty_layer(layer)) {
            rgb_matrix_set_color(tab_led, 255, 255, 0); // Yellow for QWERTY
        } else {
            rgb_matrix_set_color(tab_led, 0, 0, 255); // Blue for non-layout layers
        }
    }
    return false;
}
