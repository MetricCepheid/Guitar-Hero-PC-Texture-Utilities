#!/usr/bin/env python3
import os
import re
import struct
import subprocess
import requests
import tempfile
import shutil

def get_dds_format(dds_bytes):
    if len(dds_bytes) < 128 or dds_bytes[:4] != b'DDS ':
        return None
    fourcc = dds_bytes[84:88]
    try:
        return fourcc.decode('ascii', errors='ignore').strip()
    except:
        return None

def get_mipmap_count(dds_bytes):
    if len(dds_bytes) < 128 or dds_bytes[:4] != b'DDS ':
        return 1
    mipmap_count = struct.unpack_from('<I', dds_bytes, 28)[0]
    return mipmap_count if mipmap_count > 0 else 1

def get_dx10_dxgi_format(dds_bytes):
    if len(dds_bytes) < 128 + 20:
        return None
    dxgi = struct.unpack_from('<I', dds_bytes, 128)[0]
    return dxgi

def find_embedded_dds_length(full_data, offset):
    start = offset
    search_from = start + 4
    next_idx = full_data.find(b'DDS ', search_from)
    if next_idx == -1:
        return len(full_data) - start
    else:
        return next_idx - start

def ensure_texconv(destination="texconv.exe"):
    if os.path.exists(destination):
        return destination
    url = "https://github.com/microsoft/DirectXTex/releases/download/oct2025/texconv.exe"
    try:
        print(f"Downloading texconv from {url} ...")
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(destination, 0o755)
        print(f"Saved texconv to {destination}")
        return destination
    except Exception as e:
        print(f"Could not download texconv: {e}")
        return None

FOURCC_TO_TEXCONV_FMT = {
    'DXT1': 'BC1_UNORM',
    'DXT3': 'BC2_UNORM',
    'DXT5': 'BC3_UNORM',
    'ATI2': 'BC5_UNORM',
}

DXGI_TO_TEXCONV_FMT = {
    71: 'BC1_UNORM',  # DXGI_FORMAT_BC1_UNORM
    74: 'BC2_UNORM',  # DXGI_FORMAT_BC2_UNORM
    77: 'BC3_UNORM',  # DXGI_FORMAT_BC3_UNORM
    83: 'BC5_UNORM',  # DXGI_FORMAT_BC5_UNORM
}

def convert_png_to_dds(png_path, target_fourcc, mip_count, original_size, work_dir):
    texconv = ensure_texconv("texconv.exe")
    if not texconv:
        print("texconv.exe not available; skipping conversion.")
        return None

    if target_fourcc == 'DX10':
        print("DX10 format: conversion requires DXGI format mapping; caller must handle.")
        return None

    fmt = FOURCC_TO_TEXCONV_FMT.get(target_fourcc)
    if not fmt:
        print(f"Unsupported FourCC for conversion: {target_fourcc}")
        return None

    tmp_outdir = tempfile.mkdtemp(prefix="png_to_dds_")
    try:
        cmd = [
            texconv,
            "-ft", "DDS",
            "-f", fmt,
            "-m", str(mip_count),
            "-srgb",
            "-y",
            "-o", tmp_outdir,
            png_path
        ]
        try:
            proc = subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print("texconv failed:", e.stderr.decode(errors='ignore') if e.stderr else e)
            return None

        base = os.path.splitext(os.path.basename(png_path))[0] + ".dds"
        gen_path = os.path.join(tmp_outdir, base)
        if not os.path.exists(gen_path):
            files = [f for f in os.listdir(tmp_outdir) if f.lower().endswith('.dds')]
            if not files:
                print("texconv did not produce a .dds file.")
                return None
            gen_path = os.path.join(tmp_outdir, files[0])

        with open(gen_path, 'rb') as f:
            gen_bytes = bytearray(f.read())

        if len(gen_bytes) > original_size:
            if mip_count > 1:
                print("Generated DDS larger than original; retrying with mip_count=1...")
                shutil.rmtree(tmp_outdir)
                tmp_outdir = tempfile.mkdtemp(prefix="png_to_dds_")
                cmd = [
                    texconv,
                    "-ft", "DDS",
                    "-f", fmt,
                    "-m", "1",
                    "-y",
                    "-o", tmp_outdir,
                    png_path
                ]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    print("texconv fallback failed:", e.stderr.decode(errors='ignore') if e.stderr else e)
                    return None
                files = [f for f in os.listdir(tmp_outdir) if f.lower().endswith('.dds')]
                if not files:
                    print("Fallback texconv did not produce .dds")
                    return None
                gen_path = os.path.join(tmp_outdir, files[0])
                with open(gen_path, 'rb') as f:
                    gen_bytes = bytearray(f.read())

        if len(gen_bytes) <= original_size:
            if len(gen_bytes) < original_size:
                padding = original_size - len(gen_bytes)
                gen_bytes += b'\x00' * padding
            return bytes(gen_bytes)
        else:
            print(f"Generated DDS ({len(gen_bytes)}) larger than original embedded size ({original_size}) - skipping.")
            return None
    finally:
        try:
            shutil.rmtree(tmp_outdir)
        except Exception:
            pass

