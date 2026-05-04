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


def sampled_negative_test_batched(
    stage: int,
    total_trials: int = 10_000,
    batch_size: int = 1000,
    checkpoint: int = 250,
    reconnect_delay: float = 1.0,
):
    print(f"\nStage {stage} batched negative test")
    print(f"total_trials={total_trials}, batch_size={batch_size}")

    false_accepts = 0
    unexpected = 0
    uart_errors = 0
    completed = 0
    start = time.time()

    num_batches = (total_trials + batch_size - 1) // batch_size

    for batch in range(1, num_batches + 1):
        batch_start_trial = completed + 1
        batch_end_trial = min(completed + batch_size, total_trials)

        print(f"\n[stage {stage}] opening batch {batch}/{num_batches}: "
              f"trials {batch_start_trial}-{batch_end_trial}")

        driver = PlatformKeyValidationDriver(serial_port, baud_rate, timeout)

        try:
            print(f"[stage {stage}] batch initial status: {driver.read_status().short()}")

            for _ in range(batch_start_trial, batch_end_trial + 1):
                trial = completed + 1

                try:
                    if stage == 1:
                        reset_quiet(driver)
                        key = random_wrong_key(stage1_good)
                        status = apply_key_and_compare_quiet(driver, key)

                        false_accept = (
                            status.key_sel == 1
                            or status.state_debug == 1
                            or status.unlocked
                            or status.aes_enable
                        )

                        expected_reset = status.key_sel == 0 and status.state_debug == 0

                    elif stage == 2:
                        drive_stage2_quiet(driver)
                        key = random_wrong_key(stage2_good)
                        status = apply_key_and_compare_quiet(driver, key)

                        false_accept = (
                            status.key_sel == 2
                            or status.state_debug == 2
                            or status.unlocked
                            or status.aes_enable
                        )

                        expected_reset = status.key_sel == 0 and status.state_debug == 0

                    elif stage == 3:
                        drive_stage3_quiet(driver)
                        key = random_wrong_key(stage3_good)
                        status = apply_key_and_compare_quiet(driver, key)

                        false_accept = status.unlocked or status.aes_enable
                        expected_reset = status.key_sel == 0 and status.state_debug == 0

                    else:
                        raise ValueError("stage must be 1, 2, or 3")

                    if false_accept:
                        false_accepts += 1
                        print(
                            f"[FALSE_ACCEPT] stage={stage} trial={trial} "
                            f"key=0x{key:0{HEX_DIGITS}X} status={status.short()}"
                        )

                    elif not expected_reset:
                        unexpected += 1
                        print(
                            f"[UNEXPECTED] stage={stage} trial={trial} "
                            f"key=0x{key:0{HEX_DIGITS}X} status={status.short()}"
                        )

                    completed += 1

                    if completed % checkpoint == 0:
                        elapsed = time.time() - start
                        rate = completed / elapsed if elapsed > 0 else 0.0
                        print(
                            f"[stage {stage}] {completed}/{total_trials} "
                            f"false_accepts={false_accepts} "
                            f"unexpected={unexpected} "
                            f"uart_errors={uart_errors} "
                            f"rate={rate:.2f} trials/s"
                        )

                except Exception as e:
                    uart_errors += 1
                    print(f"[UART_ERROR] stage={stage} trial={trial}: {e}")
                    break

        finally:
            driver.close()

        if completed >= total_trials:
            break

        print(f"[stage {stage}] closing batch {batch}, sleeping {reconnect_delay}s")
        time.sleep(reconnect_delay)

    elapsed = time.time() - start
    print(
        f"\nStage {stage} complete: "
        f"completed={completed}/{total_trials}, "
        f"false_accepts={false_accepts}, "
        f"unexpected={unexpected}, "
        f"uart_errors={uart_errors}, "
        f"elapsed={elapsed:.1f}s"
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

    sampled_negative_test_batched(stage=1, total_trials=10_000, batch_size=1000)
    sampled_negative_test_batched(stage=2, total_trials=10_000, batch_size=1000)
    sampled_negative_test_batched(stage=3, total_trials=10_000, batch_size=1000)


if __name__ == "__main__":
    main()