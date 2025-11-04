import os
import re
import struct

def get_dds_format(dds_bytes):
    """Reads the FourCC compression format from a DDS header."""
    if len(dds_bytes) < 128 or dds_bytes[:4] != b'DDS ':
        return None
    # DDS header starts at byte 0x00, pixel format FourCC at offset 84
    fourcc = dds_bytes[84:88]
    return fourcc.decode('ascii', errors='ignore').strip()

def replace_dds_in_file(original_file, dds_dir, log_file, output_file):
    log_path = os.path.join(dds_dir, log_file)
    if not os.path.exists(log_path):
        print(f'Error: Could not find log file at "{log_path}"')
        return
    
    with open(log_path, 'r', encoding='utf-8') as log:
        log_text = log.read()
    entries = re.findall(r'(dds_\d+\.dds)\s*?\n\s*Offset:\s*(\d+)', log_text)
    if not entries:
        print('No DDS entries found in log file.')
        return

    with open(original_file, 'rb') as f:
        data = bytearray(f.read())

    print(f'Loaded original file: {original_file} ({len(data)} bytes)')
    print(f'Found {len(entries)} DDS entries to replace.\n')

    # Create a repair/error log
    repair_log_path = os.path.join(dds_dir, 'dds_repair_log.txt')
    repair_log = []

    for i, (dds_name, offset_str) in enumerate(entries, start=1):
        offset = int(offset_str)
        dds_path = os.path.join(dds_dir, dds_name)

        if not os.path.exists(dds_path):
            msg = f'Missing file: {dds_name} — skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue

        with open(dds_path, 'rb') as dds_file:
            dds_data = bytearray(dds_file.read())

        # Extract header from original file section (first 128 bytes of DDS data)
        original_header = data[offset:offset+128]
        if original_header[:4] != b'DDS ':
            msg = f'{dds_name} at 0x{offset:X}: No DDS header found in original file — skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue

        orig_format = get_dds_format(original_header)
        new_format = get_dds_format(dds_data)

        if not orig_format or not new_format:
            msg = f'{dds_name} at 0x{offset:X}: Could not determine DDS format — skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue

        if orig_format != new_format:
            msg = (f'{dds_name} at 0x{offset:X}: Format mismatch — '
                   f'expected {orig_format}, got {new_format}.')
            print(f'  {msg}')

            # Attempt repair: replace header FourCC with original
            dds_data[84:88] = original_header[84:88]
            repaired_format = get_dds_format(dds_data)
            if repaired_format == orig_format:
                msg += ' Header repaired.'
                print(f'> Header repaired to {repaired_format}.')
            else:
                msg += ' Repair failed — skipping replacement.'
                print(f'> Repair failed.')
                repair_log.append(msg)
                continue

            repair_log.append(msg)
        else:
            print(f'  {i}. {dds_name} matches format ({orig_format}).')

        # Replace data in file
        if offset + len(dds_data) > len(data):
            msg = f'DDS {dds_name} at 0x{offset:X} exceeds file size — skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue

        data[offset:offset + len(dds_data)] = dds_data
        print(f'  Replaced DDS at 0x{offset:X} ({offset} bytes) with {dds_name}')

    with open(output_file, 'wb') as out:
        out.write(data)

    with open(repair_log_path, 'w', encoding='utf-8') as log_out:
        log_out.write('\n'.join(repair_log))

    print(f'\nRepacking complete! New file saved as: {output_file}')
    print(f'Repair log written to: {repair_log_path}')
    print(f'Just a note: there is a chance the repair log will be empty. I do not give enough of a fuck to check if it does and not write it.')


if __name__ == '__main__':
    print("=== DDS Repacker with Header Validation ===")
    original_file = input("Enter full path to the original *.pab.xen file: ").strip('"').strip()
    dds_dir = input("Enter full path to the folder containing extracted DDS files: ").strip('"').strip()
    log_file = input("Enter DDS log filename (press Enter for default 'dds_index.txt'): ").strip('"').strip()
    output_file = input("Enter full path and filename for the repacked output file (press Enter for default 'global.pab.xen_repacked'): ").strip('"').strip()

    if not log_file:
        log_file = 'dds_index.txt'
    if not output_file:
        output_file = 'global.pab.xen_repacked'

    replace_dds_in_file(original_file, dds_dir, log_file, output_file)
