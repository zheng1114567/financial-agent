import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        SimpleHTTPRequestHandler.end_headers(self)

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    os.chdir('web/minibot-https-www-qianwen-gen-20260319233410')
    httpd = HTTPServer(('127.0.0.1', port), CORSRequestHandler)
    print(f'🚀 MiniBot frontend running at http://127.0.0.1:{port}')
    print('💡 API base: http://127.0.0.1:3000/api')
    httpd.serve_forever()