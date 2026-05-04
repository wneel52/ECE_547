import serial
import time
from dataclasses import dataclass

# Serial port configuration
KEY_W = 16
KEY_BYTES = KEY_W // 8
HEX_DIGITS = KEY_BYTES * 2
MASK = (1 << KEY_W) - 1

serial_port = "COM3"
baud_rate = 115200
timeout = 2.0
boot_delay = 2.0
step_delay = 0.2

@dataclass
class Status:
    header: int
    raw: int
    unlocked: int
    aes_enable: int
    auth_zeroize: int
    key_sel: int
    state_debug: int

    @classmethod
    def from_bytes(cls, data: bytes):
        if len(data) != 2:
            raise ValueError(f"Error: Expected 2 bytes of data, got {len(data)}")
        if data[0] != 0xD0:
            raise ValueError(f"Error: Expected header byte 0xD0, got 0x{data[0]:02X}")

        s = data[1]
        return cls(
            header=data[0],
            raw=s,
            unlocked=s & 0x1,
            aes_enable=(s >> 1) & 0x1,
            auth_zeroize=(s >> 2) & 0x1,
            key_sel=(s >> 3) & 0x3,
            state_debug=(s >> 5) & 0x3,
        )

    def short(self) -> str:
        return (
            f"raw=0x{self.raw:02X}, "
            f"unlocked={self.unlocked}, "
            f"aes_enable={self.aes_enable}, "
            f"auth_zeroize={self.auth_zeroize}, "
            f"key_sel={self.key_sel}, "
            f"state_debug={self.state_debug}"
        )


class PlatformKeyValidationDriver:
    def __init__(self, port: str, baud: int, timeout: float):
        self.timeout = timeout
        self.serial_port = serial.Serial(port, baud, timeout=timeout)
        time.sleep(boot_delay)

        self.serial_port.reset_input_buffer()
        self.serial_port.reset_output_buffer()

    def close(self):
        if self.serial_port.is_open:
            self.serial_port.close()

    def _read_exact(self, n: int) -> bytes:
        deadline = time.time() + self.timeout
        data = b""

        while len(data) < n and time.time() < deadline:
            chunk = self.serial_port.read(n - len(data))
            if chunk:
                data += chunk

        if len(data) != n:
            raise ValueError(f"Error: Expected {n} bytes, got {len(data)}")

        return data

    def read_status(self) -> Status:
        self.serial_port.reset_input_buffer()
        self.serial_port.write(bytes([0xA3]))
        self.serial_port.flush()
        data = self._read_exact(2)
        return Status.from_bytes(data)

    def load_key(self, key: int) -> str:
        max_key = (1 << KEY_W) - 1
        if not (0 <= key <= max_key):
            raise ValueError(f"Error: Key must fit in {KEY_W} bits")

        payload = key.to_bytes(KEY_BYTES, byteorder="big")

        self.serial_port.reset_input_buffer()
        self.serial_port.write(bytes([0xA1]) + payload)
        self.serial_port.flush()

        ack = self._read_exact(1)
        return ack.hex(" ")

    def compare(self) -> str:
        self.serial_port.reset_input_buffer()
        self.serial_port.write(bytes([0xA2]))
        self.serial_port.flush()
        ack = self._read_exact(1)
        return ack.hex(" ")

    def zeroize(self) -> str:
        self.serial_port.reset_input_buffer()
        self.serial_port.write(bytes([0xA4]))
        self.serial_port.flush()
        ack = self._read_exact(1)
        return ack.hex(" ")

    def commit_illegal(self) -> str:
        self.serial_port.reset_input_buffer()
        self.serial_port.write(bytes([0xA5]))
        self.serial_port.flush()
        ack = self._read_exact(1)
        return ack.hex(" ")

    def reset_to_init(self) -> Status:
        ack = self.zeroize()
        time.sleep(step_delay)
        status = self.read_status()
        print(f"zeroize ack:{ack or '<none>'} -> ({status.short()})")
        return status

    def apply_key_and_compare(self, key: int) -> Status:
        load_ack = self.load_key(key)
        time.sleep(step_delay)

        cmp_ack = self.compare()
        time.sleep(step_delay)

        status = self.read_status()

        print(
            f"key=0x{key:0{HEX_DIGITS}X} "
            f"load_ack={load_ack or '<none>'} "
            f"cmp_ack={cmp_ack or '<none>'} "
            f"status=({status.short()})"
        )

        return status

    @staticmethod
    def classify_stage1(status: Status) -> str:
        if status.unlocked:
            return "error: device should not be unlocked at stage 1"
        if status.aes_enable:
            return "error: AES should not be enabled at stage 1"
        if status.key_sel == 1 and status.state_debug == 1:
            return "advanced to stage 2"
        if status.key_sel == 0 and status.state_debug == 0:
            return "reset to init"
        return "error: unexpected status at stage 1"

    @staticmethod
    def classify_stage2(status: Status) -> str:
        if status.unlocked:
            return "error: device should not be unlocked at stage 2"
        if status.aes_enable:
            return "error: AES should not be enabled at stage 2"
        if status.key_sel == 2 and status.state_debug == 2:
            return "advanced to stage 3"
        if status.key_sel == 0 and status.state_debug == 0:
            return "reset to init"
        if status.key_sel == 1 and status.state_debug == 1:
            return "remained at stage 2"
        return "error: unexpected status at stage 2"

    @staticmethod
    def classify_stage3(status: Status) -> str:
        if status.unlocked and status.aes_enable:
            return "unlocked"
        if status.key_sel == 0 and status.state_debug == 0:
            return "reset to init"
        return "unexpected state"