from uuid import uuid4
from time import sleep
from http.server import BaseHTTPRequestHandler, HTTPServer
from enum import Enum, auto

hostName = "localhost"
serverPort = 8080

MASTER='master'
SLAVE='slave'

count_connection = 0
session_id=None
session_id_dic = [{}, {}]

class NopperState(Enum):
    login = auto
    paired = auto
    menu_done = auto
    nopper_state_length = auto

class NopperServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if (self.path.strip('/') == "login"):
            self.get_login()
        if (self.path.strip('/') == "wait_for_partner"):
            self.get_wait_for_partner(self.headers)
        if (self.path.strip('/') == "menu_done_wait"):
            self.get_menu_done_wait(self.headers)
        else:
            self.send_response(404)

    def get_login(self):
        global count_connection
        global session_id
        global session_id_dic

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        #if it's a new couple
        if ((count_connection % 2) == 0):
            role = MASTER
            session_id = str(uuid4())
            session_id_dic[0][session_id] = NopperState.login
        else:
            role = SLAVE
            session_id_dic[1][session_id] = NopperState.login
       
        count_connection += 1
        
        self.wfile.write(bytes("%s:%s" % (role, session_id), "utf-8"))

    def get_wait_for_partner(self, headers):
        global session_id_dic

        req_role = headers["X-NopperId"].split(':')[0].strip()
        req_session_id = headers["X-NopperId"].split(':')[1].strip()
        req_wait = int(headers["X-NopperTimeout"].strip())

        role_index = 0 if (req_role == MASTER) else 1
        if (not (req_session_id in session_id_dic[role_index]) or
            session_id_dic[role_index][req_session_id] > NopperState.paired):
            self.wfile.write(bytes("fail", "utf-8"))

            return

        for _ in range(0, req_wait):
            if (req_session_id in session_id_dic[role_index ^ 1]):
                session_id_dic[0][req_session_id] = NopperState.paired
                session_id_dic[1][req_session_id] = NopperState.paired
                self.wfile.write(bytes("ok", "utf-8"))

                return
            sleep(1)

        self.wfile.write(bytes("timeout", "utf-8"))

    def get_menu_done_wait(self, headers):
        global session_id_dic

        req_role = headers["X-NopperId"].split(':')[0].strip()
        req_session_id = headers["X-NopperId"].split(':')[1].strip()
        req_wait = int(headers["X-NopperTimeout"].strip())

        role_index = 0 if (req_role == MASTER) else 1
        if (not (req_session_id in session_id_dic[role_index]) or
            session_id_dic[role_index][req_session_id] > NopperState.menu_done):
            self.wfile.write(bytes("fail", "utf-8"))

            return

        session_id_dic[role_index][req_session_id] = NopperState.menu_done
        try:
            for _ in range(0, req_wait):
                if (session_id_dic[role_index ^ 1][req_session_id] == NopperState.menu_done):
                    self.wfile.write(bytes("ok", "utf-8"))

                    return
                sleep(1)
        except:
            self.wfile.write(bytes("partner_disconnected", "utf-8"))