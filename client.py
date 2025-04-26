import socket
import os
import hashlib
from socket import *

def calc_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(4096):
            hasher.update(chunk)
    return hasher.hexdigest()

def upload_file(client, filename):
    if not os.path.exists(filename):
        print("TREASURE NOT FOUND!")
        return
    
    filesize = os.path.getsize(filename)
    filehash = calc_hash(filename)
    basename = os.path.basename(filename)
    
    client.send(f"TREASURE {basename} {filesize} {filehash}".encode())
    
    with open(filename, 'rb') as f:
        while data := f.read(1024):
            client.send(data)
    print(client.recv(1024).decode())
    

def download_file(client, filename):
    offset = 0

    # Path to save the file in the Downloads folder
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(downloads, exist_ok=True)
    basename = os.path.basename(filename)
    save_path = os.path.join(downloads, basename)

    # Auto-rename if file already exists
    dup = 1
    while os.path.exists(save_path):
        name, ext = os.path.splitext(basename)
        new_name = f"{name}({dup}){ext}"
        save_path = os.path.join(downloads, new_name)
        dup += 1

    # Check if partial file exists (after determining the correct save_path!)
    if os.path.exists(save_path):
        offset = os.path.getsize(save_path)


    # Send request to the server with offset
    client.send(f"REVEAL {filename} {offset}".encode())
    response = client.recv(1024).decode().split()

    if response[0] == "READY":
        filesize = int(response[1])
        filehash = response[2]

        # Open the file in append mode if we're resuming
        mode = 'ab' if offset > 0 else 'wb'
        with open(save_path, mode) as f:
            remaining = filesize - offset
            total_downloaded = offset  # Start from the last offset

            while remaining > 0:
                data = client.recv(min(1024, remaining))
                if not data:
                    break
                f.write(data)
                remaining -= len(data)
                total_downloaded += len(data)

                # Calculate progress as a percentage
                progress = (total_downloaded / filesize) * 100

                # Print progress in 25% increments
                if progress >= 100:
                    print("Downloading... 100%")
                elif progress >= 75:
                    print("Downloading... 75%")
                elif progress >= 50:
                    print("Downloading... 50%")
                elif progress >= 25:
                    print("Downloading... 25%")
                elif progress >= 0:
                    print("Downloading... 0%")

        # Verify file integrity
        if calc_hash(save_path) == filehash:
            print(f"TREASURE UNEARTHED! Saved to {save_path}")
        else:
            os.remove(save_path)
            print("TREASURE CORRUPTED! Download failed.")
    else:
        print(response[0])

def list_files(client):
    client.send("MAP".encode())
    files = client.recv(4096).decode()
    if files:
        print("\nBuried Treasures:")
        print(files)
    else:
        print("No treasures available.")

def main():
    server_ip = input("Enter server IP (localhost if running locally): ")
    port = 5556
    
    try:
        client = socket(AF_INET, SOCK_STREAM)
        client.connect((server_ip, port))
        
        print(client.recv(1024).decode().strip())

        while True:
            command = input("> ").strip()  # Don't upper() everything
            if not command:
                continue

            parts = command.split(maxsplit=1)
            cmd = parts[0].upper()
            arguments = parts[1] if len(parts) > 1 else ""

            if cmd == "TREASURE":
                filepath = arguments if arguments else input("Enter full file path to upload: ").strip()
                upload_file(client, filepath)

            elif cmd == "REVEAL":
                filename = arguments
                print(arguments)
                if filename:
                    download_file(client, filename)
                else:
                    print("INVALID COMMAND! Usage: REVEAL <filename>")

            elif cmd == "MAP":
                list_files(client)

            elif cmd.replace(" ", "") == "ENDQUEST":
                client.send("ENDQUEST".encode())
                print(client.recv(1024).decode())
                break

            else:
                print("INVALID COMMAND!")

    except Exception as e:
        print(f"QUEST FAILED: {e}")
    finally:
        client.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()