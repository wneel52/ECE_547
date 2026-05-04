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
    time
)
# UART / Hardware configuration
# Full 128-bit platform keys from RTL
PK0_FULL = 0x00112233445566778899AABBCCDDEEFF
PK1_FULL = 0x11111111222222223333333344444444
PK2_FULL = 0xAAAABBBBCCCCDDDDEEEEFFFF12345678

def trunc_key(full_key: int) -> int:
    return full_key & MASK

def fit_key(x: int) -> int:
    return x & MASK

def byte_swap(value: int) -> int:
    return int.from_bytes(value.to_bytes(KEY_BYTES, byteorder="big"), byteorder="little")

def unique(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

# Active keys for current KEY_W
stage1_good = trunc_key(PK0_FULL)
stage2_good = trunc_key(PK1_FULL)
stage3_good = trunc_key(PK2_FULL)

# Candidate sets
stage1_candidates = unique([0x0, fit_key(0x0123456789ABCDEF), MASK, stage1_good^1, byte_swap(stage1_good), stage1_good ^ (1 << (KEY_W-1)), stage1_good])
stage2_candidates = unique([0x0, fit_key(0x0123456789ABCDEF), MASK, stage2_good^1, byte_swap(stage2_good), stage2_good ^ (1 << (KEY_W-1)), stage2_good])
stage3_candidates = unique([0x0, fit_key(0x0123456789ABCDEF), MASK, stage3_good^1, byte_swap(stage3_good), stage3_good ^ (1 << (KEY_W-1)), stage3_good])

def drive_stage2(driver):
    driver.reset_to_init()
    return driver.apply_key_and_compare(stage1_good)


def drive_stage3(driver):
    driver.reset_to_init()

    status1 = driver.apply_key_and_compare(stage1_good)
    if status1.key_sel != 1:
        print("Error: Stage 1 failed, cannot proceed to stage 2")
        return status1

    status2 = driver.apply_key_and_compare(stage2_good)
    if status2.key_sel != 2:
        print("Error: Stage 2 failed, cannot proceed to stage 3")
        return status2

    return status2

def test_stage1_candidates(driver):
    print("Testing stage 1 candidates...")
    for key in stage1_candidates:
        driver.reset_to_init()
        status = driver.apply_key_and_compare(key)
        print(f"Stage 1 candidate: 0x{key:0{HEX_DIGITS}X} -> {driver.classify_stage1(status)}")


def test_stage2_candidates(driver):
    print("Testing stage 2 candidates...")
    for key in stage2_candidates:
        drive_stage2(driver)
        status = driver.apply_key_and_compare(key)
        print(f"Stage 2 candidate: 0x{key:0{HEX_DIGITS}X} -> {driver.classify_stage2(status)}")


def test_stage3_candidates(driver):
    print("Testing stage 3 candidates...")
    for key in stage3_candidates:
        drive_stage3(driver)
        status = driver.apply_key_and_compare(key)
        print(f"Stage 3 candidate: 0x{key:0{HEX_DIGITS}X} -> {driver.classify_stage3(status)}")

def main():
    print(f"KEY_W={KEY_W}")
    print(f"PK0 active = 0x{stage1_good:0{HEX_DIGITS}X}")
    print(f"PK1 active = 0x{stage2_good:0{HEX_DIGITS}X}")
    print(f"PK2 active = 0x{stage3_good:0{HEX_DIGITS}X}")  

    driver = PlatformKeyValidationDriver(serial_port, baud_rate, timeout)


    print("status:", driver.read_status().short())
    print("cmp ack:", driver.compare())
    print("status:", driver.read_status().short())
    print("zeroize ack:", driver.zeroize())
    print("status:", driver.read_status().short())

    try:
        print("Initial status:", driver.read_status().short())
        test_stage1_candidates(driver)
        test_stage2_candidates(driver)
        test_stage3_candidates(driver)

        # drive unlock sequence
        # 
        drive_stage3(driver)
        driver.apply_key_and_compare(stage3_good)
        time.sleep(1.5)  # observe unlocked state on LEDs

        print("Zeroize ack:", driver.zeroize())
        print("Final status:", driver.read_status().short())
    finally:
        driver.close()


if __name__ == "__main__":
    main()