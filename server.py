import socket
import threading
import os
import hashlib
from socket import *
from app import db, File
from datetime import datetime

SHARED_DIR = "shared_treasures"
LOG_FILE = "server_log.txt"

if not os.path.exists(SHARED_DIR):
    os.makedirs(SHARED_DIR)

def log_event(event):
    with open(LOG_FILE, "a") as log:
        log.write(f"{event}\n")

def calc_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(4096):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_downloads_directory():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(downloads, exist_ok=True)  # Ensure Downloads folder exists
    return downloads

def get_next_version_filename(filename, directory):
    """Generate the next available versioned filename."""
    name, ext = os.path.splitext(filename)
    version = 2  # Start from v2
    new_filename = f"{name}_v{version}{ext}"
    while os.path.exists(os.path.join(directory, new_filename)):
        version += 1
        new_filename = f"{name}_v{version}{ext}"
    return new_filename

def handle_duplicate(client, filename, destination_path):
    """Handle file duplicates by offering options to overwrite or rename."""
    if os.path.exists(destination_path):
        client.send(f"A file named '{filename}' already exists.\n"
                    "Choose an option:\n"
                    "1. Append to the original file and name the result with a version number.\n"
                    "2. Just rename the new file with a version number.\n".encode())
        choice = client.recv(1024).decode().strip()

        if choice == "1":
            # Append and rename the original file
            new_version_name = get_next_version_filename(filename, os.path.dirname(destination_path))
            os.rename(destination_path, os.path.join(os.path.dirname(destination_path), new_version_name))
            client.send(f"Original file renamed to '{new_version_name}'. New file will be saved as '{filename}'.\n".encode())
            return destination_path  # Save the file with the original name
        elif choice == "2":
            # Save incoming file with a versioned name
            new_filename = get_next_version_filename(filename, os.path.dirname(destination_path))
            client.send(f"New file will be saved as '{new_filename}'.\n".encode())
            return os.path.join(os.path.dirname(destination_path), new_filename)
        else:
            client.send("Invalid choice. Upload cancelled.\n".encode())
            return None
    else:
        return destination_path  # No duplicate, return original path


port = 5559
server = socket(AF_INET, SOCK_STREAM)

# Try to bind the server to the port
try:
    server.bind(('', port))
    print(f"Server is successfully bound to port {port}.")
except Exception as e:
    print(f"Error binding server to port {port}: {str(e)}")

server.listen(500)
print(f"Server is listening on port {port}...")

def handleclient(client, addr):
    print("gi")
    print(f"New connection from {addr}")
    client.send("Welcome to Treasure Hunt!\n"
    "Choose an option:\n"
    "1. TREASURE <filename> <size> (Upload)\n"
    "2. REVEAL <filename> (Download)\n"
    "3. MAP (List Files)\n"
    "4. END QUEST (Exit)\n".encode())

    log_event(f"New connection from {addr}")

    while True:
        try:
            option = client.recv(1024).decode().strip()
            if not option:
                break

            parts = option.split(maxsplit=1)
            command = parts[0].upper()
            arguments = parts[1] if len(parts) > 1 else ""

            print(f"Received command: {command} with arguments: {arguments}")
            if command.startswith("TREASURE"):
                try:
                    args = arguments.rsplit(' ', 2)
                    if len(args) != 3:
                        client.send("INVALID TREASURE COMMAND!".encode())
                        continue
                    name = args[0]
                    size = int(args[1])
                    hsh = args[2]
                    
                    fpath = handle_duplicate(client, name, fpath)

                    if fpath is None:
                        # Client made invalid choice, cancel upload
                        continue

                    print("Shared Treasures full path:", fpath)

                    with open(fpath, 'wb') as f:
                        print(f"Receiving file {name}{ext} of size {size}")
                        print(f"Receiving data chunk of {len(data)} bytes")
                        brcv = 0
                        while brcv < size:
                            data = client.recv(1024)
                            if not data:
                                break
                            brcv += len(data)
                            print(f"Received {len(data)} bytes, total received: {brcv}/{size}")
                            f.write(data)
                    
                    comphash = calc_hash(fpath)
                    if comphash == hsh:
                        log_event(f"File '{os.path.basename(fpath)}' uploaded successfully.")
                        client.send(f"TREASURE BURIED! ({os.path.basename(fpath)})".encode())
                    else:
                        os.remove(fpath)
                        log_event(f"File '{os.path.basename(fpath)}' upload failed (hash mismatch).")
                        client.send("TREASURE CORRUPTED! Upload failed.".encode())
                except Exception:
                    client.send("INVALID TREASURE COMMAND!".encode())
                    continue

            elif command == "REVEAL":
                args = arguments.rsplit(' ', 1)
                if len(args) == 1:
                    name = args[0]
                    offset = 0
                elif len(args) == 2:
                    name = args[0]
                    offset = int(args[1])
                else:
                    client.send("INVALID REVEAL COMMAND!".encode())
                    continue

                path = os.path.join(SHARED_DIR, name)
                
                if os.path.exists(path):
                    fhash = calc_hash(path)
                    filesize = os.path.getsize(path)
                    client.send(f"READY {filesize} {fhash}".encode())

                    downloads_dir = get_downloads_directory()
                    save_path = os.path.join(downloads_dir, name)
                    print(f"Downloading file to: {save_path}")

                    with open(save_path, 'wb') as save_file:
                        with open(path, 'rb') as f:
                            f.seek(offset)
                            remaining = filesize - offset
                            while remaining > 0:
                                chunk = f.read(min(1024, remaining))
                                if not chunk:   
                                    break
                                client.send(chunk)  # Send to client
                                print("hi")
                                save_file.write(chunk)  # Save to the Downloads directory
                                remaining -= len(chunk)
                    log_event(f"File '{name}' downloaded to {save_path} (offset {offset}).")
                else:
                    client.send("TREASURE NOT FOUND!".encode())

            elif command == "MAP":
                files = os.listdir(SHARED_DIR)
                if files:
                    client.send("".join(files).encode())
                else:
                    client.send("No files available.".encode())

            elif command == "ENDQUEST":
                client.send("QUEST ENDED! Safe travels, adventurer.".encode())
                log_event(f"Client {addr} disconnected gracefully.")
                break
                
            else:
                client.send("INVALID COMMAND!".encode())

        except Exception as e:
            log_event(f"Error with {addr}: {str(e)}")
            break

    client.close()

while True:
    try:
        client, addr = server.accept()
        print(f"Accepted connection from {addr}")
        client_thread = threading.Thread(target=handleclient, args=(client, addr))
        client_thread.start()
    except Exception as e:
        print(f"Error accepting connection: {str(e)}")
        log_event(f"Server error: {str(e)}")
