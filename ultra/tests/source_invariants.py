#!/usr/bin/env python3
"""Verify the fork provenance and the off-device hardening invariants."""

import argparse
import pathlib
import subprocess
import tempfile


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)


def git_show(repo, revision, path):
    return git(repo, "show", f"{revision}:{path}")


def extract_function(source, name):
    marker = source.index(name + "(")
    start = source.index("{", marker)
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[marker:index + 1]
    raise AssertionError(f"unterminated function: {name}")


def write_source(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def apply_patches(zmk, fork_revision, ultra):
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        source_paths = (
            "app/CMakeLists.txt",
            "app/Kconfig",
            "app/module/drivers/kscan/kscan_gpio_matrix.c",
            "app/src/endpoints.c",
            "app/src/hid.c",
            "app/src/keymap.c",
            "app/src/kscan.c",
            "app/src/ppt/keyboard_ppt_app.c",
            "app/src/ppt/ppt_send.c",
            "app/src/rgb/rgb_matrix_drivers.c",
        )
        for relative in source_paths:
            write_source(root, relative, git_show(zmk, fork_revision, relative))

        for patch in sorted((ultra / "patches").glob("*.patch")):
            subprocess.run(["git", "-C", str(root), "apply", str(patch)], check=True)

        return {
            "keymap": (root / "app/src/keymap.c").read_text(),
            "ppt": (root / "app/src/ppt/ppt_send.c").read_text(),
            "diag": (root / "app/src/dwerty_diag.c").read_text(),
            "diag_header": (root / "app/module/include/zmk/dwerty_diag.h").read_text(),
        }


def compile_queue_harness(function):
    source = f"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>

#define QUEUE_CAPACITY 64
#define LOG_WRN(...) ((void)0)
#define LOG_ERR(...) ((void)0)

typedef struct {{
    int value;
    struct {{
        uint8_t opcode;
    }} packet;
}} zmk_ppt_report_t;

typedef struct {{
    zmk_ppt_report_t reports[QUEUE_CAPACITY];
    size_t head;
    size_t count;
}} ring_buf_t;

static ring_buf_t zmk_ppt_msgs;
static int lock;
typedef int k_spinlock_key_t;

static k_spinlock_key_t k_spin_lock(int *unused) {{
    (void)unused;
    return 0;
}}

static void k_spin_unlock(int *unused, k_spinlock_key_t key) {{
    (void)unused;
    (void)key;
}}

static uint32_t ring_buf_space_get(ring_buf_t *ring) {{
    return (QUEUE_CAPACITY - ring->count) * sizeof(zmk_ppt_report_t);
}}

static uint32_t ring_buf_get(ring_buf_t *ring, uint8_t *data, size_t size) {{
    if (size != sizeof(zmk_ppt_report_t) || ring->count == 0) {{
        return 0;
    }}
    memcpy(data, &ring->reports[ring->head], size);
    ring->head = (ring->head + 1) % QUEUE_CAPACITY;
    ring->count--;
    return size;
}}

static uint32_t ring_buf_put(ring_buf_t *ring, const uint8_t *data, size_t size) {{
    if (size != sizeof(zmk_ppt_report_t) || ring->count == QUEUE_CAPACITY) {{
        return 0;
    }}
    size_t index = (ring->head + ring->count) % QUEUE_CAPACITY;
    memcpy(&ring->reports[index], data, size);
    ring->count++;
    return size;
}}

static int ringbuf_used_get(void) {{
    return (int)zmk_ppt_msgs.count;
}}

#define DWERTY_DIAG_EVENT_PPT_QUEUE 12
#define DWERTY_DIAG_FLAG_ERROR 2
#define DWERTY_DIAG_FLAG_DISCARDED 4
#define DWERTY_DIAG_FREEZE_PPT_OVERFLOW 4

static void dwerty_diag_record(uint8_t type, uint8_t flags, uint16_t arg0, uint16_t arg1) {{
    (void)type;
    (void)flags;
    (void)arg0;
    (void)arg1;
}}

static void dwerty_diag_freeze(uint8_t reason) {{
    (void)reason;
}}

int {function}

int main(void) {{
    for (int value = 0; value < QUEUE_CAPACITY; value++) {{
        zmk_ppt_report_t report = {{.value = value}};
        assert(ring_buf_put(&zmk_ppt_msgs, (const uint8_t *)&report, sizeof(report)) ==
               sizeof(report));
    }}

    zmk_ppt_report_t newest = {{.value = QUEUE_CAPACITY}};
    assert(ringbuf_msg_put(&newest) == 0);
    assert(zmk_ppt_msgs.count == QUEUE_CAPACITY);

    zmk_ppt_report_t report;
    assert(ring_buf_get(&zmk_ppt_msgs, (uint8_t *)&report, sizeof(report)) == sizeof(report));
    assert(report.value == 1);
    while (zmk_ppt_msgs.count > 1) {{
        assert(ring_buf_get(&zmk_ppt_msgs, (uint8_t *)&report, sizeof(report)) == sizeof(report));
    }}
    assert(ring_buf_get(&zmk_ppt_msgs, (uint8_t *)&report, sizeof(report)) == sizeof(report));
    assert(report.value == QUEUE_CAPACITY);
    return 0;
}}
"""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        source_path = root / "queue_test.c"
        binary_path = root / "queue_test"
        source_path.write_text(source)
        subprocess.run(
            ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(source_path), "-o",
             str(binary_path)],
            check=True,
        )
        subprocess.run([str(binary_path)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zmk", type=pathlib.Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--ultra", type=pathlib.Path, required=True)
    args = parser.parse_args()
    args.ultra = args.ultra.resolve()

    morph_path = "app/src/behaviors/behavior_mod_morph.c"
    keymap_path = "app/src/keymap.c"
    base_morph = git_show(args.zmk, args.base, morph_path)
    fork_morph = git_show(args.zmk, args.fork, morph_path)
    assert base_morph == fork_morph, "fork mod-morph differs from its upstream base"

    base_keymap = git_show(args.zmk, args.base, keymap_path)
    fork_keymap = git_show(args.zmk, args.fork, keymap_path)
    assert extract_function(
        base_keymap, "zmk_keymap_position_state_changed"
    ) == extract_function(
        fork_keymap, "zmk_keymap_position_state_changed"
    ), "fork release routing differs from its upstream base"

    patched = apply_patches(args.zmk, args.fork, args.ultra)
    queue_function = extract_function(patched["ppt"], "ringbuf_msg_put")
    compile_queue_harness(queue_function)
    assert "launcher_command_kb" in patched["diag"]
    assert "DWERTY_DIAG_UART_MAGIC_0" in patched["diag"]
    assert "BUILD_ASSERT(sizeof(struct dwerty_diag_record) == 12)" in patched["diag"]
    assert "raw_hid_send(data, length);" in patched["diag"]
    assert "#define dwerty_diag_record(...) ((void)0)" in patched["diag_header"]
    assert "#define dwerty_diag_record_hid(...) ((void)0)" in patched["diag_header"]
    print(
        "Source invariants OK: fork mod-morph and release routing match "
        "upstream base; all fork patches apply; PPT queue overflow and "
        "diagnostic protocol checks passed"
    )


if __name__ == "__main__":
    main()
