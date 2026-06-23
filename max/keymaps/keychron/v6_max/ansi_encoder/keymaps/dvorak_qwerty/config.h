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

#pragma once

// 4 layers: DWERTY, QWERTY, DVORAK, FN
#define DYNAMIC_KEYMAP_LAYER_COUNT 4

// Match official V6 Max firmware 1.1.2.
// info_config.h is -included before keymap config.h (build_keyboard.mk
// line 356 vs 437), so its #ifndef guards fire first. #undef is required.
#undef DEVICE_VER
#define DEVICE_VER 0x0112

#undef DEBOUNCE
#define DEBOUNCE 50
