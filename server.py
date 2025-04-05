import socket
import threading
import os
import hashlib
import shutil
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


port=5555
server = socket(AF_INET, SOCK_STREAM)
server.bind(('', port))

server.listen(500)

def handleclient(client):
    client.send("Welcome to Treasure Hunt!\n"
    "Choose an option:\n"
    "1. TREASURE <filename> <size> (Upload)\n"
    "2. REVEAL <filename> (Download)\n"
    "3. MAP (List Files)\n"
    "4. END QUEST (Exit)\n".encode())

    while True:
        option = client.recv(1024).decode()
        if not option:
            break


        request= option.split()
        command=request[0].upper()

        if command == "TREASURE" and len(request) == 4:
            name = request[1] 
            size = int(request[2]) 
            hsh= request[3]


            fpath = os.path.join(SHARED_DIR, name)
            dup=1
            while os.path.exists(fpath):
                name, ext = os.path.splitext(name)
                name = f"{name}_v{dup}{ext}"
                fpath = os.path.join(SHARED_DIR, name)
                dup += 1
            
            with open(fpath, 'wb') as f:
                brcv = 0
                while brcv < size:
                    data = client.recv(1024)
                    brcv += len(data)
                    f.write(data)
            
            comphash = calc_hash(fpath)
            if comphash == hsh:
                log_event(f"File '{name}' uploaded successfully with valid integrity.")
                client.send(f"TREASURE BURIED! ({name})".encode())
            else:
                os.remove(fpath)
                log_event(f"File '{name}' upload failed due to hash mismatch.")
                client.send("TREASURE CORRUPTED! Upload failed.".encode())

        elif command == "REVEAL" and len(request) == 2:
            name = request[1]
            path = os.path.join(SHARED_DIR, name)
            if os.path.exists(path):
                fhash = calc_hash(path)
                client.send(f"READY {os.path.getsize(path)} {fhash}".encode())
                with open(path, 'rb') as f:
                    client.send(f.read())
                log_event(f"File '{name}' downloaded successfully.")
            else:
                client.send(f"TREASURE NOT FOUND!".encode())

        elif command == "MAP": 
            files = os.listdir(SHARED_DIR)
            if files:
                client.send("\n".join(files).encode())
            else:
                client.send("No files available.".encode())

        elif command == "END QUEST":
            client.send("QUEST ENDED! Safe travels, adventurer.".encode())
            break
        
        else:
            client.send("INVALID COMMAND!".encode())

    client.close()


while True:
    client, addr = server.accept() 
    clienthread = threading.Thread(target=handleclient, args=(client,))
    clienthread.start()