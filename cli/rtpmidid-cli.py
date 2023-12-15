#!/usr/bin/python3

import shutil
import socket
import sys
import json
import os
import time


class Connection:
    def __init__(self, filename):
        self.filename = filename
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.socket.connect(filename)
        except ConnectionRefusedError:
            print(
                "Connection refused to %s. Can set other location with --control=<path>"
                % filename
            )
            sys.exit(1)

    def command(self, command):
        self.socket.send(json.dumps(command).encode("utf8") + b"\n")
        data = self.socket.recv(1024 * 1024)  # load all you can. 1MB cool!
        return json.loads(data)


def maybe_int(txt: str):
    try:
        return int(txt)
    except:
        pass
    return txt


def parse_arguments(argv):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--control")
    parser.add_argument("--top", action="store_true")
    parser.add_argument("command", nargs="*")

    return parser.parse_args(argv[1:])


def parse_commands(argv):
    cmd = []
    for x in argv:
        if x == ".":
            yield {"method": cmd[0], "params": [maybe_int(x) for x in cmd[1:]]}
            cmd = []
        else:
            cmd.append(x)
    if cmd:
        yield {"method": cmd[0], "params": [maybe_int(x) for x in cmd[1:]]}


def safe_get(data, *keys):
    try:
        for key in keys:
            if key in data:
                data = data[key]
            else:
                return ""
    except:
        return ""
    return data


