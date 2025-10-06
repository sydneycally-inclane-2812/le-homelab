#!/usr/bin/env python3
"""
Video Transcoding and Transfer Script

This script transcodes video files from any format to H.264+AAC MKV containers,
extracts subtitles as separate SRT files, and transfers them to a remote destination.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
import paramiko
import time
import re
import getpass

def find_video_files(source_folder):
    """Find all video files in the source folder."""
    video_extensions = [
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', 
        '.m4v', '.mpg', '.mpeg', '.3gp', '.ts'
    ]
    
    video_files = []
    for ext in video_extensions:
        video_files.extend(Path(source_folder).glob(f"**/*{ext}"))
    
    return video_files

def has_subtitles(video_path):
    """Check if video has subtitle streams using ffprobe."""
    cmd = [
        'ffprobe', 
        '-v', 'error', 
        '-select_streams', 's', 
        '-show_entries', 'stream=index', 
        '-of', 'csv=p=0', 
        str(video_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip() != ''

def extract_subtitles(video_path, output_path):
    """Extract subtitles from video to SRT file."""
    
    # First, check what type of subtitles we're dealing with
    subtitle_info_cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 's:0',
        '-show_entries', 'stream=codec_name',
        '-of', 'csv=p=0',
        str(video_path)
    ]
    
    result = subprocess.run(subtitle_info_cmd, capture_output=True, text=True)
    subtitle_codec = result.stdout.strip()
    
    print(f"Detected subtitle codec: {subtitle_codec}")
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Fix potential path issues by normalizing the path
    srt_path = os.path.normpath(f"{output_path}.srt")
    
    # Different approach based on subtitle format
    if subtitle_codec in ['ass', 'ssa']:
        # For ASS/SSA subtitles, extract to ASS first then convert
        temp_ass_path = os.path.normpath(f"{output_path}.ass")
        
        try:
            # Extract to ASS
            ass_cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-map', '0:s:0',
                '-c:s', 'copy',
                temp_ass_path
            ]
            subprocess.run(ass_cmd, check=True)
            
            # Convert ASS to SRT
            srt_cmd = [
                'ffmpeg',
                '-i', temp_ass_path,
                '-c:s', 'srt',
                srt_path
            ]
            subprocess.run(srt_cmd, check=True)
            
            # Remove temporary ASS file
            os.remove(temp_ass_path)
            
        except subprocess.CalledProcessError as e:
            print(f"Warning: ASS/SSA subtitle extraction failed: {e}")
            return False
    
    elif subtitle_codec in ['dvd_subtitle', 'dvdsub', 'hdmv_pgs_subtitle', 'pgssub']:
        print("Warning: Image-based subtitles detected. OCR conversion required.")
        try:
            # Use OCR to extract subtitles from image-based formats
            ocr_cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-map', '0:s:0',
                '-c:s', 'srt',
                srt_path
            ]
            subprocess.run(ocr_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Image-based subtitle extraction failed: {e}")
            return False
    
    else:
        # Standard extraction for text-based subtitles
        try:
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-map', '0:s:0',
                '-c:s', 'srt',
                srt_path
            ]
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to extract subtitles: {e}")
            return False
    
    return os.path.exists(srt_path)

def transcode_video(video_path, output_path, bitrate='2M', use_gpu=False):
    """Transcode video to H.264+AAC MKV."""
    
    # Check if video is 10-bit (using ffprobe)
    is_10bit = False
    try:
        cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-select_streams', 'v:0', 
            '-show_entries', 'stream=bits_per_raw_sample,pix_fmt', 
            '-of', 'csv=p=0', 
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout.strip()
        is_10bit = '10' in output or 'p10' in output
        if is_10bit:
            print(f"Detected 10-bit content: {video_path}")
    except Exception as e:
        print(f"Warning: Could not determine bit depth: {e}")
    
    if use_gpu:
        # GPU-accelerated encoding with NVIDIA
        cmd = [
            'ffmpeg',
            '-i', str(video_path)
        ]
        
        # If 10-bit source, add pixel format conversion for NVENC
        if is_10bit:
            print("Converting 10-bit content for NVENC compatibility")
            cmd.extend(['-pix_fmt', 'yuv420p'])
            
        cmd.extend([
            '-c:v', 'h264_nvenc',
            '-preset', 'p4',
            '-profile:v', 'high',
            '-b:v', bitrate,
            '-c:a', 'aac',
            '-b:a', '192k',
            '-map', '0:v',
            '-map', '0:a',
            f"{output_path}.mkv"
        ])
        
        try:
            subprocess.run(cmd, check=True)
            print("GPU encoding completed successfully")
            
        except subprocess.CalledProcessError as e:
            print(f"GPU encoding failed: {e}")
            print("Falling back to CPU encoding...")
            
            # CPU encoding fallback
            cpu_cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '22',
                '-b:v', bitrate,
                '-c:a', 'aac',
                '-b:a', '192k',
                '-map', '0:v',
                '-map', '0:a',
                f"{output_path}.mkv"
            ]
            subprocess.run(cpu_cmd, check=True)
    else:
        # CPU encoding (original)
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '22',
            '-b:v', bitrate,
            '-c:a', 'aac',
            '-b:a', '192k',
            '-map', '0:v',
            '-map', '0:a',
            f"{output_path}.mkv"
        ]
        subprocess.run(cmd, check=True)
    

def create_remote_dir(sftp, remote_path):
    """Create remote directory and all parent directories if they don't exist."""
    if remote_path == '/' or remote_path == '':
        return
    
    try:
        sftp.stat(remote_path)
    except IOError:
        parent = os.path.dirname(remote_path)
        create_remote_dir(sftp, parent)
        try:
            sftp.mkdir(remote_path)
        except IOError:
            # Directory might have been created by another process
            pass