def regenerate_mipmaps(dds_path, mip_count):
    if mip_count <= 1:
        return dds_path
    temp_dir = os.path.join(os.path.dirname(dds_path), "_temp_mipmaps")
    os.makedirs(temp_dir, exist_ok=True)
    texconv = ensure_texconv("texconv.exe")
    if not texconv:
        return dds_path

    cmd = [
        texconv,
        "-m", str(mip_count),
        "-nologo",
        "-y",
        "-o", temp_dir,
        dds_path
    ]
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
        for f in os.listdir(temp_dir):
            if f.lower().endswith('.dds'):
                candidate = os.path.join(temp_dir, f)
                os.replace(candidate, dds_path)
                break
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
        png_path = os.path.join(dds_dir, os.path.splitext(dds_name)[0] + ".png")
        if not os.path.exists(dds_path) and not os.path.exists(png_path):
            msg = f'Missing file: {dds_name} (and no {os.path.splitext(dds_name)[0]}.png) - skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue

        if offset + 128 > len(data):
            msg = f'{dds_name} at 0x{offset:X}: Not enough data for DDS header in original file - skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue

        original_header = data[offset:offset+128]
        if original_header[:4] != b'DDS ':
            msg = f'{dds_name} at 0x{offset:X}: No DDS header found in original file - skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue

        orig_format = get_dds_format(original_header)
        orig_mipmaps = get_mipmap_count(original_header)
        original_embedded_len = find_embedded_dds_length(bytes(data), offset)

        generated_dds_bytes = None
        if os.path.exists(png_path):
            if orig_format == 'DX10':
                dxgi = get_dx10_dxgi_format(data[offset:offset+148])  # offset+128 + 4 needed
                texconv_fmt = DXGI_TO_TEXCONV_FMT.get(dxgi)
                if texconv_fmt:
                    print(f'  {i}. {dds_name}: Converting PNG to DX10-derived format (DXGI {dxgi}) with {orig_mipmaps} mips...')
                    texconv = ensure_texconv("texconv.exe")
                    if not texconv:
                        msg = f'{dds_name}: texconv not available for DX10 conversion.'
                        print(f'  {msg}')
                        repair_log.append(msg)
                    else:
                        tmp_dir = tempfile.mkdtemp(prefix="dx10_conv_")
                        try:
                            cmd = [
                                texconv,
                                "-ft", "DDS",
                                "-f", texconv_fmt,
                                "-m", str(orig_mipmaps),
                                "-y",
                                "-o", tmp_dir,
                                png_path
                            ]
                            try:
                                subprocess.run(cmd, check=True, capture_output=True)
                            except subprocess.CalledProcessError as e:
                                msg = f'{dds_name}: texconv failed for DX10 mapping: {e}'
                                print(f'  {msg}')
                                repair_log.append(msg)
                            else:
                                files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.dds')]
                                if files:
                                    gen = os.path.join(tmp_dir, files[0])
                                    with open(gen, 'rb') as gf:
                                        gen_bytes = gf.read()
                                    if len(gen_bytes) <= original_embedded_len:
                                        if len(gen_bytes) < original_embedded_len:
                                            gen_bytes += b'\x00' * (original_embedded_len - len(gen_bytes))
                                        generated_dds_bytes = gen_bytes
                                    else:
                                        print("Generated DX10 DDS larger than original; retrying with mips=1")
                                        try:
                                            subprocess.run([texconv, "-ft", "DDS", "-f", texconv_fmt, "-m", "1", "-y", "-o", tmp_dir, png_path], check=True, capture_output=True)
                                            files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.dds')]
                                            if files:
                                                gen = os.path.join(tmp_dir, files[0])
                                                with open(gen, 'rb') as gf:
                                                    gen_bytes = gf.read()
                                                if len(gen_bytes) <= original_embedded_len:
                                                    if len(gen_bytes) < original_embedded_len:
                                                        gen_bytes += b'\x00' * (original_embedded_len - len(gen_bytes))
                                                    generated_dds_bytes = gen_bytes
                                        except Exception:
                                            pass
                        finally:
                            try:
                                shutil.rmtree(tmp_dir)
                            except Exception:
                                pass
                else:
                    msg = f'{dds_name} DX10: Unknown DXGI format ({dxgi}) - cannot convert PNG reliably.'
                    print(f'  {msg}')
                    repair_log.append(msg)
            else:
                print(f'  {i}. {dds_name}: Converting PNG to {orig_format} with {orig_mipmaps} mips (target size {original_embedded_len} bytes)')
                gen_bytes = convert_png_to_dds(png_path, orig_format, orig_mipmaps, original_embedded_len, dds_dir)
                if gen_bytes:
                    generated_dds_bytes = gen_bytes
                else:
                    msg = f'{dds_name}: PNG->DDS conversion failed or output too large - will try existing DDS file if present.'
                    print(f'  {msg}')
                    repair_log.append(msg)

        if generated_dds_bytes is None and os.path.exists(dds_path):
            if orig_mipmaps > 1:
                regenerate_mipmaps(dds_path, orig_mipmaps)
            with open(dds_path, 'rb') as dds_file:
                dds_data = bytearray(dds_file.read())
            new_format = get_dds_format(dds_data)
            if not orig_format or not new_format:
                msg = f'{dds_name} at 0x{offset:X}: Could not determine DDS format - skipping.'
                print(f'  {msg}')
                repair_log.append(msg)
                continue

            if orig_format != new_format:
                msg = (f'{dds_name} at 0x{offset:X}: Format mismatch - expected {orig_format}, got {new_format}.')
                print(f'  {msg}')
                repair_log.append(msg)
            else:
                print(f'  {i}. {dds_name} matches format ({orig_format}), mipmaps: {orig_mipmaps}')

            if len(dds_data) > original_embedded_len:
                msg = f'{dds_name} file size ({len(dds_data)}) larger than embedded space ({original_embedded_len}) - skipping replacement.'
                print(f'  {msg}')
                repair_log.append(msg)
                continue
            if len(dds_data) < original_embedded_len:
                dds_data += b'\x00' * (original_embedded_len - len(dds_data))
            data[offset:offset + original_embedded_len] = dds_data[:original_embedded_len]
            print(f'  Replaced DDS at 0x{offset:X} ({offset} bytes) with {dds_name}')
        elif generated_dds_bytes is not None:
            gen_format = get_dds_format(generated_dds_bytes[:128])
            if gen_format and gen_format != orig_format:
                msg = f'{dds_name} generated format mismatch: expected {orig_format}, got {gen_format}; skipping replacement.'
                print(f'  {msg}')
                repair_log.append(msg)
                continue
            data[offset:offset + original_embedded_len] = generated_dds_bytes[:original_embedded_len]
            print(f'  Replaced DDS at 0x{offset:X} ({offset} bytes) with generated PNG->DDS (padded/truncated to match embedded size)')
        else:
            msg = f'{dds_name} at 0x{offset:X}: No usable replacement available - skipping.'
            print(f'  {msg}')
            repair_log.append(msg)
            continue

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