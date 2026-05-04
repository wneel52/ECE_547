import csv
import os
import random
import time

from uart_driver import (
    PlatformKeyValidationDriver,
    Status,
    KEY_W,
    KEY_BYTES,
    HEX_DIGITS,
    MASK,
    serial_port,
    baud_rate,
    timeout,
    step_delay,
)

PK0_FULL = 0x00112233445566778899AABBCCDDEEFF
PK1_FULL = 0x11111111222222223333333344444444
PK2_FULL = 0xAAAABBBBCCCCDDDDEEEEFFFF12345678

PK0 = PK0_FULL & MASK
PK1 = PK1_FULL & MASK
PK2 = PK2_FULL & MASK

RESULTS_DIR = "results"
RESULTS_CSV = os.path.join(RESULTS_DIR, f"protocol_desync_keyw_{KEY_W}.csv")


def raw_write(driver, data: bytes, read_len: int = 0):
    driver.serial_port.reset_input_buffer()
    driver.serial_port.write(data)
    driver.serial_port.flush()

    if read_len:
        return driver._read_exact(read_len)

    time.sleep(step_delay)
    return b""


def reset_quiet(driver):
    driver.zeroize()
    time.sleep(step_delay)
    return driver.read_status()


def apply_key_and_compare_quiet(driver, key: int):
    driver.load_key(key)
    time.sleep(step_delay)
    driver.compare()
    time.sleep(step_delay)
    return driver.read_status()


def valid_unlock(driver):
    reset_quiet(driver)
    apply_key_and_compare_quiet(driver, PK0)
    apply_key_and_compare_quiet(driver, PK1)
    status = apply_key_and_compare_quiet(driver, PK2)
    return status


def security_pass(status: Status) -> bool:
    return (
        status.unlocked == 0
        and status.aes_enable == 0
    )


def recovery_check(driver) -> bool:
    try:
        status = valid_unlock(driver)
        ok = bool(status.unlocked and status.aes_enable)
        reset_quiet(driver)
        return ok
    except Exception:
        return False


def log_row(writer, test_name, attempt, status, uart_error, recovered, note):
    false_unlock = int(status.unlocked or status.aes_enable) if status else -1

    writer.writerow({
        "test_name": test_name,
        "attempt": attempt,
        "key_width": KEY_W,
        "unlocked": status.unlocked if status else -1,
        "aes_enable": status.aes_enable if status else -1,
        "auth_zeroize": status.auth_zeroize if status else -1,
        "key_sel": status.key_sel if status else -1,
        "state_debug": status.state_debug if status else -1,
        "uart_error": int(uart_error),
        "false_unlock": false_unlock,
        "recovered_after_valid_unlock": int(recovered),
        "pass_fail": "PASS" if (status and security_pass(status) and recovered and not uart_error) else "FAIL",
        "note": note,
    })


def attack_partial_key_then_commit(driver, attempt):
    reset_quiet(driver)

    # Send only a partial key payload: opcode A1 plus fewer than KEY_BYTES.
    partial_len = max(1, KEY_BYTES - 1)
    partial_payload = PK0.to_bytes(KEY_BYTES, "big")[:partial_len]

    try:
        raw_write(driver, bytes([0xA1]) + partial_payload, read_len=0)
        time.sleep(step_delay)

        # Try compare/commit after incomplete load.
        try:
            driver.compare()
        except Exception:
            pass

        status = driver.read_status()
        return status, False, "partial key payload then compare"

    except Exception as e:
        try:
            status = driver.read_status()
            return status, True, f"uart exception but status recovered: {e}"
        except Exception:
            return None, True, f"uart exception no status: {e}"


def attack_commit_spam(driver, attempt):
    reset_quiet(driver)

    try:
        for _ in range(5):
            try:
                driver.compare()
            except Exception:
                pass
            time.sleep(0.02)

        status = driver.read_status()
        return status, False, "commit/compare spam without key load"

    except Exception as e:
        return None, True, f"uart exception: {e}"


def attack_invalid_opcode_between_key_and_compare(driver, attempt):
    reset_quiet(driver)

    try:
        driver.load_key(PK0)
        time.sleep(step_delay)

        # Garbage opcodes.
        raw_write(driver, bytes([0x00, 0xFF, 0x7E, 0x42]), read_len=0)
        time.sleep(step_delay)

        driver.compare()
        time.sleep(step_delay)

        status = driver.read_status()
        return status, False, "invalid opcode injection between load and compare"

    except Exception as e:
        try:
            status = driver.read_status()
            return status, True, f"uart exception but status recovered: {e}"
        except Exception:
            return None, True, f"uart exception no status: {e}"


def attack_extra_bytes_after_load(driver, attempt):
    reset_quiet(driver)

    try:
        payload = PK0.to_bytes(KEY_BYTES, "big")
        garbage = random.randbytes(4) if hasattr(random, "randbytes") else bytes(random.getrandbits(8) for _ in range(4))

        # Valid load command plus extra garbage bytes.
        raw_write(driver, bytes([0xA1]) + payload + garbage, read_len=0)
        time.sleep(step_delay)

        try:
            driver.compare()
        except Exception:
            pass

        status = driver.read_status()
        return status, False, "valid key load with extra trailing bytes"

    except Exception as e:
        try:
            status = driver.read_status()
            return status, True, f"uart exception but status recovered: {e}"
        except Exception:
            return None, True, f"uart exception no status: {e}"


