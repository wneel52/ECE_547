from uart_driver import (
    PlatformKeyValidationDriver,
    serial_port,
    baud_rate,
    timeout,
    time,
    KEY_W
)

# ============================================================
# Structured SPA / Power Profiling Test
#
# Goal:
# Create clearly separated operational windows so the
# Nordic PPK2 trace can be visually segmented and analyzed.
#
# Recommended:
# - Start PPK2 recording BEFORE running script
# - Sampling rate: 100 SPS or higher
# - Disable unnecessary LEDs if possible
#
# Window structure:
#
#   idle            5 s
#   zeroize         5 s
#   invalid compare 5 s
#   zeroize         5 s
#   valid stage1    5 s
#   zeroize         5 s
#   full unlock    10 s
#   zeroize         5 s
#
# Repeat N times
# ============================================================

# ------------------------------------------------------------
# Full platform keys from RTL
# ------------------------------------------------------------

PK0_FULL = 0x00112233445566778899AABBCCDDEEFF
PK1_FULL = 0x11111111222222223333333344444444
PK2_FULL = 0xAAAABBBBCCCCDDDDEEEEFFFF12345678

MASK = (1 << KEY_W) - 1

PK0 = PK0_FULL & MASK
PK1 = PK1_FULL & MASK
PK2 = PK2_FULL & MASK

BAD_KEY = 0xDEADBEEFCAFEBABE1234567890ABCDEF & MASK

# ------------------------------------------------------------
# Timing controls
# ------------------------------------------------------------

IDLE_TIME = 5
EVENT_TIME = 5
UNLOCK_TIME = 10

NUM_CYCLES = 20

# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def wait_window(label, seconds):
    print(f"\n[{label}] sleeping {seconds}s")
    time.sleep(seconds)


def do_zeroize(driver):
    print("[ACTION] ZEROIZE")
    ack = driver.zeroize()
    print("zeroize ack:", ack)
    print("status:", driver.read_status().short())


def do_invalid_compare(driver):
    print("[ACTION] INVALID COMPARE")

    driver.load_key(BAD_KEY)
    time.sleep(0.2)

    ack = driver.compare()
    print("compare ack:", ack)

    status = driver.read_status()
    print("status:", status.short())


def do_valid_stage1(driver):
    print("[ACTION] VALID STAGE 1")

    driver.load_key(PK0)
    time.sleep(0.2)

    ack = driver.compare()
    print("compare ack:", ack)

    status = driver.read_status()
    print("status:", status.short())


def do_full_unlock(driver):
    print("[ACTION] FULL UNLOCK")

    driver.load_key(PK0)
    time.sleep(0.2)
    driver.compare()
    print("stage1:", driver.read_status().short())

    time.sleep(0.5)

    driver.load_key(PK1)
    time.sleep(0.2)
    driver.compare()
    print("stage2:", driver.read_status().short())

    time.sleep(0.5)

    driver.load_key(PK2)
    time.sleep(0.2)
    driver.compare()

    status = driver.read_status()
    print("unlock:", status.short())


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    print("====================================================")
    print("Structured FPGA SPA / Power Profiling Test")
    print("====================================================")

    print(f"NUM_CYCLES   = {NUM_CYCLES}")
    print(f"IDLE_TIME    = {IDLE_TIME}s")
    print(f"EVENT_TIME   = {EVENT_TIME}s")
    print(f"UNLOCK_TIME  = {UNLOCK_TIME}s")

    driver = PlatformKeyValidationDriver(
        serial_port,
        baud_rate,
        timeout
    )

    try:

        print("\nInitial status:")
        print(driver.read_status().short())

        print("\n====================================================")
        print("START PPK2 RECORDING NOW")
        print("====================================================")

        time.sleep(5)

        for cycle in range(NUM_CYCLES):

            print("\n================================================")
            print(f"CYCLE {cycle + 1}/{NUM_CYCLES}")
            print("================================================")

            # ------------------------------------------------
            # Idle baseline
            # ------------------------------------------------

            wait_window("IDLE BASELINE", IDLE_TIME)

            # ------------------------------------------------
            # Zeroize
            # ------------------------------------------------

            do_zeroize(driver)
            wait_window("POST ZEROIZE", EVENT_TIME)

            # ------------------------------------------------
            # Invalid compare
            # ------------------------------------------------

            do_invalid_compare(driver)
            wait_window("POST INVALID COMPARE", EVENT_TIME)

            # ------------------------------------------------
            # Zeroize again
            # ------------------------------------------------

            do_zeroize(driver)
            wait_window("POST ZEROIZE", EVENT_TIME)

            # ------------------------------------------------
            # Valid stage 1
            # ------------------------------------------------

            do_valid_stage1(driver)
            wait_window("POST VALID STAGE1", EVENT_TIME)

            # ------------------------------------------------
            # Zeroize again
            # ------------------------------------------------

            do_zeroize(driver)
            wait_window("POST ZEROIZE", EVENT_TIME)

            # ------------------------------------------------
            # Full unlock sequence
            # ------------------------------------------------

            do_full_unlock(driver)
            wait_window("UNLOCKED WINDOW", UNLOCK_TIME)

            # ------------------------------------------------
            # Final zeroize
            # ------------------------------------------------

            do_zeroize(driver)
            wait_window("FINAL ZEROIZE", EVENT_TIME)

        print("\n====================================================")
        print("TEST COMPLETE")
        print("STOP PPK2 RECORDING")
        print("====================================================")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