def transfer_file(local_path, remote_host, remote_path, username=None, password=None, transfer_method='sftp'):
    """Transfer file to remote host using SFTP or SCP."""
    if username is None:
        username = os.getlogin()
    
    if transfer_method == 'sftp':
        # Use paramiko for SFTP
        transport = paramiko.Transport((remote_host, 22))
        
        try:
            # Try authentication methods in order
            if password:
                try:
                    print(f"Attempting password authentication for {username}@{remote_host}")
                    transport.connect(username=username, password=password)
                except paramiko.SSHException as e:
                    print(f"Password authentication failed: {e}")
                    raise
            else:
                # Try to use SSH key authentication
                print(f"Attempting key-based authentication for {username}@{remote_host}")
                key_paths = [
                    os.path.expanduser('~/.ssh/id_rsa'),
                    os.path.expanduser('~/.ssh/id_ed25519')
                ]
                
                for key_path in key_paths:
                    if os.path.exists(key_path):
                        try:
                            key = paramiko.RSAKey.from_private_key_file(key_path)
                            transport.connect(username=username, pkey=key)
                            print(f"Key authentication successful using {key_path}")
                            break
                        except Exception as e:
                            print(f"Failed to authenticate with key {key_path}: {e}")
                    else:
                        print(f"Key file not found: {key_path}")
                
                # If we got here and transport isn't active, all auth methods failed
                if not transport.is_active():
                    raise paramiko.SSHException("All authentication methods failed")
                    
            sftp = paramiko.SFTPClient.from_transport(transport)
            
            # Create remote directory if it doesn't exist
            remote_dir = os.path.dirname(remote_path)
            create_remote_dir(sftp, remote_dir)
                
            sftp.put(local_path, remote_path)
            sftp.close()
            transport.close()
            
        except Exception as e:
            transport.close()
            print(f"SFTP transfer failed: {e}")
            print("Trying SCP instead...")
            
            # Fall back to SCP
            try:
                # First ensure remote directory exists
                remote_dir = os.path.dirname(remote_path)
                if password:
                    # Use sshpass if password is provided
                    mkdir_cmd = ['sshpass', '-p', password, 'ssh', f"{username}@{remote_host}", f"mkdir -p '{remote_dir}'"]
                    scp_cmd = ['sshpass', '-p', password, 'scp', local_path, f"{username}@{remote_host}:{remote_path}"]
                else:
                    # Use regular ssh/scp with key auth
                    mkdir_cmd = ['ssh', f"{username}@{remote_host}", f"mkdir -p '{remote_dir}'"]
                    scp_cmd = ['scp', local_path, f"{username}@{remote_host}:{remote_path}"]
                
                subprocess.run(mkdir_cmd, check=True)
                subprocess.run(scp_cmd, check=True)
                return True
            except subprocess.CalledProcessError as e:
                print(f"SCP transfer also failed: {e}")
                return False
    else:
        # Use scp
        try:
            # First ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            
            if password:
                # Check if sshpass is available
                try:
                    if os.name == 'nt':  # Windows
                        check_cmd = ['where', 'sshpass']
                    else:  # Unix/Linux/Mac
                        check_cmd = ['which', 'sshpass']
                    subprocess.run(check_cmd, check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    print("Warning: sshpass not found. Password authentication may not work with SCP.")
                    print("Try installing sshpass or using key-based authentication.")
                    mkdir_cmd = ['ssh', f"{username}@{remote_host}", f"mkdir -p '{remote_dir}'"]
                    scp_cmd = ['scp', local_path, f"{username}@{remote_host}:{remote_path}"]
            else:
                mkdir_cmd = ['ssh', f"{username}@{remote_host}", f"mkdir -p '{remote_dir}'"]
                scp_cmd = ['scp', local_path, f"{username}@{remote_host}:{remote_path}"]
            
            subprocess.run(mkdir_cmd, check=True)
            subprocess.run(scp_cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"SCP transfer failed: {e}")
            return False
    
    return True
def main():
        # Check if any arguments were provided
    if len(sys.argv) == 1:
        # No arguments provided, run in interactive mode
        print("=== Video Transcoding and Transfer Tool ===")
        print("Running in interactive mode. Press Ctrl+C to exit at any time.")
        
        # Get source folder
        source = input("\nEnter source folder containing videos: ").strip()
        while not os.path.isdir(source):
            print("Invalid directory!")
            source = input("Enter source folder containing videos: ").strip()
        
        # Get bitrate
        bitrate = input("\nEnter video bitrate (leave blank for 2M): ").strip()
        if not bitrate:
            bitrate = "2M"
        
         # Add GPU option
        use_gpu = input("\nUse NVIDIA GPU acceleration? (y/n, leave blank for no): ").lower().strip() == 'y'

        # Get destination host
        dest_host = input("\nEnter destination host for file transfer: ").strip()
        while not dest_host:
            dest_host = input("Destination host is required: ").strip()
        
        # Get destination folder
        dest_folder = input("\nEnter destination folder on remote host: ").strip()
        while not dest_folder:
            dest_folder = input("Destination folder is required: ").strip()
        
        # Get username (optional)
        username = input("\nEnter username for remote host (leave blank for current user): ").strip() or None
        password = getpass.getpass("\nEnter password for remote host (leave blank for SSH key auth): ") or None
        # Get transfer method
        method = input("\nEnter transfer method (sftp/scp, leave blank for sftp): ").lower().strip()
        if not method or method not in ["sftp", "scp"]:
            method = "sftp"
        
        # Get temp folder
        temp = input("\nEnter temporary folder for transcoded files (leave blank for /tmp/transcode): ").strip()
        if not temp:
            temp = "/tmp/transcode"
        
        # Create an args-like object with the collected values
        class Args:
            pass
        
        args = Args()
        args.source = source
        args.bitrate = bitrate
        args.dest_host = dest_host
        args.dest_folder = dest_folder
        args.username = username
        args.password = password
        args.method = method
        args.temp = temp
        args.use_gpu = use_gpu
        
        print("\nStarting transcoding process with the following parameters:")
        print(f"Source: {args.source}")
        print(f"Bitrate: {args.bitrate}")
        print(f"Destination: {args.dest_host}:{args.dest_folder}")
        print(f"Transfer method: {args.method}")
        print(f"Temp directory: {args.temp}")
        confirm = input("\nContinue? (y/n): ").lower().strip()
        if confirm != 'y':
            print("Operation cancelled.")
            return
    else:
        # Use command-line arguments as before
        parser = argparse.ArgumentParser(description="Transcode videos to H.264+AAC MKV and transfer to remote host")
        parser.add_argument("source", help="Source folder containing videos")
        parser.add_argument("--bitrate", default="2M", help="Video bitrate (default: 2M)")
        parser.add_argument("dest_host", help="Destination host for file transfer")
        parser.add_argument("dest_folder", help="Destination folder on remote host")
        parser.add_argument("--username", help="Username for remote host")
        parser.add_argument("--password", help="Password for remote host")
        parser.add_argument("--method", choices=["sftp", "scp"], default="sftp", 
                          help="File transfer method (default: sftp)")
        parser.add_argument("--temp", default="/tmp/transcode", 
                          help="Temporary folder for transcoded files")
        parser.add_argument("--gpu", action="store_true", 
                          help="Use NVIDIA GPU acceleration for transcoding")
        
        args = parser.parse_args()
        args.use_gpu = args.gpu if hasattr(args, 'gpu') else False
    
    # Create temp directory if it doesn't exist
    temp_dir = Path(args.temp)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all video files in source folder
    video_files = find_video_files(args.source)
    
    if not video_files:
        print("No video files found in source folder.")
        return
    
    print(f"Found {len(video_files)} video files to process.")
    
    
    for i, video_path in enumerate(video_files, 1):
        print(f"Processing file {i}/{len(video_files)}: {video_path}")
        
        # Create output filename preserving directory structure
        rel_path = video_path.relative_to(Path(args.source))
        output_dir = temp_dir / rel_path.parent
        output_path = output_dir / rel_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Transcode video
        print(f"Transcoding {video_path}...")
        transcode_video(video_path, output_path, args.bitrate, use_gpu=args.use_gpu)
        
        # Transfer MKV file with preserved directory structure
        mkv_path = f"{output_path}.mkv"
        remote_mkv_path = f"{args.dest_folder}/{rel_path.parent/rel_path.stem}.mkv"
        print(f"Transferring {mkv_path} to {args.dest_host}:{remote_mkv_path}")
        transfer_file(mkv_path, args.dest_host, remote_mkv_path, args.username, args.password, args.method)
        
        # Transfer SRT file if it exists
        srt_path = f"{output_path}.srt"
        if os.path.exists(srt_path):
            remote_srt_path = f"{args.dest_folder}/{rel_path.parent/rel_path.stem}.srt"
            print(f"Transferring {srt_path} to {args.dest_host}:{remote_srt_path}")
            transfer_file(srt_path, args.dest_host, remote_srt_path, args.username, args.password, args.method)
        
        # Clean up temporary files
        if os.path.exists(mkv_path):
            os.remove(mkv_path)
        if os.path.exists(srt_path):
            os.remove(srt_path)
            
    print("All files processed successfully!")

if __name__ == "__main__":
    main()