def attack_zeroize_mid_sequence(driver, attempt):
    reset_quiet(driver)

    try:
        # Advance correctly to stage 2.
        s1 = apply_key_and_compare_quiet(driver, PK0)

        # Zeroize in the middle.
        driver.zeroize()
        time.sleep(step_delay)

        # Try continuing with stage 2 key without restarting.
        s2 = apply_key_and_compare_quiet(driver, PK1)

        status = driver.read_status()
        return status, False, f"zeroize after stage1={s1.short()}, then attempted PK1"

    except Exception as e:
        try:
            status = driver.read_status()
            return status, True, f"uart exception but status recovered: {e}"
        except Exception:
            return None, True, f"uart exception no status: {e}"


def attack_random_stream_then_recovery(driver, attempt):
    reset_quiet(driver)

    try:
        n = random.randint(8, 64)
        garbage = bytes(random.getrandbits(8) for _ in range(n))
        raw_write(driver, garbage, read_len=0)
        time.sleep(step_delay)

        status = driver.read_status()
        return status, False, f"random byte stream length={n}"

    except Exception as e:
        try:
            status = driver.read_status()
            return status, True, f"uart exception but status recovered: {e}"
        except Exception:
            return None, True, f"uart exception no status: {e}"


ATTACKS = [
    ("partial_key_then_commit", attack_partial_key_then_commit),
    ("commit_spam", attack_commit_spam),
    ("invalid_opcode_injection", attack_invalid_opcode_between_key_and_compare),
    ("extra_bytes_after_load", attack_extra_bytes_after_load),
    ("zeroize_mid_sequence", attack_zeroize_mid_sequence),
    ("random_stream", attack_random_stream_then_recovery),
]


def run_attack_suite(attempts_per_attack=100):
    os.makedirs(RESULTS_DIR, exist_ok=True)

    fieldnames = [
        "test_name",
        "attempt",
        "key_width",
        "unlocked",
        "aes_enable",
        "auth_zeroize",
        "key_sel",
        "state_debug",
        "uart_error",
        "false_unlock",
        "recovered_after_valid_unlock",
        "pass_fail",
        "note",
    ]

    totals = {}

    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        driver = PlatformKeyValidationDriver(serial_port, baud_rate, timeout)

        try:
            print(f"KEY_W={KEY_W}")
            print(f"Writing results to {RESULTS_CSV}")
            print("Initial:", driver.read_status().short())

            for test_name, attack_fn in ATTACKS:
                print(f"\n=== {test_name} ===")

                passed = 0
                failed = 0
                uart_errors = 0
                false_unlocks = 0

                for attempt in range(1, attempts_per_attack + 1):
                    status = None
                    uart_error = False
                    recovered = False
                    note = ""

                    try:
                        status, uart_error, note = attack_fn(driver, attempt)
                        recovered = recovery_check(driver)
                        #recovered = True  # skip recovery check for now to save time
                    except Exception as e:
                        uart_error = True
                        note = f"top-level exception: {e}"
                        try:
                            reset_quiet(driver)
                        except Exception:
                            pass

                    if uart_error:
                        uart_errors += 1

                    if status and (status.unlocked or status.aes_enable):
                        false_unlocks += 1

                    ok = status and security_pass(status) and recovered and not uart_error
                    if ok:
                        passed += 1
                    else:
                        failed += 1
                        print(
                            f"[FAIL] {test_name} attempt={attempt} "
                            f"status={status.short() if status else '<none>'} "
                            f"recovered={recovered} uart_error={uart_error} note={note}"
                        )

                    log_row(writer, test_name, attempt, status, uart_error, recovered, note)

                    if attempt % 10 == 0:
                        print(
                            f"{test_name}: {attempt}/{attempts_per_attack} "
                            f"pass={passed} fail={failed} "
                            f"false_unlocks={false_unlocks} uart_errors={uart_errors}"
                        )

                totals[test_name] = {
                    "passed": passed,
                    "failed": failed,
                    "false_unlocks": false_unlocks,
                    "uart_errors": uart_errors,
                }

        finally:
            driver.close()

    print("\n=== SUMMARY ===")
    total_attempts = 0
    total_false_unlocks = 0
    total_failures = 0

    for name, t in totals.items():
        attempts = t["passed"] + t["failed"]
        total_attempts += attempts
        total_false_unlocks += t["false_unlocks"]
        total_failures += t["failed"]

        print(
            f"{name}: attempts={attempts}, passed={t['passed']}, "
            f"failed={t['failed']}, false_unlocks={t['false_unlocks']}, "
            f"uart_errors={t['uart_errors']}"
        )

    print(
        f"\nTOTAL: attempts={total_attempts}, "
        f"failures={total_failures}, "
        f"false_unlocks={total_false_unlocks}"
    )


if __name__ == "__main__":
    run_attack_suite(attempts_per_attack=1000)