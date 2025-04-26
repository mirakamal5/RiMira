import socket
import threading
import os
import hashlib
from socket import *

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

port = 5556
server = socket(AF_INET, SOCK_STREAM)
server.bind(('', port))

server.listen(500)

def handleclient(client, addr):
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

            if command == "TREASURE":
                try:
                    # Split from the RIGHT: separate size and hash first
                    args = arguments.rsplit(' ', 2)
                    if len(args) != 3:
                        client.send("INVALID TREASURE COMMAND!".encode())
                        continue
                    name = args[0]         # filename (can have spaces)
                    size = int(args[1])    # size (must be int)
                    hsh = args[2]
                    
                    original_name, ext = os.path.splitext(name)
                    name = original_name

                    fpath = os.path.join(SHARED_DIR, f"{name}{ext}")
                    dup = 1
                    while os.path.exists(fpath):
                        name = f"{original_name}_v{dup}"
                        fpath = os.path.join(SHARED_DIR, f"{name}{ext}")
                        dup += 1
                    
                    with open(fpath, 'wb') as f:
                        brcv = 0
                        while brcv < size:
                            data = client.recv(1024)
                            if not data:
                                break
                            brcv += len(data)
                            f.write(data)
                    
                    comphash = calc_hash(fpath)
                    if comphash == hsh:
                        log_event(f"File '{name}{ext}' uploaded successfully.")
                        client.send(f"TREASURE BURIED! ({name}{ext})".encode())

                    else:
                        os.remove(fpath)
                        log_event(f"File '{name}{ext}' upload failed (hash mismatch).")
                        client.send("TREASURE CORRUPTED! Upload failed.".encode())
                except Exception:
                    client.send("INVALID TREASURE COMMAND!".encode())
                    continue

            elif command == "REVEAL":
                args = arguments.rsplit(' ', 1)  # split once from the right
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
                    with open(path, 'rb') as f:
                        f.seek(offset)
                        remaining = filesize - offset
                        while remaining > 0:
                            chunk = f.read(min(1024, remaining))
                            if not chunk:
                                break
                            client.send(chunk)
                            remaining -= len(chunk)
                    log_event(f"File '{name}' downloaded (offset {offset}).")
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
        clienthread = threading.Thread(target=handleclient, args=(client,addr))
        clienthread.start()
    except Exception as e:
        log_event(f"Server error: {str(e)}")