# her_net_simulation.py
# Smart ER Connect — Hospital Emergency Room Network (all-in-one simulation)
# Run with: python her_net_simulation.py
# Requires: matplotlib (pip install matplotlib). Tkinter usually included with Python.

import socket
import threading
import json
import time
import random
from datetime import datetime
import queue
import tkinter as tk
from tkinter import ttk
from collections import deque

# Matplotlib for embedding charts in Tkinter
import matplotlib
# Use the default interactive backend when run locally; do not force backends here.
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# -----------------------------
# Configuration
# -----------------------------
HOST = "127.0.0.1"
PORT = 9999
HOSPITAL_IDS = ["Hospital-A", "Hospital-B", "Hospital-C"]
SEND_INTERVAL_RANGE = (3, 7)  # seconds between simulated client updates
HISTORY_LEN = 40  # number of historical points to show in the chart

# Shared queue for passing updates from server thread to GUI
update_queue = queue.Queue()

# -----------------------------
# Simple TCP server to receive JSON messages (newline-delimited)
# -----------------------------
class SimpleTCPServer(threading.Thread):
    def __init__(self, host, port):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self.connections = []

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True
        print(f"[SERVER] Listening on {self.host}:{self.port}")
        while self.running:
            try:
                conn, addr = self.sock.accept()
                print(f"[SERVER] Connection from {addr}")
                t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                t.start()
                self.connections.append(conn)
            except OSError:
                break
            except Exception as e:
                print("[SERVER] accept error:", e)
                break

    def handle_client(self, conn, addr):
        buffer = b""
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        update_queue.put(msg)
                    except Exception as e:
                        print("[SERVER] JSON parse error:", e)
        except Exception as e:
            print("[SERVER] connection error:", e)
        finally:
            try:
                conn.close()
            except:
                pass
            print(f"[SERVER] Connection closed: {addr}")

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except:
            pass
        for c in self.connections:
            try:
                c.close()
            except:
                pass

# -----------------------------
# Simulated Hospital Client
# -----------------------------
class SimulatedHospital(threading.Thread):
    def __init__(self, hospital_id, host, port):
        super().__init__(daemon=True)
        self.hospital_id = hospital_id
        self.host = host
        self.port = port
        self.total_beds = random.choice([5, 6, 7, 8, 10])
        self.available_beds = random.randint(0, self.total_beds)
        self.running = True
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"[{self.hospital_id}] Connect error: {e}")
            return False

    def compute_status(self):
        if self.available_beds >= 3:
            return "GREEN"
        elif self.available_beds >= 1:
            return "YELLOW"
        else:
            return "RED"

    def send_update(self):
        if not self.sock:
            return
        msg = {
            "hospital_id": self.hospital_id,
            "timestamp": datetime.now().isoformat(),
            "total_beds": self.total_beds,
            "available_beds": self.available_beds,
            "status": self.compute_status()
        }
        try:
            self.sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        except Exception as e:
            print(f"[{self.hospital_id}] send error: {e}")

    def run(self):
        if not self.connect():
            return
        # initial update
        self.send_update()
        while self.running:
            # simulate change in bed availability (random but realistic)
            change = random.choice([-1, 0, 1, 0, 1])  # slight bias to occupancy increasing
            self.available_beds += change
            self.available_beds = max(0, min(self.available_beds, self.total_beds))
            self.send_update()
            time.sleep(random.uniform(*SEND_INTERVAL_RANGE))

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except:
            pass

