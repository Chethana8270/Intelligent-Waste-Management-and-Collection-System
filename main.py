from http.server import BaseHTTPRequestHandler, HTTPServer
import sqlite3
import json
from datetime import datetime
import os

# =========================================================
# SETTINGS
# =========================================================

HOST = "0.0.0.0"
PORT = 5000

DATABASE = "waste.db"
HTML_FILE = "index.html"


# =========================================================
# DATABASE
# =========================================================

def create_database():

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    # Current status of each bin
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bins (
            bin_id TEXT PRIMARY KEY,
            distance REAL,
            fill_level REAL,
            status TEXT,
            updated_at TEXT
        )
    """)

    # Historical readings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bin_id TEXT,
            distance REAL,
            fill_level REAL,
            status TEXT,
            recorded_at TEXT
        )
    """)

    connection.commit()
    connection.close()


# =========================================================
# BIN STATUS
# =========================================================

def get_status(fill_level):

    if fill_level >= 90:
        return "CRITICAL"

    elif fill_level >= 80:
        return "FULL"

    elif fill_level >= 50:
        return "HALF"

    else:
        return "NORMAL"


# =========================================================
# SAVE BIN DATA
# =========================================================

def save_bin_data(
    bin_id,
    distance,
    fill_level
):

    status = get_status(fill_level)

    current_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    # Insert or update current bin
    cursor.execute("""
        INSERT INTO bins (
            bin_id,
            distance,
            fill_level,
            status,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)

        ON CONFLICT(bin_id)
        DO UPDATE SET
            distance = excluded.distance,
            fill_level = excluded.fill_level,
            status = excluded.status,
            updated_at = excluded.updated_at
    """, (
        bin_id,
        distance,
        fill_level,
        status,
        current_time
    ))

    # Save historical reading
    cursor.execute("""
        INSERT INTO readings (
            bin_id,
            distance,
            fill_level,
            status,
            recorded_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        bin_id,
        distance,
        fill_level,
        status,
        current_time
    ))

    connection.commit()
    connection.close()

    print(
        f"[{current_time}] "
        f"{bin_id} | "
        f"{fill_level:.1f}% | "
        f"{status}"
    )

    return status


# =========================================================
# GET ALL BINS
# =========================================================

def get_all_bins():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            bin_id,
            distance,
            fill_level,
            status,
            updated_at
        FROM bins
        ORDER BY bin_id
    """)

    rows = cursor.fetchall()

    connection.close()

    result = []

    for row in rows:

        result.append({
            "bin_id": row["bin_id"],
            "distance": row["distance"],
            "fill_level": row["fill_level"],
            "status": row["status"],
            "updated_at": row["updated_at"]
        })

    return result


# =========================================================
# HTTP SERVER
# =========================================================

class WasteServer(BaseHTTPRequestHandler):

    # -----------------------------------------------------
    # GET REQUEST
    # -----------------------------------------------------

    def do_GET(self):

        # Dashboard
        if self.path == "/":

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/html"
            )

            self.end_headers()

            try:

                with open(
                    HTML_FILE,
                    "rb"
                ) as file:

                    self.wfile.write(
                        file.read()
                    )

            except FileNotFoundError:

                self.wfile.write(
                    b"index.html not found"
                )

            return


        # API: get bins
        if self.path == "/api/bins":

            bins = get_all_bins()

            response = json.dumps(
                bins
            ).encode("utf-8")

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json"
            )

            self.send_header(
                "Access-Control-Allow-Origin",
                "*"
            )

            self.end_headers()

            self.wfile.write(
                response
            )

            return


        # Health check
        if self.path == "/health":

            response = json.dumps({
                "status": "online"
            }).encode("utf-8")

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json"
            )

            self.end_headers()

            self.wfile.write(
                response
            )

            return


        # Not found
        self.send_response(404)

        self.end_headers()


    # -----------------------------------------------------
    # POST REQUEST
    # -----------------------------------------------------

    def do_POST(self):

        if self.path != "/api/bin":

            self.send_response(404)

            self.end_headers()

            return


        try:

            content_length = int(
                self.headers.get(
                    "Content-Length",
                    0
                )
            )

            body = self.rfile.read(
                content_length
            )

            data = json.loads(
                body.decode("utf-8")
            )


            # Get data
            bin_id = data.get(
                "bin_id"
            )

            distance = data.get(
                "distance_cm"
            )

            fill_level = data.get(
                "fill_level"
            )


            # Validate
            if bin_id is None:

                raise ValueError(
                    "bin_id is missing"
                )

            if distance is None:

                raise ValueError(
                    "distance_cm is missing"
                )

            if fill_level is None:

                raise ValueError(
                    "fill_level is missing"
                )


            distance = float(
                distance
            )

            fill_level = float(
                fill_level
            )


            # Keep fill between 0 and 100
            fill_level = max(
                0,
                min(100, fill_level)
            )


            status = save_bin_data(
                bin_id,
                distance,
                fill_level
            )


            response = json.dumps({

                "success": True,

                "bin_id": bin_id,

                "distance_cm": distance,

                "fill_level": fill_level,

                "status": status

            }).encode("utf-8")


            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json"
            )

            self.send_header(
                "Access-Control-Allow-Origin",
                "*"
            )

            self.end_headers()

            self.wfile.write(
                response
            )


        except Exception as error:

            print(
                "ERROR:",
                error
            )


            response = json.dumps({

                "success": False,

                "error": str(error)

            }).encode("utf-8")


            self.send_response(400)

            self.send_header(
                "Content-Type",
                "application/json"
            )

            self.end_headers()

            self.wfile.write(
                response
            )


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    create_database()

    server = HTTPServer(
        (HOST, PORT),
        WasteServer
    )

    print()
    print("=" * 50)
    print("INTELLIGENT WASTE MANAGEMENT SYSTEM")
    print("=" * 50)
    print()
    print(
        f"Server running on port {PORT}"
    )
    print()
    print(
        "Open on this computer:"
    )
    print(
        f"http://localhost:{PORT}"
    )
    print()
    print(
        "Waiting for ESP32 data..."
    )
    print()
    print("Press CTRL+C to stop.")
    print("=" * 50)

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print(
            "\nServer stopped."
        )

        server.server_close()
