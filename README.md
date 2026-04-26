# NTMS Azure batch - PoC storage Blobs and Queue-with-KV
* sudo apt update
* sudo apt install python3-venv -y
* python3 -m venv venv
* source venv/bin/activate
* mkdir kv-blob-queue , # Copy app.py, worker.py 
* mkdir templates, copy index.html
* sudo apt install python3 python3-pip -y
* pip3 install Flask azure-storage-blob azure-storage-queue Pillow azure.identity azure.keyvault
* Create kv, assign MI to linux VM, on kv, assign access policy permissions get only
* export KEY_VAULT_URI="https://ntmsrhkv.vault.azure.net/" # On linux VM
* python3 worker.py &
* python3 app.py # Open NSG 3000 port
* Access public ip of linux VM, upload image and see result
* stop worker.py, upload image and check queue
* start worker.py and check status of queue
# Assign RBAC role kv secrets user to Service Principal if deployment fails.