class Top:
    ANSI_CLEAR_SCREEN = "\033[2J\033[H"
    ANSI_PUSH_SCREEN = "\033[?1049h"
    ANSI_POP_SCREEN = "\033[?1049l"

    ANSI_TEXT_BLUE = "\033[34m"
    ANSI_TEXT_RED = "\033[31m"
    ANSI_TEXT_GREEN = "\033[32m"
    ANSI_TEXT_YELLOW = "\033[33m"
    ANSI_TEXT_PURPLE = "\033[35m"
    ANSI_TEXT_CYAN = "\033[36m"
    ANSI_TEXT_WHITE = "\033[37m"
    ANSI_TEXT_BLACK = "\033[30m"
    ANSI_TEXT_GREY = "\033[90m"
    ANSI_TEXT_BOLD = "\033[1m"

    ANSI_BG_BLUE = "\033[44m"
    ANSI_BG_RED = "\033[41m"
    ANSI_BG_GREEN = "\033[42m"
    ANSI_BG_DARK_GREEN = "\033[32m"
    ANSI_BG_YELLOW = "\033[43m"
    ANSI_BG_PURPLE = "\033[45m"
    ANSI_BG_CYAN = "\033[46m"
    ANSI_BG_WHITE = "\033[47m"
    ANSI_BG_BLACK = "\033[40m"
    ANSI_BG_GREY = "\033[100m"

    ANSI_RESET = "\033[0m"

    def __init__(self):
        # terminal width and height from stty
        width, height = shutil.get_terminal_size()
        self.width = width
        self.height = height

        self.COLUMNS = [
            {
                "name": "ID",
                "get": lambda data: safe_get(data, "id"),
                "width": 8,
                "align": "right",
            },
            {
                "name": "Type",
                "get": lambda data: safe_get(data, "type"),
                "width": 40,
                "align": "left",
            },
            {
                "name": "Name",
                "get": lambda data: safe_get(data, "name"),
                "width": 0,
                "align": "left",
            },
            {
                "name": "Status",
                "get": lambda data: safe_get(data, "peer", "status"),
                "width": 20,
                "align": "left",
            },
            {
                "name": "Sent",
                "get": lambda data: safe_get(data, "stats", "sent"),
                "width": 8,
                "align": "right",
            },
            {
                "name": "Received",
                "get": lambda data: safe_get(data, "stats", "recv"),
                "width": 8,
                "align": "right",
            },
            {
                "name": "Latency",
                # the unicode symbol for +- is \u00B1
                "get": self.get_latency,
                "width": 20,
                "align": "right",
            },
            {
                "name": "Send To",
                "get": lambda data: ", ".join(
                    str(x) for x in safe_get(data, "send_to")
                ),
                "width": 10,
            },
        ]

        # make Name column as wide as possible
        self.COLUMNS[2]["width"] = (
            self.width
            - sum(x["width"] for x in self.COLUMNS)
            - (3 * (len(self.COLUMNS) - 1))
        )

    def terminal_goto(self, x, y):
        print("\033[%d;%dH" % (y, x), end="")

    def get_latency(self, data):
        avg = safe_get(data, "peer", "latency_ms", "average")
        if not avg:
            return ""
        stddev = safe_get(data, "peer", "latency_ms", "stddev")
        return f"{avg}ms \u00B1 {stddev}ms"

    def print_table(self, table: list[list[str]]):
        def format_cell(cell, column):
            if column.get("align") == "right":
                return "{:>{width}}".format(cell, width=column["width"])
            else:
                return "{:{width}}".format(cell, width=column["width"])

        for idx, row in enumerate(table):
            print(self.get_color_row(row, idx), end="")
            print(
                " | ".join(
                    format_cell(x, column) for x, column in zip(row, self.COLUMNS)
                )
            )
            print(self.ANSI_RESET, end="")

    def get_color_row(self, row, idx):
        if idx == 0:
            return self.ANSI_BG_CYAN + self.ANSI_TEXT_WHITE + self.ANSI_TEXT_BOLD
        elif row[3] == "CONNECTED":
            return self.ANSI_BG_GREEN + self.ANSI_TEXT_BLACK
        elif row[3] == "CONNECTING":
            return self.ANSI_BG_YELLOW + self.ANSI_TEXT_BLACK
        elif row[3] == "":
            return self.ANSI_BG_BLACK + self.ANSI_TEXT_GREY
        else:
            return self.ANSI_BG_GREY + self.ANSI_TEXT_BLACK

    def print_header(self):
        # write a header with the rtpmidid client, version, with color until the end of line
        print(self.ANSI_BG_BLUE + self.ANSI_TEXT_BOLD + self.ANSI_TEXT_WHITE, end="")
        self.print_padding("rtpmidid-cli v23.12")
        # color until next newline
        print(self.ANSI_RESET, end="")
        print()

    def print_footer(self):
        self.terminal_goto(1, self.height)

        print(self.ANSI_BG_BLUE + self.ANSI_TEXT_BOLD + self.ANSI_TEXT_WHITE, end="")
        self.print_padding(
            "Press Ctrl-C to exit | rtpmidid-cli v23.12 | (C) Coralbits 2023"
        )
        print(self.ANSI_RESET, end="")

    def print_padding(self, text, count=None):
        if count is None:
            count = self.width

        padchars = count - len(text)
        if padchars < 0:
            padchars = 0
        print(text[:count] + " " * padchars, end="")

    def top_loop(self, conn: Connection):
        print(self.ANSI_PUSH_SCREEN, end="")
        try:
            while True:
                print(self.ANSI_CLEAR_SCREEN, end="")
                self.print_header()
                data = conn.command({"method": "status"})
                table = [[x["name"] for x in self.COLUMNS]]
                peers = data["result"]["router"]
                table.extend([[x["get"](peer) for x in self.COLUMNS] for peer in peers])
                self.print_table(table)
                self.print_footer()
                print(flush=True, end="")
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            print(self.ANSI_POP_SCREEN, end="")


def main(argv):
    settings = parse_arguments(argv)
    if settings.control:
        socketpath = settings.control
    else:
        socketpath = "/var/run/rtpmidid/control.sock"

    if not os.path.exists(socketpath):
        print("Control socket %s does not exist" % socketpath)
        sys.exit(1)

    try:
        conn = Connection(socketpath)
    except Exception as e:
        print(str(e))
        sys.exit(1)

    if settings.top:
        return Top().top_loop(conn)

    for cmd in parse_commands(settings.command or ["help"]):
        print(">>> %s" % json.dumps(cmd), file=sys.stderr)
        ret = conn.command(cmd)
        print(json.dumps(ret, indent=2))


if __name__ == "__main__":
    main(sys.argv)
