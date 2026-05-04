import random
import time

from uart_driver import (
    PlatformKeyValidationDriver,
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


def trunc_key(full_key: int) -> int:
    return full_key & MASK


stage1_good = trunc_key(PK0_FULL)
stage2_good = trunc_key(PK1_FULL)
stage3_good = trunc_key(PK2_FULL)


def random_wrong_key(good_key: int) -> int:
    while True:
        key = random.getrandbits(KEY_W) & MASK
        if key != good_key:
            return key


def apply_key_and_compare_quiet(driver, key: int):
    driver.load_key(key)
    time.sleep(step_delay)
    driver.compare()
    time.sleep(step_delay)
    return driver.read_status()


def reset_quiet(driver):
    driver.zeroize()
    time.sleep(step_delay)
    return driver.read_status()


def drive_stage2_quiet(driver):
    reset_quiet(driver)
    return apply_key_and_compare_quiet(driver, stage1_good)


def drive_stage3_quiet(driver):
    reset_quiet(driver)

    s1 = apply_key_and_compare_quiet(driver, stage1_good)
    if not (s1.key_sel == 1 and s1.state_debug == 1):
        raise RuntimeError(f"Stage 1 setup failed: {s1.short()}")

    s2 = apply_key_and_compare_quiet(driver, stage2_good)
    if not (s2.key_sel == 2 and s2.state_debug == 2):
        raise RuntimeError(f"Stage 2 setup failed: {s2.short()}")

    return s2


def repeated_unlock_test(driver, cycles: int = 100):
    print(f"\nRepeated unlock test: cycles={cycles}")
    failures = 0
    start = time.time()

    for i in range(1, cycles + 1):
        try:
            drive_stage3_quiet(driver)
            status = apply_key_and_compare_quiet(driver, stage3_good)

            if not (status.unlocked and status.aes_enable):
                failures += 1
                print(f"[FAIL] cycle={i} status={status.short()}")

            reset_quiet(driver)

        except Exception as e:
            failures += 1
            print(f"[ERROR] cycle={i}: {e}")
            try:
                reset_quiet(driver)
            except Exception:
                pass

        if i % 10 == 0:
            print(f"[unlock] {i}/{cycles}, failures={failures}")

    elapsed = time.time() - start
    print(
        f"Repeated unlock complete: passed={cycles - failures}/{cycles}, "
        f"failures={failures}, elapsed={elapsed:.1f}s"
    )


def main():
    print(f"KEY_W={KEY_W}")
    print(f"PK0 active = 0x{stage1_good:0{HEX_DIGITS}X}")
    print(f"PK1 active = 0x{stage2_good:0{HEX_DIGITS}X}")
    print(f"PK2 active = 0x{stage3_good:0{HEX_DIGITS}X}")

    driver = PlatformKeyValidationDriver(serial_port, baud_rate, timeout)
    try:
        print("Initial:", driver.read_status().short())
        repeated_unlock_test(driver, cycles=100)
    finally:
        driver.close()

if __name__ == "__main__":
    main()