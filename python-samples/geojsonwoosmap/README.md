# Python Script to export data from a Woosmap Customer as a JSON file and eventually import them to another customer.

You need to define parameter for **public_key** (origin data).
You could define parameter for **private key** (destination project) if you want to re-import them.

sample usage:

    python geojson_to_woosmap.py

The exported data is saved in the file `data.json`