# -----------------------------
# GUI — Smart ER Connect
# -----------------------------
class HERNetGUI:
    def __init__(self, root, hospital_ids):
        self.root = root
        self.hospital_ids = hospital_ids
        self.root.title("Smart ER Connect — Hospital Emergency Room Network")
        self.root.geometry("1200x720")
        self.root.configure(bg="#0f1724")

        # State store for hospitals
        self.state = {hid: {"total_beds": 0, "available_beds": 0, "status": "RED", "last_update": None} for hid in hospital_ids}
        # History for plotting
        self.history = {hid: deque(maxlen=HISTORY_LEN) for hid in hospital_ids}
        self.time_history = deque(maxlen=HISTORY_LEN)

        self._setup_styles()
        self._create_header()
        self._create_cards()
        self._create_log_table()
        self._create_chart()
        self.root.after(200, self.poll_queue)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#111827", foreground="#dbeafe", fieldbackground="#0f1724", rowheight=26, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        style.map("Treeview", background=[('selected', '#374151')], foreground=[('selected', '#ffffff')])

    def _create_header(self):
        header = tk.Frame(self.root, bg="#071029", pady=10, padx=12)
        header.pack(fill="x", padx=10, pady=(8,6))
        title = tk.Label(header, text="Smart ER Connect", font=("Segoe UI", 20, "bold"), fg="#e6eef8", bg="#071029")
        subtitle = tk.Label(header, text="Real-time ER availability across connected hospitals", font=("Segoe UI", 11), fg="#bcd1ff", bg="#071029")
        title.pack(anchor="w")
        subtitle.pack(anchor="w")

    def _create_cards(self):
        frame = tk.Frame(self.root, bg="#0f1724")
        frame.pack(fill="x", padx=10, pady=(0,8))
        self.cards = {}
        for i, hid in enumerate(self.hospital_ids):
            card = tk.Frame(frame, bg="#081025", bd=0, relief="ridge", padx=14, pady=12)
            card.grid(row=0, column=i, padx=8, sticky="nsew")
            frame.grid_columnconfigure(i, weight=1)
            label = tk.Label(card, text=hid, font=("Segoe UI", 14, "bold"), fg="#e6eef8", bg="#081025")
            label.pack(anchor="w")
            status_lbl = tk.Label(card, text="STATUS: --", font=("Segoe UI", 12, "bold"), fg="#9aa7d8", bg="#081025")
            status_lbl.pack(anchor="w", pady=(6,0))
            beds_lbl = tk.Label(card, text="Beds: --/--", font=("Segoe UI", 12), fg="#cfe4ff", bg="#081025")
            beds_lbl.pack(anchor="w", pady=(4,0))
            time_lbl = tk.Label(card, text="Last: --", font=("Segoe UI", 10), fg="#9fb6ff", bg="#081025")
            time_lbl.pack(anchor="w", pady=(6,0))
            # color indicator
            color_canvas = tk.Canvas(card, width=20, height=20, bg="#081025", highlightthickness=0)
            color_canvas.pack(anchor="e")
            oval = color_canvas.create_oval(2,2,18,18, fill="#6b7280")  # gray initially
            self.cards[hid] = {
                "frame": card,
                "status_lbl": status_lbl,
                "beds_lbl": beds_lbl,
                "time_lbl": time_lbl,
                "color_canvas": color_canvas,
                "oval": oval
            }

    def _create_log_table(self):
        frame = tk.Frame(self.root, bg="#071029", padx=10, pady=8)
        frame.pack(fill="x", padx=10, pady=(0,8))
        lbl = tk.Label(frame, text="Recent Updates (log)", font=("Segoe UI", 12, "bold"), fg="#cfe3ff", bg="#071029")
        lbl.pack(anchor="w")
        cols = ("Hospital", "Timestamp", "Total Beds", "Available Beds", "Status")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=6)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=200)
        self.tree.pack(fill="x", pady=(6,0))

    def _create_chart(self):
        frame = tk.Frame(self.root, bg="#0f1724", padx=10, pady=6)
        frame.pack(fill="both", expand=True, padx=10, pady=(0,12))
        left = tk.Frame(frame, bg="#0f1724")
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(frame, width=300, bg="#0f1724")
        right.pack(side="right", fill="y")

        # Matplotlib figure
        self.fig = Figure(figsize=(8,4), dpi=100, facecolor="#0f1724")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#071029")
        self.ax.tick_params(colors="#cfe3ff")
        self.ax.spines['bottom'].set_color('#cfe3ff')
        self.ax.spines['left'].set_color('#cfe3ff')
        self.ax.spines['top'].set_color('#0f1724')
        self.ax.spines['right'].set_color('#0f1724')
        self.ax.set_title("Available Beds Over Time", color="#e6eef8", fontsize=12)
        self.lines = {}
        colors = {"Hospital-A": "#34d399", "Hospital-B": "#fbbf24", "Hospital-C": "#fb7185"}  # green, yellow, red-ish
        for hid in self.hospital_ids:
            self.lines[hid], = self.ax.plot([], [], label=hid, linewidth=2, color=colors.get(hid, "#9ca3af"))
        self.ax.legend(facecolor="#071029", framealpha=0.3, labelcolor="#cfe3ff")
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Right-side legend + counters
        self.right_widgets = {}
        for hid in self.hospital_ids:
            panel = tk.Frame(right, bg="#071029", pady=8, padx=8)
            panel.pack(fill="x", pady=6)
            title = tk.Label(panel, text=hid, font=("Segoe UI", 11, "bold"), fg="#e3eeff", bg="#071029")
            title.pack(anchor="w")
            val = tk.Label(panel, text="Available: --", font=("Segoe UI", 12), fg="#cfe4ff", bg="#071029")
            val.pack(anchor="w", pady=(6,0))
            st = tk.Label(panel, text="Status: --", font=("Segoe UI", 11, "bold"), fg="#9fb6ff", bg="#071029")
            st.pack(anchor="w")
            self.right_widgets[hid] = {"val": val, "st": st}

    def poll_queue(self):
        updated = False
        while not update_queue.empty():
            msg = update_queue.get_nowait()
            hid = msg.get("hospital_id")
            if hid not in self.hospital_ids:
                continue
            # update state
            self.state[hid]["total_beds"] = msg.get("total_beds", 0)
            self.state[hid]["available_beds"] = msg.get("available_beds", 0)
            self.state[hid]["status"] = msg.get("status", "RED")
            ts = msg.get("timestamp")
            # parse timestamp to human-readable form
            try:
                t = datetime.fromisoformat(ts)
                pretty = t.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pretty = ts
            self.state[hid]["last_update"] = pretty
            # append to history
            self.history[hid].append(self.state[hid]["available_beds"])
            # time history keep last time label
            now_label = datetime.now().strftime("%H:%M:%S")
            if len(self.time_history) == 0 or self.time_history[-1] != now_label:
                self.time_history.append(now_label)
            # update log table
            self.tree.insert("", 0, values=(hid, pretty, self.state[hid]["total_beds"], self.state[hid]["available_beds"], self.state[hid]["status"]))
            updated = True

        if updated:
            self._refresh_cards()
            self._refresh_right_stats()
            self._refresh_chart()

        self.root.after(200, self.poll_queue)

    def _refresh_cards(self):
        for hid, card in self.cards.items():
            s = self.state[hid]
            status_text = s["status"]
            card["status_lbl"].config(text=f"STATUS: {status_text}", fg="#ffffff")
            card["beds_lbl"].config(text=f"Beds: {s['available_beds']}/{s['total_beds']}")
            lu = s["last_update"] or "--"
            card["time_lbl"].config(text=f"Last: {lu}")
            # color the oval
            if status_text == "GREEN":
                color = "#10b981"
            elif status_text == "YELLOW":
                color = "#f59e0b"
            else:
                color = "#ef4444"
            canvas = card["color_canvas"]
            canvas.itemconfig(card["oval"], fill=color)

    def _refresh_right_stats(self):
        for hid, widgets in self.right_widgets.items():
            s = self.state[hid]
            widgets["val"].config(text=f"Available: {s['available_beds']}/{s['total_beds']}")
            st = s["status"]
            widgets["st"].config(text=f"Status: {st}")
            if st == "GREEN":
                widgets["st"].config(fg="#34d399")
            elif st == "YELLOW":
                widgets["st"].config(fg="#fbbf24")
            else:
                widgets["st"].config(fg="#fb7185")

    def _refresh_chart(self):
        # align data lengths: for plotting we want consistent x axis length
        times = list(self.time_history)
        if len(times) == 0:
            return
        x = list(range(-len(times)+1, 1))  # relative x axis (e.g., -9..0)
        for hid, line in self.lines.items():
            y = list(self.history[hid])
            # pad left with None / nan so matplotlib can plot aligned arrays
            if len(y) < len(times):
                pad = [None] * (len(times) - len(y))
                y = pad + y
            line.set_data(range(len(times)), y)
        self.ax.set_xlim(0, max(1, len(times)))
        # y limits: 0 to max total beds among hospitals +1
        maxbeds = max((self.state[h]["total_beds"] or 5) for h in self.hospital_ids)
        self.ax.set_ylim(0, maxbeds + 1)
        self.ax.set_xticks(range(len(times)))
        # use last few labels to avoid crowding
        labels = [times[i] if i % max(1, len(times)//8) == 0 else "" for i in range(len(times))]
        self.ax.set_xticklabels(labels, rotation=30, color="#cfe3ff")
        self.canvas.draw_idle()

# -----------------------------
# Main: start server, clients, GUI
# -----------------------------
def main():
    # 1. Start server
    server = SimpleTCPServer(HOST, PORT)
    server.start()

    # 2. Start simulated clients
    clients = []
    for hid in HOSPITAL_IDS:
        sim = SimulatedHospital(hid, HOST, PORT)
        sim.start()
        clients.append(sim)

    # 3. Start GUI
    root = tk.Tk()
    app = HERNetGUI(root, HOSPITAL_IDS)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        # Clean shutdown
        for c in clients:
            c.stop()
        server.stop()

if __name__ == "__main__":
    main()
