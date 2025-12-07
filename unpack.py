#!/usr/bin/env python3
import os
import struct
from PIL import Image

def convert_dds_to_png(dds_path, png_path):
    try:
        with Image.open(dds_path) as img:
            img.save(png_path, "PNG")
        print(f"+ PNG saved: {png_path}")
    except Exception as e:
        print(f"- Failed to convert DDS to PNG: {dds_path}")
        print(f"- Error: {e}")

def extract_dds_files_with_log(file_path, output_dir='extracted_dds', log_file='dds_index.txt'):
    signature = b'DDS '
    offsets = []
    os.makedirs(output_dir, exist_ok=True)
    with open(file_path, 'rb') as f:
        data = f.read()
    index = data.find(signature)

    while index != -1:
        offsets.append(index)
        index = data.find(signature, index + 1)

    if not offsets:
        print(f'No DDS files found in {file_path}.')
        return

    print(f'Found {len(offsets)} DDS headers in "{os.path.basename(file_path)}":')

    log_path = os.path.join(output_dir, log_file)
    with open(log_path, 'w', encoding='utf-8') as log:
        log.write(f'Extracted DDS Files Log for {os.path.basename(file_path)}\n')
        log.write('===========================================\n\n')

        for i, start in enumerate(offsets):
            end = offsets[i + 1] if i + 1 < len(offsets) else len(data)
            dds_data = data[start:end]
            out_name = f'dds_{i+1:03}.dds'
            out_path = os.path.join(output_dir, out_name)

            try:
                fourcc_bytes = dds_data[84:88]
                fourcc = fourcc_bytes.decode('ascii', errors='ignore').strip()
                if not fourcc:
                    fourcc = "UNKNOWN"
            except Exception:
                fourcc = "UNKNOWN"

            with open(out_path, 'wb') as out_file:
                out_file.write(dds_data)

            log.write(f'{out_name}\n')
            log.write(f'  Offset: {start} bytes (0x{start:X})\n')
            log.write(f'  Format: {fourcc}\n\n')
            print(f'++ {i+1}. DDS found at 0x{start:X} -> "{out_name}" [{fourcc}]')

            png_name = f'dds_{i+1:03}.png'
            png_path = os.path.join(output_dir, png_name)
            print("+ Converting to PNG...")
            convert_dds_to_png(out_path, png_path)

            try:
                os.remove(out_path)
                print(f"+ Deleted DDS: {out_path}")
            except Exception as e:
                print(f"- Failed to delete DDS: {e}")
    print(f"\nAll DDS files extracted and converted to PNG.\nLog saved to: {log_path}\n")

def batch_extract_dds(input_dir):
    if not os.path.isdir(input_dir):
        print("Error: Provided path is not a directory.")
        return
    files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]

    if not files:
        print("No files found in directory.")
        return
    print(f"\n=== Starting batch DDS extraction from {input_dir} ===\n")

    for idx, filename in enumerate(files, start=1):
        file_path = os.path.join(input_dir, filename)
        base_name, _ = os.path.splitext(filename)
        output_dir = os.path.join(input_dir, f"{base_name}_extracted")
        print(f"[{idx}] Processing file: {filename}")
        extract_dds_files_with_log(file_path, output_dir)
    print("\n=== Batch extraction complete! ===\n")

if __name__ == '__main__':
    print("Guitar Hero III PC Texture Unpacker")
    print("Does not support console because console is bullshit")
    print("")
    mode = input("Run in batch mode? (y/n): ").strip().lower()

    if mode == 'y':
        input_dir = input("Enter path to folder containing files: ").strip('"').strip()
        batch_extract_dds(input_dir)
    else:
        file_path = input("Enter full path to input file *.pak/*.pab/*.img.xen: ").strip('"').strip()
        output_dir = input("Enter output directory (press Enter for default 'extracted_dds'): ").strip('"').strip()
        if not output_dir:
            output_dir = 'extracted_dds'
        extract_dds_files_with_log(file_path, output_dir)