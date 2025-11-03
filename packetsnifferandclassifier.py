# packet_traffic_classifier_working.py

import tkinter as tk
from tkinter import ttk
from scapy.all import sniff, IP
from collections import defaultdict
import threading

# ------------------------------
# GLOBAL VARIABLES
# ------------------------------
flows = defaultdict(lambda: {'packets': 0, 'bytes': 0})
capture_running = False

# ------------------------------
# HELPER FUNCTIONS
# ------------------------------
def classify_flow(flow):
    total_bytes = flow['bytes']
    total_packets = flow['packets']

    # Check if traffic is HTTP/HTTPS (common browsing)
    # We'll assume flows using standard web ports (80, 443)
    if flow.get('protocols'):
        if 80 in flow['protocols'] or 443 in flow['protocols']:
            return "Browsing / Chat"

    # Heavy traffic = Streaming / Download
    if total_bytes > 10000 or total_packets > 20:
        return "Streaming / Download"

    # Smaller flows = Other
    return "Background / Small Traffic"

def process_packet(packet):
    if IP in packet:
        src = packet[IP].src
        dst = packet[IP].dst
        length = len(packet)

        flow_id = (src, dst)
        flows[flow_id]['packets'] += 1
        flows[flow_id]['bytes'] += length

        # Update GUI safely
        root.after(0, update_treeview)

# ------------------------------
# GUI FUNCTIONS
# ------------------------------
def update_treeview():
    # Clear tree
    for row in tree.get_children():
        tree.delete(row)
    # Insert flows with classification
    for flow_id, data in flows.items():
        src, dst = flow_id
        classification = classify_flow(data)
        tree.insert('', 'end', values=(src, dst, data['packets'], data['bytes'], classification))

def start_capture():
    global capture_running
    capture_running = True
    threading.Thread(target=run_sniff, daemon=True).start()
    start_btn.config(state='disabled')
    stop_btn.config(state='normal')

def stop_capture():
    global capture_running
    capture_running = False
    start_btn.config(state='normal')
    stop_btn.config(state='disabled')

def run_sniff():
    sniff(prn=process_packet, store=False, stop_filter=lambda x: not capture_running)

# ------------------------------
# MAIN GUI
# ------------------------------
root = tk.Tk()
root.title("Packet Traffic Classifier")
root.geometry("900x400")

# Buttons
start_btn = tk.Button(root, text="Start Capture", command=start_capture, bg="green", fg="white", width=15)
start_btn.pack(pady=10)

stop_btn = tk.Button(root, text="Stop Capture", command=stop_capture, bg="red", fg="white", width=15)
stop_btn.pack(pady=10)
stop_btn.config(state='disabled')

# Treeview for flows
columns = ("Source IP", "Destination IP", "Packets", "Bytes", "Classification")
tree = ttk.Treeview(root, columns=columns, show='headings')
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=150)  # adjust width for readability
tree.pack(fill=tk.BOTH, expand=True)

# Start GUI loop
root.mainloop()
