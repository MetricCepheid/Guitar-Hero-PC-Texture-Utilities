#!/usr/bin/env python3
import os
import re
import struct
import subprocess
import requests

def get_dds_format(dds_bytes):
    if len(dds_bytes) < 128 or dds_bytes[:4] != b'DDS ':
        return None
    fourcc = dds_bytes[84:88]
    return fourcc.decode('ascii', errors='ignore').strip()

def get_mipmap_count(dds_bytes):
    # Return mipmap count from DDS header (default 1 if not present).
    if len(dds_bytes) < 128 or dds_bytes[:4] != b'DDS ':
        return 1
    mipmap_count = struct.unpack_from('<I', dds_bytes, 28)[0]
    return mipmap_count if mipmap_count > 0 else 1

def regenerate_mipmaps(dds_path, mip_count):
    if mip_count <= 1:
        return dds_path # No mipmaps to generate

    temp_dir = os.path.join(os.path.dirname(dds_path), "_temp_mipmaps")
    os.makedirs(temp_dir, exist_ok=True)

    if os.name == "posix":
        dds_path_win = f"Z:{dds_path.replace('/', '\\')}"
        temp_dir_win = f"Z:{temp_dir.replace('/', '\\')}"
    else:
        dds_path_win = dds_path
        temp_dir_win = temp_dir

    cmd = [
        "texconv" if os.name == "nt" else "wine",
        "texconv.exe",
        "-m", str(mip_count),
        "-nologo",
        "-y",
        "-o", temp_dir_win,
        dds_path_win
    ]
    #print(f"{cmd}")

    if not os.path.exists("./texconv.exe"):
        url = "https://github.com/microsoft/DirectXTex/releases/download/oct2025/texconv.exe"
        dest = "./texconv.exe"
        print(f"Downloading {url}...")
        r = requests.get(url, stream=True)
        r.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Saved texconv to {dest}")  

    print(f"    Regenerating {mip_count} mipmaps for {os.path.basename(dds_path)}...")
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"    texconv failed: {e}")
        return dds_path

    regenerated_name = os.path.splitext(os.path.basename(dds_path))[0] + ".dds"
    regenerated_path = os.path.join(temp_dir, regenerated_name)
    if os.path.exists(regenerated_path):
        os.replace(regenerated_path, dds_path)
    else:
        print(f"    Warning: Regenerated file not found, using original.")

    try:
        os.rmdir(temp_dir)
    except OSError:
        pass
    return dds_path


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

        # Read original header to determine mip count and format
        original_header = data[offset:offset+128]
        if original_header[:4] != b'DDS ':
            msg = f'{dds_name} at 0x{offset:X}: No DDS header found in original file — skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue
        orig_format = get_dds_format(original_header)
        orig_mipmaps = get_mipmap_count(original_header)

        # Regenerate mipmaps if original had >1
        if orig_mipmaps > 1:
            regenerate_mipmaps(dds_path, orig_mipmaps)

        with open(dds_path, 'rb') as dds_file:
            dds_data = bytearray(dds_file.read())
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
            repair_log.append(msg)
        else:
            print(f'  {i}. {dds_name} matches format ({orig_format}), mipmaps: {orig_mipmaps}')

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


def batch_repack_dds(input_dir, log_file='dds_index.txt'):
    if not os.path.isdir(input_dir):
        print("Error: Provided path is not a directory.")
        return
    extracted_folders = [f for f in os.listdir(input_dir)
                         if os.path.isdir(os.path.join(input_dir, f)) and f.endswith('_extracted')]
    if not extracted_folders:
        print("No *_extracted folders found in directory.")
        return
    print(f"\n=== Starting batch DDS repack from {input_dir} ===\n")

    for idx, folder in enumerate(extracted_folders, start=1):
        folder_path = os.path.join(input_dir, folder)
        base_name = folder[:-10]
        possible_files = [f for f in os.listdir(input_dir) if f.startswith(base_name) and not f.endswith('_extracted')]
        if not possible_files:
            print(f"[{idx}] Could not find original file for '{folder}'. Skipping.")
            continue
        original_file = os.path.join(input_dir, possible_files[0])
        output_file = os.path.join(input_dir, f"{base_name}_repacked")
        print(f"[{idx}] Repacking using folder: {folder}")
        replace_dds_in_file(original_file, folder_path, log_file, output_file)
    print("\n=== Batch repack complete! ===\n")

if __name__ == '__main__':
    print("Guitar Hero III PC Texture Repacker")
    print("Does not currently support console because console is bullshit")
    print("")
    mode = input("Run in batch mode? (y/n): ").strip().lower()
    if mode == 'y':
        input_dir = input("Enter path to folder containing *_extracted folders: ").strip('"').strip()
        log_file = input("Enter DDS log filename (press Enter for default 'dds_index.txt'): ").strip('"').strip()
        if not log_file:
            log_file = 'dds_index.txt'
        batch_repack_dds(input_dir, log_file)
    else:
        original_file = input("Enter full path to the original *.pak\\*.pab\\*.img.xen file: ").strip('"').strip()
        dds_dir = input("Enter full path to the folder containing extracted DDS files: ").strip('"').strip()
        log_file = input("Enter DDS log filename (press Enter for default 'dds_index.txt'): ").strip('"').strip()
        output_file = input("Enter full path and filename for the repacked output file (press Enter for default 'global.pab.xen_repacked'): ").strip('"').strip()
        
        if not log_file:
            log_file = 'dds_index.txt'
        if not output_file:
            output_file = 'global.pab.xen_repacked'
        replace_dds_in_file(original_file, dds_dir, log_file, output_file)
