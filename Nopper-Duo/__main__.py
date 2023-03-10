from .nopper_server import *

def main():
    webServer = ThreadedHTTPServer((hostName, serverPort), NopperServer)
    print("Server started http://%s:%s" % (hostName, serverPort))

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")

if __name__ == '__main__':
    raise SystemExit(main())