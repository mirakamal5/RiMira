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
    client.send(f"REVEAL {filename}".encode())
    response = client.recv(1024).decode().split()
    
    if response[0] == "READY":
        filesize = int(response[1])
        filehash = response[2]
        
        with open(filename, 'wb') as f:
            remaining = filesize
            while remaining > 0:
                data = client.recv(min(1024, remaining))
                f.write(data)
                remaining -= len(data)
        
        if calc_hash(filename) == filehash:
            print(f"TREASURE UNEARTHED! ({filename})")
        else:
            os.remove(filename)
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
            command = input("> ").strip().upper()
            
            if command.startswith("TREASURE"):
                if len(command.split()) >= 2:
                    filename = command.split()[1]
                    upload_file(client, filename)
                else:
                    print("INVALID COMMAND! Usage: TREASURE <filename>")
            elif command.startswith("REVEAL"):
                if len(command.split()) == 2:
                    filename = command.split()[1]
                    download_file(client, filename)
                else:
                    print("INVALID COMMAND! Usage: REVEAL <filename>")
            elif command == "MAP":
                list_files(client)
            elif command.replace(" ", "") == "ENDQUEST":
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