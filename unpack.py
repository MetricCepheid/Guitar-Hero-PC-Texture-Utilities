import os
import struct

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
        print('No DDS files found.')
        return
        
    print(f'Found {len(offsets)} DDS headers:')
    
    log_path = os.path.join(output_dir, log_file)
    with open(log_path, 'w', encoding='utf-8') as log:
        log.write('Extracted DDS Files Log\n')
        log.write('========================\n\n')
        
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
            
            print(f'  {i+1}. DDS found at 0x{start:X} ({start} bytes) -> "{out_name}" [{fourcc}]')
    
    print(f'\nAll DDS files extracted and logged to: {log_path}')


if __name__ == '__main__':
    print("=== DDS Extractor ===")
    file_path = input("Enter full path to the input file (.pab.xen (Console coming soon)): ").strip('"').strip()
    output_dir = input("Enter output directory (press Enter for default 'extracted_dds'): ").strip('"').strip()
    
    if not output_dir:
        output_dir = 'extracted_dds'
    
    extract_dds_files_with_log(file_path, output_dir)
