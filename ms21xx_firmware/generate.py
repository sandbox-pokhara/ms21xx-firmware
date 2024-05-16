from argparse import ArgumentParser
from pathlib import Path

BASE_DIR = Path(__file__).parent
MS2109 = BASE_DIR / "firmwares" / "ms2109.bin"
MS2130 = BASE_DIR / "firmwares" / "ms2130.bin"


def checksum(data: bytes, mask: int = 0xFFFF):
    return sum(data) & mask


def checksum_as_bytes(data: bytes, mask: int = 0xFFFF):
    return checksum(data, mask).to_bytes(2)


def replace_at_index(data: str, idx: int, value: str):
    idx = idx * 2
    data_before = data[:idx]
    data_after = data[idx + len(value) :]
    return data_before + value + data_after


def pretty_print(data: str):
    while data:
        line = data[:32]
        while line:
            print(line[:2], end=" ")
            line = line[2:]
        data = data[32:]
        print()


def patch_serial(data: str, header: str, value: str):
    serial_idx = data.index(header) // 2 + 4
    serial_data = value.encode("utf-16-le")
    serial_len = (len(serial_data) + 2).to_bytes(1)
    # 03 means that the descriptor is in string format
    data = replace_at_index(data, serial_idx, serial_len.hex() + "03")
    data = replace_at_index(data, serial_idx + 2, serial_data.hex())
    return data


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--chip", default="ms2130", choices=["ms2109", "ms2130"]
    )
    parser.add_argument("--output", default="output.bin")
    parser.add_argument("--vid", default="ffff")
    parser.add_argument("--pid", default="ffff")
    parser.add_argument("--firmware-version", default="ffffffff")
    parser.add_argument("--video", default="USB Video")
    parser.add_argument("--audio", default="USB Audio")
    parser.add_argument("--edid", default="")
    parser.add_argument("--serial", default="")
    args = parser.parse_args()

    # change hex values to lowercase
    args.vid = args.vid.lower()
    args.pid = args.pid.lower()
    args.firmware_version = args.firmware_version.lower()
    args.edid = args.edid.lower()

    # argument validation
    # TODO: write human readable error messages
    # TODO: check hex values are in range (0-f)
    assert len(args.vid) == 4
    assert len(args.pid) == 4
    assert len(args.firmware_version) == 8
    assert len(args.video) <= 15
    assert len(args.audio) <= 15
    assert len(args.serial) <= 30
    if args.edid:
        assert len(args.edid) == 512
        assert args.edid[:16] == "00ffffffffffff00"
        edid_hex = bytes.fromhex(args.edid)
        edid_checksum = checksum(edid_hex, mask=0xFF)
        assert edid_checksum == 0

    # data generation
    if args.chip == "ms2109":
        with open(MS2109, "rb") as fp:
            data = fp.read()

        # convert to string for easier manipulation
        data = data.hex()

        # modify the firmware data
        video_data = args.video.encode()
        video_len = (len(video_data) + 1).to_bytes(1)
        audio_data = args.audio.encode()
        audio_len = (len(audio_data) + 1).to_bytes(1)

        data = replace_at_index(data, 0x06, args.vid)
        data = replace_at_index(data, 0x08, args.pid)
        data = replace_at_index(data, 0x0C, args.firmware_version)
        data = replace_at_index(data, 0x10, video_len.hex())
        data = replace_at_index(data, 0x11, video_data.hex())
        data = replace_at_index(data, 0x20, audio_len.hex())
        data = replace_at_index(data, 0x21, audio_data.hex())
        if args.edid:
            edid_idx = data.index("00ffffffffffff00") // 2
            data = replace_at_index(data, edid_idx, args.edid)

        if args.serial:
            raise NotImplementedError("Serial is not supported in ms2109 yet.")

        # change the data back to bytes
        data = bytes.fromhex(data)

        # replace the checksum of firmware with correct checksum
        header = data[2:48]
        code = data[48:-4]
        header_checksum = checksum_as_bytes(header)
        code_checksum = checksum_as_bytes(code)
        data = data[:-4] + header_checksum + code_checksum

        # write the generated firmware
        with open(args.output, "wb") as fp:
            fp.write(data)

    if args.chip == "ms2130":
        with open(MS2130, "rb") as fp:
            data = fp.read()

        # convert to string for easier manipulation
        data = data.hex()

        # modify the firmware data
        video_data = args.video.encode()
        video_len = (len(video_data) + 1).to_bytes(1)
        audio_data = args.audio.encode()
        audio_len = (len(audio_data) + 1).to_bytes(1)

        data = replace_at_index(data, 0x04, args.vid)
        data = replace_at_index(data, 0x06, args.pid)
        data = replace_at_index(data, 0x0C, args.firmware_version)
        data = replace_at_index(data, 0x10, video_len.hex())
        data = replace_at_index(data, 0x11, video_data.hex())
        data = replace_at_index(data, 0x20, audio_len.hex())
        data = replace_at_index(data, 0x21, audio_data.hex())
        if args.edid:
            edid_idx = data.index("00ffffffffffff00") // 2
            data = replace_at_index(data, edid_idx, args.edid)

        if args.serial:
            # we are modifiying USB String Descriptors here
            data = patch_serial(data, "60402120", args.serial)
            data = patch_serial(data, "60402160", args.serial)

        # change the data back to bytes
        data = bytes.fromhex(data)

        # replace the checksum of firmware with correct checksum
        header = data[2:10] + data[16:48]
        code = data[48:-4]
        header_checksum = checksum_as_bytes(header)
        code_checksum = checksum_as_bytes(code)
        data = data[:-4] + header_checksum + code_checksum

        # write the generated firmware
        with open(args.output, "wb") as fp:
            fp.write(data)


if __name__ == "__main__":
    main()
