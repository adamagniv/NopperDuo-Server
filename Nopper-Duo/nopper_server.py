from uuid import uuid4
from time import sleep
from threading import Lock as Mutex
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from enum import IntEnum, auto

hostName = "0.0.0.0"
serverPort = 8080

MASTER='master'
SLAVE='slave'

count_connection = 0
session_id=None
session_id_dic = [{}, {}]
login_mutex = Mutex()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

class NopperState(IntEnum):
    login = auto()
    paired = auto()
    ready_to_send_line = auto()
    waiting_to_receive_line = auto()
    nopper_state_length = auto()

class NopperSession:
    def __init__(self):
        self.state = NopperState.login
        self.line = None

class NopperServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if (self.path.strip('/') == "login"):
            self.get_login()
        elif (self.path.strip('/') == "wait_for_partner"):
            self.get_wait_for_partner(self.headers)
        elif (self.path.strip('/') == "menu_done_wait"):
            self.get_menu_done_wait(self.headers)
        elif (self.path.strip('/') == "get_partner_line"):
            self.get_partner_line(self.headers)
        elif (self.path.strip('/') == "disconnect"):
            self.get_disconnect()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path.strip('/') == "send_line":
            self.accept_line()
        else:
            self.send_response(404)
            self.end_headers()

    def get_partner_session(self, my_role, session_id):
        partner_index = 1 if my_role == MASTER else 0
        return session_id_dic[partner_index].get(session_id)

    def get_login(self):
        global count_connection
        global session_id
        global session_id_dic
        global login_mutex
        self.send_response(200)
        self.end_headers()

        with login_mutex:
            # If it's a new couple
            if count_connection == 0:
                role = MASTER
                session_id = str(uuid4())
                session_id_dic[0][session_id] = NopperSession()
            elif count_connection == 1:
                role = SLAVE
                session_id_dic[1][session_id] = NopperSession()
            else:
                self.wfile.write(b"Can't have more than two participants")
                return

            count_connection += 1
        
        self.wfile.write("{}:{}".format(role, session_id).encode("utf-8"))

    def get_wait_for_partner(self, headers):
        global session_id_dic
        self.send_response(200)
        self.end_headers()

        try:
            req_role, req_session_id = headers["X-NopperId"].split(':')
        except Exception:
            self.wfile.write(b"Invalid session ID")
            return

        try:
            req_wait = int(headers["X-NopperTimeout"].strip())
        except Exception:
            self.wfile.write(b"Invalid timeout")
            return

        role_index = 0 if req_role == MASTER else 1
        current_session = session_id_dic[role_index].get(req_session_id)
        if current_session is None or current_session.state > NopperState.paired:
            self.wfile.write(b"fail")

            return

        for _ in range(0, req_wait):
            if (req_session_id in session_id_dic[role_index ^ 1]):
                current_session.state = NopperState.paired
                self.wfile.write(b"ok")

                return
            sleep(1)

        self.wfile.write(b"timeout")

    def get_menu_done_wait(self, headers):
        global session_id_dic
        self.send_response(200)
        self.end_headers()

        try:
            req_role, req_session_id = headers["X-NopperId"].split(':')
        except Exception:
            self.wfile.write(b"Invalid session ID")
            return

        try:
            req_wait = int(headers["X-NopperTimeout"].strip())
        except Exception:
            self.wfile.write(b"Invalid timeout")
            return

        role_index = 0 if req_role == MASTER else 1
        current_session = session_id_dic[role_index].get(req_session_id)
        if current_session is None or current_session.state < NopperState.paired:
            self.wfile.write(b"fail")

            return

        current_session.state = NopperState.ready_to_send_line if req_role == MASTER else NopperState.waiting_to_receive_line

        for _ in range(0, req_wait):
            parter_session = self.get_partner_session(req_role, req_session_id)
            if parter_session is None:
                self.wfile.write(b"Partner disconncted")
                self.do_disconnect()
                return

            if parter_session.state > NopperState.paired:
                self.wfile.write(b"ok")

                return
            sleep(1)

        self.wfile.write(b"timeout")

    def get_partner_line(self, headers):
        global session_id_dic
        self.send_response(200)
        self.end_headers()

        try:
            req_role, req_session_id = headers["X-NopperId"].split(':')
        except Exception:
            self.wfile.write(b"Invalid session ID")
            return

        try:
            req_wait = int(headers["X-NopperTimeout"].strip())
        except Exception:
            self.wfile.write(b"Invalid timeout")
            return

        role_index = 0 if req_role == MASTER else 1
        current_session = session_id_dic[role_index].get(req_session_id)
        if current_session is None or current_session.state != NopperState.waiting_to_receive_line:
            self.wfile.write(b"fail")
            return

        try:
            for _ in range(0, req_wait):
                parter_session = self.get_partner_session(req_role, req_session_id)
                if parter_session is None:
                    self.wfile.write(b"Partner disconncted")
                    self.do_disconnect()
                    return

                if parter_session.state == NopperState.waiting_to_receive_line and parter_session.line:
                    self.wfile.write(b"ok:%b" % parter_session.line)
                    parter_session.line = None
                    current_session.state = NopperState.ready_to_send_line
                    return

                sleep(1)
        except:
            self.wfile.write(b"Partner disconnected")
            self.do_disconnect()

    def accept_line(self):
        global session_id_dic
        self.send_response(200)
        self.end_headers()

        try:
            req_role, req_session_id = self.headers["X-NopperId"].split(':')
        except Exception:
            self.wfile.write(b"Invalid session ID")
            return

        role_index = 0 if req_role == MASTER else 1
        current_session = session_id_dic[role_index].get(req_session_id)
        if current_session is None or current_session.state != NopperState.ready_to_send_line:
            self.wfile.write(b"fail")
            return

        parter_session = self.get_partner_session(req_role, req_session_id)
        if parter_session is None:
            self.wfile.write(b"Partner disconncted")
            self.do_disconnect()
            return

        content_length = int(self.headers['Content-Length'])
        current_session.line = self.rfile.read(content_length)
        current_session.state = NopperState.waiting_to_receive_line
        self.wfile.write(b"ok")

    def get_disconnect(self):
        global session_id_dic
        self.send_response(200)
        self.end_headers()
        
        self.do_disconnect()
        self.wfile.write(b"ok")

    def do_disconnect(self):
        global session_id_dic
        
        try:
            req_role, req_session_id = self.headers["X-NopperId"].split(':')
        except Exception:
            self.wfile.write(b"Invalid session ID")
            return

        role_index = 0 if req_role == MASTER else 1
        del session_id_dic[role_index][req_session_id